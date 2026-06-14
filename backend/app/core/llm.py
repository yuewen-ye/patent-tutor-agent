"""Unified OpenAI-compatible LLM calls for DeepSeek, Qwen, and GLM."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, Self, cast

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

LLMProvider = Literal["deepseek", "qwen", "glm"]
LLMRole = Literal["system", "user", "assistant", "tool"]
AgentName = Literal[
    "diagnosis", "planner", "expert_a", "expert_b", "judge", "feedback",
    "route", "tool_agent", "chat_answer",
]

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
    "glm": {
        "api_key_env": "GLM_API_KEY",
        "model_env": "GLM_MODEL",
        "base_url_env": "GLM_BASE_URL",
        "model": "glm-5.1",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
}
AGENT_PROVIDER_ENV: dict[AgentName, str] = {
    "diagnosis": "DIAGNOSIS_PROVIDER",
    "planner": "PLANNER_PROVIDER",
    "expert_a": "EXPERT_A_PROVIDER",
    "expert_b": "EXPERT_B_PROVIDER",
    "judge": "JUDGE_PROVIDER",
    "feedback": "FEEDBACK_PROVIDER",
    "route": "ROUTE_PROVIDER",
    "tool_agent": "TOOL_AGENT_PROVIDER",
    "chat_answer": "CHAT_ANSWER_PROVIDER",
}


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, object]] | None = None
    name: str | None = None


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: LLMProvider
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float
    retry_times: int


@dataclass(frozen=True)
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a tool that can be called by the LLM."""

    name: str
    description: str
    parameters: dict[str, object]  # JSON Schema for the tool's parameters


@dataclass(frozen=True)
class LLMResponseWithTools:
    """Response from an LLM call that supports tool calling."""

    content: str | None
    tool_calls: list[ToolCall]


class LLMClient(Protocol):
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: AgentName | None = None
    ) -> object:
        """Generate and parse a JSON response from a chat model."""

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        """Generate a response with tool-calling capability. Does NOT use json_mode."""


class LLMConfigurationError(RuntimeError):
    """Raised when model provider configuration is incomplete."""


