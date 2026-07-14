from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.models import SessionCreatedResponse
from backend.app.questionnaire import onboarding_questionnaire
from backend.app.services.session_service import SessionService


class QuestionnaireResponseItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str = Field(min_length=1)
    answer: Any


class QuestionnaireSubmission(BaseModel):
    model_config = ConfigDict(frozen=True)

    learning_goal: str = Field(min_length=1)
    responses: list[QuestionnaireResponseItem] = Field(min_length=1)


class ExerciseResponseItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str = Field(min_length=1)
    answer: Any
    observed_correct: bool | None = None
    skill_id: str | None = None


class ExerciseSubmission(BaseModel):
    model_config = ConfigDict(frozen=True)

    learner_id: str = Field(min_length=1)
    responses: list[ExerciseResponseItem] = Field(min_length=1)


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
    )
    def submit_exercises(
        course_session_id: str, request: ExerciseSubmission
    ) -> SessionCreatedResponse:
        record = session_service.create_feedback_session(
            learner_id=request.learner_id,
            course_session_id=course_session_id,
            responses=[item.model_dump() for item in request.responses],
        )
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    return router
