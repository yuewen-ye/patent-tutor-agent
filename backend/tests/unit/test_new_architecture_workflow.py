from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from backend.app.agents import build_agent_nodes
from backend.app.agents.diagnosis import build_diagnosis_feedback_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_workflow
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def disable_pptx(monkeypatch: pytest.MonkeyPatch) -> None:
    """PPTX generation is tested separately; these workflow tests focus on graph topology."""
    monkeypatch.setenv("PATENT_TUTOR_PPTX_ENABLED", "false")


class PhaseLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        raise AssertionError("not used")

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        # Streaming callers accumulate the full text then parse it as JSON.
        yield json.dumps(self.generate_json(messages, temperature, agent), ensure_ascii=False)

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
            "planner": [{
                "plan_action": "replace",
                "decision_reason": "首次建立路线",
                "nodes": [
                    {"node_id": "patent-law-foundation", "node_name": "专利法律制度基础", "duration_min": 20, "strategy": "概念", "prerequisites": [], "difficulty_cap": "L1"},
                    {"node_id": "patent-system-overview", "node_name": "专利制度概论", "duration_min": 20, "strategy": "框架", "prerequisites": ["patent-law-foundation"], "difficulty_cap": "L2"},
                ],
                "question_scope": {"backward_review": [], "forward_probe": [], "weakness_probe": []},
                "iteration_directive": {"type": "无", "trigger": "首轮", "action": "反馈后调整"},
                "teaching_guidance": {"lesson_focus": ["制度基础"], "priority_weaknesses": [], "teaching_strategy": "规则讲解", "confusion_guidance": "辨析相关概念"},
            }],
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
            "slide_deck": [
                {
                    "slides": [
                        {
                            "id": "slide_001",
                            "order": 1,
                            "type": "title",
                            "title": "专利新颖性",
                            "content": {"subtitle": "三性之一"},
                            "narration": {"text": "今天我们来学习专利新颖性。"},
                        },
                        {
                            "id": "slide_002",
                            "order": 2,
                            "type": "summary",
                            "title": "小结",
                            "content": {"takeaways": ["新颖性=与现有技术不同"]},
                            "narration": {"text": "最后我们总结要点。"},
                        },
                    ],
                    "slide_to_block_id": {},
                },
            ],
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        assert agent is not None
        with self._agents_lock:
            self.agents.append(agent)
        return self.queues[agent].pop(0)

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        assert agent is not None
        with self._agents_lock:
            self.agents.append(agent)
        payload = self.queues[agent].pop(0)
        if agent == "planner" and payload.get("plan_action") == "replace":
            user_text = messages[-1].content
            marker = "# 算法候选路线"
            if marker in user_text:
                candidate_text = user_text.split(marker, 1)[1].split("\n# 基于学习目标", 1)[0]
                payload = dict(payload)
                payload["nodes"] = json.loads(candidate_text.split("\n", 1)[1])
        return iter([json.dumps(payload, ensure_ascii=False)])

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

    def _track_phase(self, agent: str | None) -> None:
        if agent in self._phase_calls:
            with self._phase_lock:
                phase_index = self._phase_calls[agent]
                self._phase_calls[agent] += 1
            if phase_index < len(self._phase_barriers):
                self._phase_barriers[phase_index].wait(timeout=2)

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self._track_phase(agent)
        return super().generate_json(messages, temperature, agent)

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        self._track_phase(agent)
        return super().generate_json_stream(
            messages,
            temperature,
            agent,
            schema_name=schema_name,
            json_schema=json_schema,
        )


def test_graph_registers_diagnosis_feedback_agent_name() -> None:
    nodes = build_agent_nodes(PhaseLLMClient())

    assert "diagnosis_feedback" in nodes
    assert "diagnosis" not in nodes
    assert "feedback" not in nodes


def test_graph_parallelizes_experts_and_branches_after_judge() -> None:
    workflow = build_workflow(llm_client=PhaseLLMClient(), slide_deck_enabled=True)
    mermaid = export_workflow_mermaid(workflow)
    edges = {(edge.source, edge.target) for edge in workflow.get_graph().edges}

    assert ("planner", "expert_a") in edges
    assert ("planner", "expert_b") in edges
    assert ("expert_a", "_experts_barrier") in edges
    assert ("expert_b", "_experts_barrier") in edges
    assert ("judge", "expert_a_integration") in edges
    assert ("judge", "slide_deck") in edges
    assert ("slide_deck", "__end__") in edges
    assert "_complete" not in {edge.target for edge in workflow.get_graph().edges}
    assert "publish_final_learning" not in mermaid
    assert "quality_gate_failed" not in mermaid
    assert "revise_integration" not in mermaid


