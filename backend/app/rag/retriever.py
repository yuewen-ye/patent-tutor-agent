from __future__ import annotations

import atexit
import importlib
import os
import shutil
import time
from pathlib import Path
from threading import Lock
from typing import Any, Final

from backend.app.schemas.state import RetrievalChunk, RetrievalMetadata

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

COLLECTION_NAME: Final = "law_knowledge_base"
MODEL_NAME: Final = "BAAI/bge-m3"

_milvus_client = None
_embedding_model = None
_sentence_transformers = None
_MILVUS_CLIENT_LOCK: Final = Lock()
_EMBEDDING_MODEL_LOCK: Final = Lock()


class RAGRetrievalError(RuntimeError):
    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return f"RAG retrieval failed at {self.stage}: {self.detail}"


def _get_db_path() -> str:
    return str(Path(__file__).resolve().parent / "data" / "milvus_lite.db")


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
                    _embedding_model = SentenceTransformer(MODEL_NAME)
                except (OSError, RuntimeError) as exc:
                    raise RAGRetrievalError(stage="embedding_model", detail=str(exc)) from exc
    return _embedding_model


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
        query_vector = model.encode([query], normalize_embeddings=True)[0].tolist()
    except RAGRetrievalError:
        raise
    except (AttributeError, IndexError, RuntimeError, ValueError) as exc:
        raise RAGRetrievalError(stage="embedding_encode", detail=str(exc)) from exc

    milvus_error = _load_exception_class(
        "pymilvus.exceptions", "MilvusException", "milvus_import"
    )
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
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

        return chunks
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise RAGRetrievalError(stage="result_parse", detail=str(exc)) from exc


def _cleanup_runtime_files() -> None:
    db_path = Path(_get_db_path())
    if not db_path.exists():
        return
    time.sleep(1)
    lock_file = db_path / "LOCK"
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception:
            pass
    for wal_dir in db_path.rglob("wal"):
        if wal_dir.is_dir():
            try:
                shutil.rmtree(wal_dir)
            except Exception:
                pass
    for prev_file in db_path.rglob("*.prev"):
        try:
            prev_file.unlink()
        except Exception:
            pass


atexit.register(_cleanup_runtime_files)
