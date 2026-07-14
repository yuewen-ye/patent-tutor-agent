"""LangGraph workflow for the real five-Agent system."""

from __future__ import annotations

import inspect
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

from backend.app.agent_runtime_config import agent_top_k
from backend.app.agents import Node, build_agent_nodes
from backend.app.artifacts import attach_markdown_artifact, write_field_artifact, write_manifest
from backend.app.core.llm import AgentLLMRouter, DefaultLLMClient, LLMClient
from backend.app.memory import save_history_snapshot
from backend.app.retrieval_selector import retrieve_context
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import AgentEvent, StateDict, completed_event
from backend.app.workflow_logging import write_workflow_log

WorkflowUpdateSink = Callable[[dict[str, Any]], None]
WorkflowEventSink = Callable[[list[dict[str, Any]]], None]
_ACCEPTED_JUDGE_DECISIONS = {"accept"}


def judge_route(state: StateDict) -> str:
    decision = _judge_decision(state.get("judge_report"))
    if decision == "accept":
        return "publish_final_learning"
    judge_round = int(state.get("judge_round", 1))
    max_rounds = int(state.get("max_debate_rounds", 3))
    if judge_round < max_rounds:
        return "revise_integration"
    return "quality_gate_failed"


def publish_final_learning_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    draft = state.get("expert_a_draft", {})
    path = state.get("learning_path", [])
    exercises = (draft.get("exercises") or []) if isinstance(draft, dict) else []
    answer_key = [
        {
            "question_id": item.get("question_id"),
            "answer": item.get("answer"),
            "explanation": item.get("explanation"),
        }
        for item in exercises
        if isinstance(item, dict)
    ]
    lines = ["# 个性化学习课程", "", "## 学习路径摘要", ""]
    for index, item in enumerate(path, start=1):
        lines.append(f"{index}. {item.get('node_name', '')}：{item.get('strategy', '')}")
    lines.extend(["", "## 课程正文", "", str(draft.get("teaching_content", ""))])
    legal_basis = draft.get("legal_basis") or []
    if legal_basis:
        lines.extend(["", "## 法律依据", ""])
        lines.extend(f"- {basis}" for basis in legal_basis)
    if exercises:
        lines.extend(["", "## 练习题", ""])
        for index, item in enumerate(exercises, start=1):
            if isinstance(item, dict):
                lines.append(f"{index}. {item.get('prompt', '')}")
    questions = draft.get("interactive_questions") or []
    if questions:
        lines.extend(["", "## 互动问题", ""])
        lines.extend(f"- {question}" for question in questions)
    save_history_snapshot(
        runtime,
        state,
        event_type="course_published",
        payload={
            "topic": state.get("learner_profile", {}).get("learning_goal") or state["user_input"],
            "knowledge_points": [item.get("node_name") for item in path],
        },
    )
    return {
        "final_learning_markdown": "\n".join(lines).strip() + "\n",
        "exercise_answer_key": answer_key,
        "workflow_status": "completed",
        "events": [completed_event("publish_final_learning", "published accepted course")],
    }


