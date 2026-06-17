from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import run_workflow
from backend.tests.helpers import completed_state

pytestmark = pytest.mark.unit


class DebateQueueLLMClient:
    """Per-agent response queues for the 5-stage expert collaboration workflow."""

    def __init__(self) -> None:
        self.agents: list[str | None] = []
        self.messages_by_agent: dict[str, list[str]] = {}
        self._queues: dict[str, list[object]] = {
            "route": [
                {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            ],
            "diagnosis": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_based",
                    "weak_points": ["新颖性判断步骤不清"],
                    "learning_goal": "学习专利新颖性",
                },
            ],
            "planner": [
                [
                    {
                        "node_id": "novelty-basics",
                        "node_name": "新颖性基础",
                        "duration_min": 20,
                        "strategy": "先看法条，再做案例",
                        "prerequisites": [],
                    },
                ],
            ],
            # Stage 1: Independent generation (single response each)
            "expert_a": [
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "严谨但缺少案例。",
                    "risks": [],
                },
            ],
            "expert_b": [
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "生动但法条回扣不足。",
                    "risks": ["法条回扣不足"],
                },
            ],
            # Stage 2: Cross-review (single response each)
            "cross_review_a": [
                {
                    "reviewer": "expert_a",
                    "target": "expert_b",
                    "review_opinions": [
                        {"category": "🔴", "location": "核心", "target_wrote": "...",
                         "problem": "法条回扣不足", "suggestion": "补充法条依据",
                         "basis": "专利法第22条"},
                    ],
                    "positive_confirmation": "B的引用验证通过",
                    "overall_assessment": "需补充法条依据",
                },
            ],
            "cross_review_b": [
                {
                    "reviewer": "expert_b",
                    "target": "expert_a",
                    "review_opinions": [
                        {"category": "🟡", "location": "概念解释", "target_wrote": "...",
                         "problem": "缺少案例", "suggestion": "增加实务案例",
                         "basis": None},
                    ],
                    "positive_confirmation": "A的法条引用准确",
                    "overall_assessment": "法律准确但缺少可代入场景",
                },
            ],
            # Stage 3: Revision (single response each)
            "expert_a_revise": [
                {
                    "agent": "expert_a",
                    "revisions": [
                        {"review_id": 1, "review_category": "🟡",
                         "review_summary": "缺少案例", "response": "已补充案例",
                         "status": "accepted"},
                    ],
                    "unresolved_disputes": [],
                    "modified_paragraphs": ["核心理解"],
                    "modification_tags": ["[经B审查修正]"],
                },
            ],
            "expert_b_revise": [
                {
                    "agent": "expert_b",
                    "revisions": [
                        {"review_id": 1, "review_category": "🔴",
                         "review_summary": "法条回扣不足", "response": "已补充法条依据",
                         "status": "accepted"},
                    ],
                    "unresolved_disputes": [],
                    "modified_paragraphs": ["核心概念"],
                    "modification_tags": ["[经A审查修正]"],
                },
            ],
            # Stage 4: Joint synthesis (2 responses: first pass + lightweight revision)
            "joint_synthesis": [
                {
                    "title": "新颖性判断标准（初版）",
                    "sections": [
                        {"heading": "法条依据", "content": "专利法第22条...", "source": "A", "note": None},
                        {"heading": "通俗解释", "content": "新颖性是指...", "source": "B", "note": None},
                    ],
                },
                {
                    "title": "新颖性判断标准（修订版）",
                    "sections": [
                        {"heading": "法条依据", "content": "专利法第22条...（修订）", "source": "A", "note": None},
                        {"heading": "通俗解释", "content": "新颖性是指...（修订）", "source": "B", "note": None},
                    ],
                },
            ],
            # Stage 5: Judge (2 responses: revise first, then accept)
            "judge": [
                {
                    "decision": "revise",
                    "accuracy_score": 3,
                    "adaptation_score": 3,
                    "completeness_score": 3,
                    "disputes": ["法条回扣和案例适配不足"],
                    "rationale": "需要按裁判意见修订后再合并。",
                    "revision_requests": [
                        {
                            "target": "both",
                            "issue": "法条回扣和案例适配不足",
                            "required_change": "补充《专利法》第二十二条，并用案例说明新颖性判断。",
                            "basis": "retrieval_context:patent-law-article-22",
                        },
                    ],
                },
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "修订后可以输出。",
                },
            ],
            # Lightweight review (1 response, when judge says revise)
            "lightweight_review": [
                {
                    "reviewed_changes": [
                        {"change_location": "法条依据", "change_description": "补充了法条",
                         "related_judge_request": "补充法条依据", "verdict": "acceptable",
                         "reason": "修改到位"},
                    ],
                    "verdict": "acceptable",
                    "unresolved": [],
                },
            ],
            "feedback": [
                {
                    "questionnaire": ["你能否说明什么是现有技术？"],
                    "next_action": "完成一个新颖性判断案例题",
                    "profile_update_hint": "继续观察案例判断能力",
                },
            ],
            "finalize": [
                {
                    "title": "专利新颖性学习建议",
                    "content": "整合后的教学内容",
                    "sources": ["第二十二条"],
                },
            ],
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.agents.append(agent)
        if agent:
            self.messages_by_agent.setdefault(agent, []).append(
                "\n".join(message.content for message in messages)
            )
            queue = self._queues.get(agent)
            if queue:
                return queue.pop(0)
        raise RuntimeError(f"No queued response for agent={agent}")

    def generate_with_tools(self, messages, tools, temperature, agent=None):
        from backend.app.core.llm import LLMResponseWithTools
        self.agents.append(agent)
        return LLMResponseWithTools(content="RAG context provided.", tool_calls=[])


