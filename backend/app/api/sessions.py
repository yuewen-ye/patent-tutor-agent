"""Session REST endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.llm import AgentName, LLMProvider
from backend.app.services.session_service import SessionService


class CreateSessionRequest(BaseModel):
    user_input: str = Field(min_length=1)
    learner_id: str | None = None
    max_debate_rounds: int = Field(default=2, ge=1, le=3)
    provider_overrides: dict[AgentName, LLMProvider] | None = None


def create_sessions_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["sessions"])

    @router.post("/sessions")
    def create_session(request: CreateSessionRequest) -> dict[str, Any]:
        record = session_service.create_session(
            user_input=request.user_input,
            learner_id=request.learner_id,
            max_debate_rounds=request.max_debate_rounds,
            provider_overrides=request.provider_overrides,
        )
        return {"session_id": record.session_id, "status": record.status}

    @router.get("/sessions")
    def list_sessions() -> dict[str, Any]:
        return {
            "sessions": [session_service.snapshot(record.session_id) for record in session_service.list_sessions()]
        }

    @router.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        try:
            return session_service.snapshot(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc

    return router
