from __future__ import annotations

from typing import Any

from backend.app.agents.route import build_route_node
from backend.app.agents.chat_answer import build_chat_answer_node
from backend.app.core.llm import (
    LLMMessage,
    LLMProviderError,
    LLMResponseWithTools,
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


class TestChatAnswerNode:
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
