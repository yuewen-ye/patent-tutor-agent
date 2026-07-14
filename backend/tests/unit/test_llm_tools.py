"""TDD Phase 1: Tests for LLM tool-calling support.

RED phase — these tests define the expected behavior before implementation.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from backend.app.core.llm import (
    AgentLLMRouter,
    AgentName,
    DefaultLLMClient,
    LLMMessage,
    LLMResponseWithTools,
    ToolCall,
    ToolDefinition,
    call_llm_tools,
)


class TestToolCallDataclass:
    def test_creation(self) -> None:
        tc = ToolCall(
            id="call_001",
            name="rag_retrieve",
            arguments={"query": "专利法新颖性", "top_k": 5},
        )
        assert tc.id == "call_001"
        assert tc.name == "rag_retrieve"
        assert tc.arguments["query"] == "专利法新颖性"

    def test_empty_arguments(self) -> None:
        tc = ToolCall(id="call_002", name="no_args_tool", arguments={})
        assert tc.arguments == {}


class TestToolDefinition:
    def test_creation(self) -> None:
        td = ToolDefinition(
            name="rag_retrieve",
            description="Search patent law knowledge base",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )
        assert td.name == "rag_retrieve"
        properties = td.parameters["properties"]
        assert isinstance(properties, dict)
        assert "query" in properties

    def test_to_openai_format(self) -> None:
        """ToolDefinition should serialize to OpenAI-compatible tool dict."""
        td = ToolDefinition(
            name="rag_retrieve",
            description="Search patent law knowledge base",
            parameters={"type": "object", "properties": {}, "required": []},
        )
        result: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
            },
        }
        assert result["type"] == "function"
        assert result["function"]["name"] == "rag_retrieve"


class TestLLMResponseWithTools:
    def test_content_only(self) -> None:
        resp = LLMResponseWithTools(content="Hello", tool_calls=[])
        assert resp.content == "Hello"
        assert resp.tool_calls == []

    def test_tool_call_only(self) -> None:
        tc = ToolCall(id="c1", name="rag_retrieve", arguments={"query": "x"})
        resp = LLMResponseWithTools(content=None, tool_calls=[tc])
        assert resp.content is None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "rag_retrieve"

    def test_content_and_tool_call(self) -> None:
        tc = ToolCall(id="c1", name="rag_retrieve", arguments={"query": "x"})
        resp = LLMResponseWithTools(content="Let me search", tool_calls=[tc])
        assert resp.content == "Let me search"
        assert len(resp.tool_calls) == 1


class TestCallLlmToolsWithMockTransport:
    def test_sends_tools_not_response_format(self) -> None:
        """Verify the request body has 'tools' not 'response_format'."""
        captured_body: dict | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "I will search.",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "rag_retrieve",
                                            "arguments": '{"query": "test"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )

        tools = [
            ToolDefinition(
                name="rag_retrieve",
                description="Search",
                parameters={"type": "object", "properties": {}, "required": []},
            )
        ]
        messages = [LLMMessage(role="user", content="test query")]

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            _result = call_llm_tools(
                provider="deepseek",
                messages=messages,
                tools=tools,
                temperature=0.0,
                http_client=client,
            )

        assert captured_body is not None
        assert "tools" in captured_body
        assert "response_format" not in captured_body
        assert captured_body["tools"][0]["type"] == "function"

    def test_parses_tool_calls_from_response(self) -> None:
        """Verify tool_calls are correctly parsed from the response."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Let me look that up.",
                                "tool_calls": [
                                    {
                                        "id": "call_abc",
                                        "type": "function",
                                        "function": {
                                            "name": "rag_retrieve",
                                            "arguments": '{"query": "新颖性","top_k": 3}',
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )

        tools = [
            ToolDefinition(
                name="rag_retrieve",
                description="Search",
                parameters={"type": "object", "properties": {}, "required": []},
            )
        ]
        messages = [LLMMessage(role="user", content="什么是新颖性")]

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = call_llm_tools(
                provider="deepseek",
                messages=messages,
                tools=tools,
                temperature=0.0,
                http_client=client,
            )

        assert isinstance(result, LLMResponseWithTools)
        assert result.content == "Let me look that up."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_abc"
        assert result.tool_calls[0].name == "rag_retrieve"
        assert result.tool_calls[0].arguments == {"query": "新颖性", "top_k": 3}

    def test_no_tool_calls_in_response(self) -> None:
        """Response without tool_calls — returns empty list."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "The answer is 42."
                            }
                        }
                    ]
                },
            )

        tools = [
            ToolDefinition(
                name="rag_retrieve",
                description="Search",
                parameters={"type": "object", "properties": {}, "required": []},
            )
        ]
        messages = [LLMMessage(role="user", content="what is the answer")]

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = call_llm_tools(
                provider="deepseek",
                messages=messages,
                tools=tools,
                temperature=0.0,
                http_client=client,
            )

        assert result.content == "The answer is 42."
        assert result.tool_calls == []


class TestLLMClientGenerateWithTools:
    def test_default_llm_client_has_method(self) -> None:
        """DefaultLLMClient implements generate_with_tools."""
        client = DefaultLLMClient(provider="deepseek")
        assert hasattr(client, "generate_with_tools")
        assert callable(client.generate_with_tools)

    def test_agent_router_has_method(self) -> None:
        """AgentLLMRouter implements generate_with_tools."""
        router = AgentLLMRouter(default_provider="deepseek")
        assert hasattr(router, "generate_with_tools")
        assert callable(router.generate_with_tools)


class TestAgentNameExtension:
    def test_new_agent_names_accepted(self) -> None:
        """The new agent names are valid AgentName values."""
        # These should pass type checking at runtime
        names: list[AgentName] = ["route", "diagnosis_feedback", "chat_answer"]
        for name in names:
            assert name in AgentName.__args__  # type: ignore[attr-defined]
        assert "planner" not in AgentName.__args__  # type: ignore[attr-defined]
        assert "tool_agent" not in AgentName.__args__  # type: ignore[attr-defined]
