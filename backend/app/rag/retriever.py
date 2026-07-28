from __future__ import annotations

import importlib
import os
from pathlib import Path
from threading import Lock
from typing import Any, Final

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

# Respect existing HF_ENDPOINT from .env, default to mirror for China users
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

COLLECTION_NAME: Final = "law_knowledge_base"
MODEL_NAME: Final = "BAAI/bge-m3"
RERANKER_MODEL_NAME: Final = "BAAI/bge-reranker-v2-m3"
EMBEDDING_MODEL_PATH_ENV: Final = "RAG_EMBEDDING_MODEL_PATH"
RERANKER_MODEL_PATH_ENV: Final = "RAG_RERANKER_MODEL_PATH"
RERANK_ENABLED_ENV: Final = "RAG_RERANK_ENABLED"
RERANK_CANDIDATE_MULTIPLIER: Final = 3

_milvus_client = None
_embedding_model = None
_reranker_model = None
_sentence_transformers = None
_MILVUS_CLIENT_LOCK: Final = Lock()
_EMBEDDING_MODEL_LOCK: Final = Lock()
_RERANKER_MODEL_LOCK: Final = Lock()
# 串行化编码调用：bge-m3 的 FastTokenizer 非线程安全，expert_a/expert_b 在 LangGraph
# 并发执行时会同时调用 rag_retrieve → model.encode 抢同一把 tokenizer 锁 → "Already borrowed"。
_EMBEDDING_ENCODE_LOCK: Final = Lock()
_RERANKER_PREDICT_LOCK: Final = Lock()


class RAGRetrievalError(RuntimeError):
    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return f"RAG retrieval failed at {self.stage}: {self.detail}"


def _get_db_path() -> str:
    return str(Path(__file__).resolve().parent / "data" / "milvus_lite.db")


def _cleanup_stale_lock(db_path: str) -> None:
    """Remove stale Milvus Lite LOCK file before connecting.

    Milvus Lite creates a LOCK file to prevent concurrent access.
    If a process crashes without releasing it, the lock becomes stale
    and the next connection fails with DataDirLockedError.
    Removing the LOCK file before connecting is safe because:
    - This runs inside _MILVUS_CLIENT_LOCK, so no concurrent calls within this process.
    - The LOCK file is re-created by Milvus on connect if needed.
    """
    lock_path = os.path.join(db_path, "LOCK")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass  # Best-effort; if removal fails, MilvusClient will raise the real error


def _load_class(module_name: str, class_name: str, stage: str) -> type[Any]:
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise RAGRetrievalError(stage=stage, detail=str(exc)) from exc

    try:
        loaded = getattr(module, class_name)
    except AttributeError as exc:
        raise RAGRetrievalError(stage=stage, detail=f"{module_name}.{class_name} missing") from exc

    if not isinstance(loaded, type):
        raise RAGRetrievalError(stage=stage, detail=f"{module_name}.{class_name} is not a class")
    return loaded


def _load_exception_class(module_name: str, class_name: str, stage: str) -> type[BaseException]:
    loaded = _load_class(module_name, class_name, stage)
    if not issubclass(loaded, BaseException):
        raise RAGRetrievalError(stage=stage, detail=f"{module_name}.{class_name} is not an exception")
    return loaded


def _lazy_import() -> None:
    global _sentence_transformers
    if _sentence_transformers is None:
        _sentence_transformers = _load_class(
            "sentence_transformers", "SentenceTransformer", "embedding_import"
        )


def _reranker_enabled() -> bool:
    val = os.getenv(RERANK_ENABLED_ENV, "true").strip().lower()
    return val in ("", "true", "1", "yes", "on")


def get_embedding_model() -> Any:
    global _embedding_model
    if _embedding_model is None:
        with _EMBEDDING_MODEL_LOCK:
            if _embedding_model is None:
                _lazy_import()
                SentenceTransformer = _sentence_transformers
                if SentenceTransformer is None:
                    raise RAGRetrievalError(
                        stage="embedding_import",
                        detail="SentenceTransformer missing",
                    )
                try:
                    local_model_path = os.getenv(EMBEDDING_MODEL_PATH_ENV, "").strip()
                    if local_model_path:
                        _embedding_model = SentenceTransformer(
                            local_model_path,
                            local_files_only=True,
                        )
                    else:
                        _embedding_model = SentenceTransformer(MODEL_NAME)
                except (OSError, RuntimeError) as exc:
                    raise RAGRetrievalError(stage="embedding_model", detail=str(exc)) from exc
    return _embedding_model


