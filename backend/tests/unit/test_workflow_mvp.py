from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolCall, ToolDefinition
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_workflow
from backend.app.memory import learner_namespace
from backend.tests.helpers import completed_teach_state

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []
        self.tool_call_agents: list[str | None] = []
        self.responses_by_agent: dict[str, list[object]] = {
            "route": [
                {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            ],
            "learner_state": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["法条概念辨析"],
                    "learning_goal": "学习专利新颖性",
                },
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
                    "reviewer": "expert_a",
                    "target": "expert_b",
                    "review_opinions": [{
                        "category": "🟡", "location": "正文", "target_wrote": "案例",
                        "problem": "法条不足", "suggestion": "补法条",
                    }],
                    "overall_assessment": "需补法条",
                },
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "严谨解释修订稿",
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
                },
                {
                    "reviewer": "expert_b",
                    "target": "expert_a",
                    "review_opinions": [{
                        "category": "🌉", "location": "正文", "target_wrote": "定义",
                        "problem": "案例不足", "suggestion": "补案例",
                    }],
                    "overall_assessment": "需补案例",
                },
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "生动解释修订稿",
                    "risks": [],
                },
            ],
            "judge": [
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
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.tool_call_agents.append(agent)
        return LLMResponseWithTools(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"{agent}-call",
                    name="rag_retrieve",
                    arguments={"query": "专利法 新颖性", "top_k": 1},
                )
            ] if agent == "expert_a" else [],
        )


def test_real_workflow_runs_full_agent_chain_with_fake_llm(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm_client = QueueLLMClient()

    state = run_workflow(
        session_id="demo-session",
        user_input="我想学习专利新颖性和创造性的区别",
        llm_client=llm_client,
        max_debate_rounds=1,
    )

    completed = completed_teach_state(state)
    assert len(llm_client.calls) == 11
    assert completed["session_id"] == "demo-session"
    assert completed["learner_profile"]["knowledge_level"] == "beginner"
    assert completed["learning_path"]
    assert completed["expert_a_draft"]["style"] == "conservative_precise"
    assert completed["expert_a_draft"]["draft_stage"] == "integration"
    assert completed["expert_a_draft"]["teaching_content"] == "整合专家A和专家B后的教学内容"
    assert completed["expert_b_draft"]["style"] == "vivid_teaching"
    assert completed["judge_report"]["decision"] == "accept"
    assert completed["workflow_status"] == "completed"
    assert "整合专家A和专家B后的教学内容" in completed["final_learning_markdown"]

    completed_events = [event for event in state["events"] if event["status"] == "completed"]
    event_names = [event["node"] for event in completed_events]
    assert event_names == [
        "route",
        "learner_state",
        "planner",
        "expert_a",
        "expert_b",
        "expert_a",
        "expert_b",
        "expert_a",
        "expert_b",
        "expert_a",
        "judge",
        "publish_final_learning",
    ]
    assert all(event["round"] == 1 for event in completed_events)
    assert all(isinstance(event["timestamp"], str) and event["timestamp"] for event in completed_events)
    assert all(isinstance(event["duration_ms"], int) for event in completed_events)
    assert llm_client.tool_call_agents.count("expert_a") == 2
    assert llm_client.tool_call_agents.count("expert_b") == 1
    assert len(completed["retrieval_context"]) >= 1
    # Verify agent call order
    assert llm_client.agents[:3] == ["route", "learner_state", "planner"]
    assert "tool_agent" not in llm_client.agents
    assert "expert_a" in llm_client.agents
    assert "expert_b" in llm_client.agents
    assert llm_client.agents.count("judge") == 1
    assert llm_client.agents.count("learner_state") == 1
    assert llm_client.agents[-1] == "judge"
    forbidden_agents = {
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
        "tool_agent",
    }
    assert forbidden_agents.isdisjoint(set(llm_client.agents))
    assert llm_client.agents[-2:] == ["expert_a", "judge"]
    assert "工作流完成" in capsys.readouterr().err


def test_teach_workflow_persists_learner_memory_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm_client = QueueLLMClient()
    store = InMemoryStore()

    run_workflow(
        session_id="memory-once-session",
        user_input="我想学习专利新颖性和创造性的区别",
        llm_client=llm_client,
        max_debate_rounds=1,
        learner_id="learner-unit",
        checkpointer=InMemorySaver(),
        store=store,
    )

    profiles = store.search(learner_namespace("learner-unit", "profile"), limit=5)
    histories = store.search(learner_namespace("learner-unit", "history"), limit=5)
    assert len(profiles) == 1
    assert len(histories) == 1


def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow(llm_client=QueueLLMClient())
    mermaid = export_workflow_mermaid(workflow)

    assert "learner_state" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "publish_final_learning" in mermaid
    assert "retrieve_context" in mermaid
    assert "planner -.-> expert_a" in mermaid or "planner --> expert_a" in mermaid
    assert "tool_agent" not in mermaid
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
