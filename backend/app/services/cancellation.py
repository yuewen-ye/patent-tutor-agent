from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.app.core.llm import AgentName, LLMClient, LLMMessage, LLMResponseWithTools, ToolDefinition


class SessionCancelled(RuntimeError):
    pass


class CancelAwareLLMClient:
    def __init__(self, inner: LLMClient, is_cancelled: Callable[[], bool]) -> None:
        self._inner = inner
        self._is_cancelled = is_cancelled

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: AgentName | None = None,
    ) -> Any:
        self._raise_if_cancelled()
        return self._inner.generate_json(messages, temperature, agent)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        self._raise_if_cancelled()
        return self._inner.generate_with_tools(messages, tools, temperature, agent)

    def _raise_if_cancelled(self) -> None:
        if self._is_cancelled():
            raise SessionCancelled
