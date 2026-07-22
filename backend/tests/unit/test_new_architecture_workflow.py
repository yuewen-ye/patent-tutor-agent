from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import cast

import pytest

from backend.app.agents import build_agent_nodes
from backend.app.agents.diagnosis import build_diagnosis_feedback_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_workflow
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
        self.agents: list[str] = []
        self._agents_lock = threading.Lock()
        draft_a: dict[str, object] = {
            "expert": "expert_a",
            "style": "conservative",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "严谨解释新颖性。",
            "risks": [],
        }
        draft_b = {
            "expert": "expert_b",
            "style": "accessible",
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
                "interactive_questions": [{"qid": "q1", "category": "理解", "difficulty": "易", "question": "如何判断新颖性？", "answer": ""}],
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
            "diagnosis_feedback": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["新颖性", "现有技术"],
                    "learning_goal": "掌握专利新颖性",
                },
                {
                    "questionnaire": ["本节内容是否清楚？"],
                    "next_action": "完成本节练习",
                    "profile_update_hint": "记录本轮审核结果",
                    "five_dimensions": {"knowledge": {"novelty": {"pl": 0.3, "ci_low": 0.15, "ci_high": 0.5, "observations": 3, "low_confidence": False}}, "cognition": {"remember": 0.8, "understand": 0.6, "apply": 0.4, "analyze": 0.3, "evaluate": 0.2, "create": 0.1}, "style": {"perception": {"chosen": "sensing", "strength": 0.7}, "input": {"chosen": "visual", "strength": 0.6}, "processing": {"chosen": "active", "strength": 0.55}, "understanding": {"chosen": "sequential", "strength": 0.65}}, "progress": {"completed_nodes": ["patent-law-basic"], "current_node": "novelty-basic", "pending_nodes": ["inventiveness"], "avg_time_per_node_min": 22, "overall_completion_ratio": 0.3}, "affect": {"primary_state": "interested", "confidence": 0.6, "signals": ["主动提问"]}},
                },
            ],
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
        with self._agents_lock:
            self.agents.append(agent)
        return self.queues[agent].pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


