from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend.app.core.agent_runtime_config import (
    clear_agent_runtime_config_cache,
    load_agent_runtime_config,
)
from backend.app.core.llm import AgentLLMRouter

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_config_cache() -> Iterator[None]:
    clear_agent_runtime_config_cache()
    yield
    clear_agent_runtime_config_cache()


def test_yaml_config_controls_router_provider_and_model(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: qwen\n"
        "providers:\n"
        "  qwen:\n"
        "    base_url: https://gw.example/v1\n"
        "  glm:\n"
        "    base_url: https://gw.example/v1\n"
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
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DIAGNOSIS_FEEDBACK_PROVIDER", "")
    monkeypatch.setenv("EXPERT_B_PROVIDER", "")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("diagnosis_feedback") == "qwen"
    assert router.model_for("diagnosis_feedback") == "qwen-plus"
    assert router.provider_for("expert_b") == "glm"
    assert router.model_for("expert_b") == "glm-5.1-air"
    assert "planner" not in router.agent_providers


@pytest.mark.parametrize(
    "temperature_field",
    ["temperature", "tool_temperature", "integration_temperature"],
)
def test_yaml_config_keeps_temperature_for_gpt56_provider(
    tmp_path, monkeypatch: pytest.MonkeyPatch, temperature_field: str
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: luna\n"
        "providers:\n"
        "  luna:\n"
        "    base_url: https://gw.example/v1\n"
        "agents:\n"
        "  expert_a:\n"
        f"    {temperature_field}: 0.2\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))

    settings = load_agent_runtime_config().agents["expert_a"]

    assert getattr(settings, temperature_field) == 0.2


def test_yaml_config_keeps_temperature_for_gpt56_model_override(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: gpt\n"
        "providers:\n"
        "  gpt:\n"
        "    model_name: gpt-5.6-sol\n"
        "agents:\n"
        "  route:\n"
        "    temperature: 0.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))

    config = load_agent_runtime_config()

    assert config.providers["gpt"].model_name == "gpt-5.6-sol"
    assert config.agents["route"].temperature == 0.0


def test_yaml_config_allows_non_model_parameters_for_gpt56_provider(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "providers:\n"
        "  luna:\n"
        "    base_url: https://gw.example/v1\n"
        "agents:\n"
        "  expert_b:\n"
        "    provider: luna\n"
        "    top_k: 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))

    settings = load_agent_runtime_config().agents["expert_b"]

    assert settings.provider == "luna"
    assert settings.top_k == 7


def test_provider_environment_override_takes_precedence_over_yaml(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "llm:\n"
        "  default_provider: gpt\n"
        "providers:\n"
        "  gpt:\n"
        "    base_url: https://gw.example/v1\n"
        "  qwen:\n"
        "    base_url: https://gw.example/v1\n"
        "agents:\n"
        "  expert_a:\n"
        "    provider: gpt\n"
        "    model_name: gpt-5.5\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("EXPERT_A_PROVIDER", "qwen")

    router = AgentLLMRouter.from_env()

    assert router.default_provider == "qwen"
    assert router.provider_for("expert_a") == "qwen"
    assert router.model_for("expert_a") is None
