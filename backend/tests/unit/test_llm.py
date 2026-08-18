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


def test_call_llm_omits_temperature_for_gpt56_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.core.llm.provider_runtime_config",
        lambda _provider: ProviderRuntimeConfig(),
    )
    monkeypatch.setenv("GPT_API_KEY", "gpt-key")
    monkeypatch.setenv("GPT_BASE_URL", "https://gateway.example/v1")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response("ok")

    result = call_llm(
        provider="gpt",
        model_name="gpt-5.6-sol",
        messages=[LLMMessage(role="user", content="你好")],
        temperature=0.2,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == "ok"
    body = cast(dict[str, Any], captured["body"])
    assert body["model"] == "gpt-5.6-sol"
    assert "temperature" not in body


def test_gpt_provider_keeps_temperature_for_supported_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.core.llm.provider_runtime_config",
        lambda _provider: ProviderRuntimeConfig(),
    )
    monkeypatch.setenv("GPT_API_KEY", "gpt-key")
    monkeypatch.setenv("GPT_BASE_URL", "https://gateway.example/v1")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response("ok")

    result = call_llm(
        provider="gpt",
        model_name="gpt-5.5",
        messages=[LLMMessage(role="user", content="你好")],
        temperature=0.2,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == "ok"
    body = cast(dict[str, Any], captured["body"])
    assert body["temperature"] == 0.2


@pytest.mark.parametrize(
    ("provider", "key_name", "model_name", "base_url"),
    [
        ("qwen", "QWEN_API_KEY", "qwen3.7-plus", "https://api-slb.krill-ai.net/codex/v1"),
        (
            "glm",
            "GLM_API_KEY",
            "GLM-5.2",
            "https://api-slb.krill-ai.net/codex/v1",
        ),
        ("gpt", "GPT_API_KEY", "gpt-5.5", "https://api-slb.krill-ai.net/codex/v1"),
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
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("QWEN_BASE_URL", "https://api-slb.krill-ai.net/codex/v1")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _json_response('{"answer": "json"}')

    result = call_llm_json(
        provider="qwen",
        messages=[LLMMessage(role="system", content="只输出 json")],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"answer": "json"}
    assert cast(dict[str, Any], captured["body"])["response_format"] == {"type": "json_object"}


def test_call_llm_json_salvages_duplicated_json_payload(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("QWEN_BASE_URL", "https://api-slb.krill-ai.net/codex/v1")

    duplicated = '{"a": 1, "b": [2]}{"a": 1, "b": [2]}'

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(duplicated)

    result = call_llm_json(
        provider="qwen",
        messages=[LLMMessage(role="system", content="只输出 json")],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"a": 1, "b": [2]}


def test_call_llm_json_salvage_failure_keeps_retryable_error(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("QWEN_BASE_URL", "https://api-slb.krill-ai.net/codex/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response('{"a": 1, broken')

    with pytest.raises(LLMProviderError) as excinfo:
        call_llm_json(
            provider="qwen",
            messages=[LLMMessage(role="system", content="只输出 json")],
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    assert excinfo.value.retryable


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
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("QWEN_BASE_URL", "https://api-slb.krill-ai.net/codex/v1")

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error": {"message": "bad request detail"}})
        )
    )

    with pytest.raises(LLMProviderError, match="bad request detail"):
        call_llm(
            provider="qwen", messages=[LLMMessage(role="user", content="x")], http_client=client
        )


def test_524_gateway_timeout_is_retryable() -> None:
    from backend.app.core.llm import _is_retryable_error

    assert _is_retryable_error(LLMProviderError("cf timeout", status_code=524))
    assert _is_retryable_error(LLMProviderError("bad gateway", status_code=502))
    assert not _is_retryable_error(LLMProviderError("bad request", status_code=400))


def test_call_llm_normalizes_socks_proxy(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("HTTP_PROXY", "socks://127.0.0.1:64193/")
    monkeypatch.setenv("HTTPS_PROXY", "socks://127.0.0.1:64193/")

    call_llm(
        provider="qwen",
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
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "qwen")
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
        model_name = "qwen3.7-plus"
        base_url = None

    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
    monkeypatch.setattr("backend.app.core.llm.provider_runtime_config", lambda p: _ProvCfg())
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_RETRY_TIMES", "7")

    cfg = load_provider_config("qwen")

    assert cfg.timeout_seconds == 600.0
    assert cfg.retry_times == 7


def test_load_provider_config_falls_back_to_yaml_when_env_unset(monkeypatch) -> None:
    # env 未设置时，应回退到 yaml（llm_runtime_config）配置，原行为不可被破坏。
    class _LlmCfg:
        timeout_seconds = 90.0
        retry_times = 5

    class _ProvCfg:
        model_name = "qwen3.7-plus"
        base_url = None

    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
    monkeypatch.setattr("backend.app.core.llm.provider_runtime_config", lambda p: _ProvCfg())
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_RETRY_TIMES", raising=False)

    cfg = load_provider_config("qwen")

    assert cfg.timeout_seconds == 90.0
    assert cfg.retry_times == 5


def test_call_llm_logs_full_payload_pair_when_enabled(monkeypatch, tmp_path) -> None:
    from backend.app.core.llm import set_llm_log_context

    monkeypatch.setattr(
        "backend.app.core.llm.provider_runtime_config",
        lambda _provider: ProviderRuntimeConfig(),
    )
    monkeypatch.setenv("GPT_API_KEY", "gpt-key")
    monkeypatch.setenv("GPT_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LLM_LOG_PAYLOAD", "true")
    set_llm_log_context(session_id="sess-payload", log_root=tmp_path)
    try:
        result = call_llm(
            provider="gpt",
            model_name="gpt-5.5",
            messages=[LLMMessage(role="user", content="你好")],
            temperature=0.2,
            json_mode=True,
            schema_name="IntentResult",
            json_schema={"type": "object", "properties": {"intent": {"type": "string"}}},
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: _json_response('{"intent":"teach"}'))
            ),
        )
    finally:
        set_llm_log_context(session_id=None, log_root=None)

    assert result == '{"intent":"teach"}'
    log_file = tmp_path / "sessions" / "sess-payload" / "llm_payloads.log.jsonl"
    records = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record["direction"] for record in records] == ["request", "response"]
    assert records[0]["call_id"] == records[1]["call_id"]
    request_body = records[0]["body"]
    assert request_body["messages"] == [{"role": "user", "content": "你好"}]
    assert request_body["response_format"]["json_schema"]["schema"]["properties"]["intent"] == {
        "type": "string"
    }
    assert records[1]["status"] == "success"
    assert records[1]["payload"]["choices"][0]["message"]["content"] == '{"intent":"teach"}'


def test_call_llm_skips_payload_log_when_disabled(monkeypatch, tmp_path) -> None:
    from backend.app.core.llm import set_llm_log_context

    monkeypatch.setattr(
        "backend.app.core.llm.provider_runtime_config",
        lambda _provider: ProviderRuntimeConfig(),
    )
    monkeypatch.setenv("GPT_API_KEY", "gpt-key")
    monkeypatch.setenv("GPT_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LLM_LOG_PAYLOAD", "false")
    set_llm_log_context(session_id="sess-no-payload", log_root=tmp_path)
    try:
        call_llm(
            provider="gpt",
            model_name="gpt-5.5",
            messages=[LLMMessage(role="user", content="你好")],
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: _json_response("ok"))
            ),
        )
    finally:
        set_llm_log_context(session_id=None, log_root=None)

    assert not (tmp_path / "sessions" / "sess-no-payload" / "llm_payloads.log.jsonl").exists()


# ---------------------------------------------------------------------------
# AgentLLMRouter fallback_model 机制
# ---------------------------------------------------------------------------


def _fallback_router() -> AgentLLMRouter:
    from backend.app.core.llm import FallbackTarget

    return AgentLLMRouter(
        default_provider="gpt",
        agent_providers={"expert_b": "deepseek"},
        agent_model_names={"expert_b": "deepseek-v4-pro"},
        agent_fallbacks={
            "expert_b": FallbackTarget(
                provider="gpt", model_name="gpt-5.6-terra", base_url="https://fb.example/v1"
            )
        },
    )


def _patch_call_llm_json(monkeypatch, script: dict[tuple[str, str | None], list[object]]):
    """Patch call_llm_json with per-(provider, model) scripted results; returns call log."""
    calls: list[dict[str, object]] = []

    def fake_call_llm_json(
        *,
        provider,
        messages,
        temperature,
        http_client=None,
        model_name=None,
        schema_name=None,
        json_schema=None,
        base_url_override=None,
        max_attempts=None,
    ):
        calls.append(
            {
                "provider": provider,
                "model_name": model_name,
                "base_url_override": base_url_override,
                "max_attempts": max_attempts,
            }
        )
        queue = script[(provider, model_name)]
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("backend.app.core.llm.call_llm_json", fake_call_llm_json)
    return calls


def _patch_retry_times(monkeypatch, retry_times: int) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "backend.app.core.llm.load_provider_config",
        lambda *a, **k: SimpleNamespace(retry_times=retry_times),
    )
    monkeypatch.setattr("backend.app.core.llm.time.sleep", lambda _s: None)


