"""LangGraph Store helpers for learner memory."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from langgraph.runtime import Runtime

from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import StateDict


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
    items = store.search(learner_namespace(learner_id, "profile"), limit=limit)
    return [dict(item.value) for item in items]


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


def _learner_id(runtime: Runtime[WorkflowContext] | None) -> str | None:
    if runtime is None:
        return None
    context = runtime.context
    if isinstance(context, dict):
        value = context.get("learner_id")
    else:
        value = getattr(context, "learner_id", None)
    return str(value) if value else None