def get_reranker_model() -> Any | None:
    """Lazy-load bge-reranker-v2-m3 as CrossEncoder. Returns None if disabled or load fails."""
    global _reranker_model
    if not _reranker_enabled():
        return None
    if _reranker_model is None:
        with _RERANKER_MODEL_LOCK:
            if _reranker_model is None:
                try:
                    _lazy_import()
                    CrossEncoder = _load_class(
                        "sentence_transformers", "CrossEncoder", "reranker_import"
                    )
                    local_model_path = os.getenv(RERANKER_MODEL_PATH_ENV, "").strip()
                    if local_model_path:
                        _reranker_model = CrossEncoder(local_model_path)
                    else:
                        _reranker_model = CrossEncoder(RERANKER_MODEL_NAME)
                except (OSError, RuntimeError, ImportError, RAGRetrievalError) as exc:
                    # Reranker is optional — degrade gracefully to vector-only
                    import logging
                    logging.getLogger(__name__).warning(
                        "Reranker model load failed, falling back to vector-only: %s", exc
                    )
                    _reranker_model = None
    return _reranker_model


def get_milvus_client() -> Any:
    global _milvus_client
    if _milvus_client is None:
        with _MILVUS_CLIENT_LOCK:
            if _milvus_client is None:
                milvus_error = _load_exception_class(
                    "pymilvus.exceptions", "MilvusException", "milvus_import"
                )
                try:
                    MilvusClient = _load_class("pymilvus", "MilvusClient", "milvus_import")
                    db_path = _get_db_path()
                    _cleanup_stale_lock(db_path)
                    _milvus_client = MilvusClient(db_path)
                    _milvus_client.load_collection(COLLECTION_NAME)
                except RAGRetrievalError:
                    raise
                except milvus_error as exc:
                    raise RAGRetrievalError(stage="milvus_client", detail=str(exc)) from exc
                except (OSError, RuntimeError) as exc:
                    raise RAGRetrievalError(stage="milvus_client", detail=str(exc)) from exc
    return _milvus_client


def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    if not query:
        return []

    try:
        client = get_milvus_client()
        model = get_embedding_model()
    except RAGRetrievalError:
        raise
    except RuntimeError as exc:
        raise RAGRetrievalError(stage="setup", detail=str(exc)) from exc

    try:
        # 加锁串行化：规避并发 encode 时 bge-m3 tokenizer "Already borrowed"
        with _EMBEDDING_ENCODE_LOCK:
            query_vector = model.encode([query], normalize_embeddings=True)[0].tolist()
    except RAGRetrievalError:
        raise
    except (AttributeError, IndexError, RuntimeError, ValueError) as exc:
        raise RAGRetrievalError(stage="embedding_encode", detail=str(exc)) from exc

    # Over-retrieve for reranking; fall back to top_k if reranker unavailable
    reranker = get_reranker_model()
    search_limit = min(top_k * RERANK_CANDIDATE_MULTIPLIER, 20) if reranker else top_k

    milvus_error = _load_exception_class(
        "pymilvus.exceptions", "MilvusException", "milvus_import"
    )
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=search_limit,
            output_fields=["text", "source"],
        )
    except RAGRetrievalError:
        raise
    except milvus_error as exc:
        raise RAGRetrievalError(stage="vector_search", detail=str(exc)) from exc
    except RuntimeError as exc:
        raise RAGRetrievalError(stage="vector_search", detail=str(exc)) from exc

    try:
        chunks: list[RetrievalChunk] = []
        for res in results[0]:
            entity = res["entity"]
            source_file = entity.get("source", "")
            text = entity.get("text", "")

            chunks.append(
                RetrievalChunk(
                    chunk_id=str(res["id"]),
                    source=source_file,
                    citation=f"{source_file}: {text[:30]}...",
                    text=text,
                    score=res["distance"],
                    metadata=RetrievalMetadata(
                        doc_type="law",
                        retrieval_method="vector",
                    ),
                )
            )
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise RAGRetrievalError(stage="result_parse", detail=str(exc)) from exc

    # Rerank with cross-encoder
    if reranker is not None and len(chunks) > 1:
        try:
            with _RERANKER_PREDICT_LOCK:
                pairs = [(query, chunk.text) for chunk in chunks]
                rerank_scores = reranker.predict(pairs)

            for chunk, rs in zip(chunks, rerank_scores):
                chunk.rerank_score = float(rs)
                chunk.metadata = RetrievalMetadata(
                    doc_type="law",
                    retrieval_method="hybrid",
                )
            # Sort by rerank_score descending
            chunks.sort(key=lambda c: c.rerank_score or 0, reverse=True)
        except (AttributeError, RuntimeError, ValueError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Rerank failed, returning vector results unsorted: %s", exc
            )

    return chunks[:top_k]
