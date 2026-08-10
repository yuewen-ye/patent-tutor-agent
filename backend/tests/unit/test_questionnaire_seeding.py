from __future__ import annotations

import pytest

from backend.app.learner_memory.bkt.model import compute_bkt_step, parameters_for_background
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore

pytestmark = pytest.mark.unit


def _expected_first_correct(parameters) -> float:
    _, posterior = compute_bkt_step(
        parameters.p_init,
        observed_correct=True,
        p_transit=min(1.0, parameters.p_transit * 1.5),
        p_guess=parameters.p_guess,
        p_slip=parameters.p_slip,
    )
    return posterior


def _expected_first_incorrect(parameters) -> float:
    _, posterior = compute_bkt_step(
        parameters.p_init,
        observed_correct=False,
        p_transit=min(1.0, parameters.p_transit * 1.5),
        p_guess=parameters.p_guess,
        p_slip=parameters.p_slip,
    )
    return posterior


def test_seeding_applies_leaf_observations_and_propagates_parent(
    tmp_path,
) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=[
            {"question_id": "Q1", "answer": "B"},  # correct -> patent-rights-nature
            {"question_id": "Q2", "answer": "A"},  # wrong -> non-patentable-subject
            {"question_id": "Q22", "answer": "C"},  # unmapped -> ignored
        ],
        education_background=None,
    )

    snapshot = store.mastery_snapshot("learner-1")
    parameters = parameters_for_background("未提供")
    expected = _expected_first_correct(parameters)

    assert snapshot["patent-rights-nature"]["observations"] == 1
    assert snapshot["patent-rights-nature"]["inferred"] is False
    assert snapshot["patent-rights-nature"]["pl"] == pytest.approx(expected, abs=1e-4)

    assert snapshot["non-patentable-subject"]["observations"] == 1
    assert snapshot["non-patentable-subject"]["inferred"] is False
    assert snapshot["non-patentable-subject"]["pl"] == pytest.approx(
        _expected_first_incorrect(parameters), abs=1e-4
    )

    # Parent of patent-rights-nature is patent-law-foundation (weighted average).
    parent = snapshot["patent-law-foundation"]
    assert parent["inferred"] is True
    assert parent["observations"] == 0
    assert parent["pl"] == pytest.approx((expected * 2 + 0.10 + 0.10) / 4, abs=1e-4)


def test_seeding_is_idempotent_for_the_same_course_session(tmp_path) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    responses = [{"question_id": "Q1", "answer": "B"}]

    first = store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=responses,
    )
    second = store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=responses,
    )

    assert first
    assert second == []
    assert store.mastery_snapshot("learner-1")["patent-rights-nature"]["observations"] == 1


def test_seeding_uses_education_background_priors(tmp_path) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=[{"question_id": "Q1", "answer": "B"}],
        education_background="法学背景+系统学过程序法",
    )

    parameters = parameters_for_background("法学背景+系统学过程序法")
    expected = _expected_first_correct(parameters)
    assert store.mastery_snapshot("learner-1")["patent-rights-nature"]["pl"] == pytest.approx(
        expected, abs=1e-4
    )


def test_seeding_ignores_unanswered_questions(tmp_path) -> None:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=[{"question_id": "Q11", "answer": "C"}],
    )

    snapshot = store.mastery_snapshot("learner-1")
    assert "civil-law-basics" in snapshot
    assert "patent-rights-nature" not in snapshot
