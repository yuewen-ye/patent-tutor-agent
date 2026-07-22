import pytest

from backend.app.agents.planner.node import _knowledge_pl_map, build_planner_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


class PlannerLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []
        self.temperatures: list[float] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        self.temperatures.append(temperature)
        return {
            "nodes": [
                {
                    "node_id": "novelty-basic",
                    "node_name": "新颖性基础",
                    "duration_min": 20,
                    "strategy": "先学概念+法条拆解",
                    "prerequisites": [],
                    "difficulty_cap": "L2",
                },
                {
                    "node_id": "novelty-3step",
                    "node_name": "新颖性三步法判断",
                    "duration_min": 30,
                    "strategy": "要件框架+易混淆辨析",
                    "prerequisites": ["novelty-basic"],
                    "difficulty_cap": "L3",
                },
            ],
            "question_scope": {
                "backward_review": [
                    {"node_id": "novelty-basic", "difficulty": "L2", "goal": "验证巩固"}
                ],
                "forward_probe": [
                    {"node_id": "inventiveness", "difficulty": "L1", "goal": "探测下一节点"}
                ],
                "weakness_probe": [
                    {"node_id": "doctrine-of-equivalents", "difficulty": "L3", "goal": "薄弱点挑战"}
                ],
            },
            "iteration_directive": {
                "type": "降维",
                "trigger": "当前节点 L1 答对率 < 60%",
                "action": "降低抽象度",
            },
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


class FailingPlannerLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        raise RuntimeError("LLM unavailable")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


def test_current_mastery_overrides_stale_profile_snapshot() -> None:
    profile = {
        "five_dimensions": {"knowledge": {"novelty": {"pl": 0.2}}},
        "mastery": {"novelty": 0.85, "inventive-step": 0.4},
    }

    mastery = _knowledge_pl_map(profile)

    assert mastery["novelty"]["pl"] == 0.85
    assert mastery["inventive-step"]["pl"] == 0.4


def test_planner_uses_llm_with_prompt() -> None:
    client = PlannerLLMClient()
    node = build_planner_node(client)
    state: StateDict = {
        "session_id": "debug",
        "user_input": "学习新颖性和创造性",
        "events": [],
    }

    result = node(state)

    # planner must now call the LLM (not the deterministic shortcut)
    assert len(client.calls) == 1
    assert client.agents == ["planner"]
    assert "路径规划" in client.calls[0][0].content

    # learning_path built from the LLM nodes, carrying difficulty_cap
    assert result["learning_path"]
    assert result["learning_path"][0]["node_id"] == "novelty-basic"
    assert result["learning_path"][0]["difficulty_cap"] == "L2"
    assert result["path_decision"]["current_node_id"] == "novelty-basic"
    assert result["path_decision"]["algorithm"] == "llm_astar"
    assert result["path_decision"]["question_scope"]["backward_review"]
    assert result["path_decision"]["iteration_directive"]["type"] == "降维"


def test_planner_falls_back_to_deterministic_on_llm_failure() -> None:
    client = FailingPlannerLLMClient()
    node = build_planner_node(client)
    state: StateDict = {
        "session_id": "debug",
        "user_input": "学习新颖性",
        "events": [],
    }

    result = node(state)

    assert result["learning_path"]
    assert result["path_decision"]["algorithm"] == "deterministic_astar"
    # deterministic 兜底同样补全 question_scope 与 difficulty_cap（P1 修复：保证 artifact 始终带资源难度匹配曲线）
    qs = result["path_decision"]["question_scope"]
    assert qs.get("backward_review") or qs.get("forward_probe") or qs.get("weakness_probe")
    assert all(it.get("difficulty_cap") for it in result["learning_path"])
