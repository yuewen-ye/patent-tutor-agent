from pathlib import Path


AGENT_MODULES = ["diagnosis", "planner", "expert_a", "expert_b", "judge", "feedback"]


def test_each_agent_has_its_own_node_module() -> None:
    agents_dir = Path("backend/app/agents")

    assert not (agents_dir / "real_nodes.py").exists()
    for module in AGENT_MODULES:
        assert (agents_dir / module / "node.py").exists(), module


def test_workflow_uses_agents_package_assembly() -> None:
    source = Path("backend/app/graph/workflow.py").read_text(encoding="utf-8")

    assert "backend.app.agents.real_nodes" not in source
    assert "from backend.app.agents import" in source
