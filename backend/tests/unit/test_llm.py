import json
import os
from collections.abc import Iterator
from typing import Any, cast

import httpx
import pytest

from backend.app.core.agent_runtime_config import (
    ProviderRuntimeConfig,
    clear_agent_runtime_config_cache,
)
from backend.app.core.llm import (
    AGENT_PROVIDER_ENV,
    AgentLLMRouter,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    call_llm,
    call_llm_json,
    load_provider_config,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_config_cache() -> Iterator[None]:
    clear_agent_runtime_config_cache()
    yield
    clear_agent_runtime_config_cache()


def _json_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_call_llm_posts_to_configured_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.7-max")
    monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response("统一回复")

    result = call_llm(
        provider="qwen",
        messages=[LLMMessage(role="user", content="你好")],
        temperature=0.2,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == "统一回复"
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["authorization"] == "Bearer qwen-key"
    assert captured["body"] == {
        "model": load_provider_config("qwen").model,
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.2,
        "stream": False,
    }


@pytest.mark.parametrize(
    ("provider", "key_name", "model_name", "base_url"),
    [
        ("deepseek", "DEEPSEEK_API_KEY", "deepseek-v4-flash", "https://api.deepseek.com"),
        (
            "qwen",
            "QWEN_API_KEY",
            "qwen3.7-max",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        ("glm", "GLM_API_KEY", "glm-5.1", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ],
)
def test_call_llm_supports_three_configured_providers(
    monkeypatch, provider: LLMProvider, key_name: str, model_name: str, base_url: str
) -> None:
    # This test exercises the legacy environment-variable fallback.  YAML is
    # intentionally higher priority, so isolate the test from the developer's
    # local config/agents.yaml provider settings.
    monkeypatch.setattr(
        "backend.app.core.llm.provider_runtime_config",
        lambda _provider: ProviderRuntimeConfig(),
    )
    monkeypatch.setenv(key_name, "provider-key")
    monkeypatch.setenv(f"{provider.upper()}_MODEL", model_name)
    monkeypatch.setenv(f"{provider.upper()}_BASE_URL", base_url)

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response("ok")

    assert (
        call_llm(
            provider=provider,
            messages=[LLMMessage(role="user", content="ping")],
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        == "ok"
    )
    assert seen["url"] == f"{base_url}/chat/completions"
    assert cast(dict[str, Any], seen["body"])["model"] == load_provider_config(provider).model


def test_call_llm_json_adds_json_mode_and_parses_response(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response('{"answer": "json"}')

    result = call_llm_json(
        provider="deepseek",
        messages=[LLMMessage(role="system", content="只输出 json")],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"answer": "json"}
    assert cast(dict[str, Any], captured["body"])["response_format"] == {"type": "json_object"}


def test_call_llm_uses_explicit_model_name_override(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response("ok")

    result = call_llm(
        provider="qwen",
        messages=[LLMMessage(role="user", content="你好")],
        model_name="qwen-plus",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == "ok"
    assert cast(dict[str, Any], captured["body"])["model"] == "qwen-plus"


def test_call_llm_wraps_provider_error_body(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": {"message": "bad request detail"}})
        )
    )

    with pytest.raises(LLMProviderError, match="bad request detail"):
        call_llm(
            provider="deepseek", messages=[LLMMessage(role="user", content="x")], http_client=client
        )


def test_call_llm_normalizes_socks_proxy(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("HTTP_PROXY", "socks://127.0.0.1:64193/")
    monkeypatch.setenv("HTTPS_PROXY", "socks://127.0.0.1:64193/")

    call_llm(
        provider="deepseek",
        messages=[LLMMessage(role="user", content="ping")],
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: _json_response("ok"))
        ),
    )

    assert os.environ["HTTP_PROXY"] == "socks5://127.0.0.1:64193/"
    assert os.environ["HTTPS_PROXY"] == "socks5://127.0.0.1:64193/"


def test_agent_llm_router_reads_agent_specific_provider_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(tmp_path / "missing-agents.yaml"))
    for env_name in AGENT_PROVIDER_ENV.values():
        monkeypatch.setenv(env_name, "")
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DIAGNOSIS_FEEDBACK_PROVIDER", "qwen")
    monkeypatch.setenv("EXPERT_B_PROVIDER", "glm")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("diagnosis_feedback") == "qwen"
    assert "planner" not in router.agent_providers
    assert router.provider_for("expert_b") == "glm"


def test_load_provider_config_env_timeout_overrides_yaml(monkeypatch) -> None:
    # 回归测试：修复 `or` 短路 bug 后，.env 的 LLM_TIMEOUT_SECONDS / LLM_RETRY_TIMES
    # 必须能覆盖 yaml（llm_runtime_config）里配的值，而非被永远忽略。
    class _LlmCfg:
        timeout_seconds = 90.0
        retry_times = 5

    class _ProvCfg:
        model_name = "deepseek-v4-flash"
        base_url = None

    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
    monkeypatch.setattr("backend.app.core.llm.provider_runtime_config", lambda p: _ProvCfg())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_RETRY_TIMES", "7")

    cfg = load_provider_config("deepseek")

    assert cfg.timeout_seconds == 600.0
    assert cfg.retry_times == 7


def test_load_provider_config_falls_back_to_yaml_when_env_unset(monkeypatch) -> None:
    # env 未设置时，应回退到 yaml（llm_runtime_config）配置，原行为不可被破坏。
    class _LlmCfg:
        timeout_seconds = 90.0
        retry_times = 5

    class _ProvCfg:
        model_name = "deepseek-v4-flash"
        base_url = None

    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
    monkeypatch.setattr("backend.app.core.llm.provider_runtime_config", lambda p: _ProvCfg())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_RETRY_TIMES", raising=False)

    cfg = load_provider_config("deepseek")

    assert cfg.timeout_seconds == 90.0
    assert cfg.retry_times == 5
