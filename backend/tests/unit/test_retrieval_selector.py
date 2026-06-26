from __future__ import annotations

import pytest

from backend.app import retrieval_selector
from backend.app.schemas.state import RetrievalChunk


pytestmark = pytest.mark.unit


def test_default_mode_uses_real_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_real(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
        calls.append((query, top_k))
        return []

    monkeypatch.delenv("RAG_RETRIEVAL_MODE", raising=False)
    monkeypatch.setattr(retrieval_selector, "rag_retrieve", fake_real)

    assert retrieval_selector.retrieve_context("新颖性", top_k=2) == []
    assert calls == [("新颖性", 2)]


def test_mock_mode_uses_mock_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")

    chunks = retrieval_selector.retrieve_context("新颖性", top_k=2)

    assert len(chunks) == 2
    assert all(chunk.metadata is not None for chunk in chunks)
    assert {chunk.metadata.retrieval_method for chunk in chunks if chunk.metadata} == {"manual"}


def test_invalid_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "manual")

    with pytest.raises(retrieval_selector.RetrievalModeError):
        retrieval_selector.retrieve_context("新颖性")
