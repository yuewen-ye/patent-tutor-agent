"""RAG retriever — currently a mock, ready for real vector/hybrid retrieval."""

from __future__ import annotations

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

_MOCK_CHUNKS: list[RetrievalChunk] = [
    RetrievalChunk(
        chunk_id="patent-law-22",
        source="专利法",
        citation="《中华人民共和国专利法》第二十二条",
        text="授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。新颖性，是指该发明或者实用新型不属于现有技术；也没有任何单位或者个人就同样的发明或者实用新型在申请日以前向国务院专利行政部门提出过申请，并记载在申请日以后公布的专利申请文件或者公告的专利文件中。创造性，是指与现有技术相比，该发明具有突出的实质性特点和显著的进步，该实用新型具有实质性特点和进步。实用性，是指该发明或者实用新型能够制造或者使用，并且能够产生积极效果。",
        score=0.95,
        metadata=RetrievalMetadata(doc_type="law", law_article="22", retrieval_method="manual"),
    ),
    RetrievalChunk(
        chunk_id="patent-law-29",
        source="专利法",
        citation="《中华人民共和国专利法》第二十九条",
        text="申请人自发明或者实用新型在外国第一次提出专利申请之日起十二个月内，或者自外观设计在外国第一次提出专利申请之日起六个月内，又在中国就相同主题提出专利申请的，依照该外国同中国签订的协议或者共同参加的国际条约，或者依照相互承认优先权的原则，可以享有优先权。",
        score=0.90,
        metadata=RetrievalMetadata(doc_type="law", law_article="29", retrieval_method="manual"),
    ),
    RetrievalChunk(
        chunk_id="patent-law-25",
        source="专利法",
        citation="《中华人民共和国专利法》第二十五条",
        text="对下列各项，不授予专利权：（一）科学发现；（二）智力活动的规则和方法；（三）疾病的诊断和治疗方法；（四）动物和植物品种；（五）原子核变换方法以及用原子核变换方法获得的物质；（六）对平面印刷品的图案、色彩或者二者的结合作出的主要起标识作用的设计。对前款第（四）项所列产品的生产方法，可以依照本法规定授予专利权。",
        score=0.85,
        metadata=RetrievalMetadata(doc_type="law", law_article="25", retrieval_method="manual"),
    ),
]


def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    """Retrieve patent law knowledge chunks for a given query.

    Currently returns mock data. Future implementations will support
    BM25, vector, and hybrid retrieval via a real document store.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results to return.

    Returns:
        List of RetrievalChunk objects sorted by relevance.
    """
    # TODO: Replace with real retrieval (embedding + vector search / BM25 / hybrid)
    return _MOCK_CHUNKS[:top_k]
