from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from backend.app.agents import build_agent_nodes
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.graph.workflow import judge_route, publish_final_learning_node, run_workflow
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


class PhaseLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        raise AssertionError("not used")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("not used")


class WorkflowLLMClient:
    def __init__(self) -> None:
        draft_a: dict[str, object] = {
            "expert": "expert_a",
            "style": "conservative_precise",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "严谨解释新颖性。",
            "risks": [],
        }
        draft_b = {
            "expert": "expert_b",
            "style": "vivid_teaching",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "用案例解释新颖性。",
            "risks": [],
        }
        review_a = {
            "reviewer": "expert_a",
            "target": "expert_b",
            "review_opinions": [
                {
                    "category": "🟡",
                    "location": "案例",
                    "target_wrote": "案例说明",
                    "problem": "法条回扣不足",
                    "suggestion": "补充第二十二条",
                }
            ],
            "overall_assessment": "案例清楚，需要补法条。",
        }
        review_b = {
            "reviewer": "expert_b",
            "target": "expert_a",
            "review_opinions": [
                {
                    "category": "🌉",
                    "location": "正文",
                    "target_wrote": "严谨定义",
                    "problem": "缺少案例",
                    "suggestion": "增加案例",
                }
            ],
            "overall_assessment": "准确但需要降低理解门槛。",
        }
        integrated = dict(draft_a)
        integrated.update(
            {
                "teaching_content": "课程正文",
                "interactive_questions": ["如何判断新颖性？"],
                "exercises": [
                    {
                        "question_id": "q1",
                        "prompt": "该方案是否具备新颖性？",
                        "answer": "具备",
                        "explanation": "未被单一现有技术完整公开",
                    }
                ],
            }
        )
        self.queues: dict[str, list[object]] = {
            "route": [{"intent": "teach", "confidence": 1, "reason": "学习"}],
            "learner_state": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["新颖性", "现有技术"],
                    "learning_goal": "掌握专利新颖性",
                }
            ],
            "planner": [[{"node_id": "novelty", "node_name": "新颖性", "duration_min": 30,
                           "strategy": "先法条后案例", "prerequisites": []}]],
            "expert_a": [draft_a, review_a, draft_a, integrated],
            "expert_b": [draft_b, review_b, draft_b],
            "judge": [
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "通过",
                }
            ],
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        assert agent is not None
        return self.queues[agent].pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])

def test_graph_registers_one_learner_state_agent_instead_of_two_nodes() -> None:
    nodes = build_agent_nodes(PhaseLLMClient())

    assert "learner_state" in nodes
    assert "diagnosis" not in nodes
    assert "feedback" not in nodes


@pytest.mark.parametrize(
    ("decision", "round_number", "expected"),
    [
        ("accept", 1, "publish_final_learning"),
        ("accept_with_minor_revision", 1, "revise_integration"),
        ("revise", 2, "revise_integration"),
        ("revise", 3, "quality_gate_failed"),
    ],
)
def test_judge_quality_gate_only_publishes_accept(
    decision: str, round_number: int, expected: str
) -> None:
    state = cast(StateDict, {
        "session_id": "judge-test",
        "user_input": "test",
        "events": [],
        "judge_report": {"decision": decision},
        "judge_round": round_number,
        "max_debate_rounds": 3,
    })

    assert judge_route(state) == expected


def test_deterministic_publisher_excludes_internal_answer_key() -> None:
    updates = publish_final_learning_node(
        cast(StateDict, {
            "session_id": "session-1",
            "user_input": "学习新颖性",
            "events": [],
            "learning_path": [{"node_name": "新颖性", "strategy": "法条后案例"}],
            "expert_a_draft": {
                "teaching_content": "课程正文",
                "legal_basis": ["专利法第二十二条"],
                "interactive_questions": ["如何判断新颖性？"],
                "exercises": [
                    {
                        "question_id": "q1",
                        "prompt": "判断题",
                        "answer": "正确",
                        "explanation": "内部解析",
                    }
                ],
            },
        })
    )

    final_markdown = updates["final_learning_markdown"]
    assert "课程正文" in final_markdown
    assert "判断题" in final_markdown
    assert "正确" not in final_markdown
    assert "内部解析" not in final_markdown
    assert updates["exercise_answer_key"][0]["answer"] == "正确"


