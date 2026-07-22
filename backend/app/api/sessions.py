"""Session REST endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.api.models import (
    ErrorResponse,
    SessionCreatedResponse,
    SessionSummaryResponse,
    SessionsListResponse,
    SessionSnapshotResponse,
)
from backend.app.core.llm import AgentName, LLMProvider
from backend.app.services.session_service import SessionService
from backend.app.services.session_types import SessionStatus


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "user_input": "我想系统学习专利新颖性",
                    "learner_id": "learner-001",
                    "mode": "teach",
                }
            ]
        },
    )

    user_input: str = Field(min_length=1, description="学员的问题或本次学习目标。")
    learner_id: str | None = Field(
        default=None,
        description="学员唯一标识；mode=teach 时必填。",
    )
    provider_overrides: dict[AgentName, LLMProvider] | None = Field(
        default=None,
        description="可选的 Agent 模型供应商覆盖；通常保持为空并使用服务端配置。",
    )
    mode: Literal["auto", "teach", "chat", "diagnose"] = Field(
        default="auto",
        description="auto 自动识别意图；也可强制进入教学、问答或诊断流程。",
    )

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
            provider_overrides=request.provider_overrides,
            workflow_mode=request.mode,
        )
        return SessionCreatedResponse(session_id=record.session_id, status=record.status)

    @router.get(
        "/sessions",
        response_model=SessionsListResponse,
        description="List filtered, paginated summaries of persisted workflow sessions.",
    )
    def list_sessions(
        session_status: Annotated[
            SessionStatus | None,
            Query(alias="status", description="只返回指定状态的会话。"),
        ] = None,
        learner_id: Annotated[
            str | None,
            Query(min_length=1, description="只返回指定学员的会话。"),
        ] = None,
        offset: Annotated[
            int,
            Query(ge=0, description="跳过的会话数量。"),
        ] = 0,
        limit: Annotated[
            int,
            Query(ge=1, le=100, description="本页最多返回的会话数量。"),
        ] = 50,
    ) -> SessionsListResponse:
        records = session_service.list_sessions()
        if session_status is not None:
            records = [record for record in records if record.status == session_status]
        if learner_id is not None:
            records = [record for record in records if record.learner_id == learner_id]
        total = len(records)
        records = records[offset : offset + limit]
        return SessionsListResponse(
            sessions=[
                SessionSummaryResponse(
                    session_id=record.session_id,
                    status=record.status,
                    learner_id=record.learner_id,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
                for record in records
            ],
            total=total,
            offset=offset,
            limit=limit,
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
