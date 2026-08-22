from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.learner_memory.memory import FileLearnerMemoryStore
from backend.app.services.session_service import SessionService
from backend.main import create_app

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.responses: list[object] = [
            {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["新颖性判断步骤"],
                "learning_goal": "学习专利新颖性",
            },
            {
                "nodes": [
                    {
                        "node_id": "novelty-basic",
                        "node_name": "新颖性基础",
                        "duration_min": 20,
                        "strategy": "先学概念+法条拆解",
                        "prerequisites": [],
                        "difficulty_cap": "L2",
                    }
                ],
                "question_scope": {
                    "backward_review": [
                        {"node_id": "novelty-basic", "difficulty": "L2", "goal": "验证巩固"}
                    ],
                    "forward_probe": [
                        {"node_id": "inventiveness", "difficulty": "L1", "goal": "探测下一节点"}
                    ],
                    "weakness_probe": [
                        {"node_id": "doctrine-of-equivalents", "difficulty": "L3", "goal": "薄弱点挑战"}
                    ],
                },
                "iteration_directive": {
                    "type": "降维",
                    "trigger": "当前节点 L1 答对率 < 60%",
                    "action": "降低抽象度",
                },
            },
            {
                "expert": "expert_a",
                "style": "conservative",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "严谨解释新颖性。",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "accessible",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "用案例解释新颖性。",
                "risks": [],
            },
            {
                "reviewer": "expert_a",
                "target": "expert_b",
                "review_opinions": [{
                    "category": "🟡", "location": "正文", "target_wrote": "案例",
                    "problem": "法条回扣不足", "suggestion": "补充法条",
                }],
                "overall_assessment": "需要补充法条。",
            },
            {
                "reviewer": "expert_b",
                "target": "expert_a",
                "review_opinions": [{
                    "category": "🌉", "location": "正文", "target_wrote": "定义",
                    "problem": "案例不足", "suggestion": "增加案例",
                }],
                "overall_assessment": "需要增加案例。",
            },
            {
                "expert": "expert_a",
                "style": "conservative",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家A修订内容。",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "accessible",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家B修订内容。",
                "risks": [],
            },
            {
                "expert": "expert_a",
                "style": "conservative",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家A整合两位专家观点后的最终教学内容。",
                "risks": [],
            },
            {
                "decision": "accept",
                "accuracy_score": 5,
                "adaptation_score": 5,
                "completeness_score": 5,
                "disputes": [],
                "rationale": "整合稿可以作为最终教学内容。",
            },
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
            {
                "questionnaire": ["本节最容易混淆什么？"],
                "next_action": "完成练习后复盘",
                "profile_update_hint": "继续观察新颖性判断步骤",
                "five_dimensions": {"knowledge": {"novelty": {"pl": 0.3, "ci_low": 0.15, "ci_high": 0.5, "observations": 3, "low_confidence": False}}, "cognition": {"remember": 0.8, "understand": 0.6, "apply": 0.4, "analyze": 0.3, "evaluate": 0.2, "create": 0.1}, "style": {"perception": {"chosen": "sensing", "strength": 0.7}, "input": {"chosen": "visual", "strength": 0.6}, "processing": {"chosen": "active", "strength": 0.55}, "understanding": {"chosen": "sequential", "strength": 0.65}}, "progress": {"completed_nodes": ["patent-law-basic"], "current_node": "novelty-basic", "pending_nodes": ["inventiveness"], "avg_time_per_node_min": 22, "overall_completion_ratio": 0.3}, "affect": {"primary_state": "interested", "confidence": 0.6, "signals": ["主动提问"]}},
            },
        ]

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return self.responses.pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


def _make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SessionService]:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
    )
    app = create_app(session_service=service)
    return TestClient(app), service


def _make_memory_client(tmp_path: Path) -> tuple[TestClient, SessionService]:
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
        store=FileLearnerMemoryStore(tmp_path / "learner-memory.json"),
    )
    return TestClient(create_app(session_service=service)), service














@pytest.mark.parametrize(
    "path",
    [
        "/learners/learner-api",
        "/learners/learner-api/profiles",
        "/learners/learner-api/history",
        "/learners/learner-api/sessions",
    ],
)
def test_learner_api_returns_controlled_error_for_corrupt_memory_store(
    path: str,
    tmp_path: Path,
) -> None:
    # Given: a learner memory store file containing invalid JSON.
    memory_path = tmp_path / "learner-memory.json"
    memory_path.write_text("{not valid json", encoding="utf-8")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
        store=FileLearnerMemoryStore(memory_path),
    )
    client = TestClient(create_app(session_service=service), raise_server_exceptions=False)

    # When: the learner memory API reads the corrupt store.
    learner = client.get(path)
    sessions = client.get("/sessions")

    # Then: the learner API returns a controlled JSON error without breaking sessions.
    assert learner.status_code == 500
    detail = learner.json()["detail"]
    assert detail["error"] == "memory_store_corrupt"
    assert detail["store"] == "learner-memory.json"
    assert sessions.status_code == 200
