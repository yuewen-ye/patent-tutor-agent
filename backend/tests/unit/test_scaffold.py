from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_required_delivery_files_exist() -> None:
    root = Path(__file__).resolve().parents[3]

    assert (root / "README.md").is_file()
    assert (root / "pyproject.toml").is_file()
    assert (root / "uv.lock").is_file()
    assert (root / "backend" / "main.py").is_file()
    assert (root / "docs" / "README.md").is_file()
    assert (root / "docs" / "agent-interface-spec.md").is_file()
    assert (root / "docs" / "workflow-technical-guide.md").is_file()


def test_monorepo_workspace_directories_exist() -> None:
    root = Path(__file__).resolve().parents[3]

    for relative_path in [
        "backend/app/api",
        "backend/app/core",
        "backend/app/curriculum",
        "backend/app/graph",
        "backend/app/learner_memory",
        "backend/app/onboarding",
        "backend/app/retrieval",
        "backend/app/runtime_outputs",
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


def test_backend_app_root_contains_only_application_boundaries() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"

    assert {path.name for path in app_root.glob("*.py")} == {
        "__init__.py",
        "config.py",
        "middleware.py",
    }


def test_curriculum_assets_are_packaged_with_backend_runtime() -> None:
    root = Path(__file__).resolve().parents[3]
    runtime_asset_root = root / "backend" / "app" / "curriculum" / "data"

    assert (runtime_asset_root / "knowledge-dag.json").is_file()
    assert (runtime_asset_root / "confusion-pairs.json").is_file()
