from __future__ import annotations

import heapq
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_ASSET_ROOT = (
    Path(__file__).resolve().parents[2] / "docs" / "各agent过程产物" / "03_双知识路径图"
)
_WEIGHTS = {"低": 0.35, "中": 0.6, "高": 0.8, "极高": 1.0}


@lru_cache(maxsize=1)
def _raw_knowledge_dag() -> dict[str, Any]:
    return json.loads((_ASSET_ROOT / "knowledge-dag.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _raw_confusion_pairs() -> dict[str, Any]:
    return json.loads((_ASSET_ROOT / "confusion-pairs.json").read_text(encoding="utf-8"))


def load_knowledge_dag() -> dict[str, Any]:
    raw = _raw_knowledge_dag()
    return {
        "version": raw["meta"]["version"],
        "meta": deepcopy(raw["meta"]),
        "nodes": deepcopy(raw["dag"]["nodes"]),
        "edges": deepcopy(raw["dag"]["edges"]),
    }


def load_confusion_pairs() -> dict[str, Any]:
    raw = _raw_confusion_pairs()
    pairs = []
    for pair in raw["confusion_pairs"]:
        normalized = deepcopy(pair)
        normalized["concept_a"] = pair["node_a"]
        normalized["concept_b"] = pair["node_b"]
        pairs.append(normalized)
    return {
        "version": raw["meta"]["version"],
        "meta": deepcopy(raw["meta"]),
        "confusion_pairs": pairs,
    }


def build_dual_axis_snapshot(
    *, profile: dict[str, Any], session_id: str
) -> dict[str, Any]:
    weak_text = " ".join(str(item) for item in profile.get("weak_points", []))
    knowledge = load_knowledge_dag()
    confusion = load_confusion_pairs()
    runtime_pairs: list[dict[str, Any]] = []
    for pair in confusion["confusion_pairs"]:
        terms = [
            str(pair["concept_a"]),
            str(pair["concept_b"]),
            str(pair.get("title", "")),
        ]
        matched = [term for term in terms if term and term in weak_text]
        base_risk = float(pair.get("difficulty", 0.5))
        risk = min(1.0, base_risk + (0.2 if matched else 0.0)) if matched else 0.0
        runtime = deepcopy(pair)
        runtime.update(
            {
                "learner_risk": risk,
                "is_active": bool(matched),
                "adjustment_reason": (
                    f"学员薄弱点命中：{', '.join(matched)}" if matched else "当前画像未命中"
                ),
            }
        )
        runtime_pairs.append(runtime)
    return {
        "session_id": session_id,
        "knowledge_axis_version": knowledge["version"],
        "confusion_axis_version": confusion["version"],
        "knowledge_axis": knowledge,
        "confusion_axis": runtime_pairs,
    }


def compute_learning_path(
    *, profile: dict[str, Any], learning_goal: str, max_nodes: int = 8
) -> list[dict[str, Any]]:
    graph = load_knowledge_dag()
    nodes = {str(node["node_id"]): node for node in graph["nodes"]}
    weak_text = " ".join(str(item) for item in profile.get("weak_points", []))
    search_text = f"{learning_goal} {weak_text}"
    mastery = profile.get("mastery", {}) if isinstance(profile.get("mastery"), dict) else {}

    targets = [node_id for node_id, node in nodes.items() if _matches_node(node, search_text)]
    if not targets:
        targets = sorted(nodes, key=lambda node_id: _node_cost(nodes[node_id], weak_text))[:3]

    required: set[str] = set()
    frontier: list[tuple[float, str]] = []
    for target in sorted(targets):
        heapq.heappush(frontier, (_node_cost(nodes[target], weak_text), target))
    while frontier and len(required) < max_nodes:
        _, node_id = heapq.heappop(frontier)
        if node_id in required or float(mastery.get(node_id, 0.0)) >= 0.8:
            continue
        required.add(node_id)
        for predecessor in nodes[node_id].get("predecessors", []):
            if predecessor in nodes and predecessor not in required:
                heapq.heappush(frontier, (_node_cost(nodes[predecessor], weak_text), predecessor))

    ordered = _topological_subset(nodes, required)
    return [
        {
            "node_id": node_id,
            "node_name": str(nodes[node_id]["node_name"]),
            "duration_min": max(10, round(float(nodes[node_id].get("estimated_hours", 1)) * 60)),
            "strategy": _strategy(nodes[node_id], weak_text),
            "prerequisites": [
                predecessor
                for predecessor in nodes[node_id].get("predecessors", [])
                if predecessor in required
            ],
            "target_ability": str(nodes[node_id].get("description", "")),
            "assessment": "完成本节点练习并达到 80% 掌握度",
        }
        for node_id in ordered
    ]


def _matches_node(node: dict[str, Any], text: str) -> bool:
    terms = [node.get("node_id"), node.get("node_name"), *node.get("tags", [])]
    return any(str(term).lower() in text.lower() for term in terms if term)


def _node_cost(node: dict[str, Any], weak_text: str) -> float:
    weakness = 1.0 if _matches_node(node, weak_text) else 0.25
    benefit = weakness * _WEIGHTS.get(str(node.get("exam_weight", "中")), 0.6)
    hours = float(node.get("estimated_hours", 1.0))
    difficulty = float(node.get("difficulty", 0.5))
    return hours * (1 + difficulty) / max(0.05, benefit)


def _topological_subset(nodes: dict[str, dict[str, Any]], selected: set[str]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in ordered or node_id in visiting:
            return
        visiting.add(node_id)
        for predecessor in sorted(nodes[node_id].get("predecessors", [])):
            if predecessor in selected:
                visit(predecessor)
        visiting.remove(node_id)
        ordered.append(node_id)

    for selected_id in sorted(selected, key=lambda item: _node_cost(nodes[item], "")):
        visit(selected_id)
    return ordered


def _strategy(node: dict[str, Any], weak_text: str) -> str:
    if _matches_node(node, weak_text):
        return "先做易混淆概念对比，再用案例和法条巩固"
    return "按知识依赖学习，完成节点练习后再进入下一节点"
