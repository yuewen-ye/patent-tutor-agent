from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.api.models import (
    ErrorResponse,
    LearnerHistoryResponse,
    LearnerMemoryResponse,
    LearnerProfilesResponse,
    LearnerSessionsResponse,
    StudentInfoResponse,
    UpdateStudentInfoRequest,
)
from backend.app.persistence.repositories import LearnerRegistrationError
from backend.app.services.session_service import SessionService


def create_learners_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["learners"])

    def read_learner_memory(learner_id: str, limit: int) -> dict[str, Any]:
        return session_service.learner_memory(learner_id, limit=limit)

    @router.get(
        "/learners/{learner_id}",
        response_model=LearnerMemoryResponse,
        responses={500: {"model": ErrorResponse}},
    )
    def get_learner_memory(
        learner_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> LearnerMemoryResponse:
        return LearnerMemoryResponse.model_validate(read_learner_memory(learner_id, limit))

    @router.get(
        "/learners/{learner_id}/profiles",
        response_model=LearnerProfilesResponse,
        responses={500: {"model": ErrorResponse}},
    )
    def list_learner_profiles(
        learner_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> LearnerProfilesResponse:
        memory = read_learner_memory(learner_id, limit)
        return LearnerProfilesResponse(learner_id=learner_id, profiles=memory["profiles"])

    @router.get(
        "/learners/{learner_id}/history",
        response_model=LearnerHistoryResponse,
        responses={500: {"model": ErrorResponse}},
    )
    def list_learner_history(
        learner_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> LearnerHistoryResponse:
        memory = read_learner_memory(learner_id, limit)
        return LearnerHistoryResponse(learner_id=learner_id, history=memory["history"])

    @router.get(
        "/learners/{learner_id}/sessions",
        response_model=LearnerSessionsResponse,
        responses={500: {"model": ErrorResponse}},
    )
    def list_learner_sessions(
        learner_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> LearnerSessionsResponse:
        sessions = session_service.learner_sessions(learner_id, limit=limit)
        return LearnerSessionsResponse(learner_id=learner_id, sessions=sessions)

    @router.get(
        "/learners/{learner_id}/info",
        response_model=StudentInfoResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_learner_info(learner_id: str) -> StudentInfoResponse:
        info = session_service.get_learner_info(learner_id)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "learner_not_found", "reason": "学员不存在"},
            )
        return StudentInfoResponse.model_validate(info)

    @router.put(
        "/learners/{learner_id}/info",
        response_model=StudentInfoResponse,
        responses={
            404: {"model": ErrorResponse},
            400: {"model": ErrorResponse},
        },
    )
    def update_learner_info(
        learner_id: str,
        request: UpdateStudentInfoRequest,
    ) -> StudentInfoResponse:
        if request.display_name is None and request.email is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "no_fields", "reason": "未提供要更新的字段"},
            )
        try:
            info = session_service.update_learner_info(
                learner_id,
                display_name=request.display_name,
                email=request.email,
            )
        except LearnerRegistrationError as exc:
            if exc.reason == "login_id_not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "learner_not_found", "reason": "学员不存在"},
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": exc.reason, "reason": str(exc)},
            ) from exc
        return StudentInfoResponse.model_validate(info)

    return router
