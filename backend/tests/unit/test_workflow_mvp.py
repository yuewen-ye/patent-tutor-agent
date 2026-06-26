from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_workflow
from backend.tests.helpers import completed_teach_state

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []
        self.responses_by_agent: dict[str, list[object]] = {
            "route": [
                {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            ],
            "diagnosis": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["法条概念辨析"],
                    "learning_goal": "学习专利新颖性",
                }
            ],
            "planner": [
                [
                    {
                        "node_id": "patentability-basic",
                        "node_name": "专利授权条件基础",
                        "duration_min": 20,
                        "strategy": "先学授权条件",
                        "prerequisites": [],
                    }
                ]
            ],
            "expert_a": [
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "严谨解释",
                    "risks": [],
                },
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性", "创造性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "整合专家A和专家B后的教学内容",
                    "risks": [],
                },
            ],
            "expert_b": [
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "生动解释",
                    "risks": [],
                }
            ],
            "judge": [
                {
                    "decision": "accept_with_minor_revision",
                    "accuracy_score": 5,
                    "adaptation_score": 4,
                    "completeness_score": 4,
                    "disputes": [],
                    "rationale": "可以合并",
                },
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "整合稿可以作为最终教学内容。",
                }
            ],
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        if agent is None:
            raise RuntimeError("Agent name is required for queued responses.")
        queue = self.responses_by_agent.get(agent)
        if not queue:
            raise RuntimeError(f"No queued response for agent={agent}")
        return queue.pop(0)

    def generate_with_tools(
        self, messages, tools, temperature, agent=None,
    ):
        from backend.app.core.llm import LLMResponseWithTools
        self.agents.append(agent)
        # tool_agent: return empty tool_calls to skip RAG, then provide content
        return LLMResponseWithTools(content="RAG context provided.", tool_calls=[])


def test_real_workflow_runs_full_agent_chain_with_fake_llm() -> None:
    llm_client = QueueLLMClient()

    state = run_workflow(
        session_id="demo-session",
        user_input="我想学习专利新颖性和创造性的区别",
        llm_client=llm_client,
    )

    completed = completed_teach_state(state)
    assert len(llm_client.calls) == 8
    assert completed["session_id"] == "demo-session"
    assert completed["learner_profile"]["knowledge_level"] == "beginner"
    assert len(completed["learning_path"]) == 1
    assert completed["expert_a_draft"]["style"] == "conservative_precise"
    assert completed["expert_a_draft"]["draft_stage"] == "integration"
    assert completed["expert_a_draft"]["teaching_content"] == "整合专家A和专家B后的教学内容"
    assert completed["expert_b_draft"]["style"] == "vivid_teaching"
    assert completed["judge_report"]["decision"] == "accept"
    assert "feedback_result" not in completed
    assert "final_answer" not in completed

    completed_events = [event for event in state["events"] if event["status"] == "completed"]
    event_names = [event["node"] for event in completed_events]
    assert event_names == [
        "route",
        "diagnosis",
        "planner",
        "tool_agent",
        "expert_a",
        "expert_b",
        "judge",
        "expert_a",
        "judge",
    ]
    assert all(event["round"] == 1 for event in completed_events)
    assert all(isinstance(event["timestamp"], str) and event["timestamp"] for event in completed_events)
    assert all(isinstance(event["duration_ms"], int) for event in completed_events)
    # Verify agent call order
    assert llm_client.agents[:3] == ["route", "diagnosis", "planner"]
    assert "tool_agent" in llm_client.agents
    assert "expert_a" in llm_client.agents
    assert "expert_b" in llm_client.agents
    assert "feedback" not in llm_client.agents
    forbidden_agents = {
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
        "feedback",
    }
    assert forbidden_agents.isdisjoint(set(llm_client.agents))
    assert llm_client.agents[-3:] == ["judge", "expert_a", "judge"]


def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow(llm_client=QueueLLMClient())
    mermaid = export_workflow_mermaid(workflow)

    assert "diagnosis" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "feedback" not in mermaid
    for removed_node in (
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
    ):
        assert removed_node not in mermaid

    output_path = tmp_path / "workflow.mmd"
    output_path.write_text(mermaid, encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == mermaid
