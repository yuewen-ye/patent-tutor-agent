"""Agent node assembly for the LangGraph workflow."""

from __future__ import annotations

from backend.app.agents.chat_answer import build_chat_answer_node
from backend.app.agents.common import Node
from backend.app.agents.diagnosis import build_diagnosis_feedback_node, build_diagnosis_node
from backend.app.agents.expert_a import build_expert_a_node
from backend.app.agents.expert_b import build_expert_b_node
from backend.app.agents.judge import build_judge_node
from backend.app.agents.planner import build_planner_node
from backend.app.agents.route import build_route_node
from backend.app.core.llm import LLMClient


def build_agent_nodes(llm_client: LLMClient) -> dict[str, Node]:
    return {
        "diagnosis": build_diagnosis_node(llm_client),
        "planner": build_planner_node(llm_client),
        "expert_a": build_expert_a_node(llm_client),
        "expert_b": build_expert_b_node(llm_client),
        "judge": build_judge_node(llm_client),
        "feedback": build_diagnosis_feedback_node(llm_client),
        "route": build_route_node(llm_client),
        "chat_answer": build_chat_answer_node(llm_client),
    }


__all__ = ["Node", "build_agent_nodes"]
