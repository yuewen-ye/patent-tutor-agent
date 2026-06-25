"""Chat answer node: generates a direct answer from tool_agent context."""

from __future__ import annotations

import json as _json
from typing import Any

from backend.app.agents.common import Node
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import ChatAnswer, completed_event

_CHAT_SYSTEM = """你是一个专利知识助手。根据检索到的法律知识和用户的问题，生成一个简洁、准确的回答。

要求：
- 回答要基于检索到的法条，引用具体法条编号
- 用通俗易懂的语言解释法律概念
- 如果用户问的是"区别"，要进行对比说明
- 控制在500字以内

你必须只输出 JSON，不要输出 Markdown。字段名必须使用 snake_case。
示例：{"content": "回答内容", "sources": ["法条来源"]}"""


def _sources_from_retrieval_context(retrieval_context: object) -> list[str]:
    if not isinstance(retrieval_context, list):
        return []
    sources: list[str] = []
    for chunk in retrieval_context:
        if not isinstance(chunk, dict):
            continue
        for key in ("source", "citation"):
            value = chunk.get(key)
            if isinstance(value, str) and value and value not in sources:
                sources.append(value)
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
