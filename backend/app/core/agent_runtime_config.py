from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    """A user-defined provider channel (OpenAI-compatible endpoint)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    supports_strict_schema: bool | None = None
    models: list[str] | None = None


class AgentRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = None
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    tool_temperature: float | None = Field(default=None, ge=0, le=2)
    integration_temperature: float | None = Field(default=None, ge=0, le=2)
    top_k: int | None = Field(default=None, ge=1, le=10)
    fallback_provider: str | None = None
    fallback_model_name: str | None = None
    fallback_base_url: str | None = None


class AgentRuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    providers: dict[str, ProviderRuntimeConfig] = Field(default_factory=dict)
    agents: dict[str, AgentRuntimeSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_provider_references(self) -> AgentRuntimeConfig:
        available = sorted(self.providers)

        def check_provider(name: str | None, source: str) -> None:
            if name is None:
                return
            if name not in self.providers:
                raise ValueError(
                    f"{source} references undefined provider '{name}'. "
                    f"Available providers: {available or '(none defined)'}"
                )

        def check_model(model: str | None, provider: str | None, source: str) -> None:
            if model is None or provider is None:
                return
            declared = self.providers[provider].models
            if declared is not None and model not in declared:
                raise ValueError(
                    f"{source} references model '{model}' not listed in "
                    f"providers.{provider}.models: {declared}"
                )

        check_provider(self.llm.default_provider, "llm.default_provider")
        for agent, settings in self.agents.items():
            check_provider(settings.provider, f"agents.{agent}.provider")
            check_provider(settings.fallback_provider, f"agents.{agent}.fallback_provider")
            primary = settings.provider or self.llm.default_provider
            check_model(settings.model_name, primary, f"agents.{agent}.model_name")
            fallback = settings.fallback_provider or primary
            check_model(
                settings.fallback_model_name, fallback, f"agents.{agent}.fallback_model_name"
            )
        return self


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


def available_provider_names() -> list[str]:
    return sorted(load_agent_runtime_config().providers)


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
