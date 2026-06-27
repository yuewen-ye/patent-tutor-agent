"""LangGraph Store helpers for learner memory."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from pathlib import Path
from typing import TypeGuard

from langgraph.runtime import Runtime

from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import StateDict

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class StoredMemoryItem:
    namespace: tuple[str, str, str]
    key: str
    value: dict[str, JsonValue]
    created_at: str
    updated_at: str


class LearnerMemoryStoreError(RuntimeError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot read learner memory store {path}: {reason}")


class FileLearnerMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def put(
        self,
        namespace: tuple[str, str, str],
        key: str,
        value: dict[str, JsonValue],
    ) -> None:
        with self._lock:
            records = self._read_records()
            now = datetime.now(UTC).isoformat()
            retained = [
                record
                for record in records
                if _record_namespace(record) != namespace or record["key"] != key
            ]
            retained.append(
                {
                    "namespace": list(namespace),
                    "key": key,
                    "value": value,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            self._write_records(retained)

    def search(
        self,
        namespace: tuple[str, str, str],
        *,
        limit: int = 10,
        query: str | None = None,
    ) -> list[StoredMemoryItem]:
        with self._lock:
            records = [
                record
                for record in self._read_records()
                if _record_namespace(record) == namespace and _matches_query(record["value"], query)
            ]
        records.sort(key=lambda record: str(record["created_at"]), reverse=True)
        return [_record_to_item(record) for record in records[:limit]]

    def _read_records(self) -> list[dict[str, JsonValue]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as exc:
            raise LearnerMemoryStoreError(self.path, exc.msg) from exc
        records = raw.get("items", []) if isinstance(raw, dict) else []
        return [record for record in records if _is_memory_record(record)]

    def _write_records(self, records: list[dict[str, JsonValue]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        payload = {"version": 1, "items": records}
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)


def learner_namespace(learner_id: str, kind: str) -> tuple[str, str, str]:
    return ("learners", learner_id, kind)


def load_profile_memories(
    runtime: Runtime[WorkflowContext] | None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    learner_id = _learner_id(runtime)
    store = getattr(runtime, "store", None) if runtime is not None else None
    if not learner_id or store is None:
        return []
    return list_learner_memories(store, learner_id=learner_id, kind="profile", limit=limit)


def save_learner_memories(
    runtime: Runtime[WorkflowContext] | None,
    state: StateDict,
    feedback_result: dict[str, Any],
) -> None:
    learner_id = _learner_id(runtime)
    store = getattr(runtime, "store", None) if runtime is not None else None
    if not learner_id or store is None:
        return

    created_at = datetime.now(UTC).isoformat()
    learner_profile = dict(state.get("learner_profile", {}))
    if learner_profile:
        learner_profile["created_at"] = created_at
        learner_profile["session_id"] = state["session_id"]
        store.put(
            learner_namespace(learner_id, "profile"),
            str(uuid.uuid4()),
            learner_profile,
        )

    learning_path = state.get("learning_path", [])
    history = {
        "session_id": state["session_id"],
        "topic": learner_profile.get("learning_goal") or state["user_input"],
        "knowledge_points": [item.get("node_name") for item in learning_path if item.get("node_name")],
        "profile_update_hint": feedback_result.get("profile_update_hint"),
        "next_action": feedback_result.get("next_action"),
        "created_at": created_at,
    }
    store.put(
        learner_namespace(learner_id, "history"),
        str(uuid.uuid4()),
        history,
    )


def learner_memory_snapshot(
    store: Any,
    *,
    learner_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    profiles = list_learner_memories(store, learner_id=learner_id, kind="profile", limit=limit)
    history = list_learner_memories(store, learner_id=learner_id, kind="history", limit=limit)
    return {
        "learner_id": learner_id,
        "latest_profile": profiles[0] if profiles else None,
        "latest_history": history[0] if history else None,
        "profiles": profiles,
        "history": history,
    }


def list_learner_memories(
    store: Any,
    *,
    learner_id: str,
    kind: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    items = store.search(learner_namespace(learner_id, kind), limit=limit)
    values = [dict(item.value) for item in items]
    return sorted(values, key=lambda value: str(value.get("created_at", "")), reverse=True)


def _learner_id(runtime: Runtime[WorkflowContext] | None) -> str | None:
    if runtime is None:
        return None
    context = runtime.context
    if isinstance(context, dict):
        value = context.get("learner_id")
    else:
        value = getattr(context, "learner_id", None)
    return str(value) if value else None


def _matches_query(value: JsonValue, query: str | None) -> bool:
    if not query:
        return True
    return query in json.dumps(value, ensure_ascii=False)


def _record_to_item(record: dict[str, JsonValue]) -> StoredMemoryItem:
    value = record["value"]
    if not isinstance(value, dict):
        raise LearnerMemoryStoreError(Path("<memory>"), "invalid value")
    return StoredMemoryItem(
        namespace=_record_namespace(record),
        key=str(record["key"]),
        value=value,
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
    )


def _record_namespace(record: dict[str, JsonValue]) -> tuple[str, str, str]:
    namespace = record["namespace"]
    if not _is_namespace(namespace):
        raise LearnerMemoryStoreError(Path("<memory>"), "invalid namespace")
    return (str(namespace[0]), str(namespace[1]), str(namespace[2]))


def _is_namespace(value: JsonValue) -> TypeGuard[list[JsonValue]]:
    return isinstance(value, list) and len(value) == 3


def _is_memory_record(value: JsonValue) -> bool:
    if not isinstance(value, dict):
        return False
    namespace = value.get("namespace")
    return (
        isinstance(namespace, list)
        and len(namespace) == 3
        and isinstance(value.get("key"), str)
        and isinstance(value.get("value"), dict)
        and isinstance(value.get("created_at"), str)
        and isinstance(value.get("updated_at"), str)
    )