def test_workflow_revises_experts_until_judge_accepts_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    llm_client = DebateQueueLLMClient()

    state = run_workflow(
        session_id="demo-session",
        user_input="我想学习专利新颖性",
        llm_client=llm_client,
        artifact_root=tmp_path / "artifacts",
        max_debate_rounds=2,
    )
    completed = completed_state(state)

    agents = llm_client.agents
    # P0.1: 5-stage workflow with lightweight review loop
    assert "route" in agents
    assert "diagnosis" in agents
    assert "planner" in agents
    assert "tool_agent" in agents
    # Stage 1: Generate (single call each)
    assert agents.count("expert_a") == 1
    assert agents.count("expert_b") == 1
    # Stage 2: Cross-review (single call each)
    assert "cross_review_a" in agents
    assert "cross_review_b" in agents
    # Stage 3: Revise (single call each)
    assert "expert_a_revise" in agents
    assert "expert_b_revise" in agents
    # Stage 4: Joint synthesis (2 calls: first + lightweight revision)
    assert agents.count("joint_synthesis") == 2
    # Stage 5: Judge + lightweight review loop
    assert agents.count("judge") == 2  # revise, then accept
    assert "lightweight_review" in agents
    assert agents[-1] == "finalize"
    assert completed["debate_round"] == 2
    assert completed["judge_report"]["decision"] == "accept"
    # New state fields populated
    assert completed["cross_review_a"]["reviewer"] == "expert_a"
    assert completed["revision_record_a"]["agent"] == "expert_a"
    assert completed["joint_synthesis_output"]["title"] == "新颖性判断标准（修订版）"

    # Debate events from revise_experts node
    debate_events = [event for event in state["events"] if event["status"] == "debate_round"]
    assert len(debate_events) == 1
    debate_event = debate_events[0]
    assert debate_event["node"] == "judge"
    assert debate_event["round"] == 2
    assert isinstance(debate_event["timestamp"], str) and debate_event["timestamp"]
    assert isinstance(debate_event["duration_ms"], int)
    assert debate_event["error_code"] is None

    artifact_paths = [Path(artifact["path"]) for artifact in completed["artifacts"]]
    assert Path("artifacts/sessions/demo-session/round-01/expert_a_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-01/cross_review_a.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-01/joint_synthesis.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-01/lightweight_review.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/joint_synthesis.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/final_answer.md") in artifact_paths

    manifest_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["session_id"] == "demo-session"
    assert manifest["status"] == "completed"

    final_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "final_answer.md"
    assert final_path.read_text(encoding="utf-8").startswith("# 个性化知识产权学习建议")
