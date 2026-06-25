from __future__ import annotations

import os
from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

COLLECTION_NAME = "law_knowledge_base"
VECTOR_DIM = 1024

_milvus_client = None
_embedding_model = None
_sentence_transformers = None


def _get_db_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "data", "milvus_lite.db")


def _lazy_import():
    global _sentence_transformers
    if _sentence_transformers is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformers = SentenceTransformer


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _lazy_import()
        SentenceTransformer = _sentence_transformers
        _embedding_model = SentenceTransformer('BAAI/bge-m3')
    return _embedding_model


def get_milvus_client():
    global _milvus_client
    if _milvus_client is None:
        from pymilvus import MilvusClient
        db_path = _get_db_path()
        _milvus_client = MilvusClient(db_path)
        _milvus_client.load_collection(COLLECTION_NAME)
    return _milvus_client


def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    if not query:
        return []

    try:
        client = get_milvus_client()
        model = get_embedding_model()

        query_vector = model.encode([query], normalize_embeddings=True)[0].tolist()

        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
            output_fields=["text", "source"]
        )

        chunks = []
        for i, res in enumerate(results[0]):
            entity = res['entity']
            source_file = entity.get('source', '')
            text = entity.get('text', '')

            chunks.append(RetrievalChunk(
                chunk_id=str(res['id']),
                source=source_file,
                citation=f"{source_file}: {text[:30]}...",
                text=text,
                score=res['distance'],
                metadata=RetrievalMetadata(
                    doc_type="law",
                    retrieval_method="vector",
                ),
            ))

        return chunks

    except Exception as e:
        print(f"[RAG] 检索失败: {e}")
        return []