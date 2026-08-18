"""Unified OpenAI-compatible LLM calls with model-aware request parameters."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, Self, cast
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.app.core.agent_runtime_config import (
    agent_runtime_settings,
    llm_runtime_config,
    provider_runtime_config,
)
from backend.app.core.model_capabilities import model_supports_request_parameter

# 准确映射：provider 名 = 真实厂商/模型，不再用壳名套壳复用。
# qwen / glm / gpt / luna / grok 经 Krill 单端点 + 单 key（nb_ 开头，
# 5 个 *_API_KEY 已统一为该值）；yangmao 为原 DeepSeek Flash 通道（保留）。
LLMProvider = Literal["qwen", "glm", "gpt", "luna", "grok", "yangmao", "mistral", "minimax", "deepseek"]
LLMRole = Literal["system", "user", "assistant", "tool"]
AgentName = Literal[
    "diagnosis_feedback",
    "expert_a",
    "expert_b",
    "judge",
    "route",
    "chat_answer",
    "planner",
    "slide_deck",
]

DEFAULT_PROVIDER: LLMProvider = "deepseek"
# 节点 → 真实模型：
#   qwen    → qwen3.7-plus    (route / chat_answer / diagnosis，通用；Krill)
#   glm     → GLM-5.2         (可用，默认未分配给节点；Krill)
#   gpt     → gpt-5.5         (planner / judge；Krill)
#   luna    → gpt-5.6-luna    (expert_b 强推理；Krill)
#   grok    → grok-4.5        (expert_a 内容生成；Krill)
#   yangmao → yangmao-main    (DeepSeek Flash，原独立通道，默认未分配给节点)
DEFAULT_CONFIG: dict[LLMProvider, dict[str, str]] = {
    "qwen": {
        "api_key_env": "QWEN_API_KEY",
        "model_env": "QWEN_MODEL",
        "base_url_env": "QWEN_BASE_URL",
        "model": "Qwen3.7-Plus",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "glm": {
        "api_key_env": "GLM_API_KEY",
        "model_env": "GLM_MODEL",
        "base_url_env": "GLM_BASE_URL",
        "model": "GLM-5.2",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "gpt": {
        "api_key_env": "GPT_API_KEY",
        "model_env": "GPT_MODEL",
        "base_url_env": "GPT_BASE_URL",
        "model": "gpt-4o",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "luna": {
        "api_key_env": "LUNA_API_KEY",
        "model_env": "LUNA_MODEL",
        "base_url_env": "LUNA_BASE_URL",
        "model": "gpt-5.6-luna",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "grok": {
        "api_key_env": "GROK_API_KEY",
        "model_env": "GROK_MODEL",
        "base_url_env": "GROK_BASE_URL",
        "model": "grok-4.3",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "yangmao": {
        "api_key_env": "YANGMAO_API_KEY",
        "model_env": "YANGMAO_MODEL",
        "base_url_env": "YANGMAO_BASE_URL",
        "model": "yangmao-main",
        "base_url": "https://ai.gz404.com:54002/v1",
    },
    "mistral": {
        "api_key_env": "MISTRAL_API_KEY",
        "model_env": "MISTRAL_MODEL",
        "base_url_env": "MISTRAL_BASE_URL",
        "model": "mistral-small-2503",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "minimax": {
        "api_key_env": "MINIMAX_API_KEY",
        "model_env": "MINIMAX_MODEL",
        "base_url_env": "MINIMAX_BASE_URL",
        "model": "MiniMax-M2.5",
        "base_url": "https://endpoint.greatrouter.com",
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model": "DeepSeek-V4-Flash",
        "base_url": "https://endpoint.greatrouter.com",
    },
}
AGENT_PROVIDER_ENV: dict[AgentName, str] = {
    "diagnosis_feedback": "DIAGNOSIS_FEEDBACK_PROVIDER",
    "expert_a": "EXPERT_A_PROVIDER",
    "expert_b": "EXPERT_B_PROVIDER",
    "judge": "JUDGE_PROVIDER",
    "route": "ROUTE_PROVIDER",
    "chat_answer": "CHAT_ANSWER_PROVIDER",
    "planner": "PLANNER_PROVIDER",
    "slide_deck": "SLIDE_DECK_PROVIDER",
}

# ── Per-provider 并发信号量 ──────────────────────────────────────────────
# 限制同一 provider 同时“在飞”的 HTTP 请求数，避免并发节点（如 expert_a /
# expert_b 同时打同一个 Krill key）被上游服务端排队/限流而长时间挂起
# → ReadTimeout。默认 2；若仍偶发超时可设为 1（彻底串行化该 provider）。
_PROVIDER_SEMAPHORES: dict[str, threading.Semaphore] = {}
_PROVIDER_SEMAPHORES_LOCK = threading.Lock()


# -- Strict JSON Schema capability cache --
# Records which providers rejected strict JSON Schema (400/404/415/422).
# Subsequent calls skip strict mode to avoid wasting API calls.
_strict_schema_rejected: dict[str, bool] = {}
_strict_schema_lock = threading.Lock()


def _mark_strict_schema_rejected(provider: str) -> None:
    with _strict_schema_lock:
        _strict_schema_rejected[provider] = True


def provider_supports_strict_schema(provider: str) -> bool:
    """Check if a provider is known to support strict JSON Schema output."""
    # 1. Check static config from yaml
    config = provider_runtime_config(provider)
    if config.supports_strict_schema is not None:
        return config.supports_strict_schema
    # 2. Check dynamic cache (learned from previous 400 responses)
    with _strict_schema_lock:
        if _strict_schema_rejected.get(provider):
            return False
    # 3. Unknown - assume yes, will learn from first attempt
    return True


def _provider_semaphore(provider: str) -> threading.Semaphore:
    with _PROVIDER_SEMAPHORES_LOCK:
        sem = _PROVIDER_SEMAPHORES.get(provider)
        if sem is None:
            limit = int(os.getenv("LLM_MAX_CONCURRENCY", "2"))
            sem = threading.Semaphore(max(1, limit))
            _PROVIDER_SEMAPHORES[provider] = sem
        return sem


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
        ...

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        """Generate a response with tool-calling capability. Does NOT use json_mode."""
        ...


class StructuredOutputLLMClient(Protocol):
    """Optional capability for providers that support strict JSON Schema output."""

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: AgentName | None = None,
    ) -> object:
        """Generate and parse a response constrained by a JSON Schema."""
        ...


class LLMConfigurationError(RuntimeError):
    """Raised when model provider configuration is incomplete."""


class LLMProviderError(RuntimeError):
    """Raised when the model provider returns an invalid or failed response."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        provider: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider
        self.retryable = retryable


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


