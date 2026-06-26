from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import run_workflow
from backend.tests.helpers import completed_teach_state

pytestmark = pytest.mark.unit


class DebateQueueLLMClient:
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
            "expert_a": [
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "严谨但缺少案例。",
                    "risks": [],
                },
                {
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性", "现有技术"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "已按 judge 意见补充法条和案例。",
                    "risks": [],
                },
                {
                    "title": "专利新颖性学习建议",
                    "content": "专家A最终审核后的教学内容",
                    "sources": ["第二十二条"],
                    "judge_summary": "修订后可以输出",
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
                {
                    "expert": "expert_b",
                    "style": "vivid_teaching",
                    "knowledge_points": ["新颖性", "案例判断"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "已按 judge 意见补充案例解释。",
                    "risks": [],
                },
            ],
            "judge": [
                {
                    "decision": "revise",
                    "accuracy_score": 3,
                    "adaptation_score": 3,
                    "completeness_score": 3,
                    "disputes": ["法条回扣和案例适配不足"],
                    "rationale": "需要按裁判意见修订后再审。",
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
    completed = completed_teach_state(state)

    agents = llm_client.agents
    assert agents.count("expert_a") == 3
    assert agents.count("expert_b") == 2
    assert agents.count("judge") == 2
    assert agents[-1] == "expert_a"
    assert {
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
    }.isdisjoint(set(agents))
    assert completed["debate_round"] == 2
    assert completed["judge_report"]["decision"] == "accept"
    assert completed["final_answer"]["content"] == "专家A最终审核后的教学内容"

    debate_events = [event for event in state["events"] if event["status"] == "debate_round"]
    assert len(debate_events) == 1
    debate_event = debate_events[0]
    assert debate_event["node"] == "revise_experts"
    assert debate_event["round"] == 2
    assert isinstance(debate_event["timestamp"], str) and debate_event["timestamp"]
    assert isinstance(debate_event["duration_ms"], int)
    assert debate_event["error_code"] is None

    artifact_paths = [Path(artifact["path"]) for artifact in completed["artifacts"]]
    assert Path("artifacts/sessions/demo-session/round-01/expert_a_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-01/expert_b_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/expert_a_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/expert_b_draft.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/final_answer.md") in artifact_paths

    manifest_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["session_id"] == "demo-session"
    assert manifest["status"] == "completed"

    final_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "final_answer.md"
    assert final_path.read_text(encoding="utf-8").startswith("# 个性化知识产权学习建议")


def test_workflow_reruns_only_targeted_expert_when_judge_targets_expert_a(
    tmp_path: Path,
) -> None:
    llm_client = DebateQueueLLMClient()
    first_judge = llm_client._queues["judge"][0]
    assert isinstance(first_judge, dict)
    first_judge["revision_requests"] = [
        {
            "target": "expert_a",
            "issue": "A 的法条骨架仍不完整",
            "required_change": "只要求专家 A 补充法条判断步骤。",
            "basis": "judge",
        }
    ]
    llm_client._queues["expert_b"] = llm_client._queues["expert_b"][:1]

    state = run_workflow(
        session_id="target-a-session",
        user_input="我想学习专利新颖性",
        llm_client=llm_client,
        artifact_root=tmp_path / "artifacts",
        max_debate_rounds=2,
    )

    completed = completed_teach_state(state)
    agents = llm_client.agents
    assert agents.count("expert_a") == 3
    assert agents.count("expert_b") == 1
    assert completed["debate_round"] == 2
    assert completed["judge_report"]["decision"] == "accept"
