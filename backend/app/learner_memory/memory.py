"""LangGraph Store helpers for learner memory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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


def load_mastery_snapshot(
    runtime: Runtime[WorkflowContext] | None,
) -> dict[str, dict[str, Any]]:
    """Load the backend-computed mastery projection without reading profile knowledge."""

    learner_id = _learner_id(runtime)
    store = getattr(runtime, "store", None) if runtime is not None else None
    reader = getattr(store, "mastery_snapshot", None)
    if not learner_id or not callable(reader):
        return {}
    snapshot = reader(learner_id)
    if not isinstance(snapshot, dict):
        return {}
    return {
        str(skill_id): dict(state)
        for skill_id, state in snapshot.items()
        if isinstance(state, dict)
    }


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
        save_profile = getattr(store, "save_profile", None)
        if callable(save_profile):
            save_profile(
                learner_id=learner_id,
                session_id=state["session_id"],
                profile=learner_profile,
                key=str(uuid.uuid4()),
                source="feedback",
            )
        else:
            store.put(
                learner_namespace(learner_id, "profile"),
                str(uuid.uuid4()),
                learner_profile,
            )

    learning_path = state.get("learning_path", [])
    history = {
        "session_id": state["session_id"],
        "event_type": "feedback_completed",
        "topic": learner_profile.get("learning_goal") or state["user_input"],
        "knowledge_points": [item.get("node_name") for item in learning_path if item.get("node_name")],
        "profile_update_hint": feedback_result.get("profile_update_hint"),
        "next_action": feedback_result.get("next_action"),
        "created_at": created_at,
    }
    save_history = getattr(store, "save_history", None)
    if callable(save_history):
        save_history(
            learner_id=learner_id,
            session_id=state["session_id"],
            event_type="feedback_completed",
            payload=history,
        )
    else:
        store.put(
            learner_namespace(learner_id, "history"),
            str(uuid.uuid4()),
            history,
        )


def save_profile_snapshot(
    runtime: Runtime[WorkflowContext] | None,
    state: StateDict,
    profile: dict[str, Any],
    *,
    source: str = "diagnosis",
) -> None:
    learner_id = _learner_id(runtime)
    store = getattr(runtime, "store", None) if runtime is not None else None
    if not learner_id or store is None:
        return
    created_at = datetime.now(UTC).isoformat()
    payload = dict(profile)
    payload.update({"created_at": created_at, "session_id": state["session_id"]})
    save_profile = getattr(store, "save_profile", None)
    if callable(save_profile):
        try:
            save_profile(
                learner_id=learner_id,
                session_id=state["session_id"],
                profile=payload,
                key=state["session_id"],
                source=source,
            )
        except TypeError:
            save_profile(
                learner_id=learner_id,
                session_id=state["session_id"],
                profile=payload,
                key=state["session_id"],
            )
    else:
        store.put(learner_namespace(learner_id, "profile"), state["session_id"], payload)


def save_history_snapshot(
    runtime: Runtime[WorkflowContext] | None,
    state: StateDict,
    *,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    learner_id = _learner_id(runtime)
    store = getattr(runtime, "store", None) if runtime is not None else None
    if not learner_id or store is None:
        return
    value = dict(payload)
    value.update(
        {
            "session_id": state["session_id"],
            "event_type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    save_history = getattr(store, "save_history", None)
    if callable(save_history):
        save_history(
            learner_id=learner_id,
            session_id=state["session_id"],
            event_type=event_type,
            payload=value,
            key=f"{state['session_id']}:{event_type}",
        )
    else:
        store.put(
            learner_namespace(learner_id, "history"),
            f"{state['session_id']}:{event_type}",
            value,
        )


def learner_memory_snapshot(
    store: Any,
    *,
    learner_id: str,
    limit: int = 10,
) -> dict[str, Any]:
    profiles = list_learner_memories(store, learner_id=learner_id, kind="profile", limit=limit)
    history = list_learner_memories(store, learner_id=learner_id, kind="history", limit=limit)
    mastery_reader = getattr(store, "mastery", None)
    mastery = mastery_reader(learner_id) if callable(mastery_reader) else {}
    active_plan_reader = getattr(store, "active_learning_plan", None)
    active_learning_plan = (
        active_plan_reader(learner_id) if callable(active_plan_reader) else None
    )
    decisions_reader = getattr(store, "list_learning_plan_decisions", None)
    planning_history = (
        decisions_reader(learner_id, limit=limit)
        if callable(decisions_reader)
        else []
    )
    return {
        "learner_id": learner_id,
        "latest_profile": profiles[0] if profiles else None,
        "latest_history": history[0] if history else None,
        "profiles": profiles,
        "history": history,
        "mastery": mastery,
        "active_learning_plan": active_learning_plan,
        "planning_history": planning_history,
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
