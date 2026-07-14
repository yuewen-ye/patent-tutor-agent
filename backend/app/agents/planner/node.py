"""Planner Agent node."""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from backend.app.agents.common import Node
from backend.app.core.llm import LLMClient
from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    compute_learning_path,
)
from backend.app.learner_memory.memory import load_profile_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import LearningPathItem, StateDict, completed_event


def build_planner_node(llm_client: LLMClient) -> Node:
    def planner_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        historical = load_profile_memories(runtime, limit=1)
        profile = dict(historical[0] if historical else state.get("learner_profile", {}))
        store = getattr(runtime, "store", None) if runtime is not None else None
        learner_id = getattr(runtime.context, "learner_id", None) if runtime is not None else None
        mastery_reader = getattr(store, "mastery", None)
        if learner_id and callable(mastery_reader):
            profile["mastery"] = mastery_reader(learner_id)
        deterministic = compute_learning_path(
            profile=profile,
            learning_goal=str(profile.get("learning_goal") or state["user_input"]),
        )
        path = [LearningPathItem.model_validate(item) for item in deterministic]
        selected = path[0].node_id if path else None
        dual_axis = build_dual_axis_snapshot(profile=profile, session_id=state["session_id"])
        return {
            "learning_path": [item.model_dump() for item in path],
            "dual_axis_snapshot": dual_axis,
            "path_decision": {
                "current_node_id": selected,
                "algorithm": "deterministic_astar",
            },
            "events": [completed_event("planner", "planned deterministic learning path")],
        }

    return planner_node