class ParallelPhaseLLMClient(WorkflowLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self._phase_calls = {"expert_a": 0, "expert_b": 0}
        self._phase_lock = threading.Lock()
        self._phase_barriers = [threading.Barrier(2) for _ in range(3)]

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        if agent in self._phase_calls:
            with self._phase_lock:
                phase_index = self._phase_calls[agent]
                self._phase_calls[agent] += 1
            if phase_index < len(self._phase_barriers):
                self._phase_barriers[phase_index].wait(timeout=2)
        return super().generate_json(messages, temperature, agent)


def test_graph_registers_diagnosis_feedback_agent_name() -> None:
    nodes = build_agent_nodes(PhaseLLMClient())

    assert "diagnosis_feedback" in nodes
    assert "diagnosis" not in nodes
    assert "feedback" not in nodes


def test_graph_parallelizes_experts_and_branches_after_judge() -> None:
    workflow = build_workflow(llm_client=PhaseLLMClient())
    mermaid = export_workflow_mermaid(workflow)
    edges = {(edge.source, edge.target) for edge in workflow.get_graph().edges}

    assert ("planner", "expert_a") in edges
    assert ("planner", "expert_b") in edges
    assert ("expert_a", "_experts_barrier") in edges
    assert ("expert_b", "_experts_barrier") in edges
    assert ("judge", "expert_a_integration") in edges
    assert ("judge", "__end__") in edges
    assert "publish_final_learning" not in mermaid
    assert "quality_gate_failed" not in mermaid
    assert "revise_integration" not in mermaid


def test_diagnosis_receives_questionnaire_responses() -> None:
    class CapturingLLM(PhaseLLMClient):
        def __init__(self) -> None:
            self.messages: list[LLMMessage] = []

        def generate_json(
            self, messages: list[LLMMessage], temperature: float, agent: str | None = None
        ) -> object:
            self.messages = messages
            assert agent == "diagnosis_feedback"
            return {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["新颖性"],
                "learning_goal": "学习新颖性",
            }

    llm = CapturingLLM()
    node = build_diagnosis_feedback_node(llm)
    node(
        cast(
            StateDict,
            {
                "session_id": "questionnaire-diagnosis",
                "user_input": "学习新颖性",
                "events": [],
                "diagnosis_feedback_phase": "diagnosis",
                "input_payload": {
                    "questionnaire_responses": [{"question_id": "Q01", "answer": "零基础"}]
                },
            },
        )
    )

    prompt_text = "\n".join(message.content or "" for message in llm.messages)
    assert "Q01" in prompt_text
    assert "零基础" in prompt_text


def test_diagnosis_normalizes_unknown_level_to_beginner() -> None:
    class UnknownLevelLLM(PhaseLLMClient):
        def generate_json(
            self, messages: list[LLMMessage], temperature: float, agent: str | None = None
        ) -> object:
            return {
                "education_background": "unknown",
                "knowledge_level": "unknown",
                "learning_style": "case_first_then_rule",
                "weak_points": "新颖性",
                "learning_goal": "学习新颖性",
            }

    result = build_diagnosis_feedback_node(UnknownLevelLLM())(
        cast(
            StateDict,
            {
                "session_id": "unknown-level",
                "user_input": "学习新颖性",
                "events": [],
                "diagnosis_feedback_phase": "diagnosis",
            },
        )
    )

    assert result["learner_profile"]["knowledge_level"] == "beginner"
    assert result["learner_profile"]["weak_points"] == ["新颖性"]


def test_experts_run_concurrently_in_draft_review_and_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm = ParallelPhaseLLMClient()

    state = run_workflow(
        session_id="parallel-experts",
        user_input="掌握专利新颖性",
        llm_client=llm,
    )

    assert "judge_report" in state
    assert state["judge_report"]["decision"] == "accept"
    assert llm._phase_calls == {"expert_a": 4, "expert_b": 3}


def test_accepted_teach_flow_waits_for_learner_answers_and_keeps_process_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    artifact_root = tmp_path / "artifacts"
    llm = WorkflowLLMClient()

    state = run_workflow(
        session_id="new-architecture",
        user_input="掌握专利新颖性",
        llm_client=llm,
        artifact_root=artifact_root,
        learner_id="learner-1",
    )

    session_root = artifact_root / "sessions" / "new-architecture"
    assert "workflow_status" in state
    assert "expert_a_cross_review" in state
    assert "expert_b_cross_review" in state
    assert state["workflow_status"] == "completed"
    assert state["expert_a_cross_review"]["target"] == "expert_b"
    assert state["expert_b_cross_review"]["target"] == "expert_a"
    assert (session_root / "profile/learner_profile.md").is_file()
    assert (session_root / "path/dual_axis_snapshot.md").is_file()
    assert (session_root / "round-01/expert_a_cross_review.md").is_file()
    assert (session_root / "round-01/course_package.md").is_file()
    assert (session_root / "round-01/judge_report.md").is_file()
    assert not (session_root / "feedback/feedback_report.md").exists()
    assert "feedback_result" not in state
    assert llm.agents.count("diagnosis_feedback") == 1
    assert llm.agents[-1] == "judge"
    assert not (session_root / "final_learning.md").exists()
    assert not (session_root / "internal/exercise_answer_key.md").exists()
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"


def test_feedback_mode_reuses_diagnosis_feedback_and_skips_course_agents(
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
                "five_dimensions": {"knowledge": {"novelty": {"pl": 0.3, "ci_low": 0.15, "ci_high": 0.5, "observations": 3, "low_confidence": False}}, "cognition": {"remember": 0.8, "understand": 0.6, "apply": 0.4, "analyze": 0.3, "evaluate": 0.2, "create": 0.1}, "style": {"perception": {"chosen": "sensing", "strength": 0.7}, "input": {"chosen": "visual", "strength": 0.6}, "processing": {"chosen": "active", "strength": 0.55}, "understanding": {"chosen": "sequential", "strength": 0.65}}, "progress": {"completed_nodes": ["patent-law-basic"], "current_node": "novelty-basic", "pending_nodes": ["inventiveness"], "avg_time_per_node_min": 22, "overall_completion_ratio": 0.3}, "affect": {"primary_state": "interested", "confidence": 0.6, "signals": ["主动提问"]}},
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
            "exercise_responses": [{"question_id": "q1", "answer": "A", "observed_correct": True}],
        },
    )

    assert llm.agents == ["diagnosis_feedback"]
    assert "workflow_status" in state
    assert "grading_report" in state
    assert state["workflow_status"] == "completed"
    assert state["grading_report"][0]["question_id"] == "q1"
    root = artifact_root / "sessions" / "feedback-1" / "feedback"
    assert (root / "feedback_report.md").is_file()
    assert (root / "grading_report.md").is_file()
    assert (root / "learner_profile_update.md").is_file()


def test_rejected_judge_reintegrates_until_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """judge 判 revise 时应打回 expert_a 重新整合（最终稿被修正），二审 accept 后完成。"""
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm = WorkflowLLMClient()
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
    accepted = {
        "decision": "accept_with_minor_revision",
        "accuracy_score": 5,
        "adaptation_score": 5,
        "completeness_score": 5,
        "disputes": [],
        "rationale": "修正后通过",
    }
    llm.queues["judge"] = [rejected, rejected, rejected, accepted]
    # 重新整合需要 expert_a 多一次 integration 响应（基于原整合稿修正）
    integrated_revised = dict(llm.queues["expert_a"][3])
    integrated_revised["teaching_content"] = "修正后的课程正文（已补充法条与案例依据）"
    llm.queues["expert_a"].append(integrated_revised)
    llm.queues["expert_a"].extend([dict(integrated_revised), dict(integrated_revised)])

    artifact_root = tmp_path / "artifacts"
    state = run_workflow(
        session_id="rejected-course",
        user_input="掌握专利新颖性",
        llm_client=llm,
        artifact_root=artifact_root,
    )

    session_root = artifact_root / "sessions" / "rejected-course"
    assert "workflow_status" in state
    assert state["workflow_status"] == "completed"
    assert "judge_attempts" not in state
    # 3 次不通过后，第 4 次通过 = 4 次 judge
    assert llm.agents.count("judge") == 4
    # 首轮 4 次，再加上 3 次重新整合
    assert llm.agents.count("expert_a") == 7
    # 最终稿被修改：course_package 是重新整合的修正版
    assert state["course_package"]["teaching_content"] == (
        "修正后的课程正文（已补充法条与案例依据）"
    )
    assert state["judge_report"]["decision"] == "accept_with_minor_revision"
    assert (session_root / "round-01/course_package.md").is_file()
    assert (session_root / "round-01/judge_report.md").is_file()
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
