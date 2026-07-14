"""Route node: classifies user intent as teach/chat/diagnose."""

from __future__ import annotations

from typing import Any, Literal


from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt
from backend.app.core.llm import LLMClient, LLMProviderError
from backend.app.schemas.state import IntentResult, completed_event

_ROUTE_SYSTEM = load_prompt(__file__)

_ROUTE_EXAMPLE = """{"intent": "teach", "confidence": 0.9, "reason": "用户请求系统学习"}"""

_DIAGNOSE_HINTS = ("诊断", "薄弱点", "评估", "测试一下", "准备情况")
_TEACH_HINTS = (
    "系统学习",
    "学习路径",
    "学习计划",
    "规划",
    "帮我准备",
    "我想学习",
    "想学习",
    "继续深入",
    "深入了解",
)

_LocalIntent = Literal["teach", "diagnose"]


def _local_intent_hint(user_input: str) -> tuple[_LocalIntent, str] | None:
    if any(hint in user_input for hint in _DIAGNOSE_HINTS):
        return "diagnose", "本地规则识别为诊断请求"
    if any(hint in user_input for hint in _TEACH_HINTS):
        return "teach", "本地规则识别为系统学习请求"
    return None


def build_route_node(llm_client: LLMClient) -> Node:

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        explicit_mode = state.get("workflow_mode")
        if explicit_mode in {"teach", "chat", "diagnose"}:
            return {
                "intent": explicit_mode,
                "events": [completed_event("route", f"used explicit mode {explicit_mode}")],
            }
        local_hint = _local_intent_hint(user_input)

        from backend.app.core.llm import LLMMessage
        messages = [
            LLMMessage(role="system", content=_ROUTE_SYSTEM),
            LLMMessage(role="user", content=f"用户输入：{user_input}"),
            LLMMessage(
                role="user",
                content="你必须只输出 JSON，不要输出 Markdown。字段必须与示例完全一致。"
                f"示例：{_ROUTE_EXAMPLE}",
            ),
        ]
        try:
            raw = llm_client.generate_json(
                messages=messages,
                temperature=agent_temperature("route", 0.0),
                agent="route",
            )
        except LLMProviderError:
            if local_hint is None:
                raise
            intent, reason = local_hint
            validated = IntentResult(intent=intent, confidence=1.0, reason=reason)
        else:
            validated = IntentResult.model_validate(raw)
            if local_hint is not None and validated.intent != local_hint[0]:
                intent, reason = local_hint
                validated = IntentResult(intent=intent, confidence=1.0, reason=reason)
        return {
            "intent": validated.intent,
            "events": [completed_event("route", f"routed to {validated.intent}: {validated.reason}")],
        }

    return route_node
