from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
AGENT_MODULES = ["diagnosis", "planner", "expert_a", "expert_b", "judge"]


def test_each_agent_has_its_own_node_module() -> None:
    agents_dir = ROOT / "backend/app/agents"

    assert not (agents_dir / "real_nodes.py").exists()
    for module in AGENT_MODULES:
        assert (agents_dir / module / "node.py").exists(), module
    assert (agents_dir / "diagnosis" / "feedback_phase.md").exists()
    assert not (agents_dir / "feedback").exists()


def test_workflow_uses_agents_package_assembly() -> None:
    source = (ROOT / "backend/app/graph/workflow.py").read_text(encoding="utf-8")

    assert "backend.app.agents.real_nodes" not in source
    assert "from backend.app.agents import" in source
