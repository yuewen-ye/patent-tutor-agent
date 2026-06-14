"""Route node: classifies user intent as teach/chat/diagnose."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import IntentResult, completed_event

_ROUTE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个专利学习助手路由器。你的任务是将用户的输入分类为三种意图之一：

- teach: 用户想要系统学习专利知识，需要完整的学习路径（诊断→规划→教学→反馈）
- chat: 用户问一个具体的、可以快速回答的问题，不需要系统学习流程
- diagnose: 用户只想做学情诊断，了解自己的薄弱点

分类规则：
- 包含"系统学习"、"学习路径"、"规划"、"帮我准备"等词语 → teach
- 包含"诊断"、"薄弱点"、"评估"、"测试一下"等词语 → diagnose
- 单个知识点、定义、对比类问题 → chat
- 默认 → chat

只返回JSON。"""),
    ("user", "用户输入：{user_input}"),
])


def build_route_node(llm_client: LLMClient) -> Node:
    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        messages = messages_from_prompt(_ROUTE_PROMPT, user_input=user_input)
        raw = llm_client.generate_json(messages=messages, temperature=0.0, agent="route")
        validated = IntentResult.model_validate(raw)
        return {
            "intent": validated.intent,
            "events": [completed_event("route", f"routed to {validated.intent}: {validated.reason}")],
        }

    return route_node