def test_rag_tool_flag_defaults_on_and_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.graph.workflow import _is_rag_tool_enabled

    monkeypatch.delenv("PATENT_TUTOR_RAG_TOOL_ENABLED", raising=False)
    assert _is_rag_tool_enabled() is True
    monkeypatch.setenv("PATENT_TUTOR_RAG_TOOL_ENABLED", "true")
    assert _is_rag_tool_enabled() is True
    monkeypatch.setenv("PATENT_TUTOR_RAG_TOOL_ENABLED", "false")
    assert _is_rag_tool_enabled() is False
    for invalid in ("True", " false", "false ", "0"):
        monkeypatch.setenv("PATENT_TUTOR_RAG_TOOL_ENABLED", invalid)
        with pytest.raises(ValueError, match="PATENT_TUTOR_RAG_TOOL_ENABLED"):
            _is_rag_tool_enabled()


def test_disabled_rag_tool_is_recorded_in_initial_state() -> None:
    state = run_workflow(
        session_id="rag-off",
        user_input="test",
        llm_client=WorkflowLLMClient(),
        slide_deck_enabled=False,
        debate_enabled=False,
        rag_tool_enabled=False,
    )
    assert state["rag_tool_enabled"] is False
    assert any(
        event["message"] == "rag_tool_enabled=false (deployment setting)"
        for event in state["events"]
    )


def test_debate_flag_defaults_on_and_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.graph.workflow import _is_debate_enabled

    monkeypatch.delenv("PATENT_TUTOR_DEBATE_ENABLED", raising=False)
    assert _is_debate_enabled() is True
    monkeypatch.setenv("PATENT_TUTOR_DEBATE_ENABLED", "false")
    assert _is_debate_enabled() is False
    for invalid in ("fasle", "True", " false", "false "):
        monkeypatch.setenv("PATENT_TUTOR_DEBATE_ENABLED", invalid)
        with pytest.raises(ValueError, match="PATENT_TUTOR_DEBATE_ENABLED"):
            _is_debate_enabled()


def test_graph_omits_debate_nodes_when_disabled() -> None:
    workflow = build_workflow(
        llm_client=PhaseLLMClient(), slide_deck_enabled=True, debate_enabled=False
    )
    mermaid = export_workflow_mermaid(workflow)
    edges = {(edge.source, edge.target) for edge in workflow.get_graph().edges}
    nodes = set(workflow.get_graph().nodes)

    assert ("planner", "expert_a") in edges
    assert ("expert_a", "judge") in edges
    assert ("judge", "slide_deck") in edges
    assert "expert_b" not in nodes
    assert "_experts_barrier" not in nodes
    assert "expert_a_integration" not in nodes
    assert "expert_b" not in mermaid
    assert "cross_review" not in mermaid
    assert "revision" not in mermaid


def test_single_agent_teach_flow_writes_course_package_without_debate_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    artifact_root = tmp_path / "artifacts"
    llm = WorkflowLLMClient()

    state = run_workflow(
        session_id="single-agent",
        user_input="掌握专利新颖性",
        llm_client=llm,
        artifact_root=artifact_root,
        learner_id="learner-1",
        debate_enabled=False,
    )

    session_root = artifact_root / "sessions" / "single-agent"
    assert state["workflow_status"] == "completed"
    assert state["teach_phase"] == "single_agent"
    assert state["expert_phase"] == "draft"
    assert {
        key: value
        for key, value in state["course_package"].items()
        if key != "markdown_artifact"
    } == {
        key: value
        for key, value in state["expert_a_draft"].items()
        if key != "markdown_artifact"
    }
    assert llm.agents.count("expert_a") == 1
    assert "expert_b" not in llm.agents
    assert "expert_b_draft" not in state
    assert "expert_a_cross_review" not in state
    assert "expert_b_cross_review" not in state
    assert "expert_a_revision" not in state
    assert "expert_b_revision" not in state
    assert (session_root / "round-01/course_package.md").is_file()
    assert not (session_root / "round-01/expert_b_draft.md").exists()
    assert not (session_root / "round-01/expert_a_cross_review.md").exists()
    assert not (session_root / "round-01/expert_a_revision.md").exists()


def test_graph_skips_slide_deck_when_disabled() -> None:
    workflow = build_workflow(llm_client=PhaseLLMClient(), slide_deck_enabled=False)
    mermaid = export_workflow_mermaid(workflow)
    edges = {(edge.source, edge.target) for edge in workflow.get_graph().edges}

    assert ("judge", "expert_a_integration") in edges
    assert ("judge", "_complete") in edges
    assert ("_complete", "__end__") in edges
    assert ("judge", "slide_deck") not in edges
    assert "slide_deck" not in mermaid


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
                    "questionnaire_responses": [{"question_id": "Q01", "answer": "B"}],
                    "questionnaire_context": [
                        {
                            "question_id": "Q01",
                            "question": "是否接触过专利法？",
                            "options": {"A": "系统学习过", "B": "零基础"},
                            "answer": "B",
                            "selected_option": "零基础",
                        }
                    ],
                },
            },
        )
    )

    prompt_text = "\n".join(message.content or "" for message in llm.messages)
    assert "Q01" in prompt_text
    assert "是否接触过专利法" in prompt_text
    assert "零基础" in prompt_text


