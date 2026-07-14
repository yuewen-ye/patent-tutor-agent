from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.learner_memory.memory import FileLearnerMemoryStore, learner_namespace

pytestmark = pytest.mark.unit


def test_file_learner_memory_store_persists_profile_and_history_between_instances(
    tmp_path: Path,
) -> None:
    # Given: learner memories written by one process-local store instance.
    store_path = tmp_path / "learner-memory.json"
    store = FileLearnerMemoryStore(store_path)
    store.put(
        learner_namespace("learner-api", "profile"),
        "profile-1",
        {
            "session_id": "session-1",
            "learning_goal": "学习专利新颖性",
            "weak_points": ["现有技术概念薄弱"],
            "created_at": "2026-06-24T01:00:00+00:00",
        },
    )
    store.put(
        learner_namespace("learner-api", "history"),
        "history-1",
        {
            "session_id": "session-1",
            "topic": "学习专利新颖性",
            "knowledge_points": ["新颖性基础"],
            "created_at": "2026-06-24T01:00:01+00:00",
        },
    )

    # When: a fresh store instance opens the same file.
    reloaded = FileLearnerMemoryStore(store_path)

    # Then: profile and history entries are available through LangGraph-style search.
    profiles = reloaded.search(learner_namespace("learner-api", "profile"), limit=5)
    histories = reloaded.search(learner_namespace("learner-api", "history"), limit=5)
    assert [item.value["weak_points"] for item in profiles] == [["现有技术概念薄弱"]]
    assert [item.value["knowledge_points"] for item in histories] == [["新颖性基础"]]
