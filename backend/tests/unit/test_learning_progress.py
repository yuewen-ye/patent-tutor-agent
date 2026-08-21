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


def test_teaching_context_includes_current_node_knowledge_points() -> None:
    progress = {
        "completed_nodes": ["foundation"],
        "current_node": "novelty",
        "pending_nodes": ["inventive-step"],
    }
    learning_path = [
        {
            "node_id": "foundation",
            "node_name": "基础",
            "difficulty_cap": "L1",
            "knowledge_points": ["基础点1", "基础点2"],
        },
        {
            "node_id": "novelty",
            "node_name": "新颖性",
            "difficulty_cap": "L2",
            "knowledge_points": ["新颖性点1", "新颖性点2", "新颖性点3"],
        },
        {
            "node_id": "inventive-step",
            "node_name": "创造性",
            "difficulty_cap": "L3",
            "knowledge_points": ["创造性点1"],
        },
    ]
    context = build_teaching_context(
        learning_path=learning_path,
        progress=progress,
        question_scope={"backward_review": [], "forward_probe": [], "weakness_probe": []},
    )
    assert context["knowledge_points"] == ["新颖性点1", "新颖性点2", "新颖性点3"]


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
    assert context["backward_review_nodes"] == []
    assert scope["forward_probe"][0]["node_id"] == "inventive-step"
    assert scope["forward_probe"][0]["difficulty"] == "L1"
    assert constrained["knowledge_points"][0]["node_id"] == "novelty"
    assert constrained["block_plan"]["node"] == "novelty"
    assert constrained["knowledge_synthesis"]["node"] == "novelty"
    assert constrained["assessment"]["items"][0]["kc"] == "novelty"
    assert constrained["interactive_questions"][0]["kc_node_id"] == "inventive-step"


def test_review_window_prioritizes_prerequisites_and_risk_not_only_previous_node() -> None:
    learning_path = [
        {
            "node_id": "foundation",
            "node_name": "基础制度",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "terminology",
            "node_name": "术语辨析",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "recent-topic",
            "node_name": "最近完成节点",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "current-topic",
            "node_name": "当前节点",
            "difficulty_cap": "L3",
            "prerequisites": ["foundation"],
        },
        {
            "node_id": "next-topic",
            "node_name": "下一节点",
            "difficulty_cap": "L3",
            "prerequisites": ["current-topic"],
        },
    ]
    scope = normalize_question_scope(
        learning_path=learning_path,
        progress={
            "completed_nodes": ["foundation", "terminology", "recent-topic"],
            "current_node": "current-topic",
            "pending_nodes": ["next-topic"],
        },
        proposed_scope={},
        mastery_snapshot={
            "foundation": {"pl": 0.82, "observations": 1},
            "terminology": {"pl": 0.58, "observations": 4},
            "recent-topic": {"pl": 0.93, "observations": 3},
        },
        weak_node_ids={"terminology"},
    )

    review_ids = [
        item["node_id"]
        for item in scope["backward_review"]
        if item["node_id"] != "current-topic"
    ]
    assert review_ids == ["foundation", "terminology"]
    assert "recent-topic" not in review_ids
    assert scope["forward_probe"][0]["node_id"] == "next-topic"
    assert scope["weakness_probe"][0]["node_id"] == "terminology"


def test_review_window_can_select_no_completed_node_when_risk_is_low() -> None:
    scope = normalize_question_scope(
        learning_path=[
            {
                "node_id": "completed",
                "node_name": "已完成",
                "difficulty_cap": "L2",
                "prerequisites": [],
            },
            {
                "node_id": "current",
                "node_name": "当前",
                "difficulty_cap": "L2",
                "prerequisites": ["completed"],
            },
        ],
        progress={
            "completed_nodes": ["completed"],
            "current_node": "current",
            "pending_nodes": [],
        },
        proposed_scope={},
        mastery_snapshot={"completed": {"pl": 0.95, "observations": 5}},
    )

    review_ids = [
        item["node_id"]
        for item in scope["backward_review"]
        if item["node_id"] != "current"
    ]
    assert review_ids == []


