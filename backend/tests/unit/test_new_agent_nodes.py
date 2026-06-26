"""TDD Phase 4: Tests for route, tool_agent, chat_answer nodes."""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.agents.route import build_route_node
from backend.app.agents.tool_agent import build_tool_agent_node
from backend.app.agents.chat_answer import build_chat_answer_node
from backend.app.core.llm import (
    LLMMessage,
    LLMProviderError,
    LLMResponseWithTools,
    ToolCall,
    ToolDefinition,
)


class FakeLLMClient:
    """Returns predetermined JSON responses."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append({"method": "generate_json", "agent": agent, "temperature": temperature})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition],
        temperature: float, agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append({"method": "generate_with_tools", "agent": agent, "temperature": temperature})
        if isinstance(self.response, LLMResponseWithTools):
            return self.response
        return LLMResponseWithTools(content=str(self.response), tool_calls=[])


class TestRouteNode:
    def test_classifies_teach(self) -> None:
        client = FakeLLMClient({
            "intent": "teach", "confidence": 0.95,
            "reason": "用户明确请求系统学习",
        })
        node = build_route_node(client)
        result = node({"user_input": "我想系统学习专利法", "session_id": "s1", "events": []})
        assert result["intent"] == "teach"
        assert len(result["events"]) == 1
        assert result["events"][0]["node"] == "route"

    def test_classifies_chat(self) -> None:
        client = FakeLLMClient({
            "intent": "chat", "confidence": 0.8, "reason": "单点问答",
        })
        node = build_route_node(client)
        result = node({"user_input": "什么是抵触申请", "session_id": "s2", "events": []})
        assert result["intent"] == "chat"

    def test_classifies_diagnose(self) -> None:
        client = FakeLLMClient({
            "intent": "diagnose", "confidence": 0.7, "reason": "仅诊断请求",
        })
        node = build_route_node(client)
        result = node({"user_input": "帮我诊断薄弱点", "session_id": "s3", "events": []})
        assert result["intent"] == "diagnose"

    def test_temperature_is_zero(self) -> None:
        client = FakeLLMClient({
            "intent": "teach", "confidence": 0.9, "reason": "x",
        })
        node = build_route_node(client)
        node({"user_input": "test", "session_id": "s1", "events": []})
        assert client.calls[0]["temperature"] == 0.0

    def test_local_learning_hint_overrides_chat_misroute(self) -> None:
        client = FakeLLMClient({
            "intent": "chat", "confidence": 0.8, "reason": "误判为单点问答",
        })
        node = build_route_node(client)
        result = node({"user_input": "我想学习专利新颖性", "session_id": "s1", "events": []})
        assert result["intent"] == "teach"

    def test_local_learning_hint_recovers_from_provider_json_error(self) -> None:
        client = FakeLLMClient(LLMProviderError("malformed route JSON"))
        node = build_route_node(client)
        result = node({"user_input": "我想继续深入了解抵触申请", "session_id": "s1", "events": []})
        assert result["intent"] == "teach"


class TestToolAgentNode:
    def test_no_tool_call_returns_directly(self) -> None:
        """When LLM returns content without tool_calls, exit immediately."""
        client = FakeLLMClient(
            LLMResponseWithTools(content="新颖性是专利授权的条件之一。", tool_calls=[])
        )
        node = build_tool_agent_node(client)
        result = node({
            "user_input": "什么是新颖性",
            "session_id": "s1",
            "events": [],
            "retrieval_context": [],
        })
        assert len(client.calls) == 1
        assert "retrieval_context" in result
        assert result["tool_agent_answer"] == "新颖性是专利授权的条件之一。"

    def test_tool_call_then_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM calls tool first, then returns content."""
        monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
        client = FakeLLMClient(None)  # Will be overridden per call
        call_count = [0]

        def custom_generate_with_tools(
            messages, tools, temperature, agent=None
        ) -> LLMResponseWithTools:
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResponseWithTools(
                    content=None,
                    tool_calls=[
                        ToolCall(id="c1", name="rag_retrieve", arguments={"query": "新颖性"})
                    ],
                )
            return LLMResponseWithTools(content="根据检索结果，新颖性是指...", tool_calls=[])

        client.generate_with_tools = custom_generate_with_tools  # type: ignore[method-assign]

        node = build_tool_agent_node(client)
        result = node({
            "user_input": "什么是新颖性",
            "session_id": "s1",
            "events": [],
            "retrieval_context": [],
        })

        assert call_count[0] == 2  # 1 tool call + 1 final answer
        assert "retrieval_context" in result
        assert result["tool_agent_answer"] == "根据检索结果，新颖性是指..."

    def test_max_rounds_capped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After 5 rounds, force exit."""
        monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")

        def always_tool_call(messages, tools, temperature, agent=None):
            return LLMResponseWithTools(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="rag_retrieve", arguments={"query": "x"})
                ],
            )

        client = FakeLLMClient(None)
        client.generate_with_tools = always_tool_call  # type: ignore[method-assign]

        node = build_tool_agent_node(client)
        result = node({
            "user_input": "test",
            "session_id": "s1",
            "events": [],
            "retrieval_context": [],
        })
        # Should exit after 5 rounds without infinite loop
        assert "retrieval_context" in result


class TestChatAnswerNode:
    def test_reuses_tool_agent_answer_without_second_llm_call(self) -> None:
        client = FakeLLMClient({
            "content": "不应调用模型", "sources": [],
        })
        node = build_chat_answer_node(client)
        result = node({
            "user_input": "什么是抵触申请",
            "session_id": "s1",
            "events": [],
            "retrieval_context": [{"citation": "专利法第22条", "text": "..."}],
            "tool_agent_answer": "抵触申请是指在先申请影响在后申请的新颖性。",
        })
        assert client.calls == []
        assert result["chat_answer"]["content"] == "抵触申请是指在先申请影响在后申请的新颖性。"
        assert result["chat_answer"]["sources"] == ["专利法第22条"]

    def test_generates_answer(self) -> None:
        client = FakeLLMClient({
            "content": "抵触申请是指...", "sources": ["专利法第22条"],
        })
        node = build_chat_answer_node(client)
        result = node({
            "user_input": "什么是抵触申请",
            "session_id": "s1",
            "events": [],
            "retrieval_context": [{"chunk_id": "x", "text": "..."}],
        })
        assert result["chat_answer"]["content"] == "抵触申请是指..."
        assert "专利法第22条" in result["chat_answer"]["sources"]
