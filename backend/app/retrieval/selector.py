from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Final, Literal, assert_never

from backend.app.rag import rag_retrieve
from backend.app.rag.retriever import RAGRetrievalError
from backend.app.retrieval.mock import mock_rag_retrieve
from backend.app.schemas.state import RetrievalChunk

RAG_RETRIEVAL_MODE_ENV: Final = "RAG_RETRIEVAL_MODE"
RAG_REAL_FALLBACK_TO_MOCK_ENV: Final = "RAG_REAL_FALLBACK_TO_MOCK"

_logger = logging.getLogger(__name__)

RetrievalMode = Literal["real", "mock"]


@dataclass(frozen=True, slots=True)
class RetrievalModeError(RuntimeError):
    mode: str

    def __str__(self) -> str:
        return f"Unsupported {RAG_RETRIEVAL_MODE_ENV}: {self.mode!r}. Use 'real' or 'mock'."


def _retrieval_mode() -> RetrievalMode:
    raw_mode = os.getenv(RAG_RETRIEVAL_MODE_ENV, "real").strip().lower()
    match raw_mode:
        case "" | "real":
            return "real"
        case "mock":
            return "mock"
        case unsupported:
            raise RetrievalModeError(mode=unsupported)


def _fallback_enabled() -> bool:
    return os.getenv(RAG_REAL_FALLBACK_TO_MOCK_ENV, "true").strip().lower() in {"", "1", "true", "yes", "on"}


def retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    mode = _retrieval_mode()
    match mode:
        case "real":
            try:
                return rag_retrieve(query=query, top_k=top_k)
            except RAGRetrievalError as exc:
                if not _fallback_enabled():
                    raise
                _logger.warning(
                    "Real RAG retrieval failed (%s); falling back to mock retriever.",
                    exc,
                )
                return mock_rag_retrieve(query=query, top_k=top_k)
        case "mock":
            return mock_rag_retrieve(query=query, top_k=top_k)
        case unreachable:
            assert_never(unreachable)
