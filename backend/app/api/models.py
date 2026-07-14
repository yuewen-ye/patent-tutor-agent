from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SessionStatusValue = Literal[
    "running", "completed", "failed", "canceled", "historical"
]


class FrozenApiModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class SessionCreatedResponse(FrozenApiModel):
    session_id: str
    status: SessionStatusValue


class SessionSnapshotResponse(FrozenApiModel):
    session_id: str
    status: SessionStatusValue
    learner_id: str | None
    state: dict[str, Any]
    error: str | None
    created_at: str
    updated_at: str


class SessionsListResponse(FrozenApiModel):
    sessions: list[SessionSnapshotResponse]


class LearnerMemoryResponse(FrozenApiModel):
    learner_id: str
    latest_profile: dict[str, Any] | None
    latest_history: dict[str, Any] | None = None
    profiles: list[dict[str, Any]]
    history: list[dict[str, Any]]
    mastery: dict[str, float] = Field(default_factory=dict)


class LearnerProfilesResponse(FrozenApiModel):
    learner_id: str
    profiles: list[dict[str, Any]]


class LearnerHistoryResponse(FrozenApiModel):
    learner_id: str
    history: list[dict[str, Any]]


class LearnerSessionsResponse(FrozenApiModel):
    learner_id: str
    sessions: list[dict[str, Any]]


class HealthSessionCounts(FrozenApiModel):
    running: int = 0
    completed: int = 0
    failed: int = 0
    canceled: int = 0
    total: int = 0


class HealthResponse(FrozenApiModel):
    status: Literal["ok"]
    sessions: HealthSessionCounts


class ReadinessResponse(FrozenApiModel):
    ready: bool
    status: Literal["ready", "not_ready"]
    reason: str | None = None


class ErrorDetail(FrozenApiModel):
    error: str
    store: str | None = None
    reason: str | None = None


class ErrorResponse(FrozenApiModel):
    detail: str | ErrorDetail


class ArtifactNotFoundResponse(FrozenApiModel):
    detail: str = Field(default="Artifact not found.")
