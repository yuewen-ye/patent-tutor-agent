import json
import os
from collections.abc import Iterator
from typing import Any, cast

import httpx
import pytest

from backend.app.core.agent_runtime_config import (
    AgentRuntimeConfigError,
    clear_agent_runtime_config_cache,
)
from backend.app.core.llm import (
    AGENT_PROVIDER_ENV,
    AgentLLMRouter,
    LLMConfigurationError,
    LLMMessage,
    LLMProviderError,
    call_llm,
    call_llm_json,
    load_provider_config,
)
from backend.tests.helpers import make_provider_config, stub_llm_providers

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_config_cache() -> Iterator[None]:
    clear_agent_runtime_config_cache()
    yield
    clear_agent_runtime_config_cache()


def _json_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_call_llm_omits_temperature_for_gpt56_model(monkeypatch) -> None:
    stub_llm_providers(monkeypatch, {"gpt": make_provider_config(model_name="gpt-5.5")})
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
    stub_llm_providers(monkeypatch, {"gpt": make_provider_config(model_name="gpt-5.5")})
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
    ("provider", "model_name", "base_url"),
    [
        ("chan-alpha", "model-a", "https://alpha.example/v1"),
        ("chan-beta", "model-b", "https://beta.example/v1"),
        ("chan-gamma", "model-c", "https://gamma.example/v1"),
    ],
)
def test_call_llm_supports_custom_channels(
    monkeypatch, provider: str, model_name: str, base_url: str
) -> None:
    # provider 名是完全自定义的通道名；base_url/model 全部来自 yaml（这里 stub）。
    stub_llm_providers(
        monkeypatch,
        {provider: make_provider_config(model_name=model_name, base_url=base_url)},
    )

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
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config(model_name="qwen3.7-plus")})
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
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

    duplicated = '{"a": 1, "b": [2]}{"a": 1, "b": [2]}'

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(duplicated)

    result = call_llm_json(
        provider="qwen",
        messages=[LLMMessage(role="system", content="只输出 json")],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"a": 1, "b": [2]}


def test_call_llm_json_salvages_leading_garbage_prefix(monkeypatch) -> None:
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

    # deepseek json_object 偶发在真正的 JSON 对象前多输出一个 '{"'
    garbage_prefixed = '{"{"slides": [{"id": "slide_001"}]}'

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(garbage_prefixed)

    result = call_llm_json(
        provider="qwen",
        messages=[LLMMessage(role="system", content="只输出 json")],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"slides": [{"id": "slide_001"}]}


