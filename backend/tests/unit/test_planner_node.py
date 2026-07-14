import pytest

from backend.app.agents.planner.node import build_planner_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


class PlannerLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        raise AssertionError("deterministic planner must not call the LLM")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("planner node must not call tools")


def test_planner_has_one_deterministic_decision_source() -> None:
    node = build_planner_node(PlannerLLMClient())
    state: StateDict = {
        "session_id": "debug",
        "user_input": "学习新颖性和创造性",
        "events": [],
    }

    result = node(state)

    assert "suggested_node_ids" not in result["path_decision"]
    assert result["path_decision"]["algorithm"] == "deterministic_astar"
    assert result["path_decision"]["current_node_id"] == result["learning_path"][0]["node_id"]
    assert result["learning_path"]
