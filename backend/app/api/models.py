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


class CourseSummaryResponse(FrozenApiModel):
    """课程摘要信息，用于列表展示。"""
    title: str | None = None
    duration_min: int = 0
    knowledge_points: list[str] = Field(default_factory=list)
    exercise_count: int = 0
    progress: int = 0  # 0-100


class SessionSummaryResponse(FrozenApiModel):
    session_id: str
    status: SessionStatusValue
    workflow_mode: str | None = None
    learner_id: str | None
    created_at: str
    updated_at: str
    course: CourseSummaryResponse | None = None


class SessionsListResponse(FrozenApiModel):
    sessions: list[SessionSummaryResponse]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class LearnerMemoryResponse(FrozenApiModel):
    learner_id: str
    latest_profile: dict[str, Any] | None
    latest_history: dict[str, Any] | None = None
    profiles: list[dict[str, Any]]
    history: list[dict[str, Any]]
    mastery: dict[str, float] = Field(default_factory=dict)
    active_learning_plan: dict[str, Any] | None = None
    planning_history: list[dict[str, Any]] = Field(default_factory=list)
    sessions: list[dict[str, Any]] = Field(default_factory=list)


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


class RegisterRequest(BaseModel):
    login_id: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)


class LoginRequest(BaseModel):
    login_id: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class AuthResponse(FrozenApiModel):
    learner_id: str
    login_id: str
    display_name: str | None = None
    email: str | None = None


class StudentInfoResponse(FrozenApiModel):
    learner_id: str
    login_id: str
    display_name: str | None = None
    email: str | None = None
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class UpdateStudentInfoRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    display_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