def test_diagnosis_derives_cold_start_level_instead_of_using_llm_level() -> None:
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
    assert result["learner_profile"]["weak_points"] == []


def test_diagnosis_discards_llm_knowledge_and_uses_cold_start_without_cat() -> None:
    class PartialKnowledgeLLM(PhaseLLMClient):
        def generate_json(
            self, messages: list[LLMMessage], temperature: float, agent: str | None = None
        ) -> object:
            return {
                "education_background": "知识产权管理经验",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["创造性"],
                "learning_goal": "学习创造性判断",
                "confidence": 0.6,
                "five_dimensions": {
                    "knowledge": {
                        "inventive-step": {
                            "pl": 0.2,
                            "ci_low": 0.08,
                            "ci_high": 0.38,
                            "observations": 2,
                            "low_confidence": True,
                        }
                    },
                    "cognition": {
                        "remember": 0.6,
                        "understand": 0.5,
                        "apply": 0.3,
                        "analyze": 0.2,
                        "evaluate": 0.1,
                        "create": 0.05,
                    },
                    "style": {
                        "perception": {"chosen": "sensing", "strength": 0.7},
                        "input": {"chosen": "verbal", "strength": 0.6},
                        "processing": {"chosen": "reflective", "strength": 0.6},
                        "understanding": {"chosen": "sequential", "strength": 0.7},
                    },
                    "progress": {
                        "completed_nodes": [],
                        "current_node": "inventive-step",
                        "pending_nodes": [],
                        "overall_completion_ratio": 0.0,
                    },
                    "affect": {
                        "primary_state": "interested",
                        "confidence": 0.6,
                        "signals": ["主动描述学习需求"],
                    },
                },
            }

    result = build_diagnosis_feedback_node(PartialKnowledgeLLM())(
        cast(
            StateDict,
            {
                "session_id": "partial-knowledge",
                "user_input": "学习创造性判断",
                "events": [],
                "diagnosis_feedback_phase": "diagnosis",
                "input_payload": {"questionnaire_responses": []},
            },
        )
    )

    knowledge = result["learner_profile"]["five_dimensions"]["knowledge"]
    assert len(knowledge) == 69
    assert knowledge["inventive-step"]["pl"] == 0.15
    assert knowledge["inventive-step"]["observations"] == 0
    assert knowledge["novelty"] == {
        "pl": 0.15,
        "ci_low": 0.02,
        "ci_high": 0.4,
        "observations": 0,
        "low_confidence": True,
        "inferred": False,
    }


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
    assert list((session_root / "profile").glob("learner_profile*.md")) == [
        session_root / "profile/learner_profile.md"
    ]
    assert state["learner_profile"]["five_dimensions"]["progress"]["current_node"]
    assert (session_root / "path/dual_axis_snapshot.md").is_file()
    assert (session_root / "round-01/expert_a_cross_review.md").is_file()
    assert (session_root / "round-01/course_package.md").is_file()
    assert (session_root / "round-01/judge_report.md").is_file()
    assert not (session_root / "feedback/feedback_report.md").exists()
    assert "feedback_result" not in state
    assert llm.agents.count("diagnosis_feedback") == 1
    assert llm.agents[-1] == "slide_deck"
    assert not (session_root / "final_learning.md").exists()
    assert not (session_root / "internal/exercise_answer_key.md").exists()
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    profile_artifacts = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact["kind"] == "learner_profile_report"
    ]
    assert len(profile_artifacts) == 1
    assert profile_artifacts[0]["created_by"] == "diagnosis_feedback"


