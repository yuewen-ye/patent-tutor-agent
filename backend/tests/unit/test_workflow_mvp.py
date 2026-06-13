from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_workflow

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []
        self.responses = [
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["法条概念辨析"],
                "learning_goal": "学习专利新颖性",
            },
            [
                {
                    "node_id": "patentability-basic",
                    "node_name": "专利授权条件基础",
                    "duration_min": 20,
                    "strategy": "先学授权条件",
                    "prerequisites": [],
                }
            ],
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "严谨解释",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "生动解释",
                "risks": [],
            },
            {
                "decision": "accept_with_minor_revision",
                "accuracy_score": 5,
                "adaptation_score": 4,
                "disputes": [],
                "rationale": "可以合并",
            },
            {
                "questionnaire": ["是否理解新颖性？"],
                "next_action": "做一道练习题",
                "profile_update_hint": "继续观察",
            },
        ]

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        return self.responses.pop(0)


def test_real_workflow_runs_full_agent_chain_with_fake_llm() -> None:
    llm_client = QueueLLMClient()

    state = run_workflow(
        session_id="demo-session",
        user_input="我想学习专利新颖性和创造性的区别",
        llm_client=llm_client,
    )

    assert len(llm_client.calls) == 6
    assert state["session_id"] == "demo-session"
    assert state["learner_profile"]["knowledge_level"] == "beginner"
    assert len(state["learning_path"]) == 1
    assert len(state["retrieval_context"]) == 1
    assert state["expert_a_draft"]["style"] == "conservative_precise"
    assert state["expert_b_draft"]["style"] == "vivid_teaching"
    assert state["judge_report"]["decision"] == "accept_with_minor_revision"
    assert state["feedback_result"]["next_action"] == "做一道练习题"
    assert state["final_answer"]["sources"] == ["第二十二条"]

    event_names = [event["node"] for event in state["events"] if event["status"] == "completed"]
    assert event_names == [
        "diagnosis",
        "planner",
        "retrieve_context",
        "expert_a",
        "expert_b",
        "judge",
        "feedback",
        "finalize",
    ]
    assert llm_client.agents == [
        "diagnosis",
        "planner",
        "expert_a",
        "expert_b",
        "judge",
        "feedback",
    ]


def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow(llm_client=QueueLLMClient())
    mermaid = export_workflow_mermaid(workflow)

    assert "diagnosis" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "feedback" in mermaid

    output_path = tmp_path / "workflow.mmd"
    output_path.write_text(mermaid, encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == mermaid