def test_review_window_uses_confusion_risk_for_non_adjacent_completed_node() -> None:
    scope = normalize_question_scope(
        learning_path=[
            {
                "node_id": "confusable",
                "node_name": "易混淆旧节点",
                "difficulty_cap": "L2",
                "prerequisites": [],
            },
            {
                "node_id": "recent",
                "node_name": "最近完成",
                "difficulty_cap": "L2",
                "prerequisites": [],
            },
            {
                "node_id": "current",
                "node_name": "当前",
                "difficulty_cap": "L3",
                "prerequisites": [],
            },
        ],
        progress={
            "completed_nodes": ["confusable", "recent"],
            "current_node": "current",
            "pending_nodes": [],
        },
        proposed_scope={},
        mastery_snapshot={
            "confusable": {"pl": 0.9, "observations": 4},
            "recent": {"pl": 0.9, "observations": 4},
        },
        confusion_risk={"confusable": 0.8},
    )

    review_ids = [
        item["node_id"]
        for item in scope["backward_review"]
        if item["node_id"] != "current"
    ]
    assert review_ids == ["confusable"]
    assert "混淆风险=0.80" in scope["backward_review"][0]["goal"]


def test_review_window_caps_at_two_highest_risk_nodes() -> None:
    completed = ["risk-low", "risk-high", "risk-medium"]
    learning_path = [
        {
            "node_id": node_id,
            "node_name": node_id,
            "difficulty_cap": "L2",
            "prerequisites": [],
        }
        for node_id in completed
    ] + [
        {
            "node_id": "current",
            "node_name": "当前",
            "difficulty_cap": "L3",
            "prerequisites": [],
        }
    ]
    scope = normalize_question_scope(
        learning_path=learning_path,
        progress={
            "completed_nodes": completed,
            "current_node": "current",
            "pending_nodes": [],
        },
        proposed_scope={},
        mastery_snapshot={
            "risk-low": {"pl": 0.75, "observations": 3},
            "risk-high": {"pl": 0.4, "observations": 3},
            "risk-medium": {"pl": 0.6, "observations": 3},
        },
        weak_node_ids=set(completed),
    )

    review_ids = [
        item["node_id"]
        for item in scope["backward_review"]
        if item["node_id"] != "current"
    ]
    assert review_ids == ["risk-high", "risk-medium"]


def test_review_window_reserves_only_one_slot_for_at_risk_prerequisite() -> None:
    learning_path = [
        {
            "node_id": "prerequisite-a",
            "node_name": "先修A",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "prerequisite-b",
            "node_name": "先修B",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "severe-weakness",
            "node_name": "严重薄弱旧节点",
            "difficulty_cap": "L2",
            "prerequisites": [],
        },
        {
            "node_id": "current",
            "node_name": "当前",
            "difficulty_cap": "L3",
            "prerequisites": ["prerequisite-a", "prerequisite-b"],
        },
    ]
    scope = normalize_question_scope(
        learning_path=learning_path,
        progress={
            "completed_nodes": [
                "prerequisite-a",
                "prerequisite-b",
                "severe-weakness",
            ],
            "current_node": "current",
            "pending_nodes": [],
        },
        proposed_scope={},
        mastery_snapshot={
            "prerequisite-a": {"pl": 0.78, "observations": 2},
            "prerequisite-b": {"pl": 0.78, "observations": 2},
            "severe-weakness": {"pl": 0.35, "observations": 4},
        },
        weak_node_ids={"severe-weakness"},
    )

    review_ids = [
        item["node_id"]
        for item in scope["backward_review"]
        if item["node_id"] != "current"
    ]
    assert review_ids == ["prerequisite-a", "severe-weakness"]
