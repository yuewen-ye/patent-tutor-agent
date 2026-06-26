from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_required_delivery_files_exist() -> None:
    root = Path(__file__).resolve().parents[3]

    assert (root / "README.md").is_file()
    assert (root / "pyproject.toml").is_file()
    assert (root / "uv.lock").is_file()
    assert (root / "backend" / "main.py").is_file()
    assert (root / "docs" / "orchestrator-selection.md").is_file()
    assert (root / "docs" / "agent-interface-spec.md").is_file()


def test_monorepo_workspace_directories_exist() -> None:
    root = Path(__file__).resolve().parents[3]

    for relative_path in [
        "backend/app/api",
        "backend/app/core",
        "backend/app/graph",
        "backend/app/schemas",
        "backend/app/agents/diagnosis",
        "backend/app/agents/planner",
        "backend/app/agents/expert_a",
        "backend/app/agents/expert_b",
        "backend/app/agents/judge",
        "backend/app/rag",
        "backend/tests",
        "frontend",
        "docs",
    ]:
        assert (root / relative_path).is_dir()
