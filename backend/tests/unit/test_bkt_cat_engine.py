from __future__ import annotations

import pytest

from backend.app.agents.diagnosis.node import (
    _authoritative_knowledge,
    _normalize_diagnosis_agent_payload,
)
from backend.app.learner_memory.bkt import (
    BKTTracker,
    CATEngine,
    load_diagnostic_questions,
    load_knowledge_graph,
    parameters_for_background,
)

pytestmark = pytest.mark.unit


def test_background_parameters_match_imported_algorithm() -> None:
    assert parameters_for_background("法学背景，系统学过程序法").p_init == 0.40
    assert parameters_for_background("理工背景+有研发经验").p_transit == 0.20
    assert parameters_for_background("无相关背景").p_init == 0.10


def test_tracker_matches_transition_before_observation_and_early_acceleration() -> None:
    tracker = BKTTracker("理工背景+有研发经验")
    tracker.record_answer_event()

    step = tracker.update(
        "novelty",
        p_guess=0.08,
        p_slip=0.05,
        observed_correct=True,
    )

    assert step.prior_pl == pytest.approx(0.15)
    assert step.p_transit == pytest.approx(0.30)
    assert step.predicted_pl == pytest.approx(0.405)
    assert step.posterior_pl == pytest.approx(0.8899, abs=0.001)


def test_tracker_accelerates_exactly_the_first_ten_questions() -> None:
    tracker = BKTTracker("理工背景+有研发经验", global_answer_count=9)
    tracker.record_answer_event()
    tenth = tracker.update(
        "novelty",
        p_guess=0.08,
        p_slip=0.05,
        observed_correct=True,
    )
    tracker.record_answer_event()
    eleventh = tracker.update(
        "inventive-step",
        p_guess=0.08,
        p_slip=0.05,
        observed_correct=True,
    )

    assert tenth.p_transit == pytest.approx(0.30)
    assert eleventh.p_transit == pytest.approx(0.20)


def test_tracker_round_trips_state_and_marks_inferred_nodes() -> None:
    tracker = BKTTracker("其他")
    tracker.force_set("patent-law-foundation", 0.42, inferred=True)

    restored = BKTTracker.from_state_dict(tracker.state_dict())
    snapshot = restored.knowledge_snapshot(["patent-law-foundation", "novelty"])

    assert snapshot["patent-law-foundation"]["pl"] == pytest.approx(0.42)
    assert snapshot["patent-law-foundation"]["inferred"] is True
    assert snapshot["patent-law-foundation"]["low_confidence"] is True
    assert snapshot["novelty"]["pl"] == pytest.approx(0.15)
    assert snapshot["novelty"]["observations"] == 0


def test_question_bank_matches_repository_knowledge_graph() -> None:
    questions = load_diagnostic_questions()
    graph = load_knowledge_graph()

    assert len(questions) == 105
    assert len(graph.nodes) == 69
    assert {skill for question in questions for skill in question.skills} == set(graph.nodes)
    assert sum(len(question.skills) > 1 for question in questions) == 20


def test_cat_selects_records_and_restores_progress() -> None:
    tracker = BKTTracker("理工背景+有研发经验")
    graph = load_knowledge_graph()
    engine = CATEngine(load_diagnostic_questions(), tracker, graph)

    question = engine.select_next()

    assert question is not None
    result = engine.answer_question(question, observed_correct=True)
    assert result["direct_steps"]
    assert question.id in engine.used_question_ids
    restored = CATEngine(
        load_diagnostic_questions(),
        BKTTracker.from_state_dict(tracker.state_dict()),
        graph,
        state=engine.state_dict(),
    )
    assert restored.used_question_ids == engine.used_question_ids
    assert restored.select_next() is not None


def test_cat_stops_at_configured_question_limit() -> None:
    engine = CATEngine(
        load_diagnostic_questions(),
        BKTTracker("其他"),
        load_knowledge_graph(),
        state={"used_question_ids": [question.id for question in load_diagnostic_questions()[:40]]},
    )

    terminated, reason = engine.check_terminate()

    assert terminated is True
    assert reason == "达到最大诊断题数"


def test_cat_does_not_classify_unobserved_prior_as_unmastered() -> None:
    engine = CATEngine(
        load_diagnostic_questions(),
        BKTTracker("其他"),
        load_knowledge_graph(),
    )

    terminated, reason = engine.check_terminate()

    assert terminated is False
    assert reason == "继续诊断"


def test_diagnostic_agent_knowledge_is_discarded_and_backend_snapshot_is_authoritative() -> None:
    llm_payload = {
        "education_background": "LLM guess",
        "weak_points": [],
        "five_dimensions": {
            "knowledge": {
                "novelty": {
                    "pl": 0.99,
                    "ci_low": 0.9,
                    "ci_high": 1.0,
                    "observations": 1,
                    "low_confidence": False,
                }
            }
        },
    }
    diagnostic = {
        "education_background": "理工背景+有研发经验",
        "knowledge": {
            "novelty": {
                "pl": 0.2,
                "ci_low": 0.05,
                "ci_high": 0.45,
                "observations": 2,
                "low_confidence": True,
                "inferred": False,
            }
        },
    }

    normalized = _normalize_diagnosis_agent_payload(llm_payload)
    knowledge = _authoritative_knowledge(diagnostic["knowledge"])

    assert isinstance(normalized, dict)
    assert normalized["learner_dimensions"] == {}
    assert "knowledge" not in normalized
    assert knowledge["novelty"]["pl"] == pytest.approx(0.2)
    assert knowledge["novelty"]["observations"] == 2
    assert knowledge["novelty"]["inferred"] is False
    assert knowledge["inventive-step"]["pl"] == pytest.approx(0.15)
