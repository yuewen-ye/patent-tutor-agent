from __future__ import annotations

import importlib
import os
from pathlib import Path
from threading import Lock
from typing import Any, Final

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

try:
    import milvus_lite.storage.manifest as _manifest
    if not getattr(_manifest, '_patched_rename', False):
        _manifest.os.rename = _manifest.os.replace
        _manifest._patched_rename = True
except ImportError:
    pass

COLLECTION_NAME: Final = "law_knowledge_base"
MODEL_NAME: Final = "BAAI/bge-m3"
RERANKER_MODEL_NAME: Final = "BAAI/bge-reranker-v2-m3"
EMBEDDING_MODEL_PATH_ENV: Final = "RAG_EMBEDDING_MODEL_PATH"
RERANKER_MODEL_PATH_ENV: Final = "RAG_RERANKER_MODEL_PATH"
RERANK_ENABLED_ENV: Final = "RAG_RERANK_ENABLED"
RERANK_CANDIDATE_MULTIPLIER: Final = 3
MILVUS_DB_PATH_ENV: Final = "MILVUS_DB_PATH"
LAW_SOURCES_ENV: Final = "RAG_LAW_SOURCES"
LAW_MIN_CHUNKS_ENV: Final = "RAG_LAW_MIN_CHUNKS"
DEFAULT_LAW_SOURCES: Final = (
    "中华人民共和国专利法.txt",
    "中华人民共和国专利法实施细则.txt",
    "专利代理条例.txt",
)

_milvus_client = None
_embedding_model = None
_reranker_model = None
_sentence_transformers = None
_MILVUS_CLIENT_LOCK: Final = Lock()
_EMBEDDING_MODEL_LOCK: Final = Lock()
_RERANKER_MODEL_LOCK: Final = Lock()
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
    configured = os.getenv(MILVUS_DB_PATH_ENV, "").strip()
    if configured:
        return configured
    return str(Path(__file__).resolve().parent / "data" / "milvus_lite.db")


def _cleanup_stale_lock(db_path: str) -> None:
    lock_path = os.path.join(db_path, "LOCK")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass


def _fix_manifest_paths(db_path: str) -> None:
    import json
    manifest_path = os.path.join(db_path, "collections", COLLECTION_NAME, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        changed = False
        for part in manifest.get("partitions", {}).values():
            data_files = part.get("data_files", [])
            fixed = [p.replace("\\", "/") for p in data_files]
            if fixed != data_files:
                part["data_files"] = fixed
                changed = True
        if changed:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
    except (OSError, ValueError, KeyError):
        pass


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
                    _fix_manifest_paths(db_path)
                    _milvus_client = MilvusClient(db_path)
                    _milvus_client.load_collection(COLLECTION_NAME)
                except RAGRetrievalError:
                    raise
                except milvus_error as exc:
                    raise RAGRetrievalError(stage="milvus_client", detail=str(exc)) from exc
                except (OSError, RuntimeError) as exc:
                    raise RAGRetrievalError(stage="milvus_client", detail=str(exc)) from exc
    return _milvus_client


def _law_source_set() -> frozenset[str]:
    raw = os.getenv(LAW_SOURCES_ENV, "").strip()
    if not raw:
        return frozenset(DEFAULT_LAW_SOURCES)
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _law_min_chunks() -> int:
    raw = os.getenv(LAW_MIN_CHUNKS_ENV, "2").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 2


def _search_law_fallback(
    query_vector: list[float], law_sources: frozenset[str], limit: int
) -> list[RetrievalChunk]:
    if limit <= 0 or not law_sources:
        return []
    client = get_milvus_client()
    quoted = ", ".join(f'"{source}"' for source in sorted(law_sources))
    milvus_error = _load_exception_class(
        "pymilvus.exceptions", "MilvusException", "milvus_import"
    )
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=limit,
            filter=f"source in [{quoted}]",
            output_fields=["text", "source"],
        )
    except (RAGRetrievalError, RuntimeError):
        return []
    except milvus_error:
        return []
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
    return chunks


def _apply_law_fallback(
    chunks: list[RetrievalChunk], query_vector: list[float], top_k: int
) -> list[RetrievalChunk]:
    selected = chunks[:top_k]
    law_sources = _law_source_set()
    min_law = min(_law_min_chunks(), top_k)
    if min_law <= 0 or not law_sources or not selected:
        return selected
    law_count = sum(1 for chunk in selected if chunk.source in law_sources)
    need = min_law - law_count
    if need <= 0:
        return selected
    additions = [chunk for chunk in chunks[top_k:] if chunk.source in law_sources][:need]
    if len(additions) < need:
        extras = _search_law_fallback(query_vector, law_sources, need - len(additions) + 2)
        seen = {chunk.chunk_id for chunk in chunks}
        additions.extend(extra for extra in extras if extra.chunk_id not in seen)
    replaced = 0
    for index in range(len(selected) - 1, -1, -1):
        if replaced >= need or not additions:
            break
        if selected[index].source not in law_sources:
            selected[index] = additions.pop(0)
            replaced += 1
    return selected


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
        with _EMBEDDING_ENCODE_LOCK:
            query_vector = model.encode([query], normalize_embeddings=True)[0].tolist()
    except RAGRetrievalError:
        raise
    except (AttributeError, IndexError, RuntimeError, ValueError) as exc:
        raise RAGRetrievalError(stage="embedding_encode", detail=str(exc)) from exc

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
            chunks.sort(key=lambda c: c.rerank_score or 0, reverse=True)
        except (AttributeError, RuntimeError, ValueError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Rerank failed, returning vector results unsorted: %s", exc
            )

    return _apply_law_fallback(chunks, query_vector, top_k)
