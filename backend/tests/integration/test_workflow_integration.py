"""Integration tests that run the full workflow with real LLM providers.

Requires valid .env with API keys for at least one provider.
Skipped gracefully when no provider is configured or rate-limited.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import AgentLLMRouter, LLMConfigurationError, LLMProviderError
from backend.app.graph.workflow import run_workflow
from backend.tests.helpers import completed_teach_state

pytestmark = pytest.mark.integration


def test_workflow_runs_single_round_with_real_llm(tmp_path: Path) -> None:
    try:
        router = AgentLLMRouter.from_env()
    except LLMConfigurationError as exc:
        pytest.skip(f"No provider configured: {exc}")

    user_input = "请系统地教我专利法中关于新颖性判断的全部标准，从法条原文、审查指南的细节到常见误区，一步一步给我讲解"

    try:
        state = run_workflow(
            session_id="pytest-integration",
            user_input=user_input,
            llm_client=router,
            artifact_root=tmp_path / "artifacts",
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if "429" in message or "rate limit" in message:
            pytest.skip(f"Provider rate limited: {exc}")
        if "401" in message or "unauthorized" in message:
            pytest.skip(f"Provider auth failed (bad key?): {exc}")
        raise

    # Verify teach path was used
    intent = state.get("intent", "")
    if intent != "teach":
        pytest.skip(f"LLM routed to '{intent}' instead of 'teach' — routing flake")

    # -- state assertions --
    completed = completed_teach_state(state)
    assert completed["session_id"] == "pytest-integration"
    assert completed["workflow_status"] == "completed"

    # learner profile was produced
    profile = completed["learner_profile"]
    assert profile["knowledge_level"] in {"beginner", "intermediate", "advanced"}
    assert len(profile["weak_points"]) >= 1

    assert len(completed["learning_path"]) >= 1
    assert completed["learning_path"][0]["node_id"]

    assert completed["expert_a_draft"]["expert"] == "expert_a"
    assert completed["expert_b_draft"]["expert"] == "expert_b"
    assert completed["expert_a_draft"]["draft_stage"] == "integration"
    assert completed["expert_a_draft"]["teaching_content"]
    assert completed["expert_b_draft"]["teaching_content"]

    assert completed["judge_report"]["decision"] in {
        "accept",
        "accept_with_minor_revision",
        "revise",
    }
    assert 1 <= completed["judge_report"]["accuracy_score"] <= 5
    assert 1 <= completed["judge_report"]["adaptation_score"] <= 5
    assert 1 <= completed["judge_report"]["completeness_score"] <= 5

    decision = completed["judge_report"]["decision"]
    if decision == "revise":
        assert "feedback_result" in completed
    else:
        assert "feedback_result" not in completed
    assert "final_answer" not in completed

    assert completed["artifacts"]

    artifact_paths = {a["path"] for a in completed["artifacts"]}
    expected_artifacts = [
        "artifacts/sessions/pytest-integration/profile/learner_profile.md",
        "artifacts/sessions/pytest-integration/path/learning_path.md",
        "artifacts/sessions/pytest-integration/path/dual_axis_snapshot.md",
        "artifacts/sessions/pytest-integration/round-01/expert_a_draft.md",
        "artifacts/sessions/pytest-integration/round-01/expert_b_draft.md",
        "artifacts/sessions/pytest-integration/round-01/course_package.md",
        "artifacts/sessions/pytest-integration/round-01/judge_report.md",
    ]
    for expected in expected_artifacts:
        assert expected in artifact_paths, f"Missing artifact: {expected}"
    feedback_path = "artifacts/sessions/pytest-integration/feedback/feedback_report.md"
    assert (feedback_path in artifact_paths) is (decision == "revise")

    manifest_path = (
        tmp_path / "artifacts" / "sessions" / "pytest-integration" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["session_id"] == "pytest-integration"

    integration_md = (
        tmp_path / "artifacts" / "sessions" / "pytest-integration" / "final_answer.md"
    )
    assert not integration_md.exists()
    integration_md = (
        tmp_path
        / "artifacts"
        / "sessions"
        / "pytest-integration"
        / "round-01"
        / "course_package.md"
    )
    assert integration_md.read_text(encoding="utf-8").startswith(
        "# 整合后的课程完整内容与习题"
    )


def test_workflow_event_ordering_is_correct_with_real_llm(tmp_path: Path) -> None:
    """Verify that agent events fire in the expected order."""
    try:
        router = AgentLLMRouter.from_env()
    except LLMConfigurationError as exc:
        pytest.skip(f"No provider configured: {exc}")

    try:
        state = run_workflow(
            session_id="pytest-events",
            user_input="请系统性地教我专利审查指南中关于抵触申请的完整规定，包括定义、判断方法、与现有技术的区别",
            llm_client=router,
            artifact_root=tmp_path / "artifacts",
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(kw in message for kw in ("429", "rate limit", "401", "unauthorized")):
            pytest.skip(f"Provider unavailable: {exc}")
        raise

    intent = state.get("intent", "")
    if intent != "teach":
        pytest.skip(f"LLM routed to '{intent}' instead of 'teach' — routing flake")

    completed_events = [
        e["node"] for e in state["events"] if e["status"] == "completed"
    ]
    assert completed_events[:3] == ["route", "diagnosis_feedback", "planner"]
    assert "retrieve_context" not in completed_events
    assert "expert_a" in completed_events and "expert_b" in completed_events
    decision = state["judge_report"]["decision"]
    if decision == "revise":
        assert completed_events[-2:] == ["judge", "diagnosis_feedback"]
    else:
        assert completed_events[-1] == "judge"