def test_call_llm_json_salvage_failure_keeps_retryable_error(monkeypatch) -> None:
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

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
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})
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
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})
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
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})
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
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(
        "llm:\n"
        "  default_provider: qwen\n"
        "providers:\n"
        "  qwen:\n"
        "    base_url: https://gw.example/v1\n"
        "  glm:\n"
        "    base_url: https://gw.example/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(yaml_path))
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

    stub_llm_providers(
        monkeypatch, {"qwen": make_provider_config(model_name="qwen3.7-plus")}
    )
    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
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

    stub_llm_providers(
        monkeypatch, {"qwen": make_provider_config(model_name="qwen3.7-plus")}
    )
    monkeypatch.setattr("backend.app.core.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr("backend.app.core.llm.llm_runtime_config", lambda: _LlmCfg())
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_RETRY_TIMES", raising=False)

    cfg = load_provider_config("qwen")

    assert cfg.timeout_seconds == 90.0
    assert cfg.retry_times == 5


def test_call_llm_logs_full_payload_pair_when_enabled(monkeypatch, tmp_path) -> None:
    from backend.app.core.llm import set_llm_log_context

    stub_llm_providers(monkeypatch, {"gpt": make_provider_config(model_name="gpt-5.5")})
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

    stub_llm_providers(monkeypatch, {"gpt": make_provider_config(model_name="gpt-5.5")})
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
# 自定义通道解析链（api_key 直写 / api_key_env / 约定名）
# ---------------------------------------------------------------------------


def _write_agent_config(monkeypatch, tmp_path, text: str) -> None:
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(yaml_path))


def test_load_provider_config_prefers_inline_api_key(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  my-chan:\n"
        "    base_url: https://gw.example/v1\n"
        "    model_name: my-model\n"
        "    api_key: sk-inline\n"
        "    api_key_env: MY_CHAN_SPECIAL_KEY\n",
    )
    monkeypatch.setenv("MY_CHAN_SPECIAL_KEY", "sk-from-env")

    cfg = load_provider_config("my-chan")

    assert cfg.api_key == "sk-inline"
    assert cfg.base_url == "https://gw.example/v1"
    assert cfg.model == "my-model"


def test_load_provider_config_uses_api_key_env(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  my-chan:\n"
        "    base_url: https://gw.example/v1\n"
        "    model_name: my-model\n"
        "    api_key_env: MY_CHAN_SPECIAL_KEY\n",
    )
    monkeypatch.setenv("MY_CHAN_SPECIAL_KEY", "sk-from-env")
    monkeypatch.delenv("MY_CHAN_API_KEY", raising=False)

    cfg = load_provider_config("my-chan")

    assert cfg.api_key == "sk-from-env"


def test_load_provider_config_uses_conventional_env_name(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  my-chan:\n"
        "    base_url: https://gw.example/v1\n"
        "    model_name: my-model\n",
    )
    # 约定：{通道名大写, 非字母数字转_}_API_KEY → MY_CHAN_API_KEY
    monkeypatch.setenv("MY_CHAN_API_KEY", "sk-conventional")

    cfg = load_provider_config("my-chan")

    assert cfg.api_key == "sk-conventional"


def test_load_provider_config_missing_key_names_env_var(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  my-chan:\n"
        "    base_url: https://gw.example/v1\n"
        "    model_name: my-model\n",
    )
    monkeypatch.delenv("MY_CHAN_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError, match="MY_CHAN_API_KEY"):
        load_provider_config("my-chan")


def test_load_provider_config_missing_base_url_errors(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n  my-chan:\n    model_name: my-model\n    api_key: sk-x\n",
    )

    with pytest.raises(LLMConfigurationError, match="base_url"):
        load_provider_config("my-chan")


def test_load_provider_config_missing_model_errors(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n  my-chan:\n    base_url: https://gw.example/v1\n    api_key: sk-x\n",
    )

    with pytest.raises(LLMConfigurationError, match="model"):
        load_provider_config("my-chan")


def test_undefined_channel_error_lists_available(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n  jiji-deepseek:\n    base_url: https://gw.example/v1\n",
    )

    with pytest.raises(LLMConfigurationError, match="jiji-deepseek"):
        load_provider_config("nope")


def test_default_provider_resolution_from_yaml(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "llm:\n"
        "  default_provider: jiji-deepseek\n"
        "providers:\n"
        "  jiji-deepseek:\n"
        "    base_url: https://gw.example/v1\n"
        "    model_name: deepseek-v4-flash\n"
        "    api_key: sk-x\n",
    )
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)

    cfg = load_provider_config()

    assert cfg.provider == "jiji-deepseek"
    assert cfg.model == "deepseek-v4-flash"


def test_default_provider_unconfigured_errors_with_available_list(
    monkeypatch, tmp_path
) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n  jiji-gpt:\n    base_url: https://gw.example/v1\n",
    )
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)

    with pytest.raises(LLMConfigurationError, match="jiji-gpt"):
        load_provider_config()


def test_yaml_default_provider_must_be_defined(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "llm:\n"
        "  default_provider: ghost\n"
        "providers:\n"
        "  jiji-gpt:\n"
        "    base_url: https://gw.example/v1\n",
    )

    from backend.app.core.agent_runtime_config import load_agent_runtime_config

    with pytest.raises(AgentRuntimeConfigError, match="ghost"):
        load_agent_runtime_config()


