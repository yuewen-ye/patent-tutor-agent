from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.models import SessionCreatedResponse
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
        record = session_service.create_course_from_questionnaire(
            learner_id=learner_id,
            learning_goal=request.learning_goal,
            responses=[item.model_dump() for item in request.responses],
        )
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

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

    return router
