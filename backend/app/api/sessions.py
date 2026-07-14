"""Session REST endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.api.models import (
    ErrorResponse,
    SessionCreatedResponse,
    SessionsListResponse,
    SessionSnapshotResponse,
)
from backend.app.core.llm import AgentName, LLMProvider
from backend.app.services.session_service import SessionService


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_input: str = Field(min_length=1)
    learner_id: str | None = None
    max_debate_rounds: int = Field(default=2, ge=1, le=3)
    provider_overrides: dict[AgentName, LLMProvider] | None = None
    mode: Literal["auto", "teach", "chat", "diagnose"] = "auto"

    @model_validator(mode="after")
    def validate_explicit_teach(self) -> CreateSessionRequest:
        if self.mode == "teach" and not self.learner_id:
            raise ValueError("learner_id is required when mode is teach")
        return self


def create_sessions_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["sessions"])

    @router.post(
        "/sessions",
        response_model=SessionCreatedResponse,
        description="Create a background tutoring workflow session.",
    )
    def create_session(request: CreateSessionRequest) -> SessionCreatedResponse:
        record = session_service.create_session(
            user_input=request.user_input,
            learner_id=request.learner_id,
            max_debate_rounds=request.max_debate_rounds,
            provider_overrides=request.provider_overrides,
            workflow_mode=request.mode,
        )
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    @router.get(
        "/sessions",
        response_model=SessionsListResponse,
        description="List in-memory workflow sessions.",
    )
    def list_sessions() -> SessionsListResponse:
        return SessionsListResponse(
            sessions=[
                SessionSnapshotResponse.model_validate(session_service.snapshot(record.session_id))
                for record in session_service.list_sessions()
            ]
        )

    @router.get(
        "/sessions/{session_id}",
        response_model=SessionSnapshotResponse,
        responses={404: {"model": ErrorResponse}},
        description="Return a workflow session state snapshot.",
    )
    def get_session(session_id: str) -> SessionSnapshotResponse:
        try:
            return SessionSnapshotResponse.model_validate(session_service.snapshot(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    @router.delete(
        "/sessions/{session_id}",
        response_model=SessionSnapshotResponse,
        responses={404: {"model": ErrorResponse}},
        status_code=status.HTTP_200_OK,
        description="Cancel a running workflow session.",
    )
    def cancel_session(session_id: str) -> SessionSnapshotResponse:
        try:
            return SessionSnapshotResponse.model_validate(session_service.cancel_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    return router
