"""Planner Agent node."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, cast

from langgraph.runtime import Runtime

from backend.app.agents.common import Node, generate_validated_json_stream, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.learning_path import (
    build_dual_axis_snapshot,
    compute_learning_path,
    load_confusion_pairs,
    load_knowledge_dag,
    recommend_target_nodes_for_goal,
)
from backend.app.curriculum.learning_plan import learning_goal_hash
from backend.app.curriculum.learning_progress import (
    build_teaching_context,
    initialize_learning_progress,
    normalize_question_scope,
    profile_progress_snapshot,
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
            raise ValueError("Planner replace proposal must include non-empty path nodes")
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


def _route_fingerprint(path: list[dict[str, Any]]) -> str:
    """Fingerprint the roadmap structure, not per-round teaching adaptation.

    Difficulty caps and teaching strategies are recalculated from the latest BKT
    snapshot on every teach session. They affect this lesson's presentation, but
    changing them must not create a new persisted roadmap version. The fingerprint
    therefore tracks only the ordered node/dependency structure that defines the
    route itself.
    """
    payload = [
        {key: item.get(key) for key in ("node_id", "prerequisites")}
        for item in path
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _planner_path_payload(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": str(item["node_id"]),
            "node_name": str(item["node_name"]),
            "duration_min": min(240, max(1, int(item.get("duration_min") or 1))),
            "strategy": str(item.get("strategy") or "按知识依赖学习"),
            "prerequisites": [str(value) for value in item.get("prerequisites") or []],
            "difficulty_cap": str(item.get("difficulty_cap") or "L2"),
        }
        for item in candidates
    ]


def _candidate_target_ids(path: list[LearningPathItem]) -> set[str]:
    route_ids = {item.node_id for item in path}
    return {
        item.node_id
        for item in path
        if not any(item.node_id in candidate.prerequisites for candidate in path if candidate.node_id in route_ids)
    }


def _required_goal_target_ids(
    recommended_targets: list[str],
    candidate_path: list[LearningPathItem],
) -> set[str]:
    candidate_ids = {item.node_id for item in candidate_path}
    recommended_ids = {str(target) for target in recommended_targets if str(target) in candidate_ids}
    return recommended_ids or _candidate_target_ids(candidate_path)


def _finalize_planner_route(
    *,
    plan_action: str,
    candidate_path: list[LearningPathItem],
    proposed_path: list[LearningPathItem],
    required_target_ids: set[str] | None = None,
) -> tuple[list[LearningPathItem], str]:
    if plan_action == "keep":
        return candidate_path, "candidate_route_keep"
    if plan_action == "replace":
        proposed_ids = {item.node_id for item in proposed_path}
        missing_targets = (required_target_ids or _candidate_target_ids(candidate_path)) - proposed_ids
        if missing_targets:
            raise ValueError(
                "Planner replace route must cover candidate targets: "
                + ", ".join(sorted(missing_targets))
            )
        return proposed_path, "llm_adjusted_route_replace"
    raise ValueError(f"unsupported Planner action: {plan_action}")


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
        recommended_targets = recommend_target_nodes_for_goal(learning_goal, knowledge, top_k=8)
        active_route = active_plan.get("nodes") if isinstance(active_plan, dict) else None
        algorithm_candidates = compute_learning_path(
            profile=profile,
            learning_goal=learning_goal,
            mastery_snapshot=_knowledge_pl_map(profile),
            current_route=active_route,
        )
        if not algorithm_candidates:
            raise ValueError("Planner deterministic candidate route is empty")
        candidate_payload = _planner_path_payload(algorithm_candidates)
        # 将路线决策所需的动态输入放在前面。静态 DAG/混淆对体积较大，必须排在
        # 动态输入之后，避免通用上下文保护逻辑在超限时只保留静态数据。
        user_text = (
            "# 学习目标\n" + learning_goal
            + "\n# 学习者画像与掌握度\n" + json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
            + "\n# 当前活动计划（可为空）\n" + json.dumps(active_plan, ensure_ascii=False, separators=(",", ":"), default=str)
            + "\n# 算法候选路线（keep 接受此路线；replace 必须返回完整调整路线）\n"
            + json.dumps(candidate_payload, ensure_ascii=False, separators=(",", ":"))
            + "\n# 基于学习目标推荐的目标原子节点（供参考，请优先在路径中纳入）\n"
            + json.dumps(recommended_targets, ensure_ascii=False)
            + "\n# 静态知识 DAG\n" + json.dumps(knowledge, ensure_ascii=False, separators=(",", ":"))
            + "\n# 静态易混淆对\n" + json.dumps(confusion, ensure_ascii=False, separators=(",", ":"))
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
        node_knowledge_points = {
            str(node["node_id"]): [
                str(item.get("point") or "")
                for item in node.get("knowledge_points", [])
                if isinstance(item, dict) and item.get("point")
            ]
            for node in knowledge.get("nodes", [])
            if isinstance(node, dict) and node.get("node_id")
        }

        def validate_planner_semantics(result: PlannerAgentResult) -> None:
            parsed = _parse_planner_plan(
                result.model_dump(),
                known_node_ids=known_ids,
                canonical_names=canonical_names,
                static_prerequisites=static_prerequisites,
            )
            if parsed["plan_action"] == "replace":
                candidate_path_for_validation = [
                    LearningPathItem.model_validate(item) for item in candidate_payload
                ]
                required_target_ids = _required_goal_target_ids(
                    recommended_targets,
                    candidate_path_for_validation,
                )
                _finalize_planner_route(
                    plan_action="replace",
                    candidate_path=candidate_path_for_validation,
                    proposed_path=parsed["learning_path"],
                    required_target_ids=required_target_ids,
                )

        proposal = generate_validated_json_stream(
            llm_client,
            messages=[
                LLMMessage(role="system", content=_PLANNER_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_text),
            ],
            temperature=agent_temperature("planner", 0.0),
            agent="planner",
            output_model=PlannerAgentResult,
            semantic_validate=validate_planner_semantics,
            schema_name="PlannerAgentResult",
        )
        plan = _parse_planner_plan(
            proposal.model_dump(),
            known_node_ids=known_ids,
            canonical_names=canonical_names,
            static_prerequisites=static_prerequisites,
        )
        candidate_path = [LearningPathItem.model_validate(item) for item in candidate_payload]
        path, route_source = _finalize_planner_route(
            plan_action=plan["plan_action"],
            candidate_path=candidate_path,
            proposed_path=plan["learning_path"],
            required_target_ids=_required_goal_target_ids(recommended_targets, candidate_path),
        )
        progress = None
        pl_map = _knowledge_pl_map(profile)
        # ``completed_nodes`` is a teaching-progress ledger.  Do not import the
        # diagnostic/profile progress projection here: CAT/questionnaire/BKT
        # evidence can guide planning and review, but cannot complete a node.
        historical_reader = getattr(store, "historical_completed_node_ids", None)
        historical_completed = (
            historical_reader(learner_id)
            if learner_id and callable(historical_reader)
            else []
        )
        historical_session_reader = getattr(store, "historical_completion_sessions", None)
        historical_sessions = (
            historical_session_reader(learner_id)
            if learner_id and callable(historical_session_reader)
            else {}
        )
        inherited_progress = (
            dict(active_plan["progress"])
            if isinstance(active_plan, dict) and isinstance(active_plan.get("progress"), dict)
            else {}
        )
        inherited_completed = [
            str(node_id) for node_id in inherited_progress.get("completed_nodes", [])
        ]
        inherited_sessions = inherited_progress.get("completion_sessions", {})
        if not isinstance(inherited_sessions, dict):
            inherited_sessions = {}
        inherited_progress["completion_sessions"] = {
            str(node_id): str(session_id)
            for node_id, session_id in inherited_sessions.items()
            if node_id in inherited_completed and session_id
        }
        for node_id in historical_completed:
            node_id = str(node_id)
            session_id = historical_sessions.get(node_id)
            if session_id and node_id not in inherited_completed:
                inherited_completed.append(node_id)
                inherited_progress["completion_sessions"][node_id] = str(session_id)
        inherited_progress["completed_nodes"] = inherited_completed
        weak_texts = [str(value) for value in profile.get("weak_points") or []]
        weak_ids = {item.node_id for item in path if any(value in item.node_id or value in item.node_name for value in weak_texts)}
        path = [
            item.model_copy(
                update={
                    "difficulty_cap": _difficulty_cap_for(item.node_id, pl_map, weak_ids),
                    "knowledge_points": node_knowledge_points.get(item.node_id, []),
                }
            )
            for item in path
        ]
        serialized_path = [item.model_dump() for item in path]
        route_fingerprint = _route_fingerprint(serialized_path)
        active_fingerprint = ""
        if isinstance(active_plan, dict):
            active_fingerprint = _route_fingerprint(
                [item for item in active_plan.get("nodes", []) if isinstance(item, dict)]
            )
        route_changed = not isinstance(active_plan, dict) or active_fingerprint != route_fingerprint
        if progress is None:
            dimensions = profile.get("five_dimensions") or {}
            progress = initialize_learning_progress(
                existing_progress=inherited_progress,
                learning_path=serialized_path,
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
        plan_metadata: dict[str, Any] = {
            "plan_action": plan["plan_action"],
            "decision_reason": plan["decision_reason"],
            "route_fingerprint": route_fingerprint,
            "route_changed": route_changed,
        }
        create_plan = getattr(store, "create_learning_plan", None)
        if learner_id and route_changed and callable(create_plan):
            persisted = cast(dict[str, Any], create_plan(
                learner_id=learner_id,
                source_session_id=state["session_id"],
                learning_goal=learning_goal,
                learning_goal_hash=learning_goal_hash(learning_goal),
                knowledge_graph_version=graph_version,
                nodes=serialized_path,
                progress=progress,
                replan_reason=plan["decision_reason"] or f"planner_{plan['plan_action']}",
                route_source=route_source,
                route_fingerprint=route_fingerprint,
                decision_kind=plan["plan_action"],
            ))
            plan_metadata.update({"plan_id": persisted["plan_id"], "plan_version": persisted["plan_version"]})
        elif isinstance(active_plan, dict):
            plan_metadata.update({"plan_id": active_plan.get("plan_id"), "plan_version": active_plan.get("plan_version")})
        updated_profile = deepcopy(profile)
        dimensions = dict(updated_profile.get("five_dimensions") or {})
        dimensions["progress"] = profile_progress_snapshot(progress)
        updated_profile["five_dimensions"] = dimensions
        save_profile_snapshot(runtime, state, updated_profile, source="planner")
        roadmap_ids = [item["node_id"] for item in serialized_path]
        roadmap_id_set = set(roadmap_ids)
        roadmap_targets = [
            node_id
            for node_id in roadmap_ids
            if not any(node_id in item.prerequisites for item in path if item.node_id in roadmap_id_set)
        ]
        decision = {
            "current_node_id": selected,
            "path_start_node_id": roadmap_ids[0] if roadmap_ids else None,
            "path_target_node_ids": roadmap_targets,
            "path_target_nodes": [
                {"node_id": item.node_id, "node_name": item.node_name}
                for item in path
                if item.node_id in roadmap_targets
            ],
            "roadmap_node_count": len(roadmap_ids),
            "algorithm": route_source,
            "route_source": route_source,
            "route_fingerprint": route_fingerprint,
            "route_changed": route_changed,
            "question_scope": scope,
            "iteration_directive": plan["iteration_directive"],
            "completed_node_ids": progress.get("completed_nodes", []),
            "pending_node_ids": progress.get("pending_nodes", []),
            "roadmap_node_ids": roadmap_ids,
            "knowledge_graph_version": graph_version,
            "lesson_scope": {
                "primary_teaching_node_id": selected,
                "review_node_ids": [item["node_id"] for item in scope["backward_review"] if item["node_id"] != selected],
                "forward_probe_node_ids": [item["node_id"] for item in scope["forward_probe"]],
            },
            **plan_metadata,
        }
        recorder = getattr(store, "record_learning_plan_decision", None)
        if learner_id and callable(recorder) and (
            not route_changed or not callable(create_plan)
        ):
            history = recorder(
                learner_id=learner_id,
                session_id=state["session_id"],
                plan_id=plan_metadata.get("plan_id"),
                previous_plan_id=(active_plan or {}).get("plan_id")
                if route_changed and isinstance(active_plan, dict)
                else None,
                decision_kind="initial" if not isinstance(active_plan, dict) else plan["plan_action"],
                outcome="created" if route_changed else "no_change",
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
                decision_key=f"{state['session_id']}:planner:{plan['plan_action']}:{route_fingerprint}",
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
