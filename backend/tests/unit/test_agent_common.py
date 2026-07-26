import pytest
from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import generate_validated_json, messages_from_prompt
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
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
