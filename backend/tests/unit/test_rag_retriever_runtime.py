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


def test_embedding_model_uses_configured_local_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    class FakeSentenceTransformer:
        def __init__(self, source: str, *, local_files_only: bool = False) -> None:
            calls.append((source, local_files_only))

    monkeypatch.setattr(retriever, "_embedding_model", None)
    monkeypatch.setattr(retriever, "_sentence_transformers", FakeSentenceTransformer)
    monkeypatch.setenv(retriever.EMBEDDING_MODEL_PATH_ENV, "D:/models/bge-m3")

    model = retriever.get_embedding_model()

    assert isinstance(model, FakeSentenceTransformer)
    assert calls == [("D:/models/bge-m3", True)]


def _make_chunk(chunk_id: str, source: str) -> retriever.RetrievalChunk:
    return retriever.RetrievalChunk(
        chunk_id=chunk_id,
        source=source,
        citation=f"{source}: text",
        text="text",
        score=0.5,
        metadata=None,
    )


def test_law_fallback_swaps_pool_chunks_into_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(retriever.LAW_MIN_CHUNKS_ENV, "2")
    chunks = [
        _make_chunk(str(i), "专利法律知识详细解读.txt") for i in range(6)
    ] + [
        _make_chunk("law1", "中华人民共和国专利法.txt"),
        _make_chunk("law2", "专利代理条例.txt"),
    ]
    monkeypatch.setattr(retriever, "_search_law_fallback", lambda *a: [])

    result = retriever._apply_law_fallback(chunks, [0.1, 0.2], top_k=5)

    assert len(result) == 5
    law_in_result = {
        chunk.source for chunk in result if chunk.source in retriever._law_source_set()
    }
    assert law_in_result == {"中华人民共和国专利法.txt", "专利代理条例.txt"}


def test_law_fallback_triggers_directed_search_when_pool_lacks_law(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(retriever.LAW_MIN_CHUNKS_ENV, "2")
    chunks = [_make_chunk(str(i), "2026相关法600题.txt") for i in range(8)]
    extra = [
        _make_chunk("law1", "中华人民共和国专利法.txt"),
        _make_chunk("law2", "专利代理条例.txt"),
    ]
    monkeypatch.setattr(retriever, "_search_law_fallback", lambda *a: extra)

    result = retriever._apply_law_fallback(chunks, [0.1], top_k=5)

    assert len(result) == 5
    law_ids = {
        chunk.chunk_id for chunk in result if chunk.source in retriever._law_source_set()
    }
    assert law_ids == {"law1", "law2"}


def test_law_fallback_disabled_by_zero_min_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(retriever.LAW_MIN_CHUNKS_ENV, "0")
    chunks = [_make_chunk(str(i), "2026相关法600题.txt") for i in range(8)]

    result = retriever._apply_law_fallback(chunks, [0.1], top_k=5)

    assert [chunk.chunk_id for chunk in result] == [str(i) for i in range(5)]


def test_law_fallback_keeps_result_when_law_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(retriever.LAW_MIN_CHUNKS_ENV, "1")
    chunks = [_make_chunk("law1", "中华人民共和国专利法实施细则.txt")] + [
        _make_chunk(str(i), "专利法律知识同步训练.txt") for i in range(7)
    ]

    result = retriever._apply_law_fallback(chunks, [0.1], top_k=5)

    assert result[0].chunk_id == "law1"
    assert len(result) == 5