def _print_summary(updates: dict[str, Any], round_num: int | None = None) -> None:
    """Print a one-line summary of an agent node's output."""
    if "learner_profile" in updates:
        p = updates["learner_profile"]
        print(
            f"  └─ 背景={p.get('education_background','?')}  "
            f"水平={p.get('knowledge_level','?')}  "
            f"风格={p.get('learning_style','?')}  "
            f"薄弱={p.get('weak_points',[])}",
            file=sys.stderr,
        )
    elif "learning_path" in updates:
        nodes_count = len(updates["learning_path"])
        names = [n.get("node_name", "") for n in updates["learning_path"]]
        print(f"  └─ {nodes_count} 个学习节点: {names}", file=sys.stderr)
    elif "retrieval_context" in updates:
        chunks = updates["retrieval_context"]
        if isinstance(chunks, list) and chunks:
            methods = {
                (c.get("metadata", {}) if isinstance(c, dict) else {}).get(
                    "retrieval_method", "?"
                )
                for c in chunks
            }
            print(
                f"  └─ 片段数={len(chunks)}  方法={', '.join(sorted(methods))}",
                file=sys.stderr,
            )
        else:
            print("  └─ 片段数=0", file=sys.stderr)
    elif "expert_a_draft" in updates:
        d = updates["expert_a_draft"]
        print(
            f"  └─ 风格={d.get('style','?')}  "
            f"知识点={d.get('knowledge_points',[])}  "
            f"法条={d.get('legal_basis',[])}",
            file=sys.stderr,
        )
    elif "expert_b_draft" in updates:
        d = updates["expert_b_draft"]
        print(
            f"  └─ 风格={d.get('style','?')}  "
            f"知识点={d.get('knowledge_points',[])}  "
            f"法条={d.get('legal_basis',[])}",
            file=sys.stderr,
        )
    elif "judge_report" in updates:
        j = updates["judge_report"]
        print(
            f"  └─ 决策={j.get('decision','?')}  "
            f"准确性={j.get('accuracy_score','?')}  "
            f"适配性={j.get('adaptation_score','?')}",
            file=sys.stderr,
        )
    elif "revision_history" in updates:
        rh = updates["revision_history"]
        if rh:
            print("  └─ 本轮评审已记录", file=sys.stderr)
    elif "feedback_result" in updates:
        f = updates["feedback_result"]
        print(
            f"  └─ 下一步={f.get('next_action','?')}  "
            f"问卷={len(f.get('questionnaire', []))}题",
            file=sys.stderr,
        )
    elif "intent" in updates:
        print(f"  └─ 意图={updates['intent']}", file=sys.stderr)
    elif "chat_answer" in updates:
        ca = updates["chat_answer"]
        content_preview = str(ca.get("content", ""))[:80]
        print(f"  └─ chat: {content_preview}...", file=sys.stderr)


def _call_node(
    node: Node,
    state: StateDict,
    runtime: Runtime[WorkflowContext] | None,
) -> dict[str, Any]:
    if len(inspect.signature(node).parameters) >= 2:
        return cast(dict[str, Any], node(state, runtime))
    return cast(dict[str, Any], node(state))


_ARTIFACT_FIELDS = (
    "learner_profile",
    "learning_path",
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "feedback_result",
    "chat_answer",
    "dual_axis_snapshot",
    "expert_a_cross_review",
    "expert_b_cross_review",
    "expert_a_revision",
    "expert_b_revision",
    "final_learning_markdown",
    "exercise_answer_key",
    "learner_profile_update",
    "course_package",
    "grading_report",
)


def _judge_decision(report: object) -> str:
    if isinstance(report, dict):
        return str(report.get("decision", ""))
    return ""


def _process_round(state: StateDict, node_label: str) -> int:
    if state.get("expert_phase") == "integration" or node_label in {
        "judge",
        "publish_final_learning",
        "quality_gate",
    }:
        return int(state.get("judge_round", 1))
    return int(state.get("debate_round", 1))


def _feedback_completes_teach(
    state: StateDict,
    updates: dict[str, Any],
    node_label: str,
) -> bool:
    return (
        node_label == "feedback"
        and state.get("teach_phase") == "integration"
        and "judge_report" in state
        and "feedback_result" in updates
    )


def _judge_accepts_teach(
    state: StateDict,
) -> bool:
    if state.get("teach_phase") != "integration":
        return False
    decision = _judge_decision(state.get("judge_report"))
    if decision in _ACCEPTED_JUDGE_DECISIONS:
        return True
    debate_round = int(state.get("debate_round", 1))
    max_debate_rounds = int(state.get("max_debate_rounds", 3))
    return decision == "revise" and debate_round >= max_debate_rounds


