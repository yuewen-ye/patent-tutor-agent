"""LangGraph workflow for the real five-Agent system."""

from __future__ import annotations

import inspect
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, assert_never, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

from backend.app.core.agent_runtime_config import agent_top_k
from backend.app.agents import Node, build_agent_nodes
from backend.app.runtime_outputs.artifacts import attach_markdown_artifact, write_field_artifact, write_manifest
from backend.app.core.llm import AgentLLMRouter, DefaultLLMClient, LLMClient
from backend.app.retrieval.selector import retrieve_context
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import JudgeReport, StateDict, completed_event
from backend.app.runtime_outputs.workflow_logging import write_workflow_log

WorkflowUpdateSink = Callable[[dict[str, Any]], None]
WorkflowEventSink = Callable[[list[dict[str, Any]]], None]


def _print_summary(updates: dict[str, Any]) -> None:
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
    "path_decision",
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
    "learner_profile_update",
    "course_package",
    "grading_report",
)


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
        print(f"▸ [{label}] 开始...", file=sys.stderr)
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
                        if evt.get("timestamp") is None:
                            evt["timestamp"] = datetime.now(UTC).isoformat()
                        if evt.get("duration_ms") is None:
                            evt["duration_ms"] = duration_ms

            _print_summary(updates)
            print(f"  [{label}] 完成 ✓  ({duration_ms}ms)", file=sys.stderr)

            artifacts: list[dict[str, Any]] = []
            if artifact_root is not None:
                round_number = 1
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


def _route_after_route(
    state: StateDict,
) -> Literal["diagnosis_feedback", "retrieve_context"]:
    intent = state.get("intent", "teach")
    if intent == "chat":
        print("▸ [路由] intent=chat → 快速问答路径", file=sys.stderr)
        return "retrieve_context"
    # teach and diagnose both go through diagnosis first
    print(f"▸ [路由] intent={intent} → diagnosis_feedback", file=sys.stderr)
    return "diagnosis_feedback"


def _route_after_diagnosis_feedback(
    state: StateDict,
) -> Literal["planner", "__end__"]:
    if state.get("diagnosis_feedback_phase") == "feedback":
        return "__end__"
    intent = state.get("intent", "teach")
    if intent == "diagnose":
        print("▸ [路由] intent=diagnose → END", file=sys.stderr)
        return "__end__"
    print("▸ [路由] intent=teach → 继续学习路径", file=sys.stderr)
    return "planner"


def _route_after_init(state: StateDict) -> Literal["route", "diagnosis_feedback"]:
    if state.get("workflow_mode") == "feedback":
        return "diagnosis_feedback"
    return "route"


def _route_after_retrieve_context(
    state: StateDict,
) -> Literal["chat_answer"]:
    print("▸ [路由] intent=chat → chat_answer", file=sys.stderr)
    return "chat_answer"


def _advance_expert_phase(state: StateDict) -> dict[str, Any]:
    phase = state.get("expert_phase", "draft")
    match phase:
        case "draft":
            return {"expert_phase": "cross_review"}
        case "cross_review":
            return {"expert_phase": "revision"}
        case "revision":
            return {"expert_phase": "integration", "teach_phase": "integration"}
        case "integration":
            raise RuntimeError("Expert integration must not enter the parallel phase barrier.")
        case unreachable:
            assert_never(unreachable)


def _route_after_experts_barrier(
    state: StateDict,
) -> list[Literal["expert_a", "expert_b"]] | Literal["expert_a_integration"]:
    phase = state.get("expert_phase", "draft")
    match phase:
        case "cross_review" | "revision":
            return ["expert_a", "expert_b"]
        case "integration":
            return "expert_a_integration"
        case "draft":
            raise RuntimeError("Parallel expert phase did not advance at the barrier.")
        case unreachable:
            assert_never(unreachable)


def _route_after_judge(
    state: StateDict,
) -> Literal["expert_a_integration", "__end__"]:
    decision = JudgeReport.model_validate(state.get("judge_report", {})).decision
    match decision:
        case "accept" | "accept_with_minor_revision":
            print("▸ [路由] judge 通过 → 完成", file=sys.stderr)
            return "__end__"
        case "revise":
            print("▸ [路由] judge 未通过 → expert_a_integration 重新整合", file=sys.stderr)
            return "expert_a_integration"
        case unreachable:
            assert_never(unreachable)


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
        updates["diagnosis_feedback_phase"] = (
            "feedback" if mode == "feedback" else "diagnosis"
        )
        updates["expert_phase"] = "draft"
        updates["workflow_status"] = "running"
        return updates

    def _wrap(name: str, artifact: bool = True, node_label: str | None = None) -> Any:
        return cast(Any, _with_runtime_side_effects(
            nodes[name], root_path if artifact else None, log_root_path,
            update_sink, event_sink, node_label=node_label or name,
        ))

    # ── All nodes ──
    builder.add_node("_init", _ensure_session_id)
    builder.add_node("route", _wrap("route"))
    builder.add_node("diagnosis_feedback", _wrap("diagnosis_feedback"))
    builder.add_node("planner", _wrap("planner"))
    builder.add_node("retrieve_context", cast(Any, _with_runtime_side_effects(
        retrieve_context_node, root_path, log_root_path,
        update_sink, event_sink, node_label="retrieve_context",
    )))
    builder.add_node("chat_answer", _wrap("chat_answer"))
    builder.add_node("expert_a", _wrap("expert_a"))
    builder.add_node("expert_b", _wrap("expert_b"))
    builder.add_node("_experts_barrier", _advance_expert_phase)
    builder.add_node("expert_a_integration", _wrap("expert_a", node_label="expert_a"))
    builder.add_node("judge", _wrap("judge"))

    # ── Edges ──

    # START → _init → route
    builder.add_edge(START, "_init")
    builder.add_conditional_edges(
        "_init",
        _route_after_init,
        {"route": "route", "diagnosis_feedback": "diagnosis_feedback"},
    )

    builder.add_conditional_edges(
        "route",
        _route_after_route,
        {
            "diagnosis_feedback": "diagnosis_feedback",
            "retrieve_context": "retrieve_context",
        },
    )

    # After diagnosis: teach → planner, diagnose → END
    builder.add_conditional_edges(
        "diagnosis_feedback",
        _route_after_diagnosis_feedback,
        {"planner": "planner", "__end__": END},
    )

    builder.add_edge("planner", "expert_a")
    builder.add_edge("planner", "expert_b")
    builder.add_conditional_edges(
        "retrieve_context",
        _route_after_retrieve_context,
        {"chat_answer": "chat_answer"},
    )

    builder.add_edge(["expert_a", "expert_b"], "_experts_barrier")
    builder.add_conditional_edges(
        "_experts_barrier",
        _route_after_experts_barrier,
        {
            "expert_a": "expert_a",
            "expert_b": "expert_b",
            "expert_a_integration": "expert_a_integration",
        },
    )
    builder.add_edge("expert_a_integration", "judge")
    builder.add_conditional_edges(
        "judge",
        _route_after_judge,
        {"expert_a_integration": "expert_a_integration", "__end__": END},
    )

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
