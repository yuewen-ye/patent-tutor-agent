from __future__ import annotations

import json

import pytest

from backend.app.learner_store import SQLiteLearnerStore, migrate_json_memory


@pytest.mark.unit
def test_sqlite_store_persists_latest_profile_and_history(tmp_path) -> None:
    database = tmp_path / "learners.sqlite3"
    store = SQLiteLearnerStore(database)
    store.save_profile(
        learner_id="learner-1",
        session_id="session-1",
        profile={"knowledge_level": "beginner", "weak_points": ["新颖性"]},
    )
    store.save_history(
        learner_id="learner-1",
        session_id="session-1",
        event_type="course_completed",
        payload={"topic": "新颖性"},
    )

    snapshot = SQLiteLearnerStore(database).snapshot("learner-1")

    assert snapshot["latest_profile"]["session_id"] == "session-1"
    assert snapshot["latest_profile"]["weak_points"] == ["新颖性"]
    assert snapshot["history"][0]["event_type"] == "course_completed"


@pytest.mark.unit
def test_json_migration_is_idempotent(tmp_path) -> None:
    source = tmp_path / "learner_memory.json"
    source.write_text(
        json.dumps(
            {
                "version": 1,
                "items": [
                    {
                        "namespace": ["learners", "learner-1", "profile"],
                        "key": "profile-1",
                        "value": {
                            "session_id": "session-1",
                            "knowledge_level": "beginner",
                            "created_at": "2026-01-01T00:00:00+00:00",
                        },
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")

    assert migrate_json_memory(source, store) == 1
    assert migrate_json_memory(source, store) == 0
    assert len(store.snapshot("learner-1")["profiles"]) == 1


@pytest.mark.unit
def test_bkt_update_uses_configured_priors(tmp_path) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")

    correct = store.update_mastery("learner-1", "novelty", observed_correct=True)
    incorrect = store.update_mastery("learner-2", "novelty", observed_correct=False)

    assert correct == pytest.approx(0.7577, abs=0.001)
    assert incorrect == pytest.approx(0.2571, abs=0.001)
    assert store.mastery("learner-1")["novelty"] == pytest.approx(correct)
