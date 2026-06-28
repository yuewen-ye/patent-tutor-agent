from __future__ import annotations

import json as _json
from typing import Any

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import ChatAnswer, completed_event

_CHAT_SYSTEM = load_prompt(__file__)


def build_chat_answer_node(llm_client: LLMClient) -> Node:
    def chat_answer_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        retrieval_context = state.get("retrieval_context", [])
        messages = [
            LLMMessage(role="system", content=_CHAT_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"用户问题：{user_input}\n\n"
                    f"检索到的法条：{_json.dumps(retrieval_context, ensure_ascii=False)}\n\n"
                    "请生成回答。"
                ),
            ),
        ]
        raw = llm_client.generate_json(
            messages=messages,
            temperature=agent_temperature("chat_answer", 0.3),
            agent="chat_answer",
        )
        validated = ChatAnswer.model_validate(raw)

        return {
            "chat_answer": validated.model_dump(),
            "events": [completed_event("chat_answer", "generated chat answer")],
        }

    return chat_answer_node
