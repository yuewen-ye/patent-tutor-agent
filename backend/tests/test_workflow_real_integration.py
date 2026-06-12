from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.core.llm import AgentLLMRouter, LLMProviderError
from backend.app.graph.workflow import run_workflow


def test_configured_real_workflow_runs_and_writes_markdown_artifacts(tmp_path: Path) -> None:
    try:
        state = run_workflow(
            session_id="pytest-real-workflow",
            user_input="我想学习专利新颖性和创造性的区别，请用案例帮助我理解。",
            llm_client=AgentLLMRouter.from_env(),
            artifact_root=tmp_path / "artifacts",
            max_debate_rounds=2,
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if "429" in message or "rate limit" in message:
            pytest.skip(f"provider is currently rate limited: {exc}")
        raise

    assert state["final_answer"]["title"]
    assert state["final_answer"]["content"]
    assert state["judge_report"]["decision"] in {
        "accept",
        "accept_with_minor_revision",
        "revise",
    }
    assert 1 <= state["debate_round"] <= state["max_debate_rounds"]
    assert state["artifacts"]

    artifact_paths = {artifact["path"] for artifact in state["artifacts"]}
    assert "artifacts/sessions/pytest-real-workflow/final_answer.md" in artifact_paths

    manifest_path = tmp_path / "artifacts" / "sessions" / "pytest-real-workflow" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert len(manifest["artifacts"]) == len(state["artifacts"])

    final_answer_path = tmp_path / "artifacts" / "sessions" / "pytest-real-workflow" / "final_answer.md"
    assert final_answer_path.read_text(encoding="utf-8").startswith("# ")
