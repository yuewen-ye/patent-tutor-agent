import pytest
from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import generate_validated_json, messages_from_prompt
from backend.app.core.llm import (
    LLMMessage,
    LLMProviderError,
    LLMResponseWithTools,
    ToolDefinition,
)
from backend.app.schemas.state import IntentResult

pytestmark = pytest.mark.unit


def test_messages_from_prompt_maps_langchain_roles_to_chat_api_roles() -> None:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "system text"),
            ("human", "hello {name}"),
            ("ai", "assistant text"),
        ]
    )

    messages = messages_from_prompt(prompt, name="learner")

    assert [message.role for message in messages] == ["system", "user", "assistant"]
    assert [message.content for message in messages] == [
        "system text",
        "hello learner",
        "assistant text",
    ]


class RepairingStructuredClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.responses = iter(
            [
                {"intent": "teach", "confidence": 0.9},
                {"intent": "teach", "confidence": 0.9, "reason": "用户希望系统学习"},
            ]
        )

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
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
        return next(self.responses)

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        raise AssertionError("structured clients must not fall back to json_object")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


class RepairingLegacyClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.responses = iter(
            [
                {"intent": "teach", "confidence": 0.9},
                {"intent": "teach", "confidence": 0.9, "reason": "已修复"},
            ]
        )

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        self.calls.append(messages)
        return next(self.responses)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


class SchemaRejectingClient(RepairingLegacyClient):
    def __init__(self) -> None:
        super().__init__()
        self.responses = iter(
            [{"intent": "teach", "confidence": 0.9, "reason": "兼容模式"}]
        )
        self.structured_calls = 0

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: str | None = None,
    ) -> object:
        self.structured_calls += 1
        raise LLMProviderError("json_schema is unsupported", status_code=400)


def test_generate_validated_json_repairs_invalid_structured_response_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = RepairingStructuredClient()

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="请分类")],
        temperature=0.0,
        agent="route",
        output_model=IntentResult,
    )

    assert result.reason == "用户希望系统学习"
    assert len(client.calls) == 2
    assert client.calls[0]["schema_name"] == "IntentResult"
    schema = client.calls[0]["json_schema"]
    assert isinstance(schema, dict)
    assert "reason" in schema["required"]
    initial_messages = client.calls[0]["messages"]
    assert isinstance(initial_messages, list)
    assert '"required":["intent","confidence","reason"]' in initial_messages[0].content
    repair_messages = client.calls[1]["messages"]
    assert isinstance(repair_messages, list)
    assert "reason" in repair_messages[-1].content
    assert "agent=route" in caplog.text
    assert "contract=IntentResult" in caplog.text
    assert "Field required" in caplog.text


def test_generate_validated_json_repairs_legacy_json_response_once() -> None:
    client = RepairingLegacyClient()

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="请分类")],
        temperature=0.0,
        agent="route",
        output_model=IntentResult,
    )

    assert result.reason == "已修复"
    assert len(client.calls) == 2
    assert "完整 JSON Schema" in client.calls[0][0].content
    assert "校验错误" in client.calls[1][-1].content


def test_generate_validated_json_falls_back_when_provider_rejects_schema(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = SchemaRejectingClient()

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="请分类")],
        temperature=0.0,
        agent="route",
        output_model=IntentResult,
    )

    assert result.reason == "兼容模式"
    assert client.structured_calls == 1
    assert len(client.calls) == 1
    assert "falling back to JSON-object mode" in caplog.text
