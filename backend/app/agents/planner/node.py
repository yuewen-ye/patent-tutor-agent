"""Planner Agent node."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, cast

from langgraph.runtime import Runtime

from backend.app.agents.common import Node, generate_validated_json, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.learning_plan import (
    learning_goal_hash,
    reusable_active_plan,
)
from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    compute_learning_path,
    load_confusion_pairs,
    load_knowledge_dag,
)
from backend.app.curriculum.learning_progress import (
    build_teaching_context,
    initialize_learning_progress,
    normalize_question_scope,
)
from backend.app.learner_memory.memory import (
    load_profile_memories,
    save_profile_snapshot,
)
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import (
    LearningPathItem,
    PlannerAgentResult,
    StateDict,
    completed_event,
)

_PLANNER_SYSTEM_PROMPT = load_prompt(__file__, "system.md")
_LOGGER = logging.getLogger(__name__)


def _knowledge_pl_map(profile: dict[str, Any]) -> dict[str, Any]:
    """提取每个知识节点的 BKT 掌握概率，数据库当前值覆盖旧画像快照。"""
    fd = profile.get("five_dimensions") or {}
    knowledge = dict(fd.get("knowledge", {}) or {})
    current_mastery = profile.get("mastery") or {}
    if isinstance(current_mastery, dict):
        for node_id, probability in current_mastery.items():
            if probability is not None:
                current = knowledge.get(str(node_id))
                merged = dict(current) if isinstance(current, dict) else {}
                merged["pl"] = float(probability)
                knowledge[str(node_id)] = merged
    return knowledge


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


def _confusion_review_risk(
    dual_axis: dict[str, Any],
    current_node_id: str | None,
) -> dict[str, float]:
    current = str(current_node_id or "")
    if not current:
        return {}
    risks: dict[str, float] = {}
    for pair in dual_axis.get("confusion_axis", []):
        if not isinstance(pair, dict) or not pair.get("is_active"):
            continue
        node_ids = {
            str(node_id)
            for node_id in (
                pair.get("node_a"),
                pair.get("node_b"),
                *(pair.get("related_nodes") or []),
            )
            if node_id
        }
        if current not in node_ids:
            continue
        try:
            risk = max(0.0, min(1.0, float(pair.get("learner_risk") or 0.0)))
        except (TypeError, ValueError):
            risk = 0.0
        for node_id in node_ids - {current}:
            risks[node_id] = max(risks.get(node_id, 0.0), risk)
    return risks


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


def _planner_fallback_reason(exc: Exception) -> str:
    detail = " ".join(str(exc).split())
    if len(detail) > 800:
        detail = f"{detail[:797]}..."
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _runtime_learner_id(runtime: Runtime[WorkflowContext] | None) -> str | None:
    if runtime is None:
        return None
    context = runtime.context
    value = context.get("learner_id") if isinstance(context, dict) else context.learner_id
    return str(value) if value else None


def _replan_reason(
    active_plan: object,
    *,
    learning_goal: str,
    knowledge_graph_version: str,
) -> str:
    if not isinstance(active_plan, dict):
        return "initial_plan"
    if str(active_plan.get("learning_goal_hash") or "") != learning_goal_hash(learning_goal):
        return "learning_goal_changed"
    if str(active_plan.get("knowledge_graph_version") or "") != knowledge_graph_version:
        return "knowledge_graph_version_changed"
    return "active_plan_invalid"


def _reuse_persisted_plan(
    *,
    state: StateDict,
    runtime: Runtime[WorkflowContext] | None,
    profile: dict[str, Any],
    active_plan: dict[str, Any],
    knowledge_graph_version: str,
) -> dict[str, Any]:
    path = [
        LearningPathItem.model_validate(item)
        for item in active_plan["nodes"]
        if isinstance(item, dict)
    ]
    progress = dict(active_plan["progress"])
    pl_map = _knowledge_pl_map(profile)
    weak_texts = profile.get("weak_points") or []
    weak_node_ids = {
        item.node_id
        for item in path
        if any(weak in item.node_id or weak in item.node_name for weak in weak_texts)
    }
    path = [
        item.model_copy(
            update={
                "difficulty_cap": _difficulty_cap_for(
                    item.node_id, pl_map, weak_node_ids
                )
            }
        )
        for item in path
    ]
    serialized_path = [item.model_dump() for item in path]
    dual_axis = build_dual_axis_snapshot(
        profile=profile,
        session_id=state["session_id"],
    )
    question_scope = normalize_question_scope(
        learning_path=serialized_path,
        progress=progress,
        proposed_scope={},
        mastery_snapshot=pl_map,
        weak_node_ids=weak_node_ids,
        confusion_risk=_confusion_review_risk(
            dual_axis, progress.get("current_node")
        ),
    )
    teaching_context = build_teaching_context(
        learning_path=serialized_path,
        progress=progress,
        question_scope=question_scope,
    )
    updated_profile = deepcopy(profile)
    updated_dimensions = dict(updated_profile.get("five_dimensions") or {})
    updated_dimensions["progress"] = progress
    updated_profile["five_dimensions"] = updated_dimensions
    save_profile_snapshot(runtime, state, updated_profile, source="planner")
    selected = progress.get("current_node")
    return {
        "learner_profile": updated_profile,
        "learning_path": serialized_path,
        "dual_axis_snapshot": dual_axis,
        "teaching_context": teaching_context,
        "path_decision": {
            "current_node_id": selected,
            "algorithm": "persisted_plan",
            "question_scope": question_scope,
            "iteration_directive": _default_iteration_directive(),
            "completed_node_ids": progress["completed_nodes"],
            "pending_node_ids": progress["pending_nodes"],
            "roadmap_node_ids": [item["node_id"] for item in serialized_path],
            "knowledge_graph_version": knowledge_graph_version,
            "plan_id": active_plan["plan_id"],
            "plan_version": active_plan["plan_version"],
            "plan_reused": True,
            "lesson_scope": {
                "primary_teaching_node_id": selected,
                "review_node_ids": [
                    item["node_id"]
                    for item in question_scope["backward_review"]
                    if item["node_id"] != selected
                ],
                "forward_probe_node_ids": [
                    item["node_id"] for item in question_scope["forward_probe"]
                ],
            },
        },
        "events": [completed_event("planner", "resumed persisted learning plan")],
    }


def _parse_planner_plan(
    raw: object,
    *,
    known_node_ids: set[str],
) -> dict[str, Any]:
    """Parse and deterministically guard the schema-valid Planner proposal."""

    if not isinstance(raw, dict):
        raise ValueError("Planner proposal is not an object")
    nodes = raw.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Planner proposal has no path nodes")
    parsed: list[LearningPathItem] = []
    seen_node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Planner path contains a non-object node")
        item = LearningPathItem.model_validate(
            {k: v for k, v in node.items() if k in LearningPathItem.model_fields}
        )
        if item.node_id not in known_node_ids:
            raise ValueError(f"Planner invented unknown node_id: {item.node_id}")
        if item.node_id in seen_node_ids:
            raise ValueError(f"Planner repeated node_id: {item.node_id}")
        missing_prerequisites = [
            prerequisite
            for prerequisite in item.prerequisites
            if prerequisite not in seen_node_ids
        ]
        if missing_prerequisites:
            raise ValueError(
                f"Planner node {item.node_id} has prerequisites that do not appear earlier: "
                f"{missing_prerequisites}"
            )
        parsed.append(item)
        seen_node_ids.add(item.node_id)

    question_scope = raw.get("question_scope") or {}
    if isinstance(question_scope, dict):
        for items in question_scope.values():
            if not isinstance(items, list):
                continue
            for item in items:
                node_id = item.get("node_id") if isinstance(item, dict) else None
                if node_id not in known_node_ids:
                    raise ValueError(f"Planner question scope uses unknown node_id: {node_id}")

    return {
        "learning_path": parsed,
        "question_scope": question_scope,
        "iteration_directive": raw.get("iteration_directive") or {},
    }


def build_planner_node(llm_client: LLMClient) -> Node:
    def planner_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        profile = _build_profile(state, runtime)
        learning_goal = str(profile.get("learning_goal") or state["user_input"])

        knowledge = load_knowledge_dag()
        knowledge_graph_version = str(knowledge.get("version") or "unknown")
        store = getattr(runtime, "store", None) if runtime is not None else None
        learner_id = _runtime_learner_id(runtime)
        active_plan_reader = getattr(store, "active_learning_plan", None)
        active_plan = (
            active_plan_reader(learner_id)
            if learner_id and callable(active_plan_reader)
            else None
        )
        if reusable_active_plan(
            active_plan,
            learning_goal=learning_goal,
            knowledge_graph_version=knowledge_graph_version,
        ):
            assert isinstance(active_plan, dict)
            try:
                return _reuse_persisted_plan(
                    state=state,
                    runtime=runtime,
                    profile=profile,
                    active_plan=active_plan,
                    knowledge_graph_version=knowledge_graph_version,
                )
            except (KeyError, TypeError, ValueError) as exc:
                _LOGGER.warning(
                    "Persisted learning plan is invalid; replanning: %s",
                    _planner_fallback_reason(exc),
                )
        plan_metadata: dict[str, Any] = {}
        confusion = load_confusion_pairs()
        planner_graph = {
            "knowledge_graph": knowledge,
            "confusion_graph": confusion,
        }
        deterministic_path = [
            LearningPathItem.model_validate(it)
            for it in compute_learning_path(
                profile=profile,
                learning_goal=learning_goal,
                max_nodes=max(1, len(knowledge.get("nodes", []))),
            )
        ]
        deterministic_candidate = [
            {
                "node_id": item.node_id,
                "node_name": item.node_name,
                "duration_min": item.duration_min,
                "strategy": item.strategy,
                "prerequisites": item.prerequisites,
                "difficulty_cap": item.difficulty_cap,
            }
            for item in deterministic_path
        ]
        user_text = (
            "# 双知识图（编排层注入，只读不改）\n"
            f"{json.dumps(planner_graph, ensure_ascii=False, separators=(',', ':'))}\n\n"
            "# 确定性 A* 完整候选路线（可优化，但必须保留完整、拓扑合法的学习路线）\n"
            f"{json.dumps(deterministic_candidate, ensure_ascii=False, separators=(',', ':'))}\n\n"
            "# 学习者画像\n"
            f"{json.dumps(profile, ensure_ascii=False, separators=(',', ':'))}\n\n"
            f"# 学习目标\n{learning_goal}"
        )

        fallback_reason: str | None = None
        try:
            proposal = generate_validated_json(
                llm_client,
                messages=[
                    LLMMessage(role="system", content=_PLANNER_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_text),
                ],
                temperature=agent_temperature("planner", 0.0),
                agent="planner",
                output_model=PlannerAgentResult,
            )
            known_node_ids = {
                str(node.get("node_id"))
                for node in knowledge.get("nodes", [])
                if isinstance(node, dict) and node.get("node_id")
            }
            plan = _parse_planner_plan(
                proposal.model_dump(),
                known_node_ids=known_node_ids,
            )
        except Exception as exc:  # noqa: BLE001 - LLM failure → deterministic fallback
            fallback_reason = _planner_fallback_reason(exc)
            _LOGGER.warning(
                "Planner Agent proposal failed; using deterministic A* fallback: %s",
                fallback_reason,
                exc_info=True,
            )
            plan = None

        # 难度上限按 P(L) 分阶确定性推导，保证 artifact 始终带『资源难度匹配曲线』数据
        pl_map = _knowledge_pl_map(profile)

        if plan is None:
            path = deterministic_path
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
        serialized_path = [it.model_dump() for it in path]
        five_dimensions = profile.get("five_dimensions")
        existing_progress = (
            five_dimensions.get("progress")
            if isinstance(five_dimensions, dict)
            else None
        )
        progress = initialize_learning_progress(
            existing_progress=existing_progress,
            learning_path=serialized_path,
            mastery_snapshot=pl_map,
        )
        plan_creator = getattr(store, "create_learning_plan", None)
        reason = _replan_reason(
            active_plan,
            learning_goal=learning_goal,
            knowledge_graph_version=knowledge_graph_version,
        )
        if learner_id and callable(plan_creator):
            persisted_plan = cast(
                dict[str, Any],
                plan_creator(
                    learner_id=learner_id,
                    source_session_id=state["session_id"],
                    learning_goal=learning_goal,
                    learning_goal_hash=learning_goal_hash(learning_goal),
                    knowledge_graph_version=knowledge_graph_version,
                    nodes=serialized_path,
                    progress=progress,
                    replan_reason=reason,
                ),
            )
            plan_metadata = {
                "plan_id": persisted_plan["plan_id"],
                "plan_version": persisted_plan["plan_version"],
                "plan_reused": False,
                "replan_reason": reason,
            }
        question_scope = normalize_question_scope(
            learning_path=serialized_path,
            progress=progress,
            proposed_scope=question_scope,
            mastery_snapshot=pl_map,
            weak_node_ids=weak_node_ids,
            confusion_risk=_confusion_review_risk(
                dual_axis, progress.get("current_node")
            ),
        )
        teaching_context = build_teaching_context(
            learning_path=serialized_path,
            progress=progress,
            question_scope=question_scope,
        )
        selected = progress.get("current_node")

        updated_profile = deepcopy(profile)
        updated_dimensions = dict(updated_profile.get("five_dimensions") or {})
        updated_dimensions["progress"] = progress
        updated_profile["five_dimensions"] = updated_dimensions
        save_profile_snapshot(
            runtime,
            state,
            updated_profile,
            source="planner",
        )
        return {
            "learner_profile": updated_profile,
            "learning_path": serialized_path,
            "dual_axis_snapshot": dual_axis,
            "teaching_context": teaching_context,
            "path_decision": {
                "current_node_id": selected,
                "algorithm": algorithm,
                "question_scope": question_scope,
                "iteration_directive": iteration_directive,
                "completed_node_ids": progress["completed_nodes"],
                "pending_node_ids": progress["pending_nodes"],
                "roadmap_node_ids": [item["node_id"] for item in serialized_path],
                "knowledge_graph_version": knowledge_graph_version,
                "lesson_scope": {
                    "primary_teaching_node_id": selected,
                    "review_node_ids": [
                        item["node_id"] for item in question_scope["backward_review"]
                        if item["node_id"] != selected
                    ],
                    "forward_probe_node_ids": [
                        item["node_id"] for item in question_scope["forward_probe"]
                    ],
                },
                **plan_metadata,
                **({"fallback_reason": fallback_reason} if fallback_reason else {}),
            },
            "events": [completed_event("planner", f"planned learning path ({algorithm})")],
        }

    return planner_node
