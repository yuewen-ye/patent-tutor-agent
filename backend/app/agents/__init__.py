"""Agent node assembly for the LangGraph workflow."""

from __future__ import annotations

from backend.app.agents.chat_answer import build_chat_answer_node
from backend.app.agents.common import Node
from backend.app.agents.cross_review_a import build_expert_a_cross_review_node
from backend.app.agents.cross_review_b import build_expert_b_cross_review_node
from backend.app.agents.diagnosis import build_diagnosis_node
from backend.app.agents.expert_a import build_expert_a_node
from backend.app.agents.expert_a_revise import build_expert_a_revise_node
from backend.app.agents.expert_b import build_expert_b_node
from backend.app.agents.expert_b_revise import build_expert_b_revise_node
from backend.app.agents.feedback import build_feedback_node
from backend.app.agents.finalize import build_finalize_node
from backend.app.agents.joint_synthesis import build_joint_synthesis_node
from backend.app.agents.judge import build_judge_node
from backend.app.agents.lightweight_review import build_lightweight_review_node
from backend.app.agents.planner import build_planner_node
from backend.app.agents.route import build_route_node
from backend.app.agents.tool_agent import build_tool_agent_node
from backend.app.core.llm import LLMClient


def build_agent_nodes(llm_client: LLMClient) -> dict[str, Node]:
    return {
        "diagnosis": build_diagnosis_node(llm_client),
        "planner": build_planner_node(llm_client),
        "expert_a": build_expert_a_node(llm_client),
        "expert_b": build_expert_b_node(llm_client),
        "judge": build_judge_node(llm_client),
        "feedback": build_feedback_node(llm_client),
        "route": build_route_node(llm_client),
        "tool_agent": build_tool_agent_node(llm_client),
        "chat_answer": build_chat_answer_node(llm_client),
        "finalize": build_finalize_node(llm_client),
        # P0.1: Five-stage expert collaboration chain
        "cross_review_a": build_expert_a_cross_review_node(llm_client),
        "cross_review_b": build_expert_b_cross_review_node(llm_client),
        "expert_a_revise": build_expert_a_revise_node(llm_client),
        "expert_b_revise": build_expert_b_revise_node(llm_client),
        "joint_synthesis": build_joint_synthesis_node(llm_client),
        "lightweight_review": build_lightweight_review_node(llm_client),
    }


__all__ = ["Node", "build_agent_nodes", "build_finalize_node"]
