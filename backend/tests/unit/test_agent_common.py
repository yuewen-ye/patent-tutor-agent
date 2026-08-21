import json
from collections.abc import Iterator

import pytest
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from backend.app.agents.common import (
    _normalize_schema_for_strict,
    _schema_has_free_form_object,
    generate_validated_json,
    generate_validated_json_stream,
    messages_from_prompt,
    normalize_expert_draft_payload,
)
from backend.app.core.llm import (
    LLMMessage,
    LLMProviderError,
    LLMResponseWithTools,
    ToolDefinition,
)
from backend.app.schemas.state import (
    ExpertDraft,
    IntentResult,
    JudgeReport,
    MnemonicPayload,
    SummaryCardPayload,
    WorkedExamplePayload,
)

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


class JudgeReportStructuredClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: str | None = None,
    ) -> object:
        self.calls.append({"schema_name": schema_name, "json_schema": json_schema})
        return {
            "decision": "accept",
            "accuracy_score": 5,
            "adaptation_score": 5,
            "completeness_score": 4,
            "disputes": [],
            "rationale": "通过",
        }

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


def test_generate_validated_json_normalizes_schema_for_strict_endpoints() -> None:
    client = JudgeReportStructuredClient()

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="请评审")],
        temperature=0.0,
        agent="judge",
        output_model=JudgeReport,
    )

    assert result.decision == "accept"
    schema = client.calls[0]["json_schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    debate_def = schema["$defs"]["DebateReport"]
    assert set(debate_def["required"]) == set(debate_def["properties"])
    assert debate_def["additionalProperties"] is False
    assert "attack_relations" in debate_def["required"]


class FreeFormPayloadModel(BaseModel):
    title: str
    payload: dict[str, object] = {}


class FreeFormClient:
    def __init__(self) -> None:
        self.structured_calls = 0
        self.json_calls = 0

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
        raise AssertionError("free-form contracts must not attempt strict schema")

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        self.json_calls += 1
        return {"title": "板块", "payload": {"body": "自由内容"}}

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


def test_generate_validated_json_skips_strict_schema_for_free_form_objects() -> None:
    client = FreeFormClient()

    result = generate_validated_json(
        client,
        messages=[LLMMessage(role="user", content="请生成")],
        temperature=0.0,
        agent="expert_a",
        output_model=FreeFormPayloadModel,
    )

    assert result.payload == {"body": "自由内容"}
    assert client.structured_calls == 0
    assert client.json_calls == 1


def _draft_with_blocks(blocks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "expert": "A",
        "style": "conservative",
        "knowledge_points": [{"node_id": "novelty", "kc_name": "新颖性"}],
        "legal_basis": ["《专利法》第二十二条"],
        "teaching_content": "正文",
        "block_plan": {"blocks": blocks},
    }


def test_expert_draft_payload_chinese_nested_keys_normalize_to_closed_contract() -> None:
    raw = _draft_with_blocks(
        [
            {
                "block_id": "b1",
                "block_type": "worked_example",
                "title": "宽限期例题",
                "payload": {
                    "problem": "展出是否破坏新颖性？",
                    "applicable_rule": "《专利法》第二十四条",
                    "steps": [{"推理": "展出日早于申请日", "小结": "落入宽限期"}],
                    "conclusion": "不破坏",
                    "takeaway": "先判范围再算日期",
                    "垃圾键": "应被丢弃",
                },
            },
            {
                "block_id": "b2",
                "block_type": "summary_card",
                "title": "要点卡",
                "payload": {
                    "cards": [{"概念": "三性", "一句话": "新颖性/创造性/实用性"}],
                    "must_recite": ["三性缺一不可"],
                    "one_line": "先客体后三性",
                },
            },
            {
                "block_id": "b3",
                "block_type": "mnemonic",
                "title": "三性记忆表",
                "payload": {
                    "device": "新/创/实",
                    "mapping": [{"新": "新颖性=未公开"}],
                    "when_recall": "看到授权条件时",
                },
            },
        ]
    )

    draft = ExpertDraft.model_validate(normalize_expert_draft_payload(raw))

    assert draft.block_plan is not None
    worked = draft.block_plan.blocks[0].payload
    assert isinstance(worked, WorkedExamplePayload)
    assert worked.steps[0].reasoning == "展出日早于申请日"
    assert worked.steps[0].summary == "落入宽限期"
    card = draft.block_plan.blocks[1].payload
    assert isinstance(card, SummaryCardPayload)
    assert card.cards[0].concept == "三性"
    assert card.cards[0].one_liner == "新颖性/创造性/实用性"
    mnemonic = draft.block_plan.blocks[2].payload
    assert isinstance(mnemonic, MnemonicPayload)
    assert mnemonic.mapping[0].term == "新"
    assert mnemonic.mapping[0].explanation == "新颖性=未公开"


def test_expert_draft_empty_or_garbage_payload_becomes_none() -> None:
    raw = _draft_with_blocks(
        [
            {"block_id": "b1", "block_type": "verbal_explanation", "title": "讲解", "payload": {}},
            {
                "block_id": "b2",
                "block_type": "verbal_explanation",
                "title": "讲解2",
                "payload": {"未知键": "x"},
            },
        ]
    )

    draft = ExpertDraft.model_validate(normalize_expert_draft_payload(raw))

    assert draft.block_plan is not None
    assert draft.block_plan.blocks[0].payload is None
    assert draft.block_plan.blocks[1].payload is None


def test_expert_draft_budget_is_closed_to_four_keys() -> None:
    raw = _draft_with_blocks([])
    raw["block_plan"] = {
        "blocks": [],
        "budget": {"adaptive_used": 2, "adaptive_max": 6, "total": 5, "total_max": 9, "垃圾": 1},
    }

    draft = ExpertDraft.model_validate(normalize_expert_draft_payload(raw))

    assert draft.block_plan is not None
    assert draft.block_plan.budget.adaptive_used == 2
    assert draft.block_plan.budget.total_max == 9


def test_expert_draft_schema_is_fully_closed_for_strict_mode() -> None:
    schema = _normalize_schema_for_strict(ExpertDraft.model_json_schema(mode="validation"))
    assert _schema_has_free_form_object(schema) is False


class StreamingJsonClient:
    """Yields JSON in chunks to exercise generate_validated_json_stream."""

    def __init__(self, payload: object) -> None:
        self.calls: list[list[LLMMessage]] = []
        text = json.dumps(payload, ensure_ascii=False)
        # Split into arbitrary chunks to verify accumulation
        self.chunks = [text[i : i + 8] for i in range(0, len(text), 8)]

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> Iterator[str]:
        self.calls.append(messages)
        yield from self.chunks

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


class StreamingRepairClient:
    """First chunk stream is invalid; second streamed attempt repairs it."""

    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.responses = iter(
            [
                '{"intent": "teach", "confidence": 0.9}',
                '{"intent": "teach", "confidence": 0.9, "reason": "已修复"}',
            ]
        )

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> Iterator[str]:
        self.calls.append(messages)
        text = next(self.responses)
        # Yield one char at a time to stress chunk concatenation
        yield from (text[i : i + 1] for i in range(len(text)))

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calling is not used by this test")


def test_generate_validated_json_stream_accumulates_chunks_and_validates() -> None:
    client = StreamingJsonClient(
        {"intent": "teach", "confidence": 0.9, "reason": "用户希望系统学习"}
    )

    result = generate_validated_json_stream(
        client,
        messages=[LLMMessage(role="user", content="请分类")],
        temperature=0.0,
        agent="route",
        output_model=IntentResult,
    )

    assert result.intent == "teach"
    assert result.confidence == 0.9
    assert result.reason == "用户希望系统学习"
    assert len(client.calls) == 1


def test_generate_validated_json_stream_repairs_invalid_stream_once() -> None:
    client = StreamingRepairClient()

    result = generate_validated_json_stream(
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
