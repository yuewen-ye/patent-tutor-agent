"""Planner Agent node."""

from __future__ import annotations

import json
from typing import Any

from langgraph.runtime import Runtime

from backend.app.agents.common import Node, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    compute_learning_path,
    load_confusion_pairs,
    load_knowledge_dag,
)
from backend.app.learner_memory.memory import load_profile_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import LearningPathItem, StateDict, completed_event

_PLANNER_SYSTEM_PROMPT = load_prompt(__file__, "system.md")


def _knowledge_pl_map(profile: dict[str, Any]) -> dict[str, Any]:
    """提取画像中每个知识节点的 BKT 掌握概率 P(L)。"""
    fd = profile.get("five_dimensions") or {}
    return fd.get("knowledge", {}) or {}


def _difficulty_cap_for(node_id: str, pl_map: dict[str, Any], weak_node_ids: set[str]) -> str:
    """按掌握概率 P(L) 推导习题难度上限（对齐提示词『难度分阶规则』）。"""
    if node_id in weak_node_ids:
        return "L3"
    node_state = pl_map.get(node_id) or {}
    pl = node_state.get("pl") if isinstance(node_state, dict) else node_state
    if pl is None:
        return "L2"
    if pl < 0.15:
        return "L1"
    if pl < 0.30:
        return "L2"
    return "L3"


def _default_question_scope(path: list[Any], profile: dict[str, Any]) -> dict[str, Any]:
    """首轮无作答数据时，按路径与画像生成三类出题范围默认值。"""
    if not path:
        return {}
    current = path[0]
    prereqs = list(current.prerequisites or [])[:1]
    backward = [
        {"node_id": nid, "difficulty": "L1", "goal": "验证已学节点是否巩固"}
        for nid in (prereqs + [current.node_id])
    ]
    forward: list[dict[str, Any]] = []
    if len(path) > 1:
        nxt = path[1]
        forward = [
            {"node_id": nxt.node_id, "difficulty": "L1", "goal": "探测下一待学节点学情，不要求掌握"}
        ]
    weakness: list[dict[str, Any]] = []
    weak = profile.get("weak_points") or []
    if weak:
        target = next(
            (it.node_id for it in path if any(w in it.node_id or w in it.node_name for w in weak)),
            current.node_id,
        )
        weakness = [{"node_id": target, "difficulty": "L3", "goal": "对应画像薄弱点的挑战题"}]
    return {"backward_review": backward, "forward_probe": forward, "weakness_probe": weakness}


def _default_iteration_directive() -> dict[str, Any]:
    return {
        "type": "无",
        "trigger": "首轮无作答数据，按基线 P(L) 规划",
        "action": "待首轮习题回灌后，依据 L1 答对率与 weak_points 下达降维/进阶/薄弱点跟进指令",
    }


def _build_profile(state: StateDict, runtime: Runtime[WorkflowContext] | None) -> dict[str, Any]:
    historical = load_profile_memories(runtime, limit=1)
    profile = dict(historical[0] if historical else state.get("learner_profile", {}))
    store = getattr(runtime, "store", None) if runtime is not None else None
    learner_id = getattr(runtime.context, "learner_id", None) if runtime is not None else None
    mastery_reader = getattr(store, "mastery", None)
    if learner_id and callable(mastery_reader):
        profile["mastery"] = mastery_reader(learner_id)
    return profile


def _parse_planner_plan(raw: object) -> dict[str, Any] | None:
    """Parse the LLM planner output into a validated path + directive fields.

    Returns ``None`` when the output cannot be trusted so the caller can fall
    back to the deterministic planner. Extra fields on each node are ignored.
    """
    if not isinstance(raw, dict):
        return None
    nodes = raw.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return None
    parsed: list[LearningPathItem] = []
    for node in nodes:
        if not isinstance(node, dict):
            return None
        try:
            item = LearningPathItem.model_validate(
                {k: v for k, v in node.items() if k in LearningPathItem.model_fields}
            )
        except Exception:  # noqa: BLE001 - any validation failure → fallback
            return None
        parsed.append(item)
    return {
        "learning_path": parsed,
        "question_scope": raw.get("question_scope") or {},
        "iteration_directive": raw.get("iteration_directive") or {},
    }


def build_planner_node(llm_client: LLMClient) -> Node:
    def planner_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        profile = _build_profile(state, runtime)
        learning_goal = str(profile.get("learning_goal") or state["user_input"])

        knowledge = load_knowledge_dag()
        confusion = load_confusion_pairs()
        user_text = (
            "# 双知识图（编排层注入，只读不改）\n"
            f"## 知识点 DAG\n{json.dumps(knowledge, ensure_ascii=False, indent=2)}\n"
            f"## 易混淆对\n{json.dumps(confusion, ensure_ascii=False, indent=2)}\n\n"
            "# 学习者画像\n"
            f"{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
            f"# 学习目标\n{learning_goal}"
        )

        try:
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(role="system", content=_PLANNER_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_text),
                ],
                temperature=agent_temperature("planner", 0.3),
                agent="planner",
            )
            plan = _parse_planner_plan(raw)
        except Exception:  # noqa: BLE001 - LLM failure → deterministic fallback
            plan = None

        # 难度上限按 P(L) 分阶确定性推导，保证 artifact 始终带『资源难度匹配曲线』数据
        pl_map = _knowledge_pl_map(profile)

        if plan is None:
            path = [
                LearningPathItem.model_validate(it)
                for it in compute_learning_path(profile=profile, learning_goal=learning_goal)
            ]
            question_scope = _default_question_scope(path, profile)
            iteration_directive = _default_iteration_directive()
            algorithm = "deterministic_astar"
        else:
            path = plan["learning_path"]
            question_scope = plan["question_scope"] or _default_question_scope(path, profile)
            iteration_directive = plan["iteration_directive"] or _default_iteration_directive()
            algorithm = "llm_astar"

        # 薄弱点中文描述解析为命中的 node_id（比对 node_id + node_name），须在 path 确定后计算
        weak_texts = profile.get("weak_points") or []
        weak_node_ids = set()
        for it in path:
            if any(w in it.node_id or w in it.node_name for w in weak_texts):
                weak_node_ids.add(it.node_id)

        dual_axis = build_dual_axis_snapshot(profile=profile, session_id=state["session_id"])

        path = [
            it.model_copy(update={"difficulty_cap": _difficulty_cap_for(it.node_id, pl_map, weak_node_ids)})
            for it in path
        ]
        selected = path[0].node_id if path else None
        return {
            "learning_path": [it.model_dump() for it in path],
            "dual_axis_snapshot": dual_axis,
            "path_decision": {
                "current_node_id": selected,
                "algorithm": algorithm,
                "question_scope": question_scope,
                "iteration_directive": iteration_directive,
            },
            "events": [completed_event("planner", f"planned learning path ({algorithm})")],
        }

    return planner_node
