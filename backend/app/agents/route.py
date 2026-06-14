"""Route node: classifies user intent as teach/chat/diagnose."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import IntentResult, completed_event

_ROUTE_SYSTEM = """你是一个专利学习助手路由器。将用户输入分类为三种意图之一，并返回JSON。

intent 可选值：
- teach: 用户想要系统学习专利知识（例如可能含"系统学习"、"学习路径"、"规划"、"帮我准备"等词）
- chat: 具体知识点问答、定义、对比类问题（如"什么是抵触申请"）
- diagnose: 用户只想做学情诊断（例如可能含"诊断"、"薄弱点"、"评估"、"测试一下"等词）
- 不确定时默认为 chat

必须返回包含 intent、confidence、reason 三个字段的 JSON。"""

_ROUTE_EXAMPLE = """{"intent": "teach", "confidence": 0.9, "reason": "用户请求系统学习"}"""


def build_route_node(llm_client: LLMClient) -> Node:
    import json as _json

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")

        from backend.app.core.llm import LLMMessage, LLMRole
        messages = [
            LLMMessage(role="system", content=_ROUTE_SYSTEM),
            LLMMessage(role="user", content=f"用户输入：{user_input}"),
            LLMMessage(
                role="user",
                content="你必须只输出 JSON，不要输出 Markdown。字段必须与示例完全一致。"
                f"示例：{_ROUTE_EXAMPLE}",
            ),
        ]
        raw = llm_client.generate_json(messages=messages, temperature=0.0, agent="route")
        validated = IntentResult.model_validate(raw)
        return {
            "intent": validated.intent,
            "events": [completed_event("route", f"routed to {validated.intent}: {validated.reason}")],
        }

    return route_node
