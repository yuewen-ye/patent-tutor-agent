"""Integration tests for three-route workflow with real LLM providers.

Requires valid .env with API keys for at least one provider.
Skipped gracefully when no provider is configured or rate-limited.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core.llm import AgentLLMRouter, LLMConfigurationError, LLMProviderError
from backend.app.graph.workflow import run_workflow

pytestmark = pytest.mark.integration


def _try_router() -> AgentLLMRouter:
    try:
        return AgentLLMRouter.from_env()
    except LLMConfigurationError as exc:
        pytest.skip(f"No provider configured: {exc}")


def _try_run(router: AgentLLMRouter, session_id: str, user_input: str,
             tmp_path: Path, max_debate_rounds: int = 1):
    try:
        return run_workflow(
            session_id=session_id,
            user_input=user_input,
            llm_client=router,
            artifact_root=tmp_path / "artifacts",
            max_debate_rounds=max_debate_rounds,
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(kw in message for kw in ("429", "rate limit", "401", "unauthorized", "402")):
            pytest.skip(f"Provider unavailable: {exc}")
        raise


class TestTeachRoute:
    def test_teach_path_produces_all_artifacts(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-teach", "我想系统学习专利新颖性的判断标准", tmp_path)
        assert state["intent"] == "teach"
        assert "learner_profile" in state
        assert "learning_path" in state
        assert "expert_a_draft" in state
        assert "expert_b_draft" in state
        assert "judge_report" in state
        assert state["judge_report"]["decision"] in {
            "accept", "accept_with_minor_revision", "revise",
        }
        assert "feedback_result" in state
        assert "final_answer" in state
        assert state["final_answer"]["content"]

    def test_teach_event_order(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-teach-events", "我想系统学习如何判断发明专利的创造性", tmp_path)
        completed = [e["node"] for e in state["events"] if e["status"] == "completed"]
        assert "route" == completed[0]
        assert "diagnosis" in completed
        assert "planner" in completed
        assert "tool_agent" in completed
        assert completed[-1] in ("expert_a", "chat_answer")


class TestChatRoute:
    """Quick Q&A path: route→tool_agent→chat_answer→END."""

    def test_chat_path_produces_chat_answer(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-chat", "什么是抵触申请", tmp_path)
        assert state["intent"] == "chat"
        assert "chat_answer" in state
        assert state["chat_answer"]["content"]
        # Chat path should NOT produce experts/judge/feedback
        assert "expert_a_draft" not in state
        assert "judge_report" not in state
        assert "final_answer" not in state

    def test_chat_event_order(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-chat-events", "新颖性和创造性有什么区别", tmp_path)
        completed = [e["node"] for e in state["events"] if e["status"] == "completed"]
        assert completed == ["route", "tool_agent", "chat_answer"]


class TestDiagnoseRoute:
    """Diagnosis-only path: route→diagnosis→END."""

    def test_diagnose_path_produces_profile_only(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-diagnose", "帮我诊断一下我的专利法薄弱点", tmp_path)
        assert state["intent"] == "diagnose"
        assert "learner_profile" in state
        assert state["learner_profile"]["knowledge_level"] in {
            "beginner", "intermediate", "advanced",
        }
        # Diagnose path should NOT produce planner/experts/judge
        assert "learning_path" not in state
        assert "expert_a_draft" not in state
        assert "judge_report" not in state

    def test_diagnose_event_order(self, tmp_path: Path) -> None:
        router = _try_router()
        state = _try_run(router, "integ-diagnose-events", "评估一下我的专利代理考试准备情况", tmp_path)
        completed = [e["node"] for e in state["events"] if e["status"] == "completed"]
        assert completed == ["route", "diagnosis"]
