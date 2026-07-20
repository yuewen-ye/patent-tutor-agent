from __future__ import annotations

import pytest

from backend.app.curriculum.learning_path import (
    _build_node_name_index,
    _pair_weak_match,
    _resolve_weak_nodes,
    build_dual_axis_snapshot,
    compute_default_block_plan,
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


@pytest.mark.unit
def test_weak_point_english_id_and_chinese_name_both_match_confusion_pair() -> None:
    # 学员写英文 id（novelty）或中文名（新颖性）都应命中「新颖性 vs 创造性」混淆对，
    # 不必死等节点名子串；纯含糊表述（无概念名）不应误命中。
    knowledge = {
        "nodes": [
            {"node_id": "novelty", "node_name": "新颖性"},
            {"node_id": "inventive-step", "node_name": "创造性"},
        ]
    }
    n2i, i2n = _build_node_name_index(knowledge)
    pair = {
        "node_a": "novelty",
        "node_b": "inventive-step",
        "title": "新颖性 vs 创造性",
        "difficulty": 0.75,
    }
    matched_en, _ = _pair_weak_match(pair, ["novelty"], n2i, i2n)
    matched_zh, _ = _pair_weak_match(pair, ["新颖性"], n2i, i2n)
    matched_vague, _ = _pair_weak_match(pair, ["这俩我老搞混"], n2i, i2n)
    assert matched_en is True
    assert matched_zh is True
    assert matched_vague is False


@pytest.mark.unit
def test_resolve_weak_nodes_handles_id_name_and_substring() -> None:
    knowledge = {
        "nodes": [
            {"node_id": "novelty", "node_name": "新颖性"},
            {"node_id": "inventive-step", "node_name": "创造性"},
        ]
    }
    n2i, i2n = _build_node_name_index(knowledge)
    resolved = _resolve_weak_nodes(["novelty", "创造性", "专利新颖性问题"], n2i, i2n)
    assert resolved == {"novelty", "inventive-step"}


@pytest.mark.unit
def test_dual_axis_snapshot_activates_on_english_id_weak_point() -> None:
    # 回归：薄弱点写英文 id 也能激活对应混淆对（之前只认节点名子串）
    snapshot = build_dual_axis_snapshot(
        profile={"weak_points": ["novelty"]},
        session_id="session-en-id",
    )
    first = snapshot["confusion_axis"][0]
    assert first["is_active"] is True
    assert "命中节点" in first["adjustment_reason"]


@pytest.mark.unit
def test_compute_learning_path_includes_confusion_companion() -> None:
    # 学员仅点名混淆对一端（新颖性），规划应把另一端（创造性）及相关节点也排进路径，
    # 确保「辨析模块」两端齐备、common_pitfall 块能真正触发（命中一端即排两端）。
    profile = {
        "knowledge_level": "beginner",
        "weak_points": ["新颖性"],
        "mastery": {},
    }
    path = compute_learning_path(profile=profile, learning_goal="复习一下专利法")
    node_ids = {item["node_id"] for item in path}
    assert "novelty" in node_ids
    assert "inventive-step" in node_ids


@pytest.mark.unit
def test_common_pitfall_fires_when_weak_point_names_current_node() -> None:
    # 当前节点被学员点名薄弱时，仍上辨析课（鲁棒版 weak_name_hit）
    plan = compute_default_block_plan(
        profile={"weak_points": ["新颖性"]},
        current_node_id="novelty",
        weak_points=["新颖性"],
    )
    blocks = {b["block_type"] for b in plan["required_blocks"]}
    assert "common_pitfall" in blocks
