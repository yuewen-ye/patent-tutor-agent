from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.api.models import (
    ErrorResponse,
    LearnerHistoryResponse,
    LearnerMemoryResponse,
    LearnerProfilesResponse,
    LearnerSessionsResponse,
)
from backend.app.memory import LearnerMemoryStoreError
from backend.app.services.session_service import SessionService


def create_learners_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["learners"])

    def read_learner_memory(learner_id: str, limit: int) -> dict[str, Any]:
        try:
            return session_service.learner_memory(learner_id, limit=limit)
        except LearnerMemoryStoreError as exc:
            raise _memory_store_exception(exc) from exc

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
        try:
            sessions = session_service.learner_sessions(learner_id, limit=limit)
        except LearnerMemoryStoreError as exc:
            raise _memory_store_exception(exc) from exc
        return LearnerSessionsResponse(learner_id=learner_id, sessions=sessions)

    return router


def _memory_store_exception(exc: LearnerMemoryStoreError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error": "memory_store_corrupt",
            "store": exc.path.name,
            "reason": exc.reason,
        },
    )