class LLMProviderError(RuntimeError):
    """Raised when the model provider returns an invalid or failed response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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


def _validate_provider(value: str, source: str) -> LLMProvider:
    provider = value.lower()
    if provider not in DEFAULT_CONFIG:
        raise LLMConfigurationError(f"Unsupported {source}: {value}")
    return cast(LLMProvider, provider)


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


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, LLMProviderError):
        return exc.status_code in {429, 500, 502, 503, 504}
    return False


def _build_chat_body(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    temperature: float,
    json_mode: bool,
    stream: bool,
) -> dict[str, object]:
    body: dict[str, object] = {
        "model": config.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "stream": stream,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


def _build_chat_body_with_tools(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    tools: list[ToolDefinition],
    temperature: float,
    stream: bool,
) -> dict[str, object]:
    def _serialize_message(m: LLMMessage) -> dict[str, object]:
        d: dict[str, object] = {"role": m.role, "content": m.content}
        if m.tool_call_id is not None:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls is not None:
            d["tool_calls"] = m.tool_calls
        if m.name is not None:
            d["name"] = m.name
        return d

    body: dict[str, object] = {
        "model": config.model,
        "messages": [_serialize_message(m) for m in messages],
        "temperature": temperature,
        "stream": stream,
        "tools": [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in tools
        ],
    }
    return body


def _post_chat_completion(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    temperature: float,
    json_mode: bool,
    http_client: httpx.Client | None,
) -> str:
    client = http_client or httpx.Client(timeout=config.timeout_seconds)
    close_client = http_client is None

    body = _build_chat_body(
        config=config,
        messages=messages,
        temperature=temperature,
        json_mode=json_mode,
        stream=False,
    )

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
                f"{config.provider} API request failed: {response.status_code} {response.text}",
                status_code=response.status_code,
            ) from exc
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
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
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )(_post_chat_completion)
    return retrying(config, messages, temperature, json_mode, http_client)


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text


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
    cleaned = _strip_json_fence(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(
            f"{provider} returned non-JSON content in json_mode: {content[:500]}"
        ) from exc


def _post_chat_completion_with_tools(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    tools: list[ToolDefinition],
    temperature: float,
    http_client: httpx.Client | None,
) -> LLMResponseWithTools:
    client = http_client or httpx.Client(timeout=config.timeout_seconds)
    close_client = http_client is None

    body = _build_chat_body_with_tools(
        config=config, messages=messages, tools=tools,
        temperature=temperature, stream=False,
    )

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
                f"{config.provider} tools API request failed: {response.status_code} {response.text}",
                status_code=response.status_code,
            ) from exc
        payload = response.json()
        choice = payload["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: list[ToolCall] = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=tc.get("id", ""), name=func.get("name", ""), arguments=args)
            )

        return LLMResponseWithTools(
            content=content if isinstance(content, str) and content.strip() else None,
            tool_calls=tool_calls,
        )
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMProviderError(
            f"{config.provider} returned an invalid tools chat response."
        ) from exc
    finally:
        if close_client:
            client.close()


def call_llm_tools(
    *,
    provider: LLMProvider = DEFAULT_PROVIDER,
    messages: list[LLMMessage],
    tools: list[ToolDefinition],
    temperature: float = 0.5,
    http_client: httpx.Client | None = None,
) -> LLMResponseWithTools:
    config = load_provider_config(provider)
    retrying = retry(
        stop=stop_after_attempt(config.retry_times),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )(_post_chat_completion_with_tools)
    return retrying(config, messages, tools, temperature, http_client)


class DefaultLLMClient:
    """Adapter used when all Agent nodes should use one provider."""

    provider: LLMProvider

    def __init__(self, provider: LLMProvider = DEFAULT_PROVIDER) -> None:
        self.provider = provider

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv()
        provider = _validate_provider(
            os.getenv("DEFAULT_LLM_PROVIDER", DEFAULT_PROVIDER), "DEFAULT_LLM_PROVIDER"
        )
        return cls(provider=provider)

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: AgentName | None = None
    ) -> object:
        return call_llm_json(provider=self.provider, messages=messages, temperature=temperature)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        return call_llm_tools(provider=self.provider, messages=messages, tools=tools, temperature=temperature)


class AgentLLMRouter:
    """Routes each Agent node to its configured provider, falling back to the default provider."""

    default_provider: LLMProvider
    agent_providers: dict[AgentName, LLMProvider]

    def __init__(
        self,
        default_provider: LLMProvider = DEFAULT_PROVIDER,
        agent_providers: Mapping[AgentName, LLMProvider] | None = None,
    ) -> None:
        self.default_provider = default_provider
        self.agent_providers = dict(agent_providers or {})

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv()
        default_provider = _validate_provider(
            os.getenv("DEFAULT_LLM_PROVIDER", DEFAULT_PROVIDER), "DEFAULT_LLM_PROVIDER"
        )
        agent_providers: dict[AgentName, LLMProvider] = {}
        for agent, env_name in AGENT_PROVIDER_ENV.items():
            value = os.getenv(env_name)
            if value:
                agent_providers[agent] = _validate_provider(value, env_name)
        return cls(default_provider=default_provider, agent_providers=agent_providers)

    def provider_for(self, agent: AgentName | None) -> LLMProvider:
        if agent is None:
            return self.default_provider
        return self.agent_providers.get(agent, self.default_provider)

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: AgentName | None = None
    ) -> object:
        return call_llm_json(
            provider=self.provider_for(agent),
            messages=messages,
            temperature=temperature,
        )

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        return call_llm_tools(
            provider=self.provider_for(agent),
            messages=messages,
            tools=tools,
            temperature=temperature,
        )
