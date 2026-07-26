"""Learner-level active learning-plan helpers."""

from __future__ import annotations

import hashlib
from typing import Any


def normalize_learning_goal(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def learning_goal_hash(value: object) -> str:
    return hashlib.sha256(normalize_learning_goal(value).encode("utf-8")).hexdigest()


def reusable_active_plan(
    plan: object,
    *,
    learning_goal: str,
    knowledge_graph_version: str,
) -> bool:
    if not isinstance(plan, dict) or plan.get("status") != "active":
        return False
    if str(plan.get("learning_goal_hash") or "") != learning_goal_hash(learning_goal):
        return False
    if str(plan.get("knowledge_graph_version") or "") != knowledge_graph_version:
        return False
    nodes = plan.get("nodes")
    progress = plan.get("progress")
    if not isinstance(nodes, list) or not nodes or not isinstance(progress, dict):
        return False
    current_node = str(progress.get("current_node") or "")
    node_ids = {
        str(node.get("node_id") or "")
        for node in nodes
        if isinstance(node, dict)
    }
    return bool(current_node and current_node in node_ids)


def plan_node_status(node_id: str, progress: dict[str, Any]) -> str:
    completed = {
        str(value) for value in progress.get("completed_nodes", []) if value
    }
    if node_id in completed:
        return "completed"
    if node_id == str(progress.get("current_node") or ""):
        return "current"
    return "pending"