def _with_runtime_side_effects(
    node: Node,
    artifact_root: Path | None,
    workflow_log_root: Path | None = None,
    update_sink: WorkflowUpdateSink | None = None,
    event_sink: WorkflowEventSink | None = None,
    node_label: str | None = None,
) -> Node:
    def wrapped(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        label = node_label or "?"
        round_num = _process_round(state, label)
        round_tag = f" R{round_num}" if round_num > 1 else ""

        print(f"▸ [{label}]{round_tag} 开始...", file=sys.stderr)
        start = time.monotonic()
        write_workflow_log(
            log_root=workflow_log_root,
            state=state,
            node=label,
            status="started",
        )
        try:
            updates = _call_node(node, state, runtime)
            duration_ms = round((time.monotonic() - start) * 1000)

            raw_events = updates.get("events")
            if isinstance(raw_events, list):
                for evt in raw_events:
                    if isinstance(evt, dict):
                        if evt.get("round") is None:
                            evt["round"] = round_num
                        if evt.get("timestamp") is None:
                            evt["timestamp"] = datetime.now(UTC).isoformat()
                        if evt.get("duration_ms") is None:
                            evt["duration_ms"] = duration_ms

            _print_summary(updates, round_num)
            print(f"  [{label}]{round_tag} 完成 ✓  ({duration_ms}ms)", file=sys.stderr)

            artifacts: list[dict[str, Any]] = []
            if artifact_root is not None:
                round_number = round_num
                session_id = state["session_id"]
                for field in _ARTIFACT_FIELDS:
                    if field not in updates:
                        continue
                    if field == "expert_a_draft" and "course_package" in updates:
                        continue
                    if field == "expert_a_draft" and "expert_a_revision" in updates:
                        continue
                    if field == "expert_b_draft" and "expert_b_revision" in updates:
                        continue
                    artifact = write_field_artifact(
                        artifact_root=artifact_root,
                        session_id=session_id,
                        field=field,
                        value=updates[field],
                        round_number=round_number,
                    )
                    artifacts.append(artifact)
                    updates[field] = attach_markdown_artifact(updates[field], artifact)

                if artifacts:
                    updates["artifacts"] = artifacts

                combined = dict(state)
                combined.update(updates)
                combined["artifacts"] = list(state.get("artifacts", [])) + artifacts
                manifest_status = str(updates.get("workflow_status", "running"))
                write_manifest(artifact_root=artifact_root, state=combined, status=manifest_status)

            write_workflow_log(
                log_root=workflow_log_root,
                state=state,
                node=label,
                status="completed",
                duration_ms=duration_ms,
                updates=updates,
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000)
            write_workflow_log(
                log_root=workflow_log_root,
                state=state,
                node=label,
                status="error",
                duration_ms=duration_ms,
                error=exc,
            )
            if artifact_root is not None:
                write_manifest(artifact_root=artifact_root, state=dict(state), status="failed")
            raise

        events = updates.get("events")
        if event_sink is not None and isinstance(events, list):
            event_sink(cast(list[dict[str, Any]], events))
        if update_sink is not None:
            update_sink(updates)

        return updates

    return wrapped


def _route_after_debate_expert(
    state: StateDict,
) -> Literal["revise_experts", "_prepare_integration"]:
    debate_round = int(state.get("debate_round", 1))
    max_debate_rounds = int(state.get("max_debate_rounds", 3))
    if debate_round < max_debate_rounds:
        return "revise_experts"
    return "_prepare_integration"


def _route_after_revise_experts(
    state: StateDict,
) -> list[Literal["expert_a", "expert_b"]]:
    return ["expert_a", "expert_b"]


def _route_after_expert_a(
    state: StateDict,
) -> Literal["judge", "revise_experts", "_prepare_integration"]:
    phase = state.get("teach_phase", "debate")
    if phase == "integration":
        print("▸ [路由] expert_a 整合稿 → judge", file=sys.stderr)
        return "judge"
    return _route_after_debate_expert(state)


def revise_experts_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    next_round = int(state.get("debate_round", 1)) + 1
    print(
        f"▸ [路由] A/B 辩论第 {next_round - 1} 轮完成 → 进入第 {next_round} 轮",
        file=sys.stderr,
    )
    revision_record = {
        "round": next_round,
        "source": "expert_debate",
        "expert_a_points": state.get("expert_a_draft", {}).get("knowledge_points", []),
        "expert_b_points": state.get("expert_b_draft", {}).get("knowledge_points", []),
    }
    event = AgentEvent(
        node="revise_experts",
        status="debate_round",
        message=f"starting expert debate round {next_round}",
        round=next_round,
    ).model_dump()
    return {
        "debate_round": next_round,
        "revision_history": [revision_record],
        "events": [event],
    }


def prepare_integration_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    print("▸ [路由] A/B 辩论轮次已完成 → expert_a 整合", file=sys.stderr)
    return {"teach_phase": "integration"}


def prepare_cross_review_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    return {"expert_phase": "cross_review"}


def prepare_expert_revision_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    return {"expert_phase": "revision"}


def prepare_course_integration_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    return {"expert_phase": "integration", "teach_phase": "integration"}


def revise_integration_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    return {
        "expert_phase": "integration",
        "teach_phase": "integration",
        "judge_round": int(state.get("judge_round", 1)) + 1,
    }


def quality_gate_failed_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    return {
        "workflow_status": "quality_gate_failed",
        "events": [completed_event("quality_gate", "course failed the judge quality gate")],
    }


def retrieve_context_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    chunks = retrieve_context(query=state["user_input"], top_k=agent_top_k("chat_answer", 5))
    return {
        "retrieval_context": [chunk.model_dump() for chunk in chunks],
        "events": [
            completed_event(
                "retrieve_context",
                f"retrieved {len(chunks)} chunk(s) deterministically",
            )
        ],
    }


def _route_after_route(state: StateDict) -> Literal["learner_state", "retrieve_context"]:
    intent = state.get("intent", "teach")
    if intent == "chat":
        print("▸ [路由] intent=chat → 快速问答路径", file=sys.stderr)
        return "retrieve_context"
    # teach and diagnose both go through diagnosis first
    print(f"▸ [路由] intent={intent} → learner_state", file=sys.stderr)
    return "learner_state"


def _route_after_learner_state(state: StateDict) -> Literal["planner", "__end__"]:
    if state.get("learner_state_phase") == "feedback":
        return "__end__"
    intent = state.get("intent", "teach")
    if intent == "diagnose":
        print("▸ [路由] intent=diagnose → END", file=sys.stderr)
        return "__end__"
    print("▸ [路由] intent=teach → 继续学习路径", file=sys.stderr)
    return "planner"


def _route_after_init(state: StateDict) -> Literal["route", "learner_state"]:
    if state.get("workflow_mode") == "feedback":
        return "learner_state"
    return "route"


def _route_after_planner(
    state: StateDict,
) -> list[Literal["expert_a", "expert_b"]]:
    print("▸ [路由] intent=teach → experts", file=sys.stderr)
    return ["expert_a", "expert_b"]


def _route_after_retrieve_context(
    state: StateDict,
) -> Literal["chat_answer"]:
    print("▸ [路由] intent=chat → chat_answer", file=sys.stderr)
    return "chat_answer"


def _route_after_expert_a_phase(state: StateDict) -> Literal["expert_b", "judge"]:
    if state.get("expert_phase") == "integration":
        return "judge"
    return "expert_b"


def _route_after_expert_b_phase(
    state: StateDict,
) -> Literal[
    "_prepare_cross_review", "_prepare_expert_revision", "_prepare_course_integration"
]:
    phase = state.get("expert_phase", "draft")
    if phase == "draft":
        return "_prepare_cross_review"
    if phase == "cross_review":
        return "_prepare_expert_revision"
    return "_prepare_course_integration"


def _route_after_judge(state: StateDict) -> Literal["feedback"]:
    if _judge_accepts_teach(state):
        print("▸ [路由] judge 已完成整合稿审核 → feedback", file=sys.stderr)
    else:
        print("▸ [路由] judge 未通过整合稿 → feedback", file=sys.stderr)
    return "feedback"


def build_workflow(
    llm_client: LLMClient | None = None,
    artifact_root: str | Path | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    update_sink: WorkflowUpdateSink | None = None,
    event_sink: WorkflowEventSink | None = None,
    use_default_checkpointing: bool = True,
    workflow_log_root: str | Path | None = None,
) -> Any:
    builder = StateGraph(StateDict, context_schema=WorkflowContext)
    nodes: dict[str, Node] = build_agent_nodes(llm_client or AgentLLMRouter.from_env())
    root_path = Path(artifact_root) if artifact_root is not None else None
    log_root_path = Path(workflow_log_root) if workflow_log_root is not None else root_path

    def _ensure_session_id(state: StateDict) -> dict[str, Any]:
        """Auto-generate session_id if not provided (e.g. from LangGraph Studio)."""
        updates: dict[str, Any] = {}
        if not state.get("session_id"):
            import uuid
            updates["session_id"] = str(uuid.uuid4())[:8]
        mode = state.get("workflow_mode", "auto")
        updates["learner_state_phase"] = "feedback" if mode == "feedback" else "diagnosis"
        updates["expert_phase"] = "draft"
        updates["judge_round"] = int(state.get("judge_round", 1))
        updates["workflow_status"] = "running"
        return updates

    def _wrap(name: str, artifact: bool = True) -> Any:
        return cast(Any, _with_runtime_side_effects(
            nodes[name], root_path if artifact else None, log_root_path,
            update_sink, event_sink, node_label=name,
        ))

    # ── All nodes ──
    builder.add_node("_init", _ensure_session_id)
    builder.add_node("route", _wrap("route"))
    builder.add_node("learner_state", _wrap("learner_state"))
    builder.add_node("planner", _wrap("planner"))
    builder.add_node("retrieve_context", cast(Any, _with_runtime_side_effects(
        retrieve_context_node, root_path, log_root_path,
        update_sink, event_sink, node_label="retrieve_context",
    )))
    builder.add_node("chat_answer", _wrap("chat_answer"))
    builder.add_node("expert_a", _wrap("expert_a"))
    builder.add_node("expert_b", _wrap("expert_b"))
    builder.add_node("judge", _wrap("judge"))
    builder.add_node("_prepare_cross_review", prepare_cross_review_node)
    builder.add_node("_prepare_expert_revision", prepare_expert_revision_node)
    builder.add_node("_prepare_course_integration", prepare_course_integration_node)
    builder.add_node("revise_integration", revise_integration_node)
    builder.add_node("publish_final_learning", cast(Any, _with_runtime_side_effects(
        publish_final_learning_node, root_path, log_root_path,
        update_sink, event_sink, node_label="publish_final_learning",
    )))
    builder.add_node("quality_gate_failed", cast(Any, _with_runtime_side_effects(
        quality_gate_failed_node, root_path, log_root_path,
        update_sink, event_sink, node_label="quality_gate",
    )))

    # ── Edges ──

    # START → _init → route
    builder.add_edge(START, "_init")
    builder.add_conditional_edges(
        "_init",
        _route_after_init,
        {"route": "route", "learner_state": "learner_state"},
    )

    builder.add_conditional_edges(
        "route",
        _route_after_route,
        {"learner_state": "learner_state", "retrieve_context": "retrieve_context"},
    )

    # After diagnosis: teach → planner, diagnose → END
    builder.add_conditional_edges(
        "learner_state",
        _route_after_learner_state,
        {"planner": "planner", "__end__": END},
    )

    builder.add_edge("planner", "expert_a")
    builder.add_conditional_edges(
        "retrieve_context",
        _route_after_retrieve_context,
        {"chat_answer": "chat_answer"},
    )

    builder.add_conditional_edges(
        "expert_a",
        _route_after_expert_a_phase,
        {"expert_b": "expert_b", "judge": "judge"},
    )
    builder.add_conditional_edges(
        "expert_b",
        _route_after_expert_b_phase,
        {
            "_prepare_cross_review": "_prepare_cross_review",
            "_prepare_expert_revision": "_prepare_expert_revision",
            "_prepare_course_integration": "_prepare_course_integration",
        },
    )
    builder.add_edge("_prepare_cross_review", "expert_a")
    builder.add_edge("_prepare_expert_revision", "expert_a")
    builder.add_edge("_prepare_course_integration", "expert_a")
    builder.add_conditional_edges(
        "judge",
        judge_route,
        {
            "publish_final_learning": "publish_final_learning",
            "revise_integration": "revise_integration",
            "quality_gate_failed": "quality_gate_failed",
        },
    )
    builder.add_edge("revise_integration", "expert_a")
    builder.add_edge("publish_final_learning", END)
    builder.add_edge("quality_gate_failed", END)

    builder.add_edge("chat_answer", END)

    _cp = checkpointer
    _st = store
    if use_default_checkpointing:
        if _cp is None:
            _cp = InMemorySaver()
        if _st is None:
            _st = InMemoryStore()
    return builder.compile(checkpointer=_cp, store=_st)


def run_workflow(
    session_id: str,
    user_input: str,
    llm_client: LLMClient | None = None,
    artifact_root: str | Path | None = None,
    max_debate_rounds: int = 3,
    learner_id: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    workflow_mode: Literal["auto", "teach", "chat", "diagnose", "feedback"] = "auto",
    input_payload: dict[str, Any] | None = None,
    parent_session_id: str | None = None,
) -> StateDict:
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"工作流启动  session={session_id}  learner={learner_id or 'N/A'}", file=sys.stderr)
    print(f"用户输入: {user_input}", file=sys.stderr)
    print(f"最大辩论轮数: {max_debate_rounds}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    workflow = build_workflow(
        llm_client=llm_client,
        artifact_root=artifact_root,
        checkpointer=checkpointer,
        store=store,
    )
    result = workflow.invoke(
        {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
            "artifacts": [],
            "debate_round": 1,
            "max_debate_rounds": max_debate_rounds,
            "revision_history": [],
            "teach_phase": "debate",
            "workflow_mode": workflow_mode,
            "input_payload": input_payload or {},
            "parent_session_id": parent_session_id,
        },
        {"configurable": {"thread_id": session_id}},
        context=WorkflowContext(learner_id=learner_id),
    )

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"工作流完成 ✓  session={session_id}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return cast(StateDict, result)


