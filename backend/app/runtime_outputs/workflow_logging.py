from __future__ import annotations

import json
import logging
import os
from threading import Lock
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from backend.app.runtime_outputs.artifacts import sanitize_session_id
from backend.app.schemas.state import StateDict

WorkflowLogStatus = Literal["started", "completed", "error"]

_LOG_FILE_NAME: Final = "workflow.log.jsonl"
_THIRD_PARTY_LOGGERS: Final = (
    "watchfiles",
    "watchfiles.main",
    "httpx",
    "httpcore",
    "langgraph",
    "langgraph_api",
    "langgraph_runtime_inmem",
    "milvus_lite",
    "faiss",
)
_WARNING_LOGGERS: Final = ("py.warnings",)
_DEFAULT_THIRD_PARTY_LOG_LEVEL: Final = "ERROR"
_LOG_LOCK: Final = Lock()


@dataclass(frozen=True, slots=True)
class WorkflowLogRecord:
    timestamp: str
    session_id: str
    node: str
    status: WorkflowLogStatus
    teach_phase: str | None
    intent: str | None
    duration_ms: int | None = None
    event_count: int | None = None
    artifact_count: int | None = None
    retrieval_methods: list[str] | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":")) + "\n"


def workflow_log_path(log_root: Path, session_id: str) -> Path:
    return log_root / "sessions" / sanitize_session_id(session_id) / _LOG_FILE_NAME


def configure_studio_terminal_logging() -> None:
    raw_level = os.getenv("STUDIO_THIRD_PARTY_LOG_LEVEL", _DEFAULT_THIRD_PARTY_LOG_LEVEL)
    level = logging.getLevelName(raw_level.strip().upper())
    if not isinstance(level, int):
        level = logging.WARNING
    for logger_name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(level)
    for logger_name in _WARNING_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def write_workflow_log(
    *,
    log_root: Path | None,
    state: StateDict,
    node: str,
    status: WorkflowLogStatus,
    duration_ms: int | None = None,
    updates: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    if log_root is None:
        return

    session_id = state["session_id"]
    record = WorkflowLogRecord(
        timestamp=datetime.now(UTC).isoformat(),
        session_id=session_id,
        node=node,
        status=status,
        teach_phase=state.get("teach_phase"),
        intent=state.get("intent"),
        duration_ms=duration_ms,
        event_count=_count_list(updates, "events"),
        artifact_count=_count_list(updates, "artifacts"),
        retrieval_methods=_retrieval_methods(updates),
        error_type=type(error).__name__ if error is not None else None,
        error_message=str(error) if error is not None else None,
    )
    path = workflow_log_path(log_root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8") as file:
            file.write(record.to_json_line())


def _count_list(updates: dict[str, Any] | None, key: str) -> int | None:
    if updates is None:
        return None
    value = updates.get(key)
    if isinstance(value, list):
        return len(value)
    return None


def _retrieval_methods(updates: dict[str, Any] | None) -> list[str] | None:
    if updates is None:
        return None
    context = updates.get("retrieval_context")
    if not isinstance(context, list):
        return None

    methods: set[str] = set()
    for chunk in context:
        if not isinstance(chunk, dict):
            continue
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            continue
        method = metadata.get("retrieval_method")
        if isinstance(method, str) and method:
            methods.add(method)
    return sorted(methods)
