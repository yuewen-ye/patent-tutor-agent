"""Chat answer node: generates a direct answer from tool_agent context."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import ChatAnswer, completed_event

_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个专利知识助手。根据检索到的法律知识和用户的问题，生成一个简洁、准确的回答。

要求：
- 回答要基于检索到的法条，引用具体法条编号
- 用通俗易懂的语言解释法律概念
- 如果用户问的是"区别"，要进行对比说明
- 控制在500字以内"""),
    ("user", "用户问题：{user_input}\n\n检索到的法条：{retrieval_context}\n\n请生成回答。"),
])


def build_chat_answer_node(llm_client: LLMClient) -> Node:
    def chat_answer_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        retrieval_context = state.get("retrieval_context", [])

        messages = messages_from_prompt(
            _CHAT_PROMPT,
            user_input=user_input,
            retrieval_context=retrieval_context,
        )
        raw = llm_client.generate_json(messages=messages, temperature=0.3, agent="chat_answer")
        validated = ChatAnswer.model_validate(raw)

        return {
            "chat_answer": validated.model_dump(),
            "events": [completed_event("chat_answer", "generated chat answer")],
        }

    return chat_answer_node
