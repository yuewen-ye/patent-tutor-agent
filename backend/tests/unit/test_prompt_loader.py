"""Tests for the prompt file loading mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.agents.common import load_prompt

# Every agent node directory that contains a system.md prompt file.
_EXPECTED_PROMPT_DIRS: list[str] = [
    "route",
    "tool_agent",
    "chat_answer",
    "finalize",
    "planner",
    "expert_a",
    "expert_b",
    "judge",
    "cross_review_a",
    "cross_review_b",
    "expert_a_revise",
    "expert_b_revise",
    "joint_synthesis",
    "lightweight_review",
]

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


class TestLoadPrompt:
    """Verify load_prompt() reads files correctly."""

    def test_loads_route_system_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "route" / "node.py")
        content = load_prompt(module_file)
        assert "专利学习助手路由器" in content
        assert "intent" in content

    def test_loads_judge_system_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "judge" / "node.py")
        content = load_prompt(module_file)
        assert "审核裁判" in content
        assert "accuracy_score" in content

    def test_loads_cross_review_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "cross_review_a" / "node.py")
        content = load_prompt(module_file)
        assert "交叉审查模式" in content
        assert "事实追问" in content

    def test_loads_joint_synthesis_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "joint_synthesis" / "node.py")
        content = load_prompt(module_file)
        assert "联合合成器" in content
        assert "合成规则" in content

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="Agent prompt file not found"):
            load_prompt("/nonexistent/path/node.py")

    def test_raises_on_missing_custom_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="missing_file.md"):
            load_prompt(str(_AGENTS_DIR / "route" / "node.py"), "missing_file.md")
