from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import run_workflow

pytestmark = pytest.mark.unit


class DebateQueueLLMClient:
    """Per-agent response queues so parallel expert calls don't swap responses."""

    def __init__(self) -> None:
        self.agents: list[str | None] = []
        self.messages_by_agent: dict[str, list[str]] = {}
        self._queues: dict[str, list[object]] = {
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
            "expert_a": [
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "第一轮 A：严谨但缺少案例。",
                    "risks": [],
                },
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性", "现有技术"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "第二轮 A：按裁判意见补充了现有技术判断。",
                    "risks": [],
                },
            ],
            "expert_b": [
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "第一轮 B：生动但法条回扣不足。",
                    "risks": ["法条回扣不足"],
                },
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性", "案例判断"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "第二轮 B：按裁判意见补充了法条回扣。",
                    "risks": [],
                },
            ],
            "judge": [
                {
                    "decision": "revise",
                    "accuracy_score": 4,
                    "adaptation_score": 3,
                    "disputes": ["专家 B 的案例解释缺少法条回扣"],
                    "rationale": "需要按裁判意见修订后再合并。",
                    "revision_requests": [
                        {
                            "target": "both",
                            "issue": "法条回扣和案例适配不足",
                            "required_change": "补充《专利法》第二十二条，并用案例说明新颖性判断。",
                            "basis": "retrieval_context:patent-law-article-22",
                        },
                    ],
                    "debate": {"round": 1},
                },
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "disputes": [],
                    "rationale": "修订后可以合并输出。",
                    "debate": {"round": 2},
                },
            ],
            "feedback": [
                {
                    "questionnaire": ["你能否说明什么是现有技术？"],
                    "next_action": "完成一个新颖性判断案例题",
                    "profile_update_hint": "继续观察案例判断能力",
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

    # diagnosis and planner are sequential; expert_a/expert_b run in parallel
    # so within each round their order is non-deterministic.
    agents = llm_client.agents
    assert agents[0] == "diagnosis"
    assert agents[1] == "planner"
    # Round-1 experts + judge
    assert set(agents[2:5]) == {"expert_a", "expert_b", "judge"}
    assert agents[4] == "judge"  # judge always last in its round
    # Round-2 experts + judge
    assert set(agents[5:8]) == {"expert_a", "expert_b", "judge"}
    assert agents[7] == "judge"
    assert agents[8] == "feedback"
    assert state["debate_round"] == 2
    assert state["judge_report"]["decision"] == "accept"
    assert state["expert_a_draft"]["teaching_content"].startswith("第二轮 A")
    assert state["expert_b_draft"]["teaching_content"].startswith("第二轮 B")
    assert "revision_requests" in llm_client.messages_by_agent["expert_a"][1]
    assert "revision_requests" in llm_client.messages_by_agent["expert_b"][1]

    debate_events = [event for event in state["events"] if event["status"] == "debate_round"]
    assert len(debate_events) == 1
    debate_event = debate_events[0]
    assert debate_event["node"] == "judge"
    assert debate_event["message"] == "judge requested expert revision round 2"
    assert debate_event["round"] == 2
    assert isinstance(debate_event["timestamp"], str) and debate_event["timestamp"]
    assert isinstance(debate_event["duration_ms"], int)
    assert debate_event["error_code"] is None

    artifact_paths = [Path(artifact["path"]) for artifact in state["artifacts"]]
    assert Path("artifacts/sessions/demo-session/round-01/expert_a_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/expert_a_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/feedback_report.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/final_answer.md") in artifact_paths

    manifest_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["session_id"] == "demo-session"
    assert manifest["status"] == "completed"
    assert len(manifest["artifacts"]) == len(state["artifacts"])

    final_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "final_answer.md"
    assert final_path.read_text(encoding="utf-8").startswith("# 个性化知识产权学习建议")
