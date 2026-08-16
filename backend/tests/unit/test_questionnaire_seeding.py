from __future__ import annotations

import pytest

from backend.app.learner_memory.bkt.model import parameters_for_background
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore

pytestmark = pytest.mark.unit


def test_seeding_writes_weak_inferred_prior_without_observations(tmp_path) -> None:
    """问卷是自陈先验：只写 inferred 弱先验（pl=p_init、obs=0），不产生真实观测。

    只有真实练习/诊断作答才能累加 observations（见 update_mastery），
    避免"零作答却 seeding 出 pl≈1.0 / obs≥2"的虚高掌握度。
    """
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=[
            {"question_id": "Q1", "answer": "B"},  # 命中 patent-rights-nature
            {"question_id": "Q2", "answer": "A"},  # 命中 non-patentable-subject
            {"question_id": "Q22", "answer": "C"},  # unmapped -> ignored
        ],
        education_background=None,
    )

    snapshot = store.mastery_snapshot("learner-1")
    parameters = parameters_for_background("未提供")

    # 叶子节点：弱先验 pl=p_init，inferred=True，不写 observations
    assert snapshot["patent-rights-nature"]["observations"] == 0
    assert snapshot["patent-rights-nature"]["inferred"] is True
    assert snapshot["patent-rights-nature"]["pl"] == pytest.approx(
        parameters.p_init, abs=1e-4
    )

    assert snapshot["non-patentable-subject"]["observations"] == 0
    assert snapshot["non-patentable-subject"]["inferred"] is True
    assert snapshot["non-patentable-subject"]["pl"] == pytest.approx(
        parameters.p_init, abs=1e-4
    )

    # Parent of patent-rights-nature is patent-law-foundation (weighted average).
    # 祖先推断不累加 obs；基于弱先验的加权平均不会虚高到 0.8。
    parent = snapshot["patent-law-foundation"]
    assert parent["inferred"] is True
    assert parent["observations"] == 0
    assert parent["pl"] < 0.8


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
    snapshot = store.mastery_snapshot("learner-1")
    assert snapshot["patent-rights-nature"]["observations"] == 0
    assert snapshot["patent-rights-nature"]["inferred"] is True


def test_seeding_uses_education_background_priors(tmp_path) -> None:
    """教育背景只影响弱先验 p_init 档位，不影响观测计数。"""
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    store.seed_mastery_from_questionnaire(
        learner_id="learner-1",
        session_id="session-1",
        responses=[{"question_id": "Q1", "answer": "B"}],
        education_background="法学背景+系统学过程序法",
    )

    parameters = parameters_for_background("法学背景+系统学过程序法")
    snapshot = store.mastery_snapshot("learner-1")
    assert snapshot["patent-rights-nature"]["pl"] == pytest.approx(
        parameters.p_init, abs=1e-4
    )
    assert snapshot["patent-rights-nature"]["observations"] == 0
    assert snapshot["patent-rights-nature"]["inferred"] is True


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
