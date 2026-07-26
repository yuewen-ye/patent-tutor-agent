import pytest

from backend.app.agents.common import constrain_expert_draft_to_current_lesson
from backend.app.curriculum.learning_progress import (
    advance_learning_progress,
    build_teaching_context,
    initialize_learning_progress,
    normalize_question_scope,
)

pytestmark = pytest.mark.unit


def _path() -> list[dict[str, object]]:
    return [
        {"node_id": "foundation", "node_name": "基础", "difficulty_cap": "L1"},
        {"node_id": "novelty", "node_name": "新颖性", "difficulty_cap": "L2"},
        {"node_id": "inventive-step", "node_name": "创造性", "difficulty_cap": "L3"},
    ]


def test_initial_progress_skips_nodes_mastered_by_cat_bkt() -> None:
    progress = initialize_learning_progress(
        existing_progress={},
        learning_path=_path(),
        mastery_snapshot={
            "foundation": {"pl": 0.92, "observations": 3},
            "novelty": {"pl": 0.45, "observations": 2},
        },
    )

    assert progress["completed_nodes"] == ["foundation"]
    assert progress["current_node"] == "novelty"
    assert progress["pending_nodes"] == ["inventive-step"]
    assert progress["overall_completion_ratio"] == pytest.approx(1 / 3, abs=1e-4)


def test_forward_probe_never_advances_current_node() -> None:
    progress, decision = advance_learning_progress(
        existing_progress={
            "completed_nodes": ["foundation"],
            "current_node": "novelty",
            "pending_nodes": ["inventive-step"],
        },
        learning_path=_path(),
        current_node_id="novelty",
        mastery_snapshot={
            "novelty": {"pl": 0.85, "observations": 3},
            "inventive-step": {"pl": 0.91, "observations": 2},
        },
        bkt_updates=[{"skill_id": "inventive-step", "posterior_pl": 0.91}],
    )

    assert decision["advanced"] is False
    assert decision["direct_evidence"] is False
    assert progress["current_node"] == "novelty"
    assert "novelty" not in progress["completed_nodes"]


def test_current_node_advances_only_with_threshold_and_evidence() -> None:
    progress, decision = advance_learning_progress(
        existing_progress={
            "completed_nodes": ["foundation"],
            "current_node": "novelty",
            "pending_nodes": ["inventive-step"],
        },
        learning_path=_path(),
        current_node_id="novelty",
        mastery_snapshot={"novelty": {"pl": 0.86, "observations": 2}},
        bkt_updates=[{"skill_id": "novelty", "posterior_pl": 0.86}],
    )

    assert decision["advanced"] is True
    assert decision["completed_node_id"] == "novelty"
    assert progress["completed_nodes"] == ["foundation", "novelty"]
    assert progress["current_node"] == "inventive-step"
    assert progress["pending_nodes"] == []


def test_teaching_context_and_draft_are_limited_to_active_window() -> None:
    progress = {
        "completed_nodes": ["foundation"],
        "current_node": "novelty",
        "pending_nodes": ["inventive-step"],
    }
    scope = normalize_question_scope(
        learning_path=_path(),
        progress=progress,
        proposed_scope={
            "backward_review": [
                {"node_id": "foundation", "difficulty": "L1", "goal": "复习"}
            ],
            "forward_probe": [
                {"node_id": "inventive-step", "difficulty": "L3", "goal": "越级教学"}
            ],
            "weakness_probe": [
                {"node_id": "inventive-step", "difficulty": "L2", "goal": "探测"}
            ],
        },
    )
    context = build_teaching_context(
        learning_path=_path(),
        progress=progress,
        question_scope=scope,
    )
    state = {
        "teaching_context": context,
        "path_decision": {"current_node_id": "novelty", "question_scope": scope},
    }
    constrained = constrain_expert_draft_to_current_lesson(
        {
            "knowledge_points": [
                {"node_id": "inventive-step", "kc_name": "错误越级知识点"}
            ],
            "block_plan": {"node": "inventive-step"},
            "knowledge_synthesis": {"node": "inventive-step"},
            "assessment": {"items": [{"qid": "q1", "kc": "inventive-step"}]},
            "interactive_questions": [
                {
                    "qid": "q2",
                    "source_tag": "forward_probe",
                    "kc_node_id": "unrelated",
                }
            ],
        },
        state,
    )

    assert context["current_node_id"] == "novelty"
    assert scope["forward_probe"][0]["node_id"] == "inventive-step"
    assert scope["forward_probe"][0]["difficulty"] == "L1"
    assert constrained["knowledge_points"][0]["node_id"] == "novelty"
    assert constrained["block_plan"]["node"] == "novelty"
    assert constrained["knowledge_synthesis"]["node"] == "novelty"
    assert constrained["assessment"]["items"][0]["kc"] == "novelty"
    assert constrained["interactive_questions"][0]["kc_node_id"] == "inventive-step"