def test_accepted_teach_flow_skips_slide_deck_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    artifact_root = tmp_path / "artifacts"
    llm = WorkflowLLMClient()

    state = run_workflow(
        session_id="no-slide-deck",
        user_input="掌握专利新颖性",
        llm_client=llm,
        artifact_root=artifact_root,
        learner_id="learner-1",
        slide_deck_enabled=False,
    )

    session_root = artifact_root / "sessions" / "no-slide-deck"
    assert state["workflow_status"] == "completed"
    assert "judge_report" in state
    assert state["judge_report"]["decision"] == "accept"
    assert "course_slides" not in state
    assert "slide_deck" not in llm.agents
    assert llm.agents[-1] == "judge"
    assert (session_root / "round-01/course_package.md").is_file()
    assert not (session_root / "round-01/course_slides.md").exists()
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
                "bkt_update": {
                    "skill_id": "novelty",
                    "observed_correct": True,
                    "error_pattern": "none",
                    "confidence": 0.9,
                },
                "five_dimensions": {"knowledge": {"novelty": {"pl": 0.3, "ci_low": 0.15, "ci_high": 0.5, "observations": 3, "low_confidence": False}}, "cognition": {"remember": 0.8, "understand": 0.6, "apply": 0.4, "analyze": 0.3, "evaluate": 0.2, "create": 0.1}, "style": {"perception": {"chosen": "sensing", "strength": 0.7}, "input": {"chosen": "visual", "strength": 0.6}, "processing": {"chosen": "active", "strength": 0.55}, "understanding": {"chosen": "sequential", "strength": 0.65}}, "progress": {"completed_nodes": ["patent-law-basic"], "current_node": "novelty-basic", "pending_nodes": ["inventiveness"], "avg_time_per_node_min": 22, "overall_completion_ratio": 0.3}, "affect": {"primary_state": "interested", "confidence": 0.6, "signals": ["主动提问"]}},
            }

        def generate_json_stream(
            self,
            messages: list[LLMMessage],
            temperature: float,
            agent: str | None = None,
            *,
            schema_name: str | None = None,
            json_schema: dict[str, object] | None = None,
        ) -> Iterator[str]:
            # Delegates to generate_json for the payload; tracking happens there.
            yield json.dumps(self.generate_json(messages, temperature, agent), ensure_ascii=False)

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
            "bkt_updates": [
                {
                    "skill_id": "novelty",
                    "observed_correct": True,
                    "posterior_pl": 0.72,
                }
            ],
            "mastery_snapshot": {
                "novelty": {
                    "pl": 0.72,
                    "ci_low": 0.4,
                    "ci_high": 0.9,
                    "observations": 4,
                    "low_confidence": False,
                    "inferred": False,
                }
            },
        },
    )

    assert llm.agents == ["diagnosis_feedback"]
    assert "workflow_status" in state
    assert "grading_report" in state
    assert state["workflow_status"] == "completed"
    assert state["grading_report"][0]["question_id"] == "q1"
    assert state["feedback_result"]["bkt_update"]["error_pattern"] is None
    assert state["feedback_result"]["five_dimensions"]["knowledge"]["novelty"]["pl"] == 0.72
    assert state["learner_profile_update"]["five_dimensions"]["knowledge"]["novelty"] == (
        state["feedback_result"]["five_dimensions"]["knowledge"]["novelty"]
    )
    root = artifact_root / "sessions" / "feedback-1" / "feedback"
    assert (root / "feedback_report.md").is_file()
    assert (root / "grading_report.md").is_file()
    assert (root / "learner_profile_update.md").is_file()


def test_rejected_judge_reintegrates_until_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """judge 判 revise 时应打回 expert_a 重新整合（最终稿被修正），复审 accept 后完成，judge 至多 3 轮。"""
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    # 默认 max_revisions=0 会跳过修订循环；本测试专门验证循环机制，显式启用上限。
    from backend.app.core.agent_runtime_config import AgentRuntimeSettings
    from backend.app.graph import workflow as workflow_module

    original_settings = workflow_module.agent_runtime_settings

    def settings_with_revision_cap(agent: str) -> AgentRuntimeSettings:
        settings = original_settings(agent)
        if agent == "judge":
            return settings.model_copy(update={"max_revisions": 3})
        return settings

    monkeypatch.setattr(workflow_module, "agent_runtime_settings", settings_with_revision_cap)
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
    llm.queues["judge"] = [rejected, rejected, accepted]
    # 重新整合需要 expert_a 多一次 integration 响应（基于原整合稿修正）
    integrated_revised = dict(cast(dict[str, object], llm.queues["expert_a"][3]))
    integrated_revised["teaching_content"] = "修正后的课程正文（已补充法条与案例依据）"
    llm.queues["expert_a"].append(integrated_revised)
    llm.queues["expert_a"].append(dict(integrated_revised))

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
    # 2 次不通过后，第 3 次通过 = 3 次 judge
    assert llm.agents.count("judge") == 3
    # 首轮 4 次，再加上 2 次重新整合
    assert llm.agents.count("expert_a") == 6
    # 最终稿被修改：course_package 是重新整合的修正版
    assert state["course_package"]["teaching_content"] == (
        "修正后的课程正文（已补充法条与案例依据）"
    )
    assert state["judge_report"]["decision"] == "accept_with_minor_revision"
    assert (session_root / "round-01/course_package.md").is_file()
    assert (session_root / "round-01/judge_report.md").is_file()
    manifest = json.loads((session_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
