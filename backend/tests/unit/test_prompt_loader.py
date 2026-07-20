"""Tests for the prompt file loading mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.agents.common import load_prompt

_EXPECTED_PROMPT_DIRS: list[str] = [
    "route",
    "chat_answer",
    "planner",
    "judge",
]
_EXPECTED_PHASE_PROMPTS: dict[str, list[str]] = {
    "diagnosis": ["diagnosis_system.md", "feedback_system.md"],
    "expert_a": ["debate_system.md", "integration_system.md"],
    "expert_b": ["draft_system.md", "cross_review_system.md", "revision_system.md"],
}

_AGENTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents"


class TestPromptFiles:
    """Verify that every expected prompt file exists and is non-empty."""

    @pytest.mark.parametrize("agent_dir", _EXPECTED_PROMPT_DIRS)
    def test_prompt_file_exists(self, agent_dir: str) -> None:
        prompt_path = _AGENTS_DIR / agent_dir / "system.md"
        assert prompt_path.is_file(), f"Missing prompt file: {prompt_path}"

    @pytest.mark.parametrize("agent_dir", _EXPECTED_PROMPT_DIRS)
    def test_prompt_file_non_empty(self, agent_dir: str) -> None:
        prompt_path = _AGENTS_DIR / agent_dir / "system.md"
        content = prompt_path.read_text(encoding="utf-8").strip()
        assert len(content) > 0, f"Empty prompt file: {prompt_path}"

    @pytest.mark.parametrize("agent_dir,phase_files", _EXPECTED_PHASE_PROMPTS.items())
    def test_phase_prompt_files_exist(self, agent_dir: str, phase_files: list[str]) -> None:
        for phase_file in phase_files:
            prompt_path = _AGENTS_DIR / agent_dir / phase_file
            assert prompt_path.is_file(), f"Missing phase prompt file: {prompt_path}"

    @pytest.mark.parametrize("agent_dir,phase_files", _EXPECTED_PHASE_PROMPTS.items())
    def test_phase_prompt_files_non_empty(self, agent_dir: str, phase_files: list[str]) -> None:
        for phase_file in phase_files:
            prompt_path = _AGENTS_DIR / agent_dir / phase_file
            content = prompt_path.read_text(encoding="utf-8").strip()
            assert len(content) > 0, f"Empty phase prompt file: {prompt_path}"

    def test_multi_phase_agents_do_not_use_default_system_prompt(self) -> None:
        for agent_dir in _EXPECTED_PHASE_PROMPTS:
            prompt_path = _AGENTS_DIR / agent_dir / "system.md"
            assert not prompt_path.exists(), f"Multi-phase agent should use phase prompts: {prompt_path}"


class TestLoadPrompt:
    """Verify load_prompt() reads files correctly."""

    def test_loads_route_system_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "route" / "node.py")
        content = load_prompt(module_file)
        assert "专利学习助手路由器" in content
        assert "intent" in content

    def test_loads_diagnosis_phase_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "diagnosis" / "node.py")
        content = load_prompt(module_file, "diagnosis_system.md")
        assert "学习者状态建模器" in content
        assert "只诊断" in content

    def test_loads_expert_a_integration_phase_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "expert_a" / "node.py")
        content = load_prompt(module_file, "integration_system.md")
        assert "当前阶段是 integration" in content
        assert "ExpertDraft" in content

    def test_loads_judge_system_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "judge" / "node.py")
        content = load_prompt(module_file)
        assert "审核裁判" in content
        assert "accuracy_score" in content

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="Agent prompt file not found"):
            load_prompt("/nonexistent/path/node.py")

    def test_raises_on_missing_custom_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="missing_file.md"):
            load_prompt(str(_AGENTS_DIR / "route" / "node.py"), "missing_file.md")
