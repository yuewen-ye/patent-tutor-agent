"""RAG retrieval tool — mock-first, real vector search when RAG_MOCK=0."""

from __future__ import annotations

import os

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

# ---- mock data ----

_MOCK_CHUNKS: list[RetrievalChunk] = [
    RetrievalChunk(
        chunk_id="mock-patent-law-art-22",
        source="中华人民共和国专利法",
        citation="第二十二条",
        text=(
            "授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。"
            "新颖性，是指该发明或者实用新型不属于现有技术；也没有任何单位或者个人"
            "就同样的发明或者实用新型在申请日以前向国务院专利行政部门提出过申请，"
            "并记载在申请日以后公布的专利申请文件或者公告的专利文件中。"
        ),
        score=0.95,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="专利法第二十二条",
            retrieval_method="manual",
        ),
    ),
    RetrievalChunk(
        chunk_id="mock-patent-law-art-25",
        source="中华人民共和国专利法",
        citation="第二十五条",
        text=(
            "对下列各项，不授予专利权：（一）科学发现；（二）智力活动的规则和方法；"
            "（三）疾病的诊断和治疗方法；（四）动物和植物品种；"
            "（五）原子核变换方法以及用原子核变换方法获得的物质；"
            "（六）对平面印刷品的图案、色彩或者二者的结合作出的主要起标识作用的设计。"
            "对前款第（四）项所列产品的生产方法，可以依照本法规定授予专利权。"
        ),
        score=0.90,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="专利法第二十五条",
            retrieval_method="manual",
        ),
    ),
    RetrievalChunk(
        chunk_id="mock-patent-law-art-29",
        source="中华人民共和国专利法",
        citation="第二十九条",
        text=(
            "申请人自发明或者实用新型在外国第一次提出专利申请之日起十二个月内，"
            "或者自外观设计在外国第一次提出专利申请之日起六个月内，又在中国就相同主题"
            "提出专利申请的，依照该外国同中国签订的协议或者共同参加的国际条约，"
            "或者依照相互承认优先权的原则，可以享有优先权。"
        ),
        score=0.85,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="专利法第二十九条",
            retrieval_method="manual",
        ),
    ),
]


def _is_mock_mode() -> bool:
    """Return True unless RAG_MOCK is explicitly set to '0'."""
    return os.getenv("RAG_MOCK", "1") != "0"


# ---- real (lazy) backend ----

DB_PATH = r"backend\app\rag\data\rag_chroma_db"

RAG_CONFIG = {
    "db_path": os.getenv("RAG_DB_PATH", DB_PATH),
    "collection_name": os.getenv("RAG_COLLECTION_NAME", "patent_law_kb"),
    "device": "cpu",
}

_embedding_model = None
_chroma_collection = None
_chromadb = None
_transformers = None
_torch = None


def _lazy_import() -> None:
    global _chromadb, _transformers, _torch
    if _chromadb is None:
        import chromadb
        from chromadb.config import Settings
        _chromadb = (chromadb, Settings)

    if _transformers is None:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        from transformers import AutoModel, AutoTokenizer
        _transformers = (AutoModel, AutoTokenizer)

    if _torch is None:
        import torch
        _torch = torch


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _lazy_import()
        AutoModel, AutoTokenizer = _transformers
        torch = _torch

        tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
        model = AutoModel.from_pretrained("BAAI/bge-m3").to(RAG_CONFIG["device"])
        model.eval()
        _embedding_model = (tokenizer, model)

    return _embedding_model


def get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is None:
        _lazy_import()
        chromadb, Settings = _chromadb

        db_path = os.path.abspath(RAG_CONFIG["db_path"])

        client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )

        _chroma_collection = client.get_collection(name=RAG_CONFIG["collection_name"])
    return _chroma_collection


def encode_query(query: str) -> list[float]:
    tokenizer, model = get_embedding_model()
    torch = _torch

    with torch.no_grad():
        inputs = tokenizer(
            [query], padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        inputs = {k: v.to(RAG_CONFIG["device"]) for k, v in inputs.items()}
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state[:, 0]
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    return embeddings.cpu().numpy().tolist()[0]


def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    """Retrieve relevant patent law chunks for *query*.

    In mock mode (the default) returns hardcoded chunks immediately
    without importing any heavy ML libraries.  Set ``RAG_MOCK=0`` to
    use the real ChromaDB + BGE-M3 vector-search backend.
    """
    if not query:
        return []

    if _is_mock_mode():
        return _MOCK_CHUNKS.copy()

    try:
        collection = get_chroma_collection()
        query_vector = encode_query(query)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        for i in range(len(results["documents"][0])):
            similarity = 1 - results["distances"][0][i]
            meta = results["metadatas"][0][i]

            chunks.append(RetrievalChunk(
                chunk_id=results["ids"][0][i],
                source="专利代理条例",
                citation=meta["chapter_title"],
                text=results["documents"][0][i],
                score=similarity,
                metadata=RetrievalMetadata(
                    doc_type="law",
                    law_article=meta["chapter_title"],
                    retrieval_method="vector",
                ),
            ))

        return chunks

    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return []
