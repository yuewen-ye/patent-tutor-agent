"""Deterministic learning-roadmap cursor and single-lesson scope helpers."""

from __future__ import annotations

from typing import Any, Iterable

DEFAULT_MASTERY_THRESHOLD = 0.80
DEFAULT_MIN_OBSERVATIONS = 2


def _node_ids(path: Iterable[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for item in path:
        node_id = str(item.get("node_id") or "")
        if node_id and node_id not in result:
            result.append(node_id)
    return result


def _mastery_value(
    mastery_snapshot: dict[str, dict[str, Any]],
    node_id: str,
) -> tuple[float | None, int]:
    state = mastery_snapshot.get(node_id)
    if not isinstance(state, dict):
        return None, 0
    raw_probability = state.get("pl", state.get("probability"))
    try:
        probability = float(raw_probability) if raw_probability is not None else None
    except (TypeError, ValueError):
        probability = None
    try:
        observations = int(state.get("observations", 0))
    except (TypeError, ValueError):
        observations = 0
    return probability, max(0, observations)


def _is_mastered(
    mastery_snapshot: dict[str, dict[str, Any]],
    node_id: str,
    *,
    mastery_threshold: float,
    minimum_observations: int,
) -> bool:
    probability, observations = _mastery_value(mastery_snapshot, node_id)
    return (
        probability is not None
        and probability >= mastery_threshold
        and observations >= minimum_observations
    )


def _unique(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value or "")
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def initialize_learning_progress(
    *,
    existing_progress: object,
    learning_path: list[dict[str, Any]],
    mastery_snapshot: dict[str, dict[str, Any]],
    mastery_threshold: float = DEFAULT_MASTERY_THRESHOLD,
    minimum_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> dict[str, Any]:
    """Initialize or reconcile the backend-owned cursor against a planned roadmap.

    CAT/BKT nodes already supported by sufficient evidence are treated as completed.
    The first unresolved topological path node becomes the only active teaching node.
    """

    previous = dict(existing_progress) if isinstance(existing_progress, dict) else {}
    roadmap = _node_ids(learning_path)
    completed = _unique(previous.get("completed_nodes") or [])
    for node_id in roadmap:
        if _is_mastered(
            mastery_snapshot,
            node_id,
            mastery_threshold=mastery_threshold,
            minimum_observations=minimum_observations,
        ) and node_id not in completed:
            completed.append(node_id)

    unresolved = [node_id for node_id in roadmap if node_id not in completed]
    current = unresolved[0] if unresolved else None
    pending = unresolved[1:] if unresolved else []
    completed_in_roadmap = sum(1 for node_id in roadmap if node_id in completed)
    ratio = completed_in_roadmap / len(roadmap) if roadmap else 1.0

    return {
        "completed_nodes": completed,
        "current_node": current,
        "pending_nodes": pending,
        "avg_time_per_node_min": previous.get("avg_time_per_node_min"),
        "overall_completion_ratio": round(ratio, 4),
    }


def advance_learning_progress(
    *,
    existing_progress: object,
    learning_path: list[dict[str, Any]],
    current_node_id: str | None,
    mastery_snapshot: dict[str, dict[str, Any]],
    bkt_updates: list[dict[str, Any]],
    mastery_threshold: float = DEFAULT_MASTERY_THRESHOLD,
    minimum_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Advance one roadmap cursor only when this lesson supplies mastery evidence."""

    previous = dict(existing_progress) if isinstance(existing_progress, dict) else {}
    roadmap = _node_ids(learning_path)
    completed = _unique(previous.get("completed_nodes") or [])
    current_before = str(current_node_id or previous.get("current_node") or "") or None
    probability: float | None = None
    observations = 0
    direct_evidence = False

    if current_before:
        probability, observations = _mastery_value(mastery_snapshot, current_before)
        direct_evidence = any(
            isinstance(update, dict) and str(update.get("skill_id") or "") == current_before
            for update in bkt_updates
        )

    mastered = bool(
        current_before
        and direct_evidence
        and probability is not None
        and probability >= mastery_threshold
        and observations >= minimum_observations
    )
    if mastered and current_before is not None and current_before not in completed:
        completed.append(current_before)

    unresolved = [node_id for node_id in roadmap if node_id not in completed]
    if mastered:
        current_after = unresolved[0] if unresolved else None
    else:
        current_after = current_before if current_before in unresolved else (
            unresolved[0] if unresolved else None
        )
    pending = [node_id for node_id in unresolved if node_id != current_after]
    completed_in_roadmap = sum(1 for node_id in roadmap if node_id in completed)
    ratio = completed_in_roadmap / len(roadmap) if roadmap else 1.0

    if not current_before:
        reason = "course session has no authoritative current node"
    elif not direct_evidence:
        reason = "no BKT update was recorded for the current teaching node"
    elif probability is None:
        reason = "current teaching node has no mastery probability"
    elif probability < mastery_threshold:
        reason = (
            f"current node mastery {probability:.4f} is below threshold "
            f"{mastery_threshold:.2f}"
        )
    elif observations < minimum_observations:
        reason = (
            f"current node has {observations} observation(s), below minimum "
            f"{minimum_observations}"
        )
    elif current_after:
        reason = f"current node mastered; advance to {current_after}"
    else:
        reason = "current node mastered; roadmap completed"

    progress = {
        "completed_nodes": completed,
        "current_node": current_after,
        "pending_nodes": pending,
        "avg_time_per_node_min": previous.get("avg_time_per_node_min"),
        "overall_completion_ratio": round(ratio, 4),
    }
    decision = {
        "current_node_before": current_before,
        "current_node_after": current_after,
        "completed_node_id": current_before if mastered else None,
        "advanced": mastered,
        "path_completed": bool(mastered and not current_after),
        "mastery_probability": probability,
        "observations": observations,
        "mastery_threshold": mastery_threshold,
        "minimum_observations": minimum_observations,
        "direct_evidence": direct_evidence,
        "reason": reason,
    }
    return progress, decision


def normalize_question_scope(
    *,
    learning_path: list[dict[str, Any]],
    progress: dict[str, Any],
    proposed_scope: object,
) -> dict[str, list[dict[str, Any]]]:
    """Constrain questions to current/review/next-probe nodes for one lesson."""

    path_by_id = {
        str(item.get("node_id")): item
        for item in learning_path
        if isinstance(item, dict) and item.get("node_id")
    }
    current = str(progress.get("current_node") or "")
    completed = _unique(progress.get("completed_nodes") or [])
    pending = _unique(progress.get("pending_nodes") or [])
    proposed = dict(proposed_scope) if isinstance(proposed_scope, dict) else {}

    def proposed_items(key: str) -> list[dict[str, Any]]:
        items = proposed.get(key)
        return [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    backward: list[dict[str, Any]] = []
    allowed_backward = set(completed) | ({current} if current else set())
    for item in proposed_items("backward_review"):
        node_id = str(item.get("node_id") or "")
        if node_id in allowed_backward and node_id in path_by_id and node_id != current:
            backward.append(item)
            break
    if current:
        backward.append(
            {
                "node_id": current,
                "difficulty": next(
                    (
                        str(item.get("difficulty") or "L1")
                        for item in proposed_items("backward_review")
                        if str(item.get("node_id") or "") == current
                    ),
                    "L1",
                ),
                "goal": "验证当前教学节点是否达到掌握标准",
            }
        )

    forward: list[dict[str, Any]] = []
    if pending:
        next_node = pending[0]
        forward = [
            {
                "node_id": next_node,
                "difficulty": "L1",
                "goal": "仅探测下一待学节点，不据此判定该节点完成",
            }
        ]

    weakness: list[dict[str, Any]] = []
    active_window = {item["node_id"] for item in backward + forward}
    for item in proposed_items("weakness_probe"):
        node_id = str(item.get("node_id") or "")
        if node_id in active_window:
            weakness = [
                {
                    "node_id": node_id,
                    "difficulty": "L3",
                    "goal": str(item.get("goal") or "探测当前活动窗口中的薄弱点"),
                }
            ]
            break
    if not weakness and current:
        weakness = [
            {
                "node_id": current,
                "difficulty": "L3",
                "goal": "挑战当前教学节点的易错或易混淆知识",
            }
        ]

    return {
        "backward_review": backward,
        "forward_probe": forward,
        "weakness_probe": weakness,
    }


def build_teaching_context(
    *,
    learning_path: list[dict[str, Any]],
    progress: dict[str, Any],
    question_scope: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build the small, explicit context consumed by both teaching Experts."""

    path_by_id = {
        str(item.get("node_id")): dict(item)
        for item in learning_path
        if isinstance(item, dict) and item.get("node_id")
    }
    current_id = str(progress.get("current_node") or "")

    def scoped_nodes(key: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for scope in question_scope.get(key, []):
            node_id = str(scope.get("node_id") or "")
            if node_id in path_by_id:
                result.append({**path_by_id[node_id], "question_scope": dict(scope)})
        return result

    return {
        "current_node_id": current_id or None,
        "current_node": path_by_id.get(current_id),
        "backward_review_nodes": scoped_nodes("backward_review"),
        "forward_probe_nodes": scoped_nodes("forward_probe"),
        "weakness_probe_nodes": scoped_nodes("weakness_probe"),
        "progress": progress,
        "lesson_policy": {
            "primary_teaching_nodes": [current_id] if current_id else [],
            "review_nodes_are_not_new_teaching_targets": True,
            "forward_probe_does_not_complete_next_node": True,
        },
    }


def deterministic_next_action(decision: dict[str, Any]) -> str:
    if decision.get("path_completed"):
        return "当前节点已掌握，学习路径已完成"
    if decision.get("advanced"):
        return f"当前节点已掌握，下一节学习 {decision.get('current_node_after')}"
    current = decision.get("current_node_before") or decision.get("current_node_after")
    return f"继续强化当前节点 {current}" if current else "等待后端重新规划学习路径"
