"""LangGraph workflow for the DeepSeek-backed five-Agent MVP."""

from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from backend.app.agents.deepseek_nodes import Node, build_agent_nodes
from backend.app.agents.mock_nodes import (
    diagnosis_node as mock_diagnosis_node,
    expert_a_node as mock_expert_a_node,
    expert_b_node as mock_expert_b_node,
    feedback_node as mock_feedback_node,
    judge_node as mock_judge_node,
    planner_node as mock_planner_node,
    retrieve_context_node as mock_retrieve_context_node,
)
from backend.app.agents.mock_nodes import finalize_node
from backend.app.core.llm import DeepSeekChatClient, LLMClient
from backend.app.schemas.state import StateDict


def build_workflow(llm_client: LLMClient | None = None, use_mock: bool = False) -> Any:
    builder = StateGraph(StateDict)
    if use_mock:
        nodes: dict[str, Node] = {
            "diagnosis": mock_diagnosis_node,
            "planner": mock_planner_node,
            "retrieve_context": mock_retrieve_context_node,
            "expert_a": mock_expert_a_node,
            "expert_b": mock_expert_b_node,
            "judge": mock_judge_node,
            "feedback": mock_feedback_node,
        }
    else:
        nodes = build_agent_nodes(llm_client or DeepSeekChatClient.from_env())

    builder.add_node("diagnosis", cast(Any, nodes["diagnosis"]))
    builder.add_node("planner", cast(Any, nodes["planner"]))
    builder.add_node("retrieve_context", cast(Any, nodes["retrieve_context"]))
    builder.add_node("expert_a", cast(Any, nodes["expert_a"]))
    builder.add_node("expert_b", cast(Any, nodes["expert_b"]))
    builder.add_node("judge", cast(Any, nodes["judge"]))
    builder.add_node("feedback", cast(Any, nodes["feedback"]))
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "diagnosis")
    builder.add_edge("diagnosis", "planner")
    builder.add_edge("planner", "retrieve_context")
    builder.add_edge("retrieve_context", "expert_a")
    builder.add_edge("retrieve_context", "expert_b")
    builder.add_edge("expert_a", "judge")
    builder.add_edge("expert_b", "judge")
    builder.add_edge("judge", "feedback")
    builder.add_edge("feedback", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


def run_workflow(session_id: str, user_input: str, llm_client: LLMClient | None = None) -> StateDict:
    workflow = build_workflow(llm_client=llm_client)
    result = workflow.invoke(
        {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
        }
    )
    return cast(StateDict, result)


def run_mock_workflow(session_id: str, user_input: str) -> StateDict:
    workflow = build_workflow(use_mock=True)
    result = workflow.invoke(
        {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
        }
    )
    return cast(StateDict, result)


def export_workflow_mermaid(workflow: Any | None = None) -> str:
    compiled = workflow or build_workflow(use_mock=True)
    return cast(str, compiled.get_graph().draw_mermaid())
