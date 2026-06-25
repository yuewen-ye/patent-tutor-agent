"""Chat answer node: generates a direct answer from tool_agent context."""

from __future__ import annotations

import json as _json
from typing import Any

from backend.app.agents.common import Node, load_prompt
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import ChatAnswer, completed_event

_CHAT_SYSTEM = load_prompt(__file__)


def _sources_from_retrieval_context(retrieval_context: object) -> list[str]:
    if not isinstance(retrieval_context, list):
        return []
    sources: list[str] = []
    for chunk in retrieval_context:
        if not isinstance(chunk, dict):
            continue
        citation = chunk.get("citation")
        if isinstance(citation, str) and citation and citation not in sources:
            sources.append(citation)
    return sources


def build_chat_answer_node(llm_client: LLMClient) -> Node:
    def chat_answer_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        retrieval_context = state.get("retrieval_context", [])
        tool_agent_answer = state.get("tool_agent_answer")
        if isinstance(tool_agent_answer, str) and tool_agent_answer.strip():
            validated = ChatAnswer.model_validate({
                "content": tool_agent_answer,
                "sources": _sources_from_retrieval_context(retrieval_context),
            })
            return {
                "chat_answer": validated.model_dump(),
                "events": [completed_event("chat_answer", "reused tool agent answer")],
            }

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
        raw = llm_client.generate_json(messages=messages, temperature=0.3, agent="chat_answer")
        validated = ChatAnswer.model_validate(raw)

        return {
            "chat_answer": validated.model_dump(),
            "events": [completed_event("chat_answer", "generated chat answer")],
        }

    return chat_answer_node
