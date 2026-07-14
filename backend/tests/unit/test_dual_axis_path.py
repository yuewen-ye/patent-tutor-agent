from __future__ import annotations

import pytest

from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    compute_learning_path,
    load_confusion_pairs,
    load_knowledge_dag,
)


@pytest.mark.unit
def test_versioned_graph_assets_load_from_runtime_package() -> None:
    graph = load_knowledge_dag()
    pairs = load_confusion_pairs()

    assert graph["version"]
    assert len(graph["nodes"]) >= 60
    assert len(graph["edges"]) >= 70
    assert len(pairs["confusion_pairs"]) == 25


@pytest.mark.unit
def test_confusion_axis_adds_session_risk_without_mutating_static_pair() -> None:
    static_pairs = load_confusion_pairs()
    first_static = dict(static_pairs["confusion_pairs"][0])
    snapshot = build_dual_axis_snapshot(
        profile={"weak_points": [first_static["concept_a"], first_static["concept_b"]]},
        session_id="session-1",
    )

    first_runtime = snapshot["confusion_axis"][0]
    assert first_runtime["learner_risk"] > 0
    assert first_runtime["is_active"] is True
    assert first_runtime["adjustment_reason"]
    assert static_pairs["confusion_pairs"][0] == first_static


@pytest.mark.unit
def test_confusion_axis_uses_bkt_mastery_from_learner_profile() -> None:
    snapshot = build_dual_axis_snapshot(
        profile={
            "weak_points": [],
            "mastery": {"novelty": 0.2, "inventive-step": 0.3},
        },
        session_id="session-bkt",
    )

    first_runtime = snapshot["confusion_axis"][0]
    assert first_runtime["is_active"] is True
    assert first_runtime["learner_risk"] > first_runtime["difficulty"]
    assert "BKT" in first_runtime["adjustment_reason"]


@pytest.mark.unit
def test_astar_path_is_deterministic_and_respects_prerequisites() -> None:
    profile = {
        "knowledge_level": "beginner",
        "weak_points": ["新颖性", "现有技术"],
        "mastery": {},
    }

    first = compute_learning_path(profile=profile, learning_goal="掌握专利新颖性")
    second = compute_learning_path(profile=profile, learning_goal="掌握专利新颖性")

    assert first == second
    assert first
    positions = {item["node_id"]: index for index, item in enumerate(first)}
    for item in first:
        for prerequisite in item["prerequisites"]:
            if prerequisite in positions:
                assert positions[prerequisite] < positions[item["node_id"]]
