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

from backend.app.agents import Node, build_agent_nodes
from backend.app.artifacts import attach_markdown_artifact, write_field_artifact, write_manifest
from backend.app.core.llm import AgentLLMRouter, DefaultLLMClient, LLMClient
from backend.app.memory import save_learner_memories
from backend.app.retrieval_selector import retrieve_context
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import AgentEvent, StateDict, completed_event

WorkflowUpdateSink = Callable[[dict[str, Any]], None]
WorkflowEventSink = Callable[[list[dict[str, Any]]], None]
_ACCEPTED_JUDGE_DECISIONS = {"accept", "accept_with_minor_revision"}


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
)


def _judge_decision(report: object) -> str:
    if isinstance(report, dict):
        return str(report.get("decision", ""))
    return ""


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


def _memory_summary_from_final_judge(state: StateDict) -> dict[str, Any]:
    judge_report = state.get("judge_report", {})
    expert_a_draft = state.get("expert_a_draft", {})
    rationale = judge_report.get("rationale") if isinstance(judge_report, dict) else None
    points = expert_a_draft.get("knowledge_points") if isinstance(expert_a_draft, dict) else None
    next_action = "复习本次专家 A 整合稿并完成一个对应案例题"
    if isinstance(points, list) and points:
        next_action = f"围绕{points[0]}完成一个对应案例题"
    return {
        "profile_update_hint": str(rationale or "记录本次 teach 路由最终整合稿表现"),
        "next_action": next_action,
    }


