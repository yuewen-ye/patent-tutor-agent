"""RAG module — patent law knowledge retrieval."""

from backend.app.rag.retriever import RAGRetrievalError, rag_retrieve

__all__ = ["RAGRetrievalError", "rag_retrieve"]
