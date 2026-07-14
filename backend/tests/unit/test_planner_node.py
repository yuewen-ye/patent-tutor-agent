import pytest

from backend.app.agents.planner.node import build_planner_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


class PlannerLLMClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[tuple[list[LLMMessage], str | None]] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append((messages, agent))
        return self.response

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("planner node must not call tools")


def test_planner_normalizes_model_generated_node_ids_to_slug() -> None:
    node = build_planner_node(
        PlannerLLMClient(
            [
                {
                    "node_id": "case_intro_novelty_inventiveness",
                    "node_name": "案例导入",
                    "duration_min": 15,
                    "strategy": "先用案例导入",
                    "prerequisites": [],
                }
            ]
        )
    )
    state: StateDict = {
        "session_id": "debug",
        "user_input": "学习新颖性和创造性",
        "events": [],
    }

    result = node(state)

    assert result["path_decision"]["suggested_node_ids"] == [
        "case-intro-novelty-inventiveness"
    ]
    assert result["path_decision"]["algorithm"] == "deterministic_astar"
    assert result["learning_path"]
