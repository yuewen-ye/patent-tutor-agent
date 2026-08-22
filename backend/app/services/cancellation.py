from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from backend.app.core.llm import (
    AgentName,
    LLMClient,
    LLMMessage,
    LLMResponseWithTools,
    ToolDefinition,
)


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

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: AgentName | None = None,
    ) -> Any:
        self._raise_if_cancelled()
        structured_generate = getattr(self._inner, "generate_structured_json", None)
        if callable(structured_generate):
            return structured_generate(
                messages,
                temperature,
                schema_name=schema_name,
                json_schema=json_schema,
                agent=agent,
            )
        return self._inner.generate_json(messages, temperature, agent)

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: AgentName | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        self._raise_if_cancelled()
        stream_generate = getattr(self._inner, "generate_json_stream", None)
        if stream_generate is None:
            # Graceful fallback: yield the complete non-streaming response as a single
            # chunk so callers can still accumulate and parse it as streamed JSON.
            def _fallback_stream() -> Iterator[str]:
                raw = self._inner.generate_json(messages, temperature, agent)
                yield json.dumps(raw, ensure_ascii=False) if not isinstance(raw, str) else raw

            return _fallback_stream()
        return stream_generate(
            messages,
            temperature,
            agent,
            schema_name=schema_name,
            json_schema=json_schema,
        )

    def generate_structured_validated_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        validator: Callable[[object], Any],
        agent: AgentName | None = None,
    ) -> Any:
        self._raise_if_cancelled()
        validated_generate = getattr(self._inner, "generate_structured_validated_json", None)
        if callable(validated_generate):
            return validated_generate(
                messages,
                temperature,
                schema_name=schema_name,
                json_schema=json_schema,
                validator=validator,
                agent=agent,
            )
        raise NotImplementedError(
            f"{type(self._inner).__name__} does not support generate_structured_validated_json"
        )

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
