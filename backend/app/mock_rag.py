from __future__ import annotations

from typing import Final

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata


_MOCK_CHUNKS: Final = [
    RetrievalChunk(
        chunk_id="mock-patent-law-22",
        source="中华人民共和国专利法",
        citation="专利法第二十二条",
        text=(
            "授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。"
            "新颖性，是指该发明或者实用新型不属于现有技术。"
        ),
        score=1.0,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="第二十二条",
            retrieval_method="manual",
        ),
    ),
    RetrievalChunk(
        chunk_id="mock-patent-law-25",
        source="中华人民共和国专利法",
        citation="专利法第二十五条",
        text="对科学发现、智力活动的规则和方法、疾病的诊断和治疗方法等，不授予专利权。",
        score=0.8,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="第二十五条",
            retrieval_method="manual",
        ),
    ),
    RetrievalChunk(
        chunk_id="mock-patent-law-29",
        source="中华人民共和国专利法",
        citation="专利法第二十九条",
        text="申请人自发明或者实用新型在外国第一次提出专利申请之日起十二个月内享有优先权。",
        score=0.7,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="第二十九条",
            retrieval_method="manual",
        ),
    ),
]


def mock_rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    if not query:
        return []
    return list(_MOCK_CHUNKS[:top_k])
