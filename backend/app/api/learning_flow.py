from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.models import SessionCreatedResponse
from backend.app.learner_memory.bkt.contracts import DiagnosticProgress
from backend.app.onboarding.questionnaire import onboarding_questionnaire
from backend.app.services.session_service import SessionService


class QuestionnaireResponseItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str = Field(min_length=1)
    answer: Any


class QuestionnaireSubmission(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "learning_goal": "系统掌握专利新颖性判断",
                    "responses": [
                        {"question_id": "Q1", "answer": "B"},
                        {"question_id": "Q23", "answer": "A"},
                        {
                            "question_id": "Q47",
                            "answer": "我对相关法律知识掌握较弱，希望结合案例学习。",
                        },
                    ],
                }
            ]
        },
    )

    learning_goal: str = Field(min_length=1, description="学员本阶段的学习目标。")
    education_background: str | None = Field(
        default=None,
        description="可选的结构化教育背景；CAT 诊断流程使用它选择 BKT 先验。",
    )
    responses: list[QuestionnaireResponseItem] = Field(
        min_length=1,
        description="问卷回答列表；正式流程应提交学员已填写的全部题目。",
    )


class ExerciseResponseItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str = Field(min_length=1)
    answer: Any
    selected_option: str | None = None
    response_ms: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    observed_correct: bool | None = Field(
        default=None,
        description="兼容旧客户端的观测字段；MySQL 生产路径优先使用服务端答案判定。",
    )
    skill_id: str | None = None
    skill_ids: list[str] | None = None
    is_subjective: bool = Field(
        default=False,
        description="主观题标记；主观题不参与 BKT 判分，仅用于反馈 Agent 参考。",
    )


class ExerciseSubmission(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "learner_id": "learner-001",
                    "responses": [
                        {
                            "question_id": "novelty-q1",
                            "answer": "该技术方案在申请日前已经公开，因此不具备新颖性。",
                            "observed_correct": True,
                            "skill_id": "patent-novelty",
                        }
                    ],
                }
            ]
        },
    )

    learner_id: str = Field(min_length=1, description="提交练习的学员唯一标识。")
    responses: list[ExerciseResponseItem] = Field(
        min_length=1,
        description="本次练习回答列表。",
    )


class ReteachRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    learner_id: str = Field(min_length=1, description="学员唯一标识。")


class DiagnosticSessionSubmission(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "learning_goal": "系统掌握专利新颖性判断",
                    "education_background": "理工背景+有研发经验",
                    "responses": [],
                }
            ]
        },
    )

    learning_goal: str = Field(min_length=1)
    education_background: str | None = Field(
        default=None,
        description="教育背景（BKT 先验参数桶）；缺省时从问卷 Q0 自动派生。",
    )
    responses: list[QuestionnaireResponseItem] = Field(
        default_factory=list,
        description="问卷预筛回答；纯 CAT 诊断流程可留空，由 CAT 引擎自适应出题。",
    )


class DiagnosticResponseSubmission(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "question_id": "q_patent-law-foundation_001",
                    "answer": "A",
                    "response_ms": 5200,
                    "idempotency_key": "learner-001-diagnostic-1",
                }
            ]
        },
    )

    question_id: str = Field(min_length=1)
    answer: str = Field(default="", description="答案文本；开放题跳过（skip=true）时可为空。")
    response_ms: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    skip: bool = Field(default=False, description="开放题跳过标记；仅画像阶段的开放题有效。")