def test_models_list_validation_accepts_declared_model(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  jiji-gpt:\n"
        "    base_url: https://gw.example/v1\n"
        "    models: [gpt-5.4-mini, gpt-5.6-terra]\n"
        "agents:\n"
        "  judge:\n"
        "    provider: jiji-gpt\n"
        "    model_name: gpt-5.6-terra\n",
    )

    from backend.app.core.agent_runtime_config import load_agent_runtime_config

    config = load_agent_runtime_config()

    assert config.agents["judge"].model_name == "gpt-5.6-terra"


def test_models_list_validation_rejects_typo(monkeypatch, tmp_path) -> None:
    _write_agent_config(
        monkeypatch,
        tmp_path,
        "providers:\n"
        "  jiji-gpt:\n"
        "    base_url: https://gw.example/v1\n"
        "    models: [gpt-5.4-mini]\n"
        "agents:\n"
        "  judge:\n"
        "    provider: jiji-gpt\n"
        "    model_name: gpt-5.6-terra\n",
    )

    from backend.app.core.agent_runtime_config import load_agent_runtime_config

    with pytest.raises(AgentRuntimeConfigError, match="gpt-5.6-terra"):
        load_agent_runtime_config()


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


def test_semantic_validation_failure_uses_fallback_then_returns_to_primary(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 2)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [{"valid": False}, {"valid": True}],
            ("gpt", "gpt-5.6-terra"): [{"valid": False}],
        },
    )

    def validator(raw: object) -> dict[str, bool]:
        assert isinstance(raw, dict)
        if raw.get("valid") is not True:
            raise ValueError("semantic route failure")
        return {"valid": True}

    result = _fallback_router().generate_structured_validated_json(
        [LLMMessage(role="user", content="hi")],
        0.5,
        schema_name="PlannerAgentResult",
        json_schema={"type": "object"},
        validator=validator,
        agent="expert_b",
    )

    assert result == {"valid": True}
    assert [(call["provider"], call["model_name"]) for call in calls] == [
        ("deepseek", "deepseek-v4-pro"),
        ("gpt", "gpt-5.6-terra"),
        ("deepseek", "deepseek-v4-pro"),
    ]


def test_our_side_error_also_triggers_fallback(monkeypatch) -> None:
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [LLMProviderError("bad schema", status_code=400)],
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
        "llm:\n"
        "  default_provider: deepseek\n"
        "providers:\n"
        "  deepseek:\n"
        "    base_url: https://gw.example/v1\n"
        "  gpt:\n"
        "    base_url: https://gw.example/v1\n"
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
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)

    router = AgentLLMRouter.from_env()

    target = router.agent_fallbacks["expert_b"]
    assert target.provider == "gpt"
    assert target.model_name == "gpt-5.6-terra"
    assert target.base_url == "https://fb.example/v1"


def test_env_provider_override_ignores_yaml_fallback(monkeypatch, tmp_path) -> None:
    yaml_path = tmp_path / "agents.yaml"
    yaml_path.write_text(
        "llm:\n"
        "  default_provider: deepseek\n"
        "providers:\n"
        "  deepseek:\n"
        "    base_url: https://gw.example/v1\n"
        "  gpt:\n"
        "    base_url: https://gw.example/v1\n"
        "agents:\n"
        "  expert_b:\n"
        "    provider: deepseek\n"
        "    fallback_model_name: deepseek-v4-flash\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_CONFIG_PATH", str(yaml_path))
    for env_name in AGENT_PROVIDER_ENV.values():
        monkeypatch.setenv(env_name, "")
    monkeypatch.delenv("DEFAULT_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("EXPERT_B_PROVIDER", "gpt")

    router = AgentLLMRouter.from_env()

    assert router.provider_for("expert_b") == "gpt"
    assert "expert_b" not in router.agent_fallbacks
