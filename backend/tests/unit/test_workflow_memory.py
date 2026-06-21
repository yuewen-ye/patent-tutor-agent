from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import run_workflow

pytestmark = pytest.mark.unit


class MemoryQueueLLMClient:
    def __init__(self, learning_goal: str, weak_point: str) -> None:
        self.messages_by_agent: dict[str, list[str]] = {}
        self.responses: list[object] = [
            # route
            {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            # diagnosis
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": [weak_point],
                "learning_goal": learning_goal,
            },
            # planner
            [
                {
                    "node_id": "novelty-basics",
                    "node_name": "新颖性基础",
                    "duration_min": 20,
                    "strategy": "案例优先",
                    "prerequisites": [],
                }
            ],
            # expert_a
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "严谨解释",
                "risks": [],
            },
            # expert_b
            {
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "案例解释",
                "risks": [],
            },
            # cross_review_a
            {
                "reviewer": "expert_a",
                "target": "expert_b",
                "review_opinions": [
                    {"category": "🟢", "location": "核心", "target_wrote": "x",
                     "problem": "遗漏", "suggestion": "补充", "basis": "法22条"}
                ],
                "positive_confirmation": "引用存在",
                "overall_assessment": "基本正确",
            },
            # cross_review_b
            {
                "reviewer": "expert_b",
                "target": "expert_a",
                "review_opinions": [
                    {"category": "🟡", "location": "概念", "target_wrote": "x",
                     "problem": "抽象", "suggestion": "加案例", "basis": None}
                ],
                "positive_confirmation": "准确",
                "overall_assessment": "法律准确",
            },
            # expert_a_revise
            {
                "agent": "expert_a",
                "revisions": [
                    {"review_id": 1, "review_category": "🟡",
                     "review_summary": "抽象", "response": "已改进", "status": "accepted"}
                ],
                "unresolved_disputes": [],
                "modified_paragraphs": ["核心"],
                "modification_tags": ["[经B审查修正]"],
            },
            # expert_b_revise
            {
                "agent": "expert_b",
                "revisions": [
                    {"review_id": 1, "review_category": "🟢",
                     "review_summary": "遗漏", "response": "已补充", "status": "accepted"}
                ],
                "unresolved_disputes": [],
                "modified_paragraphs": ["核心"],
                "modification_tags": ["[经A审查修正]"],
            },
            # joint_synthesis
            {
                "title": "新颖性判断标准",
                "sections": [
                    {"heading": "法条", "content": "...", "source": "A", "note": None},
                    {"heading": "解释", "content": "...", "source": "B", "note": None},
                ],
            },
            # judge
            {
                "decision": "accept",
                "accuracy_score": 5,
                "adaptation_score": 4,
                "completeness_score": 4,
                "disputes": [],
                "rationale": "可以输出",
            },
            # feedback
            {
                "questionnaire": ["你能说出现有技术的含义吗？"],
                "next_action": "继续做案例题",
                "profile_update_hint": "保留薄弱点并继续观察案例判断能力",
            },
            # finalize
            {
                "title": "个性化知识产权学习建议",
                "content": "整合",
                "sources": ["第二十二条"],
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

    def generate_with_tools(self, messages, tools, temperature, agent=None):
        from backend.app.core.llm import LLMResponseWithTools
        return LLMResponseWithTools(content="RAG context provided.", tool_calls=[])


def test_workflow_uses_checkpointer_and_store_for_learner_memory() -> None:
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
    assert history_items
    assert profile_items[-1].value["weak_points"] == ["现有技术概念薄弱"]
    assert history_items[-1].value["session_id"] == first_state["session_id"]
    assert history_items[-1].value["topic"] == "学习专利新颖性"

    second_llm = MemoryQueueLLMClient("复习专利新颖性", "案例判断薄弱")
    run_workflow(
        session_id="memory-session-2",
        user_input="我想继续学习专利新颖性",
        llm_client=second_llm,
        checkpointer=checkpointer,
        store=store,
        learner_id="learner-alice",
    )

    diagnosis_prompt = second_llm.messages_by_agent["diagnosis"][0]
    assert "历史学习者画像" in diagnosis_prompt
    assert "现有技术概念薄弱" in diagnosis_prompt
