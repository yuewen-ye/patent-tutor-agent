"""Unified OpenAI-compatible LLM calls for DeepSeek, Qwen, and Kimi."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, Self

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

LLMProvider = Literal["deepseek", "qwen", "kimi"]
LLMRole = Literal["system", "user", "assistant"]

DEFAULT_PROVIDER: LLMProvider = "deepseek"
DEFAULT_CONFIG: dict[LLMProvider, dict[str, str]] = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    },
    "qwen": {
        "api_key_env": "QWEN_API_KEY",
        "model_env": "QWEN_MODEL",
        "base_url_env": "QWEN_BASE_URL",
        "model": "qwen3.7-max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "kimi": {
        "api_key_env": "KIMI_API_KEY",
        "model_env": "KIMI_MODEL",
        "base_url_env": "KIMI_BASE_URL",
        "model": "moonshotai/Kimi-K2.6",
        "base_url": "https://api-inference.modelscope.cn/v1",
    },
}


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: LLMProvider
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float
    retry_times: int


class LLMClient(Protocol):
    def generate_json(self, messages: list[LLMMessage], temperature: float) -> object:
        """Generate and parse a JSON response from a chat model."""


class LLMConfigurationError(RuntimeError):
    """Raised when model provider configuration is incomplete."""


class LLMProviderError(RuntimeError):
    """Raised when the model provider returns an invalid or failed response."""


def normalize_socks_proxy_env(
    keys: Iterable[str] = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ),
) -> None:
    for key in keys:
        value = os.environ.get(key)
        if value and value.startswith("socks://"):
            os.environ[key] = "socks5://" + value.removeprefix("socks://")


def load_provider_config(provider: LLMProvider) -> LLMProviderConfig:
    load_dotenv()
    normalize_socks_proxy_env()
    defaults = DEFAULT_CONFIG[provider]
    api_key = os.getenv(defaults["api_key_env"], "")
    if not api_key:
        raise LLMConfigurationError(f"{defaults['api_key_env']} is required for {provider} calls.")
    return LLMProviderConfig(
        provider=provider,
        api_key=api_key,
        model=os.getenv(defaults["model_env"], defaults["model"]),
        base_url=os.getenv(defaults["base_url_env"], defaults["base_url"]).rstrip("/"),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        retry_times=int(os.getenv("LLM_RETRY_TIMES", "3")),
    )


def _post_chat_completion(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    temperature: float,
    json_mode: bool,
    http_client: httpx.Client | None,
) -> str:
    client = http_client or httpx.Client(timeout=config.timeout_seconds)
    close_client = http_client is None
    body: dict[str, object] = {
        "model": config.model,
        "messages": [message.__dict__ for message in messages],
        "temperature": temperature,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        response = client.post(
            f"{config.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"{config.provider} API request failed: {response.status_code} {response.text}"
            ) from exc
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content:
            raise LLMProviderError(f"{config.provider} returned empty content.")
        return content
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMProviderError(f"{config.provider} returned an invalid chat response.") from exc
    finally:
        if close_client:
            client.close()




def call_llm(
    *,
    provider: LLMProvider = DEFAULT_PROVIDER,
    messages: list[LLMMessage],
    temperature: float = 0.5,
    json_mode: bool = False,
    http_client: httpx.Client | None = None,
) -> str:
    config = load_provider_config(provider)
    retrying = retry(
        stop=stop_after_attempt(config.retry_times),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )(_post_chat_completion)
    return retrying(config, messages, temperature, json_mode, http_client)


def call_llm_json(
    *,
    provider: LLMProvider = DEFAULT_PROVIDER,
    messages: list[LLMMessage],
    temperature: float = 0.5,
    http_client: httpx.Client | None = None,
) -> object:
    content = call_llm(
        provider=provider,
        messages=messages,
        temperature=temperature,
        json_mode=True,
        http_client=http_client,
    )
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(f"{provider} returned non-JSON content in json_mode.") from exc


class DefaultLLMClient:
    """Adapter used by Agent nodes; defaults to DeepSeek unless configured otherwise."""

    def __init__(self, provider: LLMProvider = DEFAULT_PROVIDER) -> None:
        self.provider = provider

    @classmethod
    def from_env(cls) -> Self:
        provider = os.getenv("DEFAULT_LLM_PROVIDER", DEFAULT_PROVIDER).lower()
        if provider not in DEFAULT_CONFIG:
            raise LLMConfigurationError(f"Unsupported DEFAULT_LLM_PROVIDER: {provider}")
        return cls(provider=provider)  # type: ignore[arg-type]

    def generate_json(self, messages: list[LLMMessage], temperature: float) -> object:
        return call_llm_json(provider=self.provider, messages=messages, temperature=temperature)
