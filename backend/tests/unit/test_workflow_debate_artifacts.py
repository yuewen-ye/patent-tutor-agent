from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
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
                }
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
                    "expert": "expert_a",
                    "style": "conservative_precise",
                    "knowledge_points": ["新颖性", "现有技术", "案例判断"],
                    "legal_basis": ["《专利法》第二十二条"],
                    "teaching_content": "专家A整合A/B辩论结果后的教学内容",
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
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "整合稿可以作为最终教学内容。",
                },
            ],
            "feedback": [
                {
                    "questionnaire": ["本轮整合稿中哪个判断步骤最容易混淆？"],
                    "next_action": "完成一个新颖性案例判断题。",
                    "profile_update_hint": "继续巩固新颖性判断步骤。",
                },
                {
                    "questionnaire": ["请复述新颖性判断的三步法。"],
                    "next_action": "复盘 A/B 辩论中的案例判断。",
                    "profile_update_hint": "案例判断仍需加强。",
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

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("debate workflow tests must not call tool-capable LLM mode")


def test_workflow_revises_experts_until_judge_accepts_and_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
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
    assert agents.count("judge") == 1
    assert agents.count("diagnosis") == 1
    assert agents.count("feedback") == 1
    assert "tool_agent" not in agents
    assert agents[-1] == "feedback"
    assert {
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
        "tool_agent",
    }.isdisjoint(set(agents))
    assert completed["debate_round"] == 2
    assert completed["judge_report"]["decision"] == "accept"
    assert completed["feedback_result"]["next_action"] == "完成一个新颖性案例判断题。"
    assert completed["expert_a_draft"]["draft_stage"] == "integration"
    assert completed["expert_a_draft"]["teaching_content"] == "专家A整合A/B辩论结果后的教学内容"
    assert "final_answer" not in completed

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
    assert Path("artifacts/sessions/demo-session/round-02/expert_a_draft-02.md") in artifact_paths
    assert Path("artifacts/sessions/demo-session/round-02/feedback_report.md") in artifact_paths
    assert len(artifact_paths) == len(set(artifact_paths))

    manifest_path = tmp_path / "artifacts" / "sessions" / "demo-session" / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["session_id"] == "demo-session"
    assert manifest["status"] == "completed"

    integration_path = (
        tmp_path
        / "artifacts"
        / "sessions"
        / "demo-session"
        / "round-02"
        / "expert_a_draft-02.md"
    )
    assert "专家A整合A/B辩论结果后的教学内容" in integration_path.read_text(encoding="utf-8")


def test_workflow_runs_both_experts_for_each_debate_round_before_integration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm_client = DebateQueueLLMClient()

    state = run_workflow(
        session_id="two-round-session",
        user_input="我想学习专利新颖性",
        llm_client=llm_client,
        artifact_root=tmp_path / "artifacts",
        max_debate_rounds=2,
    )

    completed = completed_teach_state(state)
    agents = llm_client.agents
    assert agents.count("expert_a") == 3
    assert agents.count("expert_b") == 2
    assert agents.count("judge") == 1
    assert agents.count("feedback") == 1
    assert "tool_agent" not in agents
    assert completed["debate_round"] == 2
    assert completed["judge_report"]["decision"] == "accept"
    assert completed["expert_a_draft"]["draft_stage"] == "integration"