def test_fallback_model_used_on_model_side_failure(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [LLMProviderError("cf timeout", status_code=524)],
            ("gpt", "gpt-5.6-terra"): [{"answer": "from-fallback"}],
        },
    )

    result = _fallback_router().generate_json(
        [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
    )

    assert result == {"answer": "from-fallback"}
    assert [(c["provider"], c["model_name"]) for c in calls] == [
        ("deepseek", "deepseek-v4-pro"),
        ("gpt", "gpt-5.6-terra"),
    ]
    assert calls[0]["max_attempts"] == 1 and calls[0]["base_url_override"] is None
    assert calls[1]["max_attempts"] == 1
    assert calls[1]["base_url_override"] == "https://fb.example/v1"


def test_fallback_failure_returns_to_primary_next_round(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [
                LLMProviderError("cf timeout", status_code=524),
                {"answer": "primary-round-2"},
            ],
            ("gpt", "gpt-5.6-terra"): [LLMProviderError("bad gateway", status_code=502)],
        },
    )

    result = _fallback_router().generate_json(
        [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
    )

    assert result == {"answer": "primary-round-2"}
    assert [(c["provider"], c["model_name"]) for c in calls] == [
        ("deepseek", "deepseek-v4-pro"),
        ("gpt", "gpt-5.6-terra"),
        ("deepseek", "deepseek-v4-pro"),
    ]


def test_fallback_exhausts_rounds_then_raises(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 2)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [
                LLMProviderError("cf timeout", status_code=524),
                LLMProviderError("cf timeout again", status_code=524),
            ],
            ("gpt", "gpt-5.6-terra"): [
                LLMProviderError("bad gateway", status_code=502),
                LLMProviderError("bad gateway again", status_code=502),
            ],
        },
    )

    with pytest.raises(LLMProviderError, match="bad gateway again"):
        _fallback_router().generate_json(
            [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
        )

    assert len(calls) == 4  # 2 rounds x (primary + fallback)


def test_our_side_error_never_triggers_fallback(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [LLMProviderError("bad schema", status_code=400)],
            ("gpt", "gpt-5.6-terra"): [{"answer": "should-not-be-used"}],
        },
    )

    with pytest.raises(LLMProviderError, match="bad schema"):
        _fallback_router().generate_json(
            [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
        )

    assert len(calls) == 1


def test_agent_without_fallback_keeps_default_retry_path(monkeypatch) -> None:
    calls = _patch_call_llm_json(
        monkeypatch, {("gpt", None): [{"answer": "plain"}]}
    )
    router = AgentLLMRouter(default_provider="gpt")

    result = router.generate_json([LLMMessage(role="user", content="hi")], 0.5, agent="judge")

    assert result == {"answer": "plain"}
    assert len(calls) == 1
    assert calls[0]["max_attempts"] is None  # 内部 tenacity 重试行为不变


def test_from_env_reads_fallback_config(monkeypatch, tmp_path) -> None:
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(
        "agents:\n"
        "  expert_b:\n"
        "    provider: deepseek\n"
        "    model_name: deepseek-v4-pro\n"
        "    fallback_provider: gpt\n"
        "    fallback_model_name: gpt-5.6-terra\n"
        "    fallback_base_url: https://fb.example/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(yaml_path))
    for env_name in AGENT_PROVIDER_ENV.values():
        monkeypatch.setenv(env_name, "")

    router = AgentLLMRouter.from_env()

    target = router.agent_fallbacks["expert_b"]
    assert target.provider == "gpt"
    assert target.model_name == "gpt-5.6-terra"
    assert target.base_url == "https://fb.example/v1"


def test_env_provider_override_ignores_yaml_fallback(monkeypatch, tmp_path) -> None:
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(
        "agents:\n"
        "  expert_b:\n"
        "    provider: deepseek\n"
        "    fallback_model_name: deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(yaml_path))
    for env_name in AGENT_PROVIDER_ENV.values():
        monkeypatch.setenv(env_name, "")
    monkeypatch.setenv("EXPERT_B_PROVIDER", "gpt")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("expert_b") == "gpt"
    assert "expert_b" not in router.agent_fallbacks
