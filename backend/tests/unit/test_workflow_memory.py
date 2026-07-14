from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.graph.workflow import run_workflow

pytestmark = pytest.mark.unit


class MemoryQueueLLMClient:
    def __init__(self, learning_goal: str, weak_point: str) -> None:
        self.messages_by_agent: dict[str, list[str]] = {}
        self.tool_call_agents: list[str | None] = []
        self.responses: list[object] = [
            {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": [weak_point],
                "learning_goal": learning_goal,
            },
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
                "teaching_content": "案例解释",
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
                "reviewer": "expert_b",
                "target": "expert_a",
                "review_opinions": [{
                    "category": "🌉", "location": "正文", "target_wrote": "定义",
                    "problem": "案例不足", "suggestion": "补案例",
                }],
                "overall_assessment": "需补案例",
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
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "案例解释修订稿",
                "risks": [],
            },
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "整合专家 A 和专家 B 后的教学内容",
                "risks": [],
            },
            {
                "decision": "accept",
                "accuracy_score": 5,
                "adaptation_score": 5,
                "completeness_score": 5,
                "disputes": [],
                "rationale": "整合稿可以输出",
            },
            {
                "questionnaire": ["本节最容易混淆什么？"],
                "next_action": "完成练习后复盘",
                "profile_update_hint": weak_point,
            },
        ]

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        if agent:
            self.messages_by_agent.setdefault(agent, []).append(
                "\n".join(message.content for message in messages)
            )
        return self.responses.pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.tool_call_agents.append(agent)
        return LLMResponseWithTools(content=None, tool_calls=[])


def test_workflow_uses_checkpointer_and_store_for_learner_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    checkpointer = InMemorySaver()
    store = InMemoryStore()

    first_llm = MemoryQueueLLMClient("学习专利新颖性", "现有技术概念薄弱")
    first_state = run_workflow(
        session_id="memory-session-1",
        user_input="我想学习专利新颖性",
        llm_client=first_llm,
        checkpointer=checkpointer,
        store=store,
        learner_id="learner-alice",
    )

    checkpoint_config: Any = {"configurable": {"thread_id": "memory-session-1"}}
    assert list(checkpointer.list(checkpoint_config))

    profile_items = store.search(("learners", "learner-alice", "profile"), limit=5)
    history_items = store.search(("learners", "learner-alice", "history"), limit=5)
    assert profile_items
    assert history_items == []
    assert profile_items[-1].value["weak_points"] == ["现有技术概念薄弱"]
    assert first_state["workflow_status"] == "completed"

    second_llm = MemoryQueueLLMClient("复习专利新颖性", "案例判断薄弱")
    run_workflow(
        session_id="memory-session-2",
        user_input="我想继续学习专利新颖性",
        llm_client=second_llm,
        checkpointer=checkpointer,
        store=store,
        learner_id="learner-alice",
    )

    diagnosis_prompt = second_llm.messages_by_agent["diagnosis_feedback"][0]
    assert "历史学习者画像" in diagnosis_prompt
    assert "现有技术概念薄弱" in diagnosis_prompt
