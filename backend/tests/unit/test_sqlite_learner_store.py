from __future__ import annotations

import json

import pytest

from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore, migrate_json_memory


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

    assert correct == pytest.approx(0.8710, abs=0.001)
    assert incorrect == pytest.approx(0.0300, abs=0.001)
    assert store.mastery("learner-1")["novelty"] == pytest.approx(correct)


@pytest.mark.unit
def test_diagnostic_session_and_snapshot_are_durable(tmp_path) -> None:
    database = tmp_path / "learners.sqlite3"
    store = SQLiteLearnerStore(database)
    payload = {
        "diagnostic_session_id": "diagnostic-1",
        "learner_id": "learner-1",
        "status": "completed",
        "learning_goal": "学习新颖性",
        "education_background": "理工背景+有研发经验",
        "created_at": "2026-07-25T00:00:00+00:00",
    }

    store.save_diagnostic_session(payload=payload)
    store.complete_diagnostic_session(
        diagnostic_session_id="diagnostic-1",
        learner_id="learner-1",
        diagnostic_payload={
            "knowledge": {
                "novelty": {
                    "pl": 0.72,
                    "observations": 2,
                    "inferred": False,
                }
            }
        },
    )

    assert SQLiteLearnerStore(database).load_diagnostic_session("diagnostic-1") == payload
    assert SQLiteLearnerStore(database).mastery("learner-1")["novelty"] == pytest.approx(0.72)


@pytest.mark.unit
def test_direct_feedback_observation_replaces_inferred_mastery_state(tmp_path) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.complete_diagnostic_session(
        diagnostic_session_id="diagnostic-1",
        learner_id="learner-1",
        diagnostic_payload={
            "knowledge": {
                "novelty": {
                    "pl": 0.35,
                    "observations": 0,
                    "inferred": True,
                }
            }
        },
    )

    assert store.mastery_snapshot("learner-1")["novelty"]["inferred"] is True

    store.update_mastery(
        "learner-1",
        "novelty",
        observed_correct=True,
        p_init=0.15,
        p_transit=0.30,
    )
    updated = store.mastery_snapshot("learner-1")["novelty"]

    assert updated["observations"] == 1
    assert updated["inferred"] is False
    assert updated["pl"] > 0.35
