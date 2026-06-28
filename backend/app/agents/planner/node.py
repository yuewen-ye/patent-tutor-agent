"""Planner Agent node."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient, LLMProviderError
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

    def planner_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=agent_temperature("planner", 0.5),
            agent="planner",
        )
        if not isinstance(raw, list):
            raise LLMProviderError("Planner Agent must return a JSON array.")
        path = [
            LearningPathItem.model_validate(_normalize_learning_path_item(item, index))
            for index, item in enumerate(raw, start=1)
        ]
        return {
            "learning_path": [item.model_dump() for item in path],
            "events": [completed_event("planner", "planned learning path with LLM")],
        }

    return planner_node
