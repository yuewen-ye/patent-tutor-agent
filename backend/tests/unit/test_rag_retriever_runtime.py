from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.rag import retriever

pytestmark = pytest.mark.unit


def test_rag_error_allows_traceback_assignment() -> None:
    error = retriever.RAGRetrievalError(stage="milvus_client", detail="locked")

    try:
        raise RuntimeError("source")
    except RuntimeError as exc:
        error.__traceback__ = exc.__traceback__

    assert str(error) == "RAG retrieval failed at milvus_client: locked"
    assert error.__traceback__ is not None


def test_milvus_client_is_initialized_once_under_parallel_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(retriever, "_milvus_client", None)
    init_count = 0

    class FakeMilvusException(Exception):
        pass

    class FakeMilvusClient:
        def __init__(self, db_path: str) -> None:
            nonlocal init_count
            init_count += 1
            self.db_path = db_path
            self.loaded_collections: list[str] = []

        def load_collection(self, collection_name: str) -> None:
            self.loaded_collections.append(collection_name)

    def fake_load_class(module_name: str, class_name: str, stage: str) -> type[FakeMilvusClient]:
        assert (module_name, class_name, stage) == ("pymilvus", "MilvusClient", "milvus_import")
        return FakeMilvusClient

    monkeypatch.setattr(retriever, "_load_exception_class", lambda *_args: FakeMilvusException)
    monkeypatch.setattr(retriever, "_load_class", fake_load_class)
    monkeypatch.setattr(retriever, "_get_db_path", lambda: "/tmp/milvus-lite-test.db")

    with ThreadPoolExecutor(max_workers=2) as executor:
        clients = list(executor.map(lambda _index: retriever.get_milvus_client(), range(2)))

    assert clients[0] is clients[1]
    assert init_count == 1
    assert clients[0].loaded_collections == [retriever.COLLECTION_NAME]


def test_embedding_model_uses_local_cache_before_mirror_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeSentenceTransformer:
        def __init__(self, source: str, *, local_files_only: bool = False) -> None:
            calls.append((source, local_files_only))
            if local_files_only:
                raise OSError("model is not cached")

    monkeypatch.delenv(retriever.EMBEDDING_MODEL_PATH_ENV, raising=False)

    model = retriever._load_embedding_model(FakeSentenceTransformer)

    assert isinstance(model, FakeSentenceTransformer)
    assert calls == [
        (retriever.MODEL_NAME, True),
        (retriever.MODEL_NAME, False),
    ]


def test_embedding_model_prefers_configured_local_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeSentenceTransformer:
        def __init__(self, source: str, *, local_files_only: bool = False) -> None:
            calls.append((source, local_files_only))

    monkeypatch.setenv(retriever.EMBEDDING_MODEL_PATH_ENV, "D:/models/bge-m3")

    model = retriever._load_embedding_model(FakeSentenceTransformer)

    assert isinstance(model, FakeSentenceTransformer)
    assert calls == [("D:/models/bge-m3", True)]
