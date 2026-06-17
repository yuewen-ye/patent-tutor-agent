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
                }
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
            "cross_review_a": [
                {
                    "reviewer": "expert_a",
                    "target": "expert_b",
                    "review_opinions": [
                        {
                            "category": "🔴",
                            "location": "核心段落",
                            "target_wrote": "新颖性就是...",
                            "problem": "遗漏抵触申请要件",
                            "suggestion": "补充抵触申请说明",
                            "basis": "专利法第22条第2款",
                        }
                    ],
                    "positive_confirmation": "B的引用均检索验证",
                    "overall_assessment": "可理解性好，需补充法律要件",
                }
            ],
            "cross_review_b": [
                {
                    "reviewer": "expert_b",
                    "target": "expert_a",
                    "review_opinions": [
                        {
                            "category": "🟡",
                            "location": "概念解释",
                            "target_wrote": "新颖性要求...",
                            "problem": "对初学者太抽象",
                            "suggestion": "增加日常类比",
                            "basis": None,
                        }
                    ],
                    "positive_confirmation": "A的法条引用准确",
                    "overall_assessment": "法律准确，可读性可改善",
                }
            ],
            "expert_a_revise": [
                {
                    "agent": "expert_a",
                    "revisions": [
                        {
                            "review_id": 1,
                            "review_category": "🟡",
                            "review_summary": "表述太抽象",
                            "response": "已增加一句话概括",
                            "status": "accepted",
                        }
                    ],
                    "unresolved_disputes": [],
                    "modified_paragraphs": ["核心理解"],
                    "modification_tags": ["[经B审查修正]"],
                }
            ],
            "expert_b_revise": [
                {
                    "agent": "expert_b",
                    "revisions": [
                        {
                            "review_id": 1,
                            "review_category": "🔴",
                            "review_summary": "遗漏抵触申请要件",
                            "response": "已补充",
                            "status": "accepted",
                        }
                    ],
                    "unresolved_disputes": [],
                    "modified_paragraphs": ["核心概念"],
                    "modification_tags": ["[经A审查修正]"],
                }
            ],
            "joint_synthesis": [
                {
                    "node_id": "novelty",
                    "title": "新颖性判断标准",
                    "sections": [
                        {
                            "heading": "法条依据",
                            "content": "专利法第22条第2款...",
                            "source": "A",
                            "note": None,
                        },
                        {
                            "heading": "通俗解释",
                            "content": "新颖性是指...",
                            "source": "B",
                            "note": None,
                        },
                    ],
                    "transition_notes": [],
                    "unresolved_in_synthesis": [],
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
                }
            ],
            "feedback": [
                {
                    "questionnaire": ["是否理解新颖性？"],
                    "next_action": "做一道练习题",
                    "profile_update_hint": "继续观察",
                }
            ],
            "finalize": [
                {
                    "title": "个性化知识产权学习建议",
                    "content": "整合后的教学内容",
                    "sources": ["第二十二条"],
                    "judge_summary": None,
                    "next_questions": None,
                }
            ],
            # lightweight_review not queued — not called when decision=accept
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
    # P0.1: route + diagnosis + planner + expert_a + expert_b +
    #       cross_review_a + cross_review_b + expert_a_revise + expert_b_revise +
    #       joint_synthesis + judge + feedback + finalize = 13 generate_json calls
    # tool_agent uses generate_with_tools, not in calls
    assert len(llm_client.calls) == 13
    assert completed["session_id"] == "demo-session"
    assert completed["learner_profile"]["knowledge_level"] == "beginner"
    assert len(completed["learning_path"]) == 1
    assert completed["expert_a_draft"]["style"] == "conservative_precise"
    assert completed["expert_b_draft"]["style"] == "vivid_teaching"
    # P0.1: New state fields
    assert completed["cross_review_a"]["reviewer"] == "expert_a"
    assert completed["cross_review_b"]["reviewer"] == "expert_b"
    assert completed["revision_record_a"]["agent"] == "expert_a"
    assert completed["revision_record_b"]["agent"] == "expert_b"
    assert completed["joint_synthesis_output"]["title"] == "新颖性判断标准"
    assert completed["judge_report"]["decision"] == "accept_with_minor_revision"
    assert completed["feedback_result"]["next_action"] == "做一道练习题"
    assert "第二十二条" in str(completed["final_answer"].get("sources", []))

    completed_events = [event for event in state["events"] if event["status"] == "completed"]
    event_names = [event["node"] for event in completed_events]
    assert event_names == [
        "route",
        "diagnosis",
        "planner",
        "tool_agent",
        "expert_a",
        "expert_b",
        "cross_review_a",
        "cross_review_b",
        "expert_a",
        "expert_b",
        "joint_synthesis",
        "judge",
        "feedback",
        "finalize",
    ]
    assert all(event["round"] == 1 for event in completed_events)
    assert all(isinstance(event["timestamp"], str) and event["timestamp"] for event in completed_events)
    assert all(isinstance(event["duration_ms"], int) for event in completed_events)
    # Verify agent call order
    assert llm_client.agents[:3] == ["route", "diagnosis", "planner"]
    assert "tool_agent" in llm_client.agents
    assert "expert_a" in llm_client.agents
    assert "expert_b" in llm_client.agents
    assert "cross_review_a" in llm_client.agents
    assert "cross_review_b" in llm_client.agents
    assert "joint_synthesis" in llm_client.agents
    assert llm_client.agents[-3:] == ["judge", "feedback", "finalize"]


def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow(llm_client=QueueLLMClient())
    mermaid = export_workflow_mermaid(workflow)

    assert "diagnosis" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "feedback" in mermaid
    # P0.1: New nodes
    assert "cross_review_a" in mermaid
    assert "cross_review_b" in mermaid
    assert "expert_a_revise" in mermaid
    assert "expert_b_revise" in mermaid
    assert "joint_synthesis" in mermaid
    assert "lightweight_review" in mermaid

    output_path = tmp_path / "workflow.mmd"
    output_path.write_text(mermaid, encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == mermaid
