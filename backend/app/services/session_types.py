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
    session_id: str
    user_input: str
    learner_id: str | None
    status: SessionStatus
    state: StateDict
    created_at: str
    updated_at: str
    error: str | None
    done: threading.Event
    cancel_requested: threading.Event
    thread: threading.Thread | None

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
    state = compact_state(record.state)
    # 为前端讲义 tab 补全「教学正文完整版」（teaching_content + 各 block payload 详细内容），
    # 与 course_package.md 的「教学正文」段一致。只在返回副本上追加，绝不改动存储中的 state。
    course_pkg = state.get("course_package")
    if isinstance(course_pkg, dict) and course_pkg.get("block_plan"):
        from ..runtime_outputs.artifacts import course_teaching_content_full

        enriched = dict(course_pkg)
        enriched["teaching_content_full"] = course_teaching_content_full(course_pkg)
        state = {**state, "course_package": enriched}
    return {
        "session_id": record.session_id,
        "status": record.status,
        "learner_id": record.learner_id,
        "state": state,
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
