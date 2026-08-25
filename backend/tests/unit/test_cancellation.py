"""Tests for session cancellation-aware LLM client wrapper."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from pydantic import BaseModel

from backend.app.agents.common import generate_validated_json
from backend.app.core.llm import LLMClient, LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.services.cancellation import CancelAwareLLMClient, SessionCancelled

pytestmark = pytest.mark.unit


class _RecordingValidatedClient:
    """Records calls and returns scripted data.

    ``generate_json`` returns an invalid payload so the test fails cleanly when
    ``generate_validated_json`` does not find ``generate_structured_validated_json``
    on the cancellation wrapper. ``generate_structured_validated_json`` returns a
    valid payload, so the test passes only after the wrapper proxies that method.
    """

    def __init__(self, valid_response: object) -> None:
        self.calls: list[dict[str, object]] = []
        self.valid_response = valid_response

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        return {"valid": False}

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        raise AssertionError("streaming is not used by this test")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")

    def generate_structured_validated_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        validator: Callable[[object], Any],
        agent: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "schema_name": schema_name,
                "json_schema": json_schema,
                "agent": agent,
            }
        )
        return validator(self.valid_response)


def test_cancel_aware_client_proxies_structured_validated_json() -> None:
    """Regression: wrapper must expose generate_structured_validated_json.

    ``generate_validated_json`` delegates to ``generate_structured_validated_json``
    when a ``semantic_validate`` callable is supplied and the client supports it.
    ``AgentLLMRouter`` provides this method and converts semantic validation failures
    into retryable ``LLMProviderError``s that trigger fallback models. If the
    cancellation wrapper hides this method, semantic validation failures bypass the
    failover loop entirely and crash the session as uncaught ``ValueError``.
    """

    class _Model(BaseModel):
        valid: bool

    inner = _RecordingValidatedClient({"valid": True})
    client = CancelAwareLLMClient(inner, is_cancelled=lambda: False)

    def _semantic_validate(result: _Model) -> None:
        if not result.valid:
            raise ValueError("semantic failure")

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="hi")],
        temperature=0.0,
        agent="planner",
        output_model=_Model,
        schema_name="_Model",
        semantic_validate=_semantic_validate,
    )

    assert result.valid is True
    assert len(inner.calls) == 1
    assert inner.calls[0]["schema_name"] == "_Model"
    assert inner.calls[0]["agent"] == "planner"


class _RecordingStreamClient:
    """Records streaming calls and returns scripted chunks."""

    def __init__(self, chunks: list[str]) -> None:
        self.calls: list[dict[str, object]] = []
        self.chunks = chunks

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        raise AssertionError("non-streaming JSON is not used by this test")

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "agent": agent,
                "schema_name": schema_name,
                "json_schema": json_schema,
            }
        )
        yield from self.chunks

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


class _RecordingNonStreamClient:
    """Only supports generate_json; used to test streaming fallback."""

    def __init__(self, response: object) -> None:
        self.calls: list[dict[str, object]] = []
        self.response = response

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        self.calls.append(
            {"messages": messages, "temperature": temperature, "agent": agent}
        )
        return self.response

    # Intentionally no generate_json_stream: CancelAware should fall back to
    # generate_json and yield its JSON. The cast silences the LLMClient protocol.


def test_cancel_aware_stream_proxies_inner_stream() -> None:
    """Regression: streaming must actually call the inner client.

    If ``generate_json_stream`` contains a ``yield`` anywhere in its body, Python
    treats it as a generator and a ``return inner_generator()`` silently drops the
    inner stream, making callers see an empty iterator. The wrapper must return a
    plain iterator that delegates to the inner stream.
    """
    inner = _RecordingStreamClient(['{"valid": true}'])
    client = CancelAwareLLMClient(inner, is_cancelled=lambda: False)

    chunks = list(
        client.generate_json_stream(
            messages=[LLMMessage(role="user", content="hi")],
            temperature=0.5,
            agent="diagnosis_feedback",
            schema_name="DiagnosisAgentResult",
            json_schema={"type": "object"},
        )
    )

    assert chunks == ['{"valid": true}']
    assert len(inner.calls) == 1
    assert inner.calls[0]["agent"] == "diagnosis_feedback"
    assert inner.calls[0]["schema_name"] == "DiagnosisAgentResult"


def test_cancel_aware_stream_falls_back_to_non_stream() -> None:
    """When the inner client lacks streaming, yield the non-streaming JSON."""
    from typing import cast

    inner_raw = _RecordingNonStreamClient({"valid": True})
    inner = cast(LLMClient, inner_raw)
    client = CancelAwareLLMClient(inner, is_cancelled=lambda: False)

    chunks = list(
        client.generate_json_stream(
            messages=[LLMMessage(role="user", content="hi")],
            temperature=0.5,
            agent="planner",
        )
    )

    assert chunks == ['{"valid": true}']
    assert len(inner_raw.calls) == 1
    assert inner_raw.calls[0]["agent"] == "planner"


def test_cancel_aware_stream_raises_when_cancelled() -> None:
    """Cancelled sessions must not start streaming."""
    client = CancelAwareLLMClient(
        _RecordingStreamClient([]), is_cancelled=lambda: True
    )

    with pytest.raises(SessionCancelled):
        list(client.generate_json_stream([], temperature=0.0))