def _with_runtime_side_effects(
    node: Node,
    artifact_root: Path | None,
    update_sink: WorkflowUpdateSink | None = None,
    event_sink: WorkflowEventSink | None = None,
    node_label: str | None = None,
) -> Node:
    def wrapped(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        round_num = int(state.get("debate_round", 1))
        label = node_label or "?"
        round_tag = f" R{round_num}" if round_num > 1 else ""

        print(f"▸ [{label}]{round_tag} 开始...", file=sys.stderr)
        start = time.monotonic()
        updates = _call_node(node, state, runtime)
        duration_ms = round((time.monotonic() - start) * 1000)

        # Enrich events with metadata that only the workflow wrapper knows.
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
        completed_teach = _feedback_completes_teach(state, updates, label)
        if artifact_root is not None:
            round_number = int(state.get("debate_round", 1))
            session_id = state["session_id"]
            for field in _ARTIFACT_FIELDS:
                if field not in updates:
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

            if completed_teach:
                combined = dict(state)
                combined.update(updates)
                combined["artifacts"] = list(state.get("artifacts", [])) + artifacts
                write_manifest(artifact_root=artifact_root, state=combined, status="completed")

        if completed_teach:
            combined = dict(state)
            combined.update(updates)
            if artifacts:
                combined["artifacts"] = list(state.get("artifacts", [])) + artifacts
            save_learner_memories(
                runtime,
                cast(StateDict, combined),
                _memory_summary_from_final_judge(cast(StateDict, combined)),
            )

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
        print(
            f"▸ [路由] A/B 辩论第 {debate_round} 轮完成 → 进入第 {debate_round + 1} 轮",
            file=sys.stderr,
        )
        return "revise_experts"
    print("▸ [路由] A/B 辩论轮次已完成 → expert_a 整合", file=sys.stderr)
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
    return {"teach_phase": "integration"}


def retrieve_context_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    chunks = retrieve_context(query=state["user_input"], top_k=5)
    existing = list(state.get("retrieval_context", []) or [])
    existing.extend(chunk.model_dump() for chunk in chunks)
    return {
        "retrieval_context": existing,
        "events": [
            completed_event(
                "retrieve_context",
                f"retrieved {len(chunks)} chunk(s) deterministically",
            )
        ],
    }


def _route_after_route(state: StateDict) -> Literal["diagnosis", "retrieve_context"]:
    intent = state.get("intent", "teach")
    if intent == "chat":
        print("▸ [路由] intent=chat → 快速问答路径", file=sys.stderr)
        return "retrieve_context"
    # teach and diagnose both go through diagnosis first
    print(f"▸ [路由] intent={intent} → diagnosis", file=sys.stderr)
    return "diagnosis"


def _route_after_diagnosis(state: StateDict) -> Literal["planner", "__end__"]:
    intent = state.get("intent", "teach")
    if intent == "diagnose":
        print("▸ [路由] intent=diagnose → END", file=sys.stderr)
        return "__end__"
    print("▸ [路由] intent=teach → 继续学习路径", file=sys.stderr)
    return "planner"


def _route_after_retrieve_context(
    state: StateDict,
) -> Literal["chat_answer"] | list[Literal["expert_a", "expert_b"]]:
    intent = state.get("intent", "teach")
    if intent == "chat":
        print("▸ [路由] intent=chat → chat_answer", file=sys.stderr)
        return "chat_answer"
    print("▸ [路由] intent=teach → experts", file=sys.stderr)
    return ["expert_a", "expert_b"]


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
) -> Any:
    builder = StateGraph(StateDict, context_schema=WorkflowContext)
    nodes: dict[str, Node] = build_agent_nodes(llm_client or AgentLLMRouter.from_env())
    root_path = Path(artifact_root) if artifact_root is not None else None

    def _ensure_session_id(state: StateDict) -> dict[str, Any]:
        """Auto-generate session_id if not provided (e.g. from LangGraph Studio)."""
        if not state.get("session_id"):
            import uuid
            return {"session_id": str(uuid.uuid4())[:8]}
        return {}

    def _wrap(name: str, artifact: bool = True) -> Any:
        return cast(Any, _with_runtime_side_effects(
            nodes[name], root_path if artifact else None,
            update_sink, event_sink, node_label=name,
        ))

    # ── All nodes ──
    builder.add_node("_init", _ensure_session_id)
    builder.add_node("route", _wrap("route"))
    builder.add_node("diagnosis", _wrap("diagnosis"))
    builder.add_node("planner", _wrap("planner"))
    builder.add_node("retrieve_context", cast(Any, _with_runtime_side_effects(
        retrieve_context_node, root_path, update_sink, event_sink, node_label="retrieve_context",
    )))
    builder.add_node("chat_answer", _wrap("chat_answer"))
    builder.add_node("expert_a", _wrap("expert_a"))
    builder.add_node("expert_b", _wrap("expert_b"))
    builder.add_node("judge", _wrap("judge"))
    builder.add_node("feedback", _wrap("feedback"))
    builder.add_node("revise_experts", cast(Any, _with_runtime_side_effects(
        revise_experts_node, None, update_sink, event_sink, node_label="revise_experts",
    )))
    builder.add_node("_prepare_integration", prepare_integration_node)

    # ── Edges ──

    # START → _init → route
    builder.add_edge(START, "_init")
    builder.add_edge("_init", "route")

    builder.add_conditional_edges(
        "route",
        _route_after_route,
        {"diagnosis": "diagnosis", "retrieve_context": "retrieve_context"},
    )

    # After diagnosis: teach → planner, diagnose → END
    builder.add_conditional_edges(
        "diagnosis",
        _route_after_diagnosis,
        {"planner": "planner", "__end__": END},
    )

    builder.add_edge("planner", "retrieve_context")
    builder.add_conditional_edges(
        "retrieve_context",
        _route_after_retrieve_context,
        {"expert_a": "expert_a", "expert_b": "expert_b", "chat_answer": "chat_answer"},
    )

    builder.add_conditional_edges(
        "expert_a",
        _route_after_expert_a,
        {"judge": "judge", "revise_experts": "revise_experts", "_prepare_integration": "_prepare_integration"},
    )
    builder.add_conditional_edges(
        "expert_b",
        _route_after_debate_expert,
        {"revise_experts": "revise_experts", "_prepare_integration": "_prepare_integration"},
    )

    builder.add_edge("_prepare_integration", "expert_a")
    builder.add_conditional_edges("judge", _route_after_judge, {"feedback": "feedback"})
    builder.add_edge("feedback", END)

    builder.add_conditional_edges(
        "revise_experts",
        _route_after_revise_experts,
        {"expert_a": "expert_a", "expert_b": "expert_b"},
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
    max_debate_rounds: int = 3,
    learner_id: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
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
        },
        {"configurable": {"thread_id": session_id}},
        context=WorkflowContext(learner_id=learner_id),
    )
    return cast(StateDict, result)


def export_workflow_mermaid(workflow: Any | None = None) -> str:
    compiled = workflow or build_workflow(llm_client=DefaultLLMClient(provider="deepseek"))
    return cast(str, compiled.get_graph().draw_mermaid())
