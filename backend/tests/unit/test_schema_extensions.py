"""TDD Phase 2 & 3: Tests for new state models and RAG tool."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.state import (
    AgentNode,
    ChatAnswer,
    IntentResult,
    StateDict,
    agent_output_json_schemas,
)
from backend.app.rag import retriever


class TestIntentResult:
    def test_valid_teach(self) -> None:
        r = IntentResult(intent="teach", confidence=0.95, reason="用户请求系统学习")
        assert r.intent == "teach"
        assert r.confidence == 0.95

    def test_valid_chat(self) -> None:
        r = IntentResult(intent="chat", confidence=0.8, reason="单点问答")
        assert r.intent == "chat"

    def test_valid_diagnose(self) -> None:
        r = IntentResult(intent="diagnose", confidence=0.7, reason="仅诊断")
        assert r.intent == "diagnose"

    def test_invalid_intent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IntentResult.model_validate({"intent": "invalid", "confidence": 0.5, "reason": ""})


class TestChatAnswer:
    def test_valid(self) -> None:
        a = ChatAnswer(content="新颖性是指发明不属于现有技术。", sources=["专利法第22条"])
        assert "新颖性" in a.content
        assert len(a.sources) == 1

    def test_empty_sources(self) -> None:
        a = ChatAnswer(content="回答", sources=[])
        assert a.sources == []

    def test_missing_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatAnswer.model_validate({"sources": []})


class TestAgentNodeExtension:
    def test_new_nodes_in_literal(self) -> None:
        assert "route" in AgentNode.__args__  # type: ignore[attr-defined]
        assert "tool_agent" in AgentNode.__args__  # type: ignore[attr-defined]
        assert "chat_answer" in AgentNode.__args__  # type: ignore[attr-defined]
        assert "expert_a_revise" in AgentNode.__args__  # type: ignore[attr-defined]
        assert "expert_b_revise" in AgentNode.__args__  # type: ignore[attr-defined]
        assert "revise_experts" in AgentNode.__args__  # type: ignore[attr-defined]

    def test_existing_nodes_preserved(self) -> None:
        for name in ("diagnosis", "planner", "expert_a", "expert_b", "judge", "feedback", "finalize"):
            assert name in AgentNode.__args__  # type: ignore[attr-defined]


class TestStateDictNewFields:
    def test_intent_field(self) -> None:
        s: StateDict = {
            "session_id": "s1",
            "user_input": "test",
            "events": [],
            "intent": "teach",
        }
        assert s["intent"] == "teach"

    def test_chat_answer_field(self) -> None:
        s: StateDict = {
            "session_id": "s1",
            "user_input": "test",
            "events": [],
            "chat_answer": {"content": "回答", "sources": []},
        }
        assert s["chat_answer"]["content"] == "回答"

    def test_tool_agent_answer_field(self) -> None:
        s: StateDict = {
            "session_id": "s1",
            "user_input": "test",
            "events": [],
            "tool_agent_answer": "可直接复用的回答",
        }
        assert s["tool_agent_answer"] == "可直接复用的回答"

    def test_both_new_fields(self) -> None:
        s: StateDict = {
            "session_id": "s1",
            "user_input": "test",
            "events": [],
            "intent": "chat",
            "chat_answer": {"content": "回答", "sources": ["法条1"]},
        }
        assert s["intent"] == "chat"
        assert s["chat_answer"]["content"] == "回答"


class TestAgentOutputJsonSchemas:
    def test_includes_route_schema(self) -> None:
        schemas = agent_output_json_schemas()
        assert "route" in schemas
        route_schema = schemas["route"]
        assert route_schema["type"] == "object"
        assert "intent" in route_schema["properties"]

    def test_includes_chat_answer_schema(self) -> None:
        schemas = agent_output_json_schemas()
        assert "chat_answer" in schemas


class TestRagRetrieve:
    def test_returns_list_of_chunks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeVector:
            def tolist(self) -> list[float]:
                return [0.1, 0.2, 0.3]

        class FakeModel:
            def encode(self, texts: list[str], normalize_embeddings: bool) -> list[FakeVector]:
                assert texts == ["新颖性"]
                assert normalize_embeddings is True
                return [FakeVector()]

        class FakeClient:
            def search(
                self,
                collection_name: str,
                data: list[list[float]],
                limit: int,
                output_fields: list[str],
            ) -> list[list[dict[str, object]]]:
                assert collection_name == retriever.COLLECTION_NAME
                assert data == [[0.1, 0.2, 0.3]]
                assert limit == 5
                assert output_fields == ["text", "source"]
                return [[{
                    "id": "chunk-1",
                    "distance": 0.9,
                    "entity": {"source": "专利法", "text": "新颖性条文"},
                }]]

        monkeypatch.setattr(retriever, "get_milvus_client", lambda: FakeClient())
        monkeypatch.setattr(retriever, "get_embedding_model", lambda: FakeModel())

        results = retriever.rag_retrieve("新颖性")
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].chunk_id == "chunk-1"
        assert results[0].text == "新颖性条文"
        assert results[0].metadata is not None
        assert results[0].metadata.retrieval_method == "vector"

    def test_accepts_top_k(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeVector:
            def tolist(self) -> list[float]:
                return [0.1]

        class FakeModel:
            def encode(self, texts: list[str], normalize_embeddings: bool) -> list[FakeVector]:
                return [FakeVector()]

        class FakeClient:
            def search(
                self,
                collection_name: str,
                data: list[list[float]],
                limit: int,
                output_fields: list[str],
            ) -> list[list[dict[str, object]]]:
                assert limit == 3
                return [[]]

        monkeypatch.setattr(retriever, "get_milvus_client", lambda: FakeClient())
        monkeypatch.setattr(retriever, "get_embedding_model", lambda: FakeModel())

        results = retriever.rag_retrieve("专利法", top_k=3)
        assert isinstance(results, list)

    def test_empty_query_returns_empty_list(self) -> None:
        results = retriever.rag_retrieve("")
        assert isinstance(results, list)

    def test_surfaces_vector_store_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def unavailable_client() -> None:
            raise RuntimeError("milvus unavailable")

        monkeypatch.setattr(retriever, "get_milvus_client", unavailable_client)

        with pytest.raises(retriever.RAGRetrievalError, match="milvus unavailable"):
            retriever.rag_retrieve("新颖性")
