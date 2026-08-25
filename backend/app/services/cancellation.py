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

    def generate_validated_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        validator: Callable[[str], Any],
        repair_messages: Callable[[list[LLMMessage], str, Exception], list[LLMMessage]],
        agent: AgentName | None = None,
        repair_attempts: int = 2,
    ) -> Any:
        self._raise_if_cancelled()
        validated_generate = getattr(self._inner, "generate_validated_json_stream", None)
        if callable(validated_generate):
            return validated_generate(
                messages,
                temperature,
                schema_name=schema_name,
                json_schema=json_schema,
                validator=validator,
                repair_messages=repair_messages,
                agent=agent,
                repair_attempts=repair_attempts,
            )
        current_messages = list(messages)
        last_error: Exception | None = None
        for attempt in range(repair_attempts):
            self._raise_if_cancelled()
            raw_text = "".join(
                self.generate_json_stream(
                    current_messages,
                    temperature,
                    agent,
                    schema_name=schema_name,
                    json_schema=json_schema,
                )
            )
            try:
                return validator(raw_text)
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= repair_attempts:
                    raise
                current_messages = repair_messages(current_messages, raw_text, exc)
        assert last_error is not None
        raise last_error

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
        repair_messages: Callable[[list[LLMMessage], object, Exception], list[LLMMessage]] | None = None,
        repair_attempts: int = 2,
        agent: AgentName | None = None,
    ) -> Any:
        self._raise_if_cancelled()
        validated_generate = getattr(self._inner, "generate_structured_validated_json", None)
        if callable(validated_generate):
            if repair_messages is None:
                return validated_generate(
                    messages,
                    temperature,
                    schema_name=schema_name,
                    json_schema=json_schema,
                    validator=validator,
                    agent=agent,
                )
            try:
                return validated_generate(
                    messages,
                    temperature,
                    schema_name=schema_name,
                    json_schema=json_schema,
                    validator=validator,
                    repair_messages=repair_messages,
                    repair_attempts=repair_attempts,
                    agent=agent,
                )
            except TypeError as exc:
                if "repair_messages" not in str(exc):
                    raise
                return validated_generate(
                    messages,
                    temperature,
                    schema_name=schema_name,
                    json_schema=json_schema,
                    validator=validator,
                    agent=agent,
                )

    def generate_validated_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        *,
        validator: Callable[[LLMResponseWithTools], Any],
        repair_messages: Callable[[list[LLMMessage], LLMResponseWithTools, Exception], list[LLMMessage]] | None = None,
        repair_attempts: int = 2,
        agent: AgentName | None = None,
    ) -> Any:
        self._raise_if_cancelled()
        validated_generate = getattr(self._inner, "generate_validated_with_tools", None)
        if callable(validated_generate):
            return validated_generate(
                messages,
                tools,
                temperature,
                validator=validator,
                repair_messages=repair_messages,
                repair_attempts=repair_attempts,
                agent=agent,
            )
        current_messages = list(messages)
        for attempt in range(repair_attempts):
            self._raise_if_cancelled()
            response = self._inner.generate_with_tools(current_messages, tools, temperature, agent)
            try:
                return validator(response)
            except Exception as exc:
                if repair_messages is None or attempt + 1 >= repair_attempts:
                    raise
                current_messages = repair_messages(current_messages, response, exc)
        raise RuntimeError("tool-call validation loop exited unexpectedly")

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