def create_learning_flow_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["learning-flow"])

    @router.get("/questionnaires/onboarding")
    def get_onboarding_questionnaire() -> dict[str, str]:
        return onboarding_questionnaire()

    @router.post(
        "/learners/{learner_id}/questionnaire-responses",
        response_model=SessionCreatedResponse,
    )
    def submit_questionnaire(
        learner_id: str, request: QuestionnaireSubmission
    ) -> SessionCreatedResponse:
        try:
            record = session_service.create_course_from_questionnaire(
                learner_id=learner_id,
                learning_goal=request.learning_goal,
                responses=[item.model_dump() for item in request.responses],
                education_background=request.education_background,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    @router.post(
        "/learners/{learner_id}/diagnostic-sessions",
        response_model=DiagnosticProgress,
    )
    def create_diagnostic_session(
        learner_id: str,
        request: DiagnosticSessionSubmission,
    ) -> DiagnosticProgress:
        try:
            progress = session_service.create_diagnostic_session(
                learner_id=learner_id,
                learning_goal=request.learning_goal,
                education_background=request.education_background,
                responses=[item.model_dump() for item in request.responses],
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": "diagnostic_creation_failed", "reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "diagnostic_creation_error", "reason": str(exc)},
            ) from exc
        return DiagnosticProgress.model_validate(progress)

    @router.get(
        "/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}",
        response_model=DiagnosticProgress,
    )
    def get_diagnostic_session(
        learner_id: str,
        diagnostic_session_id: str,
    ) -> DiagnosticProgress:
        try:
            progress = session_service.diagnostic_progress(
                learner_id=learner_id,
                diagnostic_session_id=diagnostic_session_id,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "diagnostic_session_not_found", "reason": str(exc)},
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "permission_denied", "reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "diagnostic_progress_error", "reason": str(exc)},
            ) from exc
        return DiagnosticProgress.model_validate(progress)

    @router.post(
        "/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses",
        response_model=DiagnosticProgress,
    )
    def submit_diagnostic_response(
        learner_id: str,
        diagnostic_session_id: str,
        request: DiagnosticResponseSubmission,
    ) -> DiagnosticProgress:
        try:
            progress = session_service.submit_diagnostic_response(
                learner_id=learner_id,
                diagnostic_session_id=diagnostic_session_id,
                question_id=request.question_id,
                answer=request.answer,
                response_ms=request.response_ms,
                idempotency_key=request.idempotency_key,
                skip=request.skip,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "diagnostic_session_not_found", "reason": str(exc)},
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "permission_denied", "reason": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"error": "invalid_response", "reason": str(exc)},
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "diagnostic_conflict", "reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "diagnostic_submit_error", "reason": str(exc)},
            ) from exc
        return DiagnosticProgress.model_validate(progress)

    @router.post(
        "/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete",
        response_model=DiagnosticProgress,
    )
    def complete_diagnostic_session(
        learner_id: str,
        diagnostic_session_id: str,
    ) -> DiagnosticProgress:
        try:
            progress = session_service.complete_diagnostic_session(
                learner_id=learner_id,
                diagnostic_session_id=diagnostic_session_id,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "diagnostic_session_not_found", "reason": str(exc)},
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "permission_denied", "reason": str(exc)},
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "diagnostic_conflict", "reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "diagnostic_complete_error", "reason": str(exc)},
            ) from exc
        return DiagnosticProgress.model_validate(progress)

    @router.post(
        "/sessions/{course_session_id}/exercise-responses",
        response_model=SessionCreatedResponse,
        responses={
            403: {"description": "The learner does not own the course session."},
            404: {"description": "Course session not found."},
            409: {"description": "Course session is not completed yet."},
        },
    )
    def submit_exercises(
        course_session_id: str, request: ExerciseSubmission
    ) -> SessionCreatedResponse:
        try:
            record = session_service.create_feedback_session(
                learner_id=request.learner_id,
                course_session_id=course_session_id,
                responses=[item.model_dump() for item in request.responses],
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course session not found.") from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Learner does not own the course session.",
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    @router.post(
        "/sessions/{course_session_id}/reteach",
        response_model=SessionCreatedResponse,
        responses={
            403: {"description": "The learner does not own the course session."},
            404: {"description": "Course session not found."},
        },
    )
    def reteach(
        course_session_id: str, request: ReteachRequest
    ) -> SessionCreatedResponse:
        """Re-run the teach workflow with updated BKT mastery after exercises."""
        try:
            record = session_service.create_reteach_session(
                learner_id=request.learner_id,
                course_session_id=course_session_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Course session not found.") from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=403,
                detail="Learner does not own the course session.",
            ) from exc
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    return router
