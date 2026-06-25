"""Tests for the prompt file loading mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.agents.common import load_prompt

# Every agent node that loads a system prompt from a file, with the expected filename.
_EXPECTED_PROMPT_FILES: dict[str, str] = {
    # Pattern B — full system prompt files
    "route": "system.md",
    "tool_agent": "system.md",
    "chat_answer": "system.md",
    "finalize": "system.md",
    # Pattern A — extra text appended after schema_note()
    "planner": "system.md",
    "expert_a": "system.md",
    "expert_b": "system.md",
    "judge": "system.md",
    # P0.1 — custom filenames (not default "system.md")
    "expert_a/cross_review.py": "cross_review_system.md",
    "expert_b/cross_review.py": "cross_review_system.md",
    "expert_a/revise.py": "revise_system.md",
    "expert_b/revise.py": "revise_system.md",
    "joint_synthesis.py": "joint_synthesis_system.md",
    "lightweight_review.py": "lightweight_review_system.md",
}

_AGENTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents"


class TestPromptFiles:
    """Verify that every expected prompt file exists and is non-empty."""

    @pytest.mark.parametrize("module_relpath,filename", list(_EXPECTED_PROMPT_FILES.items()))
    def test_prompt_file_exists(self, module_relpath: str, filename: str) -> None:
        if module_relpath.endswith(".py"):
            parent = str(Path(module_relpath).parent)
            prompt_path = _AGENTS_DIR / parent / filename
        else:
            prompt_path = _AGENTS_DIR / module_relpath / filename
        assert prompt_path.is_file(), f"Missing prompt file: {prompt_path}"

    @pytest.mark.parametrize("module_relpath,filename", list(_EXPECTED_PROMPT_FILES.items()))
    def test_prompt_file_non_empty(self, module_relpath: str, filename: str) -> None:
        if module_relpath.endswith(".py"):
            parent = str(Path(module_relpath).parent)
            prompt_path = _AGENTS_DIR / parent / filename
        else:
            prompt_path = _AGENTS_DIR / module_relpath / filename
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

    def test_loads_custom_filename(self) -> None:
        module_file = str(_AGENTS_DIR / "expert_a" / "cross_review.py")
        content = load_prompt(module_file, "cross_review_system.md")
        assert "交叉审查模式" in content
        assert "事实追问" in content

    def test_loads_flat_file_prompt(self) -> None:
        module_file = str(_AGENTS_DIR / "joint_synthesis.py")
        content = load_prompt(module_file, "joint_synthesis_system.md")
        assert "联合合成器" in content
        assert "合成规则" in content

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="Agent prompt file not found"):
            load_prompt("/nonexistent/path/node.py")

    def test_raises_on_missing_custom_file(self) -> None:
        with pytest.raises(FileNotFoundError, match="missing_file.md"):
            load_prompt(str(_AGENTS_DIR / "route" / "node.py"), "missing_file.md")
