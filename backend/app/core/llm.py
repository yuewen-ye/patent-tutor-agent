"""LLM client abstractions and DeepSeek OpenAI-compatible chat client."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol, Self

import httpx
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


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
    """Normalize proxy URLs that httpx rejects but local tooling often exports."""
    for key in keys:
        value = os.environ.get(key)
        if value and value.startswith("socks://"):
            os.environ[key] = "socks5://" + value.removeprefix("socks://")


class DeepSeekChatClient:
    """Small DeepSeek client using the OpenAI-compatible chat completions API."""

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
        timeout_seconds: float = 30.0,
        retry_times: int = 3,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or ""
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retry_times = retry_times
        self._http_client = http_client

    @classmethod
    def from_env(cls, http_client: httpx.Client | None = None) -> Self:
        load_dotenv()
        normalize_socks_proxy_env()
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
            base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            retry_times=int(os.getenv("LLM_RETRY_TIMES", "3")),
            http_client=http_client,
        )

    def generate_json(self, messages: list[LLMMessage], temperature: float) -> object:
        if not self.api_key:
            raise LLMConfigurationError("DEEPSEEK_API_KEY is required for DeepSeek calls.")
        return self._generate_json_with_retry(messages=messages, temperature=temperature)

    def _generate_json_with_retry(self, messages: list[LLMMessage], temperature: float) -> object:
        retrying = retry(
            stop=stop_after_attempt(self.retry_times),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            reraise=True,
        )(self._post_chat_completion)
        return retrying(messages, temperature)

    def _post_chat_completion(self, messages: list[LLMMessage], temperature: float) -> object:
        client = self._http_client or httpx.Client(timeout=self.timeout_seconds)
        close_client = self._http_client is None
        try:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [message.__dict__ for message in messages],
                    "temperature": temperature,
                    "stream": False,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not content:
                raise LLMProviderError("DeepSeek returned empty content.")
            return json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMProviderError("DeepSeek returned an invalid JSON chat response.") from exc
        finally:
            if close_client:
                client.close()
