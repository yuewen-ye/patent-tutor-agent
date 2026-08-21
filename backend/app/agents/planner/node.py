"""Planner Agent node."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, cast

from langgraph.runtime import Runtime

from backend.app.agents.common import Node, generate_validated_json, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    load_confusion_pairs,
    load_knowledge_dag,
)
from backend.app.curriculum.learning_plan import learning_goal_hash
from backend.app.curriculum.learning_progress import (
    build_teaching_context,
    initialize_learning_progress,
    normalize_question_scope,
)
from backend.app.learner_memory.memory import load_profile_memories, save_profile_snapshot
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import (
    LearningPathItem,
    PlannerAgentResult,
    StateDict,
    completed_event,
)

_PLANNER_SYSTEM_PROMPT = load_prompt(__file__, "system.md")


def _knowledge_pl_map(profile: dict[str, Any]) -> dict[str, Any]:
    dimensions = profile.get("five_dimensions") or {}
    knowledge = dict(dimensions.get("knowledge", {}) or {})
    mastery = profile.get("mastery") or {}
    if isinstance(mastery, dict):
        for node_id, probability in mastery.items():
            if probability is not None:
                current = dict(knowledge.get(str(node_id), {}) or {})
                current["pl"] = float(probability)
                knowledge[str(node_id)] = current
    return knowledge


def _difficulty_cap_for(node_id: str, pl_map: dict[str, Any], weak_node_ids: set[str]) -> str:
    if node_id in weak_node_ids:
        return "L3"
    value = pl_map.get(node_id) or {}
    probability = value.get("pl") if isinstance(value, dict) else value
    if probability is None:
        return "L2"
    if probability < 0.15:
        return "L1"
    if probability < 0.30:
        return "L2"
    return "L3"


def _confusion_review_risk(dual_axis: dict[str, Any], current_node_id: str | None) -> dict[str, float]:
    current = str(current_node_id or "")
    risks: dict[str, float] = {}
    for pair in dual_axis.get("confusion_axis", []):
        if not isinstance(pair, dict) or not pair.get("is_active"):
            continue
        ids = {str(pair.get("node_a") or ""), str(pair.get("node_b") or "")}
        ids.update(str(value) for value in pair.get("related_nodes") or [] if value)
        ids.discard("")
        if current not in ids:
            continue
        try:
            risk = max(0.0, min(1.0, float(pair.get("learner_risk") or 0.0)))
        except (TypeError, ValueError):
            risk = 0.0
        for node_id in ids - {current}:
            risks[node_id] = max(risks.get(node_id, 0.0), risk)
    return risks


def _build_profile(state: StateDict, runtime: Runtime[WorkflowContext] | None) -> dict[str, Any]:
    historical = load_profile_memories(runtime, limit=1)
    profile = dict(historical[0] if historical else state.get("learner_profile", {}))
    store = getattr(runtime, "store", None) if runtime is not None else None
    learner_id = _runtime_learner_id(runtime)
    reader = getattr(store, "mastery", None)
    if learner_id and callable(reader):
        profile["mastery"] = reader(learner_id)
    return profile


def _runtime_learner_id(runtime: Runtime[WorkflowContext] | None) -> str | None:
    if runtime is None:
        return None
    context = runtime.context
    value = context.get("learner_id") if isinstance(context, dict) else context.learner_id
    return str(value) if value else None


def _static_pairs_for_node(confusion: dict[str, Any], node_id: str | None) -> list[dict[str, Any]]:
    current = str(node_id or "")
    result = []
    for pair in confusion.get("confusion_pairs", []):
        if not isinstance(pair, dict):
            continue
        ids = {str(pair.get("node_a") or ""), str(pair.get("node_b") or "")}
        ids.update(str(value) for value in pair.get("related_nodes") or [] if value)
        if current and current in ids:
            result.append(dict(pair))
    return result


def _parse_planner_plan(
    raw: dict[str, Any],
    *,
    known_node_ids: set[str],
    canonical_names: dict[str, str],
    static_prerequisites: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    action = raw.get("plan_action")
    if action not in {"keep", "replace"}:
        raise ValueError("Planner plan_action must be keep or replace")
    nodes = raw.get("nodes")
    parsed: list[LearningPathItem] = []
    if action == "keep" and nodes is not None:
        raise ValueError("Planner keep proposal must not include path nodes")
    if action == "replace":
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("Planner replace proposal has no path nodes")
        selected: dict[str, dict[str, Any]] = {}
        original_order: dict[str, int] = {}
        for index, raw_node in enumerate(nodes):
            if not isinstance(raw_node, dict):
                raise TypeError("Planner path contains a non-object node")
            node_id = str(raw_node.get("node_id") or "")
            if node_id not in known_node_ids:
                raise ValueError(f"Planner invented unknown node_id: {node_id}")
            if node_id in selected:
                raise ValueError(f"Planner repeated node_id: {node_id}")
            selected[node_id] = dict(raw_node)
            original_order[node_id] = index

        def prerequisites_for(node_id: str) -> list[str]:
            if static_prerequisites is not None:
                return list(static_prerequisites.get(node_id, []))
            proposed = selected[node_id].get("prerequisites") or []
            return [str(value) for value in proposed]

        missing_prerequisites = {
            node_id: [value for value in prerequisites_for(node_id) if value not in selected]
            for node_id in selected
        }
        missing_prerequisites = {
            node_id: values for node_id, values in missing_prerequisites.items() if values
        }
        if missing_prerequisites:
            node_id, missing = next(iter(missing_prerequisites.items()))
            raise ValueError(f"Planner node {node_id} missing static prerequisites: {missing}")

        remaining = set(selected)
        emitted: set[str] = set()
        while remaining:
            ready = sorted(
                (
                    node_id
                    for node_id in remaining
                    if set(prerequisites_for(node_id)).issubset(emitted)
                ),
                key=original_order.__getitem__,
            )
            if not ready:
                raise ValueError("Planner selected nodes contain a prerequisite cycle")
            for node_id in ready:
                node = {
                    **selected[node_id],
                    "node_name": canonical_names[node_id],
                    "prerequisites": prerequisites_for(node_id),
                }
                parsed.append(
                    LearningPathItem.model_validate(
                        {
                            key: value
                            for key, value in node.items()
                            if key in LearningPathItem.model_fields
                        }
                    )
                )
                emitted.add(node_id)
                remaining.remove(node_id)
    scope = raw.get("question_scope")
    if not isinstance(scope, dict):
        raise TypeError("Planner question_scope must be an object")
    for values in scope.values():
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and item.get("node_id") not in known_node_ids:
                    raise ValueError(f"Planner question scope uses unknown node_id: {item.get('node_id')}")
    return {
        "plan_action": action,
        "decision_reason": str(raw.get("decision_reason") or ""),
        "learning_path": parsed,
        "question_scope": scope,
        "iteration_directive": raw.get("iteration_directive") or {},
        "teaching_guidance": raw.get("teaching_guidance") or {},
    }


def build_planner_node(llm_client: LLMClient) -> Node:
    def planner_node(state: StateDict, runtime: Runtime[WorkflowContext] | None = None) -> dict[str, Any]:
        profile = _build_profile(state, runtime)
        learning_goal = str(profile.get("learning_goal") or state["user_input"])
        knowledge = load_knowledge_dag()
        confusion = load_confusion_pairs()
        graph_version = str(knowledge.get("version") or "unknown")
        store = getattr(runtime, "store", None) if runtime is not None else None
        learner_id = _runtime_learner_id(runtime)
        reader = getattr(store, "active_learning_plan", None)
        active_plan = reader(learner_id) if learner_id and callable(reader) else None
        user_text = (
            "# 静态知识 DAG\n" + json.dumps(knowledge, ensure_ascii=False, separators=(",", ":"))
            + "\n# 静态易混淆对\n" + json.dumps(confusion, ensure_ascii=False, separators=(",", ":"))
            + "\n# 学习者画像与掌握度\n" + json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
            + "\n# 当前活动计划（可为空）\n" + json.dumps(active_plan, ensure_ascii=False, separators=(",", ":"), default=str)
            + f"\n# 学习目标\n{learning_goal}"
        )
        known_ids = {
            str(node["node_id"])
            for node in knowledge.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        }
        canonical_names = {
            str(node["node_id"]): str(node.get("node_name") or node["node_id"])
            for node in knowledge.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        }
        static_prerequisites = {
            str(node["node_id"]): [str(value) for value in node.get("predecessors", [])]
            for node in knowledge.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        }

        def validate_planner_semantics(result: PlannerAgentResult) -> None:
            _parse_planner_plan(
                result.model_dump(),
                known_node_ids=known_ids,
                canonical_names=canonical_names,
                static_prerequisites=static_prerequisites,
            )

        proposal = generate_validated_json(
            llm_client,
            messages=[
                LLMMessage(role="system", content=_PLANNER_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_text),
            ],
            temperature=agent_temperature("planner", 0.0),
            agent="planner",
            output_model=PlannerAgentResult,
            semantic_validate=validate_planner_semantics,
        )
        plan = _parse_planner_plan(
            proposal.model_dump(),
            known_node_ids=known_ids,
            canonical_names=canonical_names,
            static_prerequisites=static_prerequisites,
        )
        if plan["plan_action"] == "keep":
            if not isinstance(active_plan, dict) or not active_plan.get("nodes"):
                raise ValueError("Planner cannot keep a missing active plan")
            path = [LearningPathItem.model_validate(item) for item in active_plan["nodes"] if isinstance(item, dict)]
            progress = dict(active_plan.get("progress") or {})
        else:
            path = plan["learning_path"]
            progress = None
        pl_map = _knowledge_pl_map(profile)
        weak_texts = [str(value) for value in profile.get("weak_points") or []]
        weak_ids = {item.node_id for item in path if any(value in item.node_id or value in item.node_name for value in weak_texts)}
        path = [item.model_copy(update={"difficulty_cap": _difficulty_cap_for(item.node_id, pl_map, weak_ids)}) for item in path]
        serialized_path = [item.model_dump() for item in path]
        if progress is None:
            dimensions = profile.get("five_dimensions") or {}
            progress = initialize_learning_progress(
                existing_progress=dimensions.get("progress") if isinstance(dimensions, dict) else None,
                learning_path=serialized_path,
                mastery_snapshot=pl_map,
            )
        dual_axis = build_dual_axis_snapshot(profile=profile, session_id=state["session_id"])
        scope = normalize_question_scope(
            learning_path=serialized_path,
            progress=progress,
            proposed_scope=plan["question_scope"],
            mastery_snapshot=pl_map,
            weak_node_ids=weak_ids,
            confusion_risk=_confusion_review_risk(dual_axis, progress.get("current_node")),
        )
        selected = str(progress.get("current_node") or "") or None
        guidance = dict(plan["teaching_guidance"])
        teaching_context = build_teaching_context(
            learning_path=serialized_path,
            progress=progress,
            question_scope=scope,
            static_confusion_pairs=_static_pairs_for_node(confusion, selected),
            planner_guidance=guidance,
            iteration_directive=plan["iteration_directive"],
        )
        plan_metadata: dict[str, Any] = {"plan_action": plan["plan_action"], "decision_reason": plan["decision_reason"]}
        if learner_id and callable(getattr(store, "create_learning_plan", None)) and plan["plan_action"] == "replace":
            persisted = cast(dict[str, Any], store.create_learning_plan(
                learner_id=learner_id,
                source_session_id=state["session_id"],
                learning_goal=learning_goal,
                learning_goal_hash=learning_goal_hash(learning_goal),
                knowledge_graph_version=graph_version,
                nodes=serialized_path,
                progress=progress,
                replan_reason=plan["decision_reason"] or "planner_replace",
            ))
            plan_metadata.update({"plan_id": persisted["plan_id"], "plan_version": persisted["plan_version"]})
        elif isinstance(active_plan, dict):
            plan_metadata.update({"plan_id": active_plan.get("plan_id"), "plan_version": active_plan.get("plan_version")})
        updated_profile = deepcopy(profile)
        dimensions = dict(updated_profile.get("five_dimensions") or {})
        dimensions["progress"] = progress
        updated_profile["five_dimensions"] = dimensions
        save_profile_snapshot(runtime, state, updated_profile, source="planner")
        decision = {
            "current_node_id": selected,
            "algorithm": "llm_planner",
            "question_scope": scope,
            "iteration_directive": plan["iteration_directive"],
            "completed_node_ids": progress.get("completed_nodes", []),
            "pending_node_ids": progress.get("pending_nodes", []),
            "roadmap_node_ids": [item["node_id"] for item in serialized_path],
            "knowledge_graph_version": graph_version,
            "lesson_scope": {
                "primary_teaching_node_id": selected,
                "review_node_ids": [item["node_id"] for item in scope["backward_review"] if item["node_id"] != selected],
                "forward_probe_node_ids": [item["node_id"] for item in scope["forward_probe"]],
            },
            **plan_metadata,
        }
        recorder = getattr(store, "record_learning_plan_decision", None)
        if learner_id and callable(recorder) and not (
            plan["plan_action"] == "replace"
            and callable(getattr(store, "create_learning_plan", None))
        ):
            history = recorder(
                learner_id=learner_id,
                session_id=state["session_id"],
                plan_id=plan_metadata.get("plan_id"),
                previous_plan_id=(active_plan or {}).get("plan_id")
                if plan["plan_action"] == "replace" and isinstance(active_plan, dict)
                else None,
                decision_kind="replace" if plan["plan_action"] == "replace" else "keep",
                outcome="created" if plan["plan_action"] == "replace" else "kept",
                reason_code=plan["decision_reason"] or f"planner_{plan['plan_action']}",
                learning_goal_hash=learning_goal_hash(learning_goal),
                knowledge_graph_version=graph_version,
                from_plan_version=(active_plan or {}).get("plan_version")
                if isinstance(active_plan, dict)
                else None,
                to_plan_version=plan_metadata.get("plan_version"),
                from_current_node_id=(active_plan or {}).get("progress", {}).get("current_node")
                if isinstance(active_plan, dict)
                else None,
                to_current_node_id=selected,
                progress_before=(active_plan or {}).get("progress")
                if isinstance(active_plan, dict)
                else None,
                progress_after=progress,
                path_decision=decision,
                teaching_context=teaching_context,
                decision_key=f"{state['session_id']}:planner:{plan['plan_action']}",
            )
            decision["planning_history_id"] = history.get("decision_id")
        return {
            "learner_profile": updated_profile,
            "learning_path": serialized_path,
            "dual_axis_snapshot": dual_axis,
            "teaching_context": teaching_context,
            "path_decision": decision,
            "events": [completed_event("planner", f"planned learning path ({plan['plan_action']})")],
        }

    return planner_node
