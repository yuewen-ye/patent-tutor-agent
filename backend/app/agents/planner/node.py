"""Planner Agent node."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient, LLMProviderError
from backend.app.learning_path import build_dual_axis_snapshot, compute_learning_path
from backend.app.memory import load_profile_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import LearningPathItem, StateDict, completed_event

_NODE_ID_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_NODE_ID_REPEATED_DASHES = re.compile(r"-+")

_EXTRA_TEXT = load_prompt(__file__)


def _normalize_node_id(value: object, fallback_index: int) -> str:
    slug = str(value or "").strip().lower().replace("_", "-")
    slug = _NODE_ID_INVALID_CHARS.sub("-", slug)
    slug = _NODE_ID_REPEATED_DASHES.sub("-", slug).strip("-")
    return slug or f"learning-step-{fallback_index}"


def _normalize_learning_path_item(item: object, index: int) -> object:
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    normalized["node_id"] = _normalize_node_id(normalized.get("node_id"), index)
    return normalized


def build_planner_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "list[LearningPathItem]",
                    '[{"node_id":"patentability-basic","node_name":"专利授权条件基础",'
                    '"duration_min":20,"strategy":"先学概念","prerequisites":[]}]',
                )
                + _EXTRA_TEXT,
            ),
            (
                "user",
                "用户问题：{user_input}\n学习者画像：{learner_profile}\n请规划学习路径。",
            ),
        ]
    )

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
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=profile,
            ),
            temperature=agent_temperature("planner", 0.5),
            agent="planner",
        )
        if not isinstance(raw, list):
            raise LLMProviderError("Planner Agent must return a JSON array.")
        deterministic = compute_learning_path(
            profile=profile,
            learning_goal=str(profile.get("learning_goal") or state["user_input"]),
        )
        path = [LearningPathItem.model_validate(item) for item in deterministic]
        suggested = [
            _normalize_learning_path_item(item, index)
            for index, item in enumerate(raw, start=1)
        ]
        suggested_ids = [
            item.get("node_id") for item in suggested if isinstance(item, dict)
        ]
        selected = next(
            (item.node_id for item in path if item.node_id in suggested_ids),
            path[0].node_id if path else None,
        )
        dual_axis = build_dual_axis_snapshot(profile=profile, session_id=state["session_id"])
        return {
            "learning_path": [item.model_dump() for item in path],
            "dual_axis_snapshot": dual_axis,
            "path_decision": {
                "current_node_id": selected,
                "algorithm": "deterministic_astar",
                "suggested_node_ids": suggested_ids,
            },
            "events": [completed_event("planner", "planned learning path with LLM")],
        }

    return planner_node
