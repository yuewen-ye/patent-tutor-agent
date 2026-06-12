"""Mock RAG retrieval node used until the knowledge base module is implemented."""

from __future__ import annotations

from typing import Any

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata, StateDict, completed_event


def retrieve_context_node(state: StateDict) -> dict[str, Any]:
    chunks = [
        RetrievalChunk(
            chunk_id="patent-law-22",
            source="专利法",
            citation="第二十二条",
            text="授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。",
            metadata=RetrievalMetadata(doc_type="law", law_article="第二十二条", retrieval_method="manual"),
        )
    ]
    return {
        "retrieval_context": [chunk.model_dump() for chunk in chunks],
        "events": [completed_event("retrieve_context", "attached mock patent law context")],
    }
