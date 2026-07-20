from __future__ import annotations

from collections.abc import Iterator

import pytest

import backend.app.agents.rag_tools as rag_tools
from backend.app.core.agent_runtime_config import clear_agent_runtime_config_cache
from backend.app.agents.expert_b.node import build_expert_b_node
from backend.app.agents.planner.node import build_planner_node
from backend.app.core.llm import (
    AgentLLMRouter,
    LLMMessage,
    LLMResponseWithTools,
    ToolCall,
    ToolDefinition,
)
from backend.app.schemas.state import RetrievalChunk

pytestmark = pytest.mark.unit


class PlannerTemperatureLLMClient:
    def __init__(self) -> None:
        self.temperatures: list[float] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.temperatures.append(temperature)
        return [
            {
                "node_id": "novelty",
                "node_name": "新颖性",
                "duration_min": 20,
                "strategy": "先看法条",
                "prerequisites": [],
            }
        ]

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


class ExpertToolTopKLLMClient:
    def __init__(self) -> None:
        self.tool_temperatures: list[float] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return {
            "expert": "expert_b",
            "style": "accessible",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "结合检索结果解释新颖性。",
            "risks": [],
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.tool_temperatures.append(temperature)
        return LLMResponseWithTools(
            content=None,
            tool_calls=[
                ToolCall(id="call-1", name="rag_retrieve", arguments={"query": "专利法 新颖性"})
            ],
        )


@pytest.fixture(autouse=True)
def clear_config_cache() -> Iterator[None]:
    clear_agent_runtime_config_cache()
    yield
    clear_agent_runtime_config_cache()


def test_planner_calls_llm_with_configured_temperature() -> None:
    client = PlannerTemperatureLLMClient()

    build_planner_node(client)(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
        }
    )

    assert client.temperatures == [0.3]


def test_yaml_config_controls_expert_tool_temperature_and_default_top_k(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "agents:\n  expert_b:\n    tool_temperature: 0.19\n    top_k: 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))

    def fake_retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
        assert query == "专利法 新颖性"
        assert top_k == 7
        return [
            RetrievalChunk(
                chunk_id="patent-law-22",
                source="patent_law",
                citation="专利法第二十二条",
                text="新颖性，是指该发明或者实用新型不属于现有技术。",
                score=0.9,
            )
        ]

    monkeypatch.setattr(rag_tools, "retrieve_context", fake_retrieve_context)
    client = ExpertToolTopKLLMClient()

    result = build_expert_b_node(client)(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
        }
    )

    assert client.tool_temperatures == [0.19]
    assert result["retrieval_context"][0]["citation"] == "专利法第二十二条"


def test_yaml_config_controls_router_provider_and_model(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: deepseek\n"
        "agents:\n"
        "  diagnosis_feedback:\n"
        "    provider: qwen\n"
        "    model_name: qwen-plus\n"
        "  expert_b:\n"
        "    provider: glm\n"
        "    model_name: glm-5.1-air\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DIAGNOSIS_FEEDBACK_PROVIDER", "")
    monkeypatch.setenv("EXPERT_B_PROVIDER", "")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("diagnosis_feedback") == "qwen"
    assert router.model_for("diagnosis_feedback") == "qwen-plus"
    assert router.provider_for("expert_b") == "glm"
    assert router.model_for("expert_b") == "glm-5.1-air"
    assert "planner" not in router.agent_providers


def test_provider_environment_override_takes_precedence_over_yaml(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: deepseek\n"
        "agents:\n"
        "  expert_a:\n"
        "    provider: deepseek\n"
        "    model_name: deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("EXPERT_A_PROVIDER", "qwen")

    router = AgentLLMRouter.from_env()

    assert router.default_provider == "qwen"
    assert router.provider_for("expert_a") == "qwen"
    assert router.model_for("expert_a") is None