_LLM_LOG_LOCK = threading.Lock()
_llm_log_ctx = threading.local()


def set_llm_log_context(
    *, session_id: str | None = None, log_root: Path | None = None
) -> None:
    _llm_log_ctx.session_id = session_id
    if log_root is not None and session_id:
        from backend.app.runtime_outputs.artifacts import sanitize_session_id

        _llm_log_ctx.log_path = (
            log_root / "sessions" / sanitize_session_id(session_id) / "llm_calls.log.jsonl"
        )
    else:
        _llm_log_ctx.log_path = None


def _log_llm_call(**kwargs: object) -> None:
    log_path = getattr(_llm_log_ctx, "log_path", None)
    if log_path is None:
        return
    record: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": getattr(_llm_log_ctx, "session_id", ""),
        "type": "llm_call",
    }
    record.update(kwargs)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str, separators=(",", ":")) + chr(10)
    with _LLM_LOG_LOCK, log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _llm_payload_log_enabled() -> bool:
    return os.getenv("LLM_LOG_PAYLOAD", "true").strip().lower() not in {"0", "false", "no", "off"}


def _log_llm_payload(call_id: str, direction: str, **kwargs: object) -> None:
    """Write a full request/response record paired by ``call_id``.

    Enabled by default; set ``LLM_LOG_PAYLOAD=false`` to disable. Records land in
    ``llm_payloads.log.jsonl`` next to ``llm_calls.log.jsonl``. Request records
    carry the exact JSON ``body`` sent to the provider (messages, response_format
    schema, tools); response records carry the raw provider payload or the full
    error body. ``Authorization`` headers are never logged.
    """
    if not _llm_payload_log_enabled():
        return
    log_path = getattr(_llm_log_ctx, "log_path", None)
    if log_path is None:
        return
    payload_path = log_path.with_name("llm_payloads.log.jsonl")
    record: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "session_id": getattr(_llm_log_ctx, "session_id", ""),
        "type": "llm_payload",
        "call_id": call_id,
        "direction": direction,
    }
    record.update(kwargs)
    line = json.dumps(record, ensure_ascii=False, default=str, separators=(",", ":")) + chr(10)
    with _LLM_LOG_LOCK, payload_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _validate_provider(value: str, source: str) -> LLMProvider:
    provider = value.lower()
    if provider not in DEFAULT_CONFIG:
        raise LLMConfigurationError(f"Unsupported {source}: {value}")
    return cast(LLMProvider, provider)