async def arun_workflow(
    session_id: str,
    user_input: str,
    llm_client: LLMClient | None = None,
    artifact_root: str | Path | None = None,
    max_debate_rounds: int = 3,
    learner_id: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    update_sink: WorkflowUpdateSink | None = None,
    event_sink: WorkflowEventSink | None = None,
    workflow_mode: Literal["auto", "teach", "chat", "diagnose", "feedback"] = "auto",
    input_payload: dict[str, Any] | None = None,
    parent_session_id: str | None = None,
) -> StateDict:
    workflow = build_workflow(
        llm_client=llm_client,
        artifact_root=artifact_root,
        checkpointer=checkpointer,
        store=store,
        update_sink=update_sink,
        event_sink=event_sink,
    )
    result = await workflow.ainvoke(
        {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
            "artifacts": [],
            "debate_round": 1,
            "max_debate_rounds": max_debate_rounds,
            "revision_history": [],
            "teach_phase": "debate",
            "workflow_mode": workflow_mode,
            "input_payload": input_payload or {},
            "parent_session_id": parent_session_id,
        },
        {"configurable": {"thread_id": session_id}},
        context=WorkflowContext(learner_id=learner_id),
    )
    return cast(StateDict, result)


def export_workflow_mermaid(workflow: Any | None = None) -> str:
    compiled = workflow or build_workflow(llm_client=DefaultLLMClient(provider="deepseek"))
    return cast(str, compiled.get_graph().draw_mermaid())
