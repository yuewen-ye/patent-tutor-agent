"""LangGraph workflow for the real five-Agent system."""

from __future__ import annotations

import inspect
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
) -> Node:
    def wrapped(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        updates = _call_node(node, state, runtime)

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
        return "revise_experts"
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
            _with_runtime_side_effects(nodes["diagnosis"], root_path, update_sink, event_sink),
        ),
    )
    builder.add_node(
        "planner",
        cast(Any, _with_runtime_side_effects(nodes["planner"], root_path, update_sink, event_sink)),
    )
    builder.add_node(
        "retrieve_context",
        cast(
            Any,
            _with_runtime_side_effects(
                nodes["retrieve_context"], root_path, update_sink, event_sink
            ),
        ),
    )
    builder.add_node(
        "expert_a",
        cast(Any, _with_runtime_side_effects(nodes["expert_a"], root_path, update_sink, event_sink)),
    )
    builder.add_node(
        "expert_b",
        cast(Any, _with_runtime_side_effects(nodes["expert_b"], root_path, update_sink, event_sink)),
    )
    builder.add_node(
        "judge",
        cast(Any, _with_runtime_side_effects(nodes["judge"], root_path, update_sink, event_sink)),
    )
    builder.add_node(
        "revise_experts",
        cast(Any, _with_runtime_side_effects(revise_experts_node, None, update_sink, event_sink)),
    )
    builder.add_node(
        "feedback",
        cast(Any, _with_runtime_side_effects(nodes["feedback"], root_path, update_sink, event_sink)),
    )
    builder.add_node(
        "finalize",
        cast(Any, _with_runtime_side_effects(finalize_node, root_path, update_sink, event_sink)),
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
