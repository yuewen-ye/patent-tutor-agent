from pathlib import Path


def test_required_delivery_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "README.md").is_file()
    assert (root / "pyproject.toml").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "main.py").is_file()
    assert (root / "docs" / "orchestrator-selection.md").is_file()
    assert (root / "docs" / "agent-interface-spec.md").is_file()


def test_agent_workspace_directories_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    for relative_path in [
        "agents/diagnosis",
        "agents/planner",
        "agents/expert_a",
        "agents/expert_b",
        "agents/judge",
        "agents/feedback",
        "rag",
        "frontend",
        "tests",
        "docs",
    ]:
        assert (root / relative_path).is_dir()