def load_provider_config(provider: LLMProvider, model_name: str | None = None) -> LLMProviderConfig:
    load_dotenv(encoding="utf-8")
    normalize_socks_proxy_env()
    defaults = DEFAULT_CONFIG[provider]
    provider_config = provider_runtime_config(provider)
    llm_config = llm_runtime_config()
    api_key = os.getenv(defaults["api_key_env"], "")
    if not api_key:
        raise LLMConfigurationError(f"{defaults['api_key_env']} is required for {provider} calls.")
    configured_model = (
        model_name
        or provider_config.model_name
        or os.getenv(defaults["model_env"])
        or defaults["model"]
    )
    configured_base_url = (
        provider_config.base_url or os.getenv(defaults["base_url_env"]) or defaults["base_url"]
    )
    return LLMProviderConfig(
        provider=provider,
        api_key=api_key,
        model=configured_model,
        base_url=configured_base_url.rstrip("/"),
        # env 显式覆盖优先于 yaml/config，再回退默认值
        # （修复原 `or` 短路：yaml 配了值后 .env 的 LLM_TIMEOUT_SECONDS / LLM_RETRY_TIMES 永远失效）
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS") or llm_config.timeout_seconds or 30),
        retry_times=int(os.getenv("LLM_RETRY_TIMES") or llm_config.retry_times or 3),
    )


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, LLMProviderError):
        return exc.status_code in {429, 500, 502, 503, 504} or exc.retryable
    return False


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1 token ≈ 3 chars for mixed CJK/English text."""
    return max(1, len(text) // 3)


_MAX_INPUT_TOKENS = 24000


def _truncate_messages_for_token_limit(
    messages: list[LLMMessage],
    max_tokens: int = _MAX_INPUT_TOKENS,
) -> list[LLMMessage]:
    """Truncate message contents to fit within the model's input token limit.

    Strategy: keep system message intact, proportionally truncate user/assistant
    messages from the end (least important context first). If still too large,
    truncate from the beginning of the conversation history.
    """
    total_tokens = sum(_estimate_tokens(m.content) for m in messages)
    if total_tokens <= max_tokens:
        return messages

    system_msgs = [m for m in messages if m.role == "system"]
    non_system_msgs = [m for m in messages if m.role != "system"]

    system_tokens = sum(_estimate_tokens(m.content) for m in system_msgs)
    remaining_budget = max_tokens - system_tokens - 2000  # leave 2k buffer

    if remaining_budget <= 0:
        return messages

    non_system_total = sum(_estimate_tokens(m.content) for m in non_system_msgs)
    if non_system_total <= remaining_budget:
        return messages

    ratio = remaining_budget / non_system_total
    truncated: list[LLMMessage] = []
    for m in non_system_msgs:
        original_len = len(m.content)
        target_len = int(original_len * ratio * 0.95)
        if target_len < 100:
            target_len = min(100, original_len)
        if target_len < original_len:
            content = m.content[:target_len] + "\n...[truncated]"
        else:
            content = m.content
        truncated.append(LLMMessage(role=m.role, content=content))

    return system_msgs + truncated


def _build_chat_body(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    temperature: float,
    json_mode: bool,
    stream: bool,
    *,
    schema_name: str | None = None,
    json_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "model": config.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": stream,
    }
    if model_supports_request_parameter(
        provider=config.provider,
        model_name=config.model,
        parameter="temperature",
    ):
        body["temperature"] = temperature
    if json_schema is not None:
        if not schema_name:
            raise ValueError("schema_name is required when json_schema is provided")
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }
    elif json_mode:
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
        "stream": stream,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ],
    }
    if model_supports_request_parameter(
        provider=config.provider,
        model_name=config.model,
        parameter="temperature",
    ):
        body["temperature"] = temperature
    return body


def _post_chat_completion(
    config: LLMProviderConfig,
    messages: list[LLMMessage],
    temperature: float,
    json_mode: bool,
    http_client: httpx.Client | None,
    schema_name: str | None = None,
    json_schema: dict[str, object] | None = None,
) -> str:
    client = http_client or httpx.Client(timeout=config.timeout_seconds)
    close_client = http_client is None

    truncated_messages = _truncate_messages_for_token_limit(messages)

    body = _build_chat_body(
        config=config,
        messages=truncated_messages,
        temperature=temperature,
        json_mode=json_mode,
        stream=False,
        schema_name=schema_name,
        json_schema=json_schema,
    )

    _call_start = time.monotonic()
    call_id = uuid4().hex
    _log_llm_call(
        provider=config.provider,
        model=config.model,
        json_mode=json_mode,
        has_schema=json_schema is not None,
        schema_name=schema_name,
        message_count=len(truncated_messages),
        estimated_input_tokens=sum(_estimate_tokens(m.content) for m in truncated_messages),
        status="attempting",
    )
    _log_llm_payload(
        call_id,
        "request",
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        body=body,
    )

    try:
        with _provider_semaphore(config.provider):
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
            _log_llm_call(
                provider=config.provider,
                model=config.model,
                json_mode=json_mode,
                status="error",
                error_type="HTTPStatusError",
                error_message=f"{response.status_code} {response.text[:300]}",
                status_code=response.status_code,
                retryable=response.status_code in {429, 500, 502, 503, 504},
                duration_ms=round((time.monotonic() - _call_start) * 1000),
            )
            _log_llm_payload(
                call_id,
                "response",
                status="error",
                status_code=response.status_code,
                error_body=response.text,
            )
            raise LLMProviderError(
                f"{config.provider} API request failed: {response.status_code} {response.text}",
                status_code=response.status_code,
                provider=config.provider,
            ) from exc
        payload = response.json()
        choice = payload["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")
        finish_reason = choice.get("finish_reason", "unknown")
        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                content = reasoning
            else:
                _log_llm_call(
                    provider=config.provider,
                    model=config.model,
                    json_mode=json_mode,
                    status="error",
                    error_type="LLMProviderError",
                    error_message=f"empty content (finish_reason={finish_reason})",
                    retryable=True,
                    duration_ms=round((time.monotonic() - _call_start) * 1000),
                )
                raise LLMProviderError(
                    f"{config.provider} returned empty content (finish_reason={finish_reason}).",
                    provider=config.provider,
                    retryable=True,
                )
        _log_llm_call(
            provider=config.provider,
            model=config.model,
            json_mode=json_mode,
            status="success",
            finish_reason=finish_reason,
            content_length=len(content),
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(call_id, "response", status="success", payload=payload)
        return content
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        _log_llm_call(
            provider=config.provider,
            model=config.model,
            json_mode=json_mode,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc)[:300],
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            body_preview=response.text[:300],
            retryable=True,
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(
            call_id,
            "response",
            status="error",
            status_code=response.status_code,
            error_body=response.text,
        )
        raise LLMProviderError(
            f"{config.provider} returned an invalid chat response "
            f"(status={response.status_code}, body_preview={response.text[:120]!r}).",
            response.status_code,
            provider=config.provider,
            retryable=True,
        ) from exc
    except httpx.TransportError as exc:
        _log_llm_call(
            provider=config.provider,
            model=config.model,
            json_mode=json_mode,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc)[:300],
            retryable=True,
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(
            call_id,
            "response",
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise LLMProviderError(
            f"{config.provider} transport error: {exc}",
            provider=config.provider,
            retryable=True,
        ) from exc
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
    model_name: str | None = None,
    schema_name: str | None = None,
    json_schema: dict[str, object] | None = None,
) -> str:
    config = load_provider_config(provider, model_name=model_name)
    retrying = retry(
        stop=stop_after_attempt(config.retry_times),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )(_post_chat_completion)
    return retrying(
        config,
        messages,
        temperature,
        json_mode,
        http_client,
        schema_name,
        json_schema,
    )


def _salvage_first_json_value(text: str) -> tuple[bool, object]:
    """Tolerant parse: decode the first complete JSON value and drop trailing junk.

    Compatible endpoints occasionally emit a duplicated payload (``{...}{...}``)
    or trailing prose even in JSON mode. Only reached after ``json.loads`` has
    failed, so any trailing content here is genuinely unusable. Returns
    ``(True, value)`` when a complete leading value decodes, ``(False, None)``
    otherwise (caller keeps the normal parse_error path).
    """
    try:
        value, _end = json.JSONDecoder().raw_decode(text.lstrip())
    except json.JSONDecodeError:
        return False, None
    return True, value


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    if not text.startswith("{") and not text.startswith("["):
        start = text.find("{")
        if start == -1:
            start = text.find("[")
        end = text.rfind("}")
        if end == -1:
            end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
    return text


def call_llm_json(
    *,
    provider: LLMProvider = DEFAULT_PROVIDER,
    messages: list[LLMMessage],
    temperature: float = 0.5,
    http_client: httpx.Client | None = None,
    model_name: str | None = None,
    schema_name: str | None = None,
    json_schema: dict[str, object] | None = None,
) -> object:
    # Drop json_schema if provider is known to not support strict schema
    if json_schema is not None and not provider_supports_strict_schema(provider):
        json_schema = None
        schema_name = None
    try:
        content = call_llm(
            provider=provider,
            messages=messages,
            temperature=temperature,
            json_mode=True,
            http_client=http_client,
            model_name=model_name,
            schema_name=schema_name,
            json_schema=json_schema,
        )
    except LLMProviderError as exc:
        if exc.status_code in {401, 403}:
            raise
        _log_llm_call(
            provider=provider,
            status="fallback",
            from_json_mode=True,
            to_json_mode=False,
            reason=str(exc)[:300],
        )
        content = call_llm(
            provider=provider,
            messages=messages,
            temperature=temperature,
            json_mode=False,
            http_client=http_client,
            model_name=model_name,
            schema_name=None,
            json_schema=None,
        )
    cleaned = _strip_json_fence(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        salvaged, value = _salvage_first_json_value(cleaned)
        if salvaged:
            _log_llm_call(
                provider=provider,
                status="parse_salvaged",
                content_preview=content[:300],
                error_message=str(exc)[:300],
            )
            return value
        _log_llm_call(
            provider=provider,
            status="parse_error",
            content_preview=content[:300],
            error_message=str(exc)[:300],
        )
        raise LLMProviderError(
            f"{provider} returned non-JSON content: {content[:500]}",
            provider=provider,
            retryable=True,
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
        config=config,
        messages=messages,
        tools=tools,
        temperature=temperature,
        stream=False,
    )

    _call_start = time.monotonic()
    call_id = uuid4().hex
    _log_llm_call(
        provider=config.provider,
        model=config.model,
        json_mode=False,
        has_schema=False,
        message_count=len(messages),
        estimated_input_tokens=sum(_estimate_tokens(m.content) for m in messages),
        status="attempting",
        tool_call=True,
    )
    _log_llm_payload(
        call_id,
        "request",
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        tool_call=True,
        body=body,
    )

    try:
        with _provider_semaphore(config.provider):
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
            _log_llm_call(
                provider=config.provider,
                model=config.model,
                status="error",
                error_type="HTTPStatusError",
                error_message=f"{response.status_code} {response.text[:300]}",
                status_code=response.status_code,
                retryable=response.status_code in {429, 500, 502, 503, 504},
                tool_call=True,
                duration_ms=round((time.monotonic() - _call_start) * 1000),
            )
            _log_llm_payload(
                call_id,
                "response",
                status="error",
                status_code=response.status_code,
                tool_call=True,
                error_body=response.text,
            )
            raise LLMProviderError(
                f"{config.provider} tools API request failed: {response.status_code} {response.text}",
                status_code=response.status_code,
                provider=config.provider,
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

        _log_llm_call(
            provider=config.provider,
            model=config.model,
            status="success",
            finish_reason=choice.get("finish_reason", "unknown"),
            tool_call_count=len(tool_calls),
            content_length=len(content) if isinstance(content, str) else 0,
            tool_call=True,
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(call_id, "response", status="success", tool_call=True, payload=payload)
        return LLMResponseWithTools(
            content=content if isinstance(content, str) and content.strip() else None,
            tool_calls=tool_calls,
        )
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        _log_llm_call(
            provider=config.provider,
            model=config.model,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc)[:300],
            retryable=True,
            tool_call=True,
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(
            call_id,
            "response",
            status="error",
            status_code=response.status_code,
            tool_call=True,
            error_body=response.text,
        )
        raise LLMProviderError(
                f"{config.provider} returned an invalid tools chat response.",
                provider=config.provider,
                retryable=True,
            ) from exc
    except httpx.TransportError as exc:
        _log_llm_call(
            provider=config.provider,
            model=config.model,
            status="error",
            error_type=type(exc).__name__,
            error_message=str(exc)[:300],
            retryable=True,
            tool_call=True,
            duration_ms=round((time.monotonic() - _call_start) * 1000),
        )
        _log_llm_payload(
            call_id,
            "response",
            status="error",
            error_type=type(exc).__name__,
            tool_call=True,
            error_message=str(exc),
        )
        raise LLMProviderError(
            f"{config.provider} transport error: {exc}",
            provider=config.provider,
            retryable=True,
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
    model_name: str | None = None,
) -> LLMResponseWithTools:
    config = load_provider_config(provider, model_name=model_name)
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
    model_name: str | None

    def __init__(
        self, provider: LLMProvider = DEFAULT_PROVIDER, model_name: str | None = None
    ) -> None:
        self.provider = provider
        self.model_name = model_name

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv(encoding="utf-8")
        llm_config = llm_runtime_config()
        default_provider_name = (
            os.getenv("DEFAULT_LLM_PROVIDER") or llm_config.default_provider or DEFAULT_PROVIDER
        )
        provider = _validate_provider(
            default_provider_name,
            "DEFAULT_LLM_PROVIDER",
        )
        return cls(provider=provider)

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: AgentName | None = None
    ) -> object:
        return call_llm_json(
            provider=self.provider,
            messages=messages,
            temperature=temperature,
            model_name=self.model_name,
        )

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: AgentName | None = None,
    ) -> object:
        return call_llm_json(
            provider=self.provider,
            messages=messages,
            temperature=temperature,
            model_name=self.model_name,
            schema_name=schema_name,
            json_schema=json_schema,
        )

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: AgentName | None = None,
    ) -> LLMResponseWithTools:
        return call_llm_tools(
            provider=self.provider,
            messages=messages,
            tools=tools,
            temperature=temperature,
            model_name=self.model_name,
        )


class AgentLLMRouter:
    """Routes each Agent node to its configured provider, falling back to the default provider."""

    default_provider: LLMProvider
    agent_providers: dict[AgentName, LLMProvider]
    agent_model_names: dict[AgentName, str]

    def __init__(
        self,
        default_provider: LLMProvider = DEFAULT_PROVIDER,
        agent_providers: Mapping[AgentName, LLMProvider] | None = None,
        agent_model_names: Mapping[AgentName, str] | None = None,
    ) -> None:
        self.default_provider = default_provider
        self.agent_providers = dict(agent_providers or {})
        self.agent_model_names = dict(agent_model_names or {})

    @classmethod
    def from_env(cls) -> Self:
        load_dotenv(encoding="utf-8")
        llm_config = llm_runtime_config()
        default_provider_name = (
            os.getenv("DEFAULT_LLM_PROVIDER") or llm_config.default_provider or DEFAULT_PROVIDER
        )
        default_provider = _validate_provider(
            default_provider_name,
            "DEFAULT_LLM_PROVIDER",
        )
        agent_providers: dict[AgentName, LLMProvider] = {}
        agent_model_names: dict[AgentName, str] = {}
        for agent, env_name in AGENT_PROVIDER_ENV.items():
            settings = agent_runtime_settings(agent)
            environment_provider = os.getenv(env_name)
            value = environment_provider or settings.provider
            if value:
                agent_providers[agent] = _validate_provider(value, env_name)
            if settings.model_name and not environment_provider:
                agent_model_names[agent] = settings.model_name
        return cls(
            default_provider=default_provider,
            agent_providers=agent_providers,
            agent_model_names=agent_model_names,
        )

    def provider_for(self, agent: AgentName | None) -> LLMProvider:
        if agent is None:
            return self.default_provider
        return self.agent_providers.get(agent, self.default_provider)

    def model_for(self, agent: AgentName | None) -> str | None:
        if agent is None:
            return None
        return self.agent_model_names.get(agent)

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: AgentName | None = None
    ) -> object:
        return call_llm_json(
            provider=self.provider_for(agent),
            messages=messages,
            temperature=temperature,
            model_name=self.model_for(agent),
        )

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: AgentName | None = None,
    ) -> object:
        return call_llm_json(
            provider=self.provider_for(agent),
            messages=messages,
            temperature=temperature,
            model_name=self.model_for(agent),
            schema_name=schema_name,
            json_schema=json_schema,
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
            model_name=self.model_for(agent),
        )
