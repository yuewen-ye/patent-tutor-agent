import json
import os
from typing import Any, cast

import httpx
import pytest

from backend.app.core.llm import (
    AgentLLMRouter,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    call_llm,
    call_llm_json,
)


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
        "model": "qwen3.7-max",
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
        ("kimi", "KIMI_API_KEY", "moonshotai/Kimi-K2.5", "https://api-inference.modelscope.cn/v1"),
    ],
)
def test_call_llm_supports_three_configured_providers(
    monkeypatch, provider: LLMProvider, key_name: str, model_name: str, base_url: str
) -> None:
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
    assert cast(dict[str, Any], seen["body"])["model"] == model_name


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


def test_call_llm_wraps_provider_error_body(monkeypatch) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")
    monkeypatch.setenv("KIMI_MODEL", "moonshotai/Kimi-K2.5")
    monkeypatch.setenv("KIMI_BASE_URL", "https://api-inference.modelscope.cn/v1")

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": {"message": "bad request detail"}})
        )
    )

    with pytest.raises(LLMProviderError, match="bad request detail"):
        call_llm(
            provider="kimi", messages=[LLMMessage(role="user", content="x")], http_client=client
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


def test_agent_llm_router_reads_agent_specific_provider_config(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DIAGNOSIS_PROVIDER", "qwen")
    monkeypatch.setenv("EXPERT_B_PROVIDER", "kimi")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("diagnosis") == "qwen"
    assert router.provider_for("planner") == "deepseek"
    assert router.provider_for("expert_b") == "kimi"
