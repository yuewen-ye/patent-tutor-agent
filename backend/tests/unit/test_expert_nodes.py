import pytest

import backend.app.agents.rag_tools as rag_tools
from backend.app.agents.expert_b.node import build_expert_b_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolCall, ToolDefinition
from backend.app.schemas.state import RetrievalChunk

pytestmark = pytest.mark.unit


class CamelCaseExpertLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append("generate_json")
        return {
            "expert": "expert_b",
            "style": "vivid_teaching",
            "knowledgePoints": ["新颖性"],
            "legalBasis": ["专利法第二十二条"],
            "teachingContent": "用案例解释新颖性。",
            "risks": [],
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append("generate_with_tools")
        return LLMResponseWithTools(content=None, tool_calls=[])


class ToolCallingExpertLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append("generate_json")
        return {
            "expert": "expert_b",
            "style": "vivid_teaching",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "结合检索结果解释新颖性。",
            "risks": [],
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append("generate_with_tools")
        return LLMResponseWithTools(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="rag_retrieve",
                    arguments={"query": "专利法 新颖性", "top_k": 1},
                )
            ],
        )


def test_expert_b_accepts_known_provider_camel_case_keys_as_contract_fields() -> None:
    client = CamelCaseExpertLLMClient()
    node = build_expert_b_node(client)

    result = node(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
        }
    )

    draft = result["expert_b_draft"]
    assert draft["knowledge_points"] == ["新颖性"]
    assert draft["legal_basis"] == ["专利法第二十二条"]
    assert draft["teaching_content"] == "用案例解释新颖性。"
    assert "knowledgePoints" not in draft
    assert client.calls == ["generate_with_tools", "generate_json"]


def test_expert_b_runs_requested_rag_tool_and_returns_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
        assert query == "专利法 新颖性"
        assert top_k == 1
        return [
            RetrievalChunk(
                chunk_id="patent-law-22",
                source="patent_law",
                citation="专利法第二十二条",
                text="新颖性，是指该发明或者实用新型不属于现有技术。",
                score=0.9,
            )
        ]

    monkeypatch.setattr(rag_tools, "retrieve_context", fake_retrieve_context)
    client = ToolCallingExpertLLMClient()
    node = build_expert_b_node(client)

    result = node(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
        }
    )

    assert client.calls == ["generate_with_tools", "generate_json"]
    assert result["retrieval_context"][0]["citation"] == "专利法第二十二条"
    assert result["expert_b_draft"]["teaching_content"] == "结合检索结果解释新颖性。"
