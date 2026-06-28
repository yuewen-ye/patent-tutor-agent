from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEFAULT_AGENT_CONFIG_PATH: Final = Path("config/agents.yaml")
AGENT_CONFIG_PATH_ENV: Final = "AGENT_CONFIG_PATH"


class AgentRuntimeConfigError(RuntimeError):
    pass


class LLMRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    default_provider: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    retry_times: int | None = Field(default=None, ge=1)


class ProviderRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str | None = None
    base_url: str | None = None


class AgentRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = None
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    tool_temperature: float | None = Field(default=None, ge=0, le=2)
    integration_temperature: float | None = Field(default=None, ge=0, le=2)
    top_k: int | None = Field(default=None, ge=1, le=10)


class AgentRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    providers: dict[str, ProviderRuntimeConfig] = Field(default_factory=dict)
    agents: dict[str, AgentRuntimeSettings] = Field(default_factory=dict)


def clear_agent_runtime_config_cache() -> None:
    load_agent_runtime_config.cache_clear()


@lru_cache(maxsize=1)
def load_agent_runtime_config() -> AgentRuntimeConfig:
    load_dotenv(encoding="utf-8")
    raw_path = os.getenv(AGENT_CONFIG_PATH_ENV, str(DEFAULT_AGENT_CONFIG_PATH))
    path = Path(raw_path)
    if not path.exists():
        return AgentRuntimeConfig()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AgentRuntimeConfigError(f"Invalid YAML in {path}") from exc
    if loaded is None:
        return AgentRuntimeConfig()
    try:
        return AgentRuntimeConfig.model_validate(loaded)
    except ValidationError as exc:
        raise AgentRuntimeConfigError(f"Invalid agent runtime config in {path}: {exc}") from exc


def llm_runtime_config() -> LLMRuntimeConfig:
    return load_agent_runtime_config().llm


def provider_runtime_config(provider: str) -> ProviderRuntimeConfig:
    return load_agent_runtime_config().providers.get(provider, ProviderRuntimeConfig())


def agent_runtime_settings(agent: str) -> AgentRuntimeSettings:
    return load_agent_runtime_config().agents.get(agent, AgentRuntimeSettings())


def agent_temperature(agent: str, default: float, field: str = "temperature") -> float:
    settings = agent_runtime_settings(agent)
    match field:
        case "temperature":
            configured = settings.temperature
        case "tool_temperature":
            configured = settings.tool_temperature
        case "integration_temperature":
            configured = settings.integration_temperature
        case unsupported:
            raise AgentRuntimeConfigError(f"Unsupported temperature field: {unsupported}")
    return configured if configured is not None else default


def agent_top_k(agent: str, default: int) -> int:
    configured = agent_runtime_settings(agent).top_k
    return configured if configured is not None else default
