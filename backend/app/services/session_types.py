from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from backend.app.schemas.state import StateDict

SessionStatus = Literal["running", "completed", "failed", "canceled"]
ReadinessValue = Literal["ready", "not_ready"]


class SessionCounts(TypedDict):
    running: int
    completed: int
    failed: int
    canceled: int
    total: int


class ReadinessStatus(TypedDict):
    ready: bool
    status: ReadinessValue
    reason: str | None


class SessionRecord:
    __slots__ = (
        "cancel_requested",
        "created_at",
        "done",
        "error",
        "learner_id",
        "session_id",
        "state",
        "status",
        "thread",
        "updated_at",
        "user_input",
    )

    def __init__(
        self,
        *,
        session_id: str,
        user_input: str,
        learner_id: str | None,
        status: SessionStatus,
        state: StateDict,
        created_at: str,
        updated_at: str,
    ) -> None:
        self.session_id = session_id
        self.user_input = user_input
        self.learner_id = learner_id
        self.status = status
        self.state = state
        self.created_at = created_at
        self.updated_at = updated_at
        self.error: str | None = None
        self.done = threading.Event()
        self.cancel_requested = threading.Event()
        self.thread: threading.Thread | None = None


def record_to_response(record: SessionRecord) -> dict[str, Any]:
    return {
        "session_id": record.session_id,
        "status": record.status,
        "learner_id": record.learner_id,
        "state": compact_state(record.state),
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def compact_state(state: StateDict) -> dict[str, Any]:
    return {key: value for key, value in state.items() if value is not None}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
