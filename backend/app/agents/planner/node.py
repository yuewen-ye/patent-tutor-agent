"""Planner Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient, LLMProviderError
from backend.app.schemas.state import LearningPathItem, StateDict, completed_event


def build_planner_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "list[LearningPathItem]",
                    '[{"node_id":"patentability-basic","node_name":"专利授权条件基础",'
                    '"duration_min":20,"strategy":"先学概念","prerequisites":[]}]',
                ),
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
            temperature=0.5,
            agent="planner",
        )
        if not isinstance(raw, list):
            raise LLMProviderError("Planner Agent must return a JSON array.")
        path = [LearningPathItem.model_validate(item) for item in raw]
        return {
            "learning_path": [item.model_dump() for item in path],
            "events": [completed_event("planner", "planned learning path with LLM")],
        }

    return planner_node
