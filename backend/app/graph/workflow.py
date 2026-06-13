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

from backend.app.agents import Node, build_agent_nodes, finalize_node
from backend.app.artifacts import attach_markdown_artifact, write_field_artifact, write_manifest
from backend.app.core.llm import AgentLLMRouter, DefaultLLMClient, LLMClient
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import AgentEvent, StateDict

WorkflowUpdateSink = Callable[[dict[str, Any]], None]
WorkflowEventSink = Callable[[list[dict[str, Any]]], None]


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
    elif "final_answer" in updates:
        fa = updates["final_answer"]
        title = fa.get("title", "")
        sources_count = len(fa.get("sources", []))
        print(f"  └─ 标题={title}  来源数={sources_count}", file=sys.stderr)


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
    "final_answer",
)


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

            if "final_answer" in updates:
                combined = dict(state)
                combined.update(updates)
                combined["artifacts"] = list(state.get("artifacts", [])) + artifacts
                write_manifest(artifact_root=artifact_root, state=combined, status="completed")

        events = updates.get("events")
        if event_sink is not None and isinstance(events, list):
            event_sink(cast(list[dict[str, Any]], events))
        if update_sink is not None:
            update_sink(updates)

        return updates

    return wrapped


def _route_after_judge(state: StateDict) -> Literal["revise_experts", "feedback"]:
    decision = str(state.get("judge_report", {}).get("decision", ""))
    debate_round = int(state.get("debate_round", 1))
    max_debate_rounds = int(state.get("max_debate_rounds", 2))
    if decision == "revise" and debate_round < max_debate_rounds:
        print(
            f"▸ [路由] judge 要求修订 → 进入第 {debate_round + 1} 轮辩论",
            file=sys.stderr,
        )
        return "revise_experts"
    print(f"▸ [路由] judge 决策={decision} → 进入反馈环节", file=sys.stderr)
    return "feedback"


def revise_experts_node(
    state: StateDict, runtime: Runtime[WorkflowContext] | None = None
) -> dict[str, Any]:
    next_round = int(state.get("debate_round", 1)) + 1
    judge_report = state.get("judge_report", {})
    revision_record = {
        "round": next_round,
        "judge_decision": judge_report.get("decision"),
        "revision_requests": judge_report.get("revision_requests", []),
        "rationale": judge_report.get("rationale"),
    }
    event = AgentEvent(
        node="judge",
        status="debate_round",
        message=f"judge requested expert revision round {next_round}",
        round=next_round,
    ).model_dump()
    return {
        "debate_round": next_round,
        "revision_history": [revision_record],
        "events": [event],
    }


def build_workflow(
    llm_client: LLMClient | None = None,
    artifact_root: str | Path | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    update_sink: WorkflowUpdateSink | None = None,
    event_sink: WorkflowEventSink | None = None,
) -> Any:
    builder = StateGraph(StateDict, context_schema=WorkflowContext)
    nodes: dict[str, Node] = build_agent_nodes(llm_client or AgentLLMRouter.from_env())
    root_path = Path(artifact_root) if artifact_root is not None else None

    builder.add_node(
        "diagnosis",
        cast(
            Any,
            _with_runtime_side_effects(nodes["diagnosis"], root_path, update_sink, event_sink, node_label="diagnosis"),
        ),
    )
    builder.add_node(
        "planner",
        cast(Any, _with_runtime_side_effects(nodes["planner"], root_path, update_sink, event_sink, node_label="planner")),
    )
    builder.add_node(
        "retrieve_context",
        cast(
            Any,
            _with_runtime_side_effects(
                nodes["retrieve_context"], root_path, update_sink, event_sink, node_label="retrieve_context"
            ),
        ),
    )
    builder.add_node(
        "expert_a",
        cast(Any, _with_runtime_side_effects(nodes["expert_a"], root_path, update_sink, event_sink, node_label="expert_a")),
    )
    builder.add_node(
        "expert_b",
        cast(Any, _with_runtime_side_effects(nodes["expert_b"], root_path, update_sink, event_sink, node_label="expert_b")),
    )
    builder.add_node(
        "judge",
        cast(Any, _with_runtime_side_effects(nodes["judge"], root_path, update_sink, event_sink, node_label="judge")),
    )
    builder.add_node(
        "revise_experts",
        cast(Any, _with_runtime_side_effects(revise_experts_node, None, update_sink, event_sink, node_label="revise_experts")),
    )
    builder.add_node(
        "feedback",
        cast(Any, _with_runtime_side_effects(nodes["feedback"], root_path, update_sink, event_sink, node_label="feedback")),
    )
    builder.add_node(
        "finalize",
        cast(Any, _with_runtime_side_effects(finalize_node, root_path, update_sink, event_sink, node_label="finalize")),
    )

    builder.add_edge(START, "diagnosis")
    builder.add_edge("diagnosis", "planner")
    builder.add_edge("planner", "retrieve_context")
    builder.add_edge("retrieve_context", "expert_a")
    builder.add_edge("retrieve_context", "expert_b")
    builder.add_edge("expert_a", "judge")
    builder.add_edge("expert_b", "judge")
    builder.add_conditional_edges(
        "judge",
        _route_after_judge,
        {"revise_experts": "revise_experts", "feedback": "feedback"},
    )
    builder.add_edge("revise_experts", "expert_a")
    builder.add_edge("revise_experts", "expert_b")
    builder.add_edge("feedback", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
        store=store if store is not None else InMemoryStore(),
    )


def run_workflow(
    session_id: str,
    user_input: str,
    llm_client: LLMClient | None = None,
    artifact_root: str | Path | None = None,
    max_debate_rounds: int = 2,
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
    max_debate_rounds: int = 2,
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
        },
        {"configurable": {"thread_id": session_id}},
        context=WorkflowContext(learner_id=learner_id),
    )
    return cast(StateDict, result)


def export_workflow_mermaid(workflow: Any | None = None) -> str:
    compiled = workflow or build_workflow(llm_client=DefaultLLMClient(provider="deepseek"))
    return cast(str, compiled.get_graph().draw_mermaid())