def test_full_teach_flow_writes_process_and_final_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    artifact_root = tmp_path / "artifacts"

    state = run_workflow(
        session_id="new-architecture",
        user_input="掌握专利新颖性",
        llm_client=WorkflowLLMClient(),
        artifact_root=artifact_root,
        learner_id="learner-1",
        max_debate_rounds=3,
    )

    session_root = artifact_root / "sessions" / "new-architecture"
    assert state["workflow_status"] == "completed"
    assert state["expert_a_cross_review"]["target"] == "expert_b"
    assert state["expert_b_cross_review"]["target"] == "expert_a"
    assert (session_root / "profile/learner_profile.md").is_file()
    assert (session_root / "path/dual_axis_snapshot.md").is_file()
    assert (session_root / "round-01/expert_a_cross_review.md").is_file()
    assert (session_root / "round-01/course_package.md").is_file()
    final = (session_root / "final_learning.md").read_text(encoding="utf-8")
    answer_key = (session_root / "internal/exercise_answer_key.md").read_text(encoding="utf-8")
    assert "该方案是否具备新颖性" in final
    assert "未被单一现有技术完整公开" not in final
    assert "未被单一现有技术完整公开" in answer_key
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"


def test_feedback_mode_reuses_learner_state_and_skips_course_agents(
    tmp_path: Path,
) -> None:
    class FeedbackLLM:
        agents: list[str | None]

        def __init__(self) -> None:
            self.agents = []

        def generate_json(
            self, messages: list[LLMMessage], temperature: float, agent: str | None = None
        ) -> object:
            self.agents.append(agent)
            return {
                "questionnaire": ["为什么选择该答案？"],
                "next_action": "复习单独对比原则",
                "profile_update_hint": "新颖性判断已改善",
            }

        def generate_with_tools(
            self,
            messages: list[LLMMessage],
            tools: list[ToolDefinition],
            temperature: float,
            agent: str | None = None,
        ) -> LLMResponseWithTools:
            raise AssertionError("feedback does not use tools")

    llm = FeedbackLLM()
    artifact_root = tmp_path / "artifacts"
    state = run_workflow(
        session_id="feedback-1",
        user_input='[{"question_id":"q1","observed_correct":true}]',
        llm_client=llm,
        artifact_root=artifact_root,
        learner_id="learner-1",
        workflow_mode="feedback",
        input_payload={
            "course_session_id": "course-1",
            "exercise_responses": [
                {"question_id": "q1", "answer": "A", "observed_correct": True}
            ],
        },
    )

    assert llm.agents == ["learner_state"]
    assert state["workflow_status"] == "completed"
    assert state["grading_report"][0]["question_id"] == "q1"
    root = artifact_root / "sessions" / "feedback-1" / "feedback"
    assert (root / "feedback_report.md").is_file()
    assert (root / "grading_report.md").is_file()
    assert (root / "learner_profile_update.md").is_file()


def test_three_rejected_judge_rounds_do_not_publish_final_learning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm = WorkflowLLMClient()
    integration = dict(cast(dict[str, object], llm.queues["expert_a"][-1]))
    llm.queues["expert_a"].extend([integration, integration])
    rejected = {
        "decision": "revise",
        "accuracy_score": 3,
        "adaptation_score": 4,
        "completeness_score": 3,
        "disputes": ["证据不足"],
        "rationale": "补充证据后重审",
        "revision_requests": [
            {
                "target": "expert_a",
                "issue": "证据不足",
                "required_change": "补充法条和案例依据",
            }
        ],
    }
    llm.queues["judge"] = [rejected, rejected, rejected]
    artifact_root = tmp_path / "artifacts"

    state = run_workflow(
        session_id="rejected-course",
        user_input="掌握专利新颖性",
        llm_client=llm,
        artifact_root=artifact_root,
        max_debate_rounds=3,
    )

    session_root = artifact_root / "sessions" / "rejected-course"
    assert state["workflow_status"] == "quality_gate_failed"
    assert state["judge_round"] == 3
    assert not (session_root / "final_learning.md").exists()
    assert (session_root / "round-02/course_package.md").is_file()
    assert (session_root / "round-03/judge_report.md").is_file()
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "quality_gate_failed"
