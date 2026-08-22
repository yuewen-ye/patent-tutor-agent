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
    LLMProviderConfig,
    LLMProviderError,
    _post_chat_completion_stream,
    _strict_schema_rejected,
    call_llm,
    call_llm_json,
    call_llm_json_stream,
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


def _sse_response(content: str, chunk_size: int = 8) -> httpx.Response:
    """Return an OpenAI-compatible streaming completion response."""
    lines: list[str] = []
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        payload = json.dumps({"choices": [{"delta": {"content": chunk}}]}, ensure_ascii=False)
        lines.append(f"data: {payload}")
    lines.append("data: [DONE]")
    body = "\n\n".join(lines) + "\n\n"
    return httpx.Response(
        200,
        content=body.encode("utf-8"),
        headers={"content-type": "text/event-stream"},
    )


def _choices_null_response() -> httpx.Response:
    """Return a degenerate 200 response with choices:null (gateway bug)."""
    return httpx.Response(200, json={"choices": None})


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


def test_call_llm_treats_choices_null_as_retryable_provider_error(monkeypatch) -> None:
    """Regression: gateway may return HTTP 200 with choices:null.

    Previously ``payload['choices'][0]`` raised ``TypeError`` because the
    except clause only caught ``KeyError/IndexError/JSONDecodeError``.
    This must be converted to a retryable ``LLMProviderError``.
    """
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

    with pytest.raises(LLMProviderError) as excinfo:
        call_llm(
            provider="qwen",
            messages=[LLMMessage(role="user", content="hi")],
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: _choices_null_response())
            ),
        )

    assert excinfo.value.retryable
    assert "invalid chat response" in str(excinfo.value)


def test_call_llm_tools_treats_choices_null_as_retryable_provider_error(monkeypatch) -> None:
    """The tools variant has the same choices:null vulnerability."""
    from backend.app.core.llm import ToolDefinition, call_llm_tools

    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

    with pytest.raises(LLMProviderError) as excinfo:
        call_llm_tools(
            provider="qwen",
            messages=[LLMMessage(role="user", content="hi")],
            tools=[
                ToolDefinition(
                    name="search",
                    description="search",
                    parameters={"type": "object", "properties": {}},
                )
            ],
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: _choices_null_response())
            ),
        )

    assert excinfo.value.retryable
    assert "invalid tools chat response" in str(excinfo.value)


def test_call_llm_json_stream_fallback_yields_valid_json(monkeypatch) -> None:
    """Regression: streaming fallback must yield JSON, not Python repr.

    When the streaming endpoint times out, ``call_llm_json_stream`` falls back
    to ``call_llm_json`` which returns a parsed Python object. Previously the
    fallback yielded ``str(obj)`` (single-quoted repr); downstream chunk
    concatenation and JSON parsing could then salvage an empty ``[]`` from the
    repr and fail validation with ``Input should be a valid dictionary``.
    """
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config()})

    expected = {"expert": "expert_a", "items": [], "nested": {"value": 1}}
    call_llm_json_calls: list[dict[str, object]] = []

    def fake_call_llm_json(**kwargs: object) -> object:
        call_llm_json_calls.append(kwargs)
        return expected

    monkeypatch.setattr("backend.app.core.llm.call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(
        "backend.app.core.llm._post_chat_completion_stream",
        lambda *a, **k: (_ for _ in ()).throw(
            LLMProviderError("stream timeout", retryable=True)
        ),
    )

    chunks = list(
        call_llm_json_stream(
            provider="qwen",
            messages=[LLMMessage(role="user", content="hi")],
            temperature=0.5,
        )
    )

    joined = "".join(chunks)
    assert json.loads(joined) == expected
    assert len(call_llm_json_calls) == 1


def test_call_llm_json_stream_uses_json_schema_response_format(monkeypatch) -> None:
    """Streaming JSON generation must send the schema via response_format."""
    stub_llm_providers(monkeypatch, {"qwen": make_provider_config(model_name="qwen3.7-plus")})
    captured: dict[str, object] = {}
    schema: dict[str, object] = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _sse_response('{"answer": "streamed"}')

    chunks = list(
        call_llm_json_stream(
            provider="qwen",
            messages=[LLMMessage(role="user", content="hi")],
            temperature=0.5,
            schema_name="Answer",
            json_schema=schema,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    )

    joined = "".join(chunks)
    assert json.loads(joined) == {"answer": "streamed"}
    body = cast(dict[str, Any], captured["body"])
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "Answer"
    assert body["response_format"]["json_schema"]["schema"] == schema


def test_post_chat_completion_stream_reads_error_body_on_http_status_error() -> None:
    """Regression: streaming error responses must be read before accessing text.

    ``httpx`` streaming responses raise ``ResponseNotRead`` if ``response.text`` is
    accessed before the body is consumed. Previously the 502 error handler did exactly
    that, so a retryable gateway error became an uncaught ``ResponseNotRead`` and
    bypassed the primary/fallback model failover loop.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        # Use a streaming body so the response is not pre-read; accessing
        # ``response.text`` before ``response.read()`` would raise ``ResponseNotRead``.
        def body() -> Iterator[bytes]:
            yield b'{"error": {"message": "Bad Gateway"}}'

        return httpx.Response(
            502,
            content=body(),
            headers={"content-type": "text/event-stream"},
        )

    config = LLMProviderConfig(
        provider="qwen",
        api_key="test-key",
        model="qwen3.7-plus",
        base_url="https://gateway.example/v1",
        timeout_seconds=30.0,
        retry_times=3,
    )

    with pytest.raises(LLMProviderError, match="Bad Gateway") as excinfo:
        list(
            _post_chat_completion_stream(
                config=config,
                messages=[LLMMessage(role="user", content="hi")],
                temperature=0.5,
                json_mode=True,
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            )
        )

    assert excinfo.value.retryable
    assert "streaming API request failed" in str(excinfo.value)


def test_call_llm_json_stream_logs_full_content_before_downstream_parse(monkeypatch, tmp_path) -> None:
    """Streaming payload must record the accumulated content before JSON parsing."""
    from backend.app.core.llm import set_llm_log_context

    stub_llm_providers(monkeypatch, {"qwen": make_provider_config(model_name="qwen3.7-plus")})
    monkeypatch.setenv("LLM_LOG_PAYLOAD", "true")
    set_llm_log_context(session_id="sess-stream-payload", log_root=tmp_path)
    try:
        chunks = list(
            call_llm_json_stream(
                provider="qwen",
                messages=[LLMMessage(role="user", content="hi")],
                temperature=0.5,
                http_client=httpx.Client(
                    transport=httpx.MockTransport(
                        lambda request: _sse_response('{"answer": "streamed"}')
                    )
                ),
            )
        )
    finally:
        set_llm_log_context(session_id=None, log_root=None)

    assert "".join(chunks) == '{"answer": "streamed"}'
    log_file = tmp_path / "sessions" / "sess-stream-payload" / "llm_payloads.log.jsonl"
    records = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record["direction"] for record in records] == ["request", "response"]
    assert records[1]["status"] == "success"
    assert records[1]["body"] == '{"answer": "streamed"}'


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
    response_body = json.loads(records[1]["body"])
    assert response_body["choices"][0]["message"]["content"] == '{"intent":"teach"}'


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


def _patch_call_llm_json_stream(
    monkeypatch,
    script: dict[tuple[str, str | None], list[list[str] | Exception]],
):
    """Patch call_llm_json_stream with per-(provider, model) scripted iterators; returns call log."""
    calls: list[dict[str, object]] = []

    def fake_call_llm_json_stream(
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

        def _iter() -> Iterator[str]:
            yield from outcome

        return _iter()

    monkeypatch.setattr("backend.app.core.llm.call_llm_json_stream", fake_call_llm_json_stream)
    return calls


def test_fallback_model_used_on_streaming_failure(monkeypatch) -> None:
    """Streaming JSON generation must fail over to fallback model when primary stream fails."""
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json_stream(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [LLMProviderError("stream timeout", retryable=True)],
            ("gpt", "gpt-5.6-terra"): [['{"answer": "from-fallback"}']],
        },
    )

    chunks = list(
        _fallback_router().generate_json_stream(
            [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
        )
    )

    assert "".join(chunks) == '{"answer": "from-fallback"}'
    assert [(c["provider"], c["model_name"]) for c in calls] == [
        ("deepseek", "deepseek-v4-pro"),
        ("gpt", "gpt-5.6-terra"),
    ]


def test_fallback_streaming_failure_returns_to_primary_next_round(monkeypatch) -> None:
    """If fallback stream also fails, the next round starts from primary again."""
    _patch_retry_times(monkeypatch, 3)
    calls = _patch_call_llm_json_stream(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [
                LLMProviderError("stream timeout", retryable=True),
                ['{"answer": "primary-round-2"}'],
            ],
            ("gpt", "gpt-5.6-terra"): [LLMProviderError("fallback stream broken", retryable=True)],
        },
    )

    chunks = list(
        _fallback_router().generate_json_stream(
            [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
        )
    )

    assert "".join(chunks) == '{"answer": "primary-round-2"}'
    assert [(c["provider"], c["model_name"]) for c in calls] == [
        ("deepseek", "deepseek-v4-pro"),
        ("gpt", "gpt-5.6-terra"),
        ("deepseek", "deepseek-v4-pro"),
    ]


def test_fallback_streaming_exhausts_rounds_then_raises(monkeypatch) -> None:
    """Streaming failover alternates primary/fallback until rounds are exhausted."""
    _patch_retry_times(monkeypatch, 2)
    calls = _patch_call_llm_json_stream(
        monkeypatch,
        {
            ("deepseek", "deepseek-v4-pro"): [
                LLMProviderError("primary round 1", retryable=True),
                LLMProviderError("primary round 2", retryable=True),
            ],
            ("gpt", "gpt-5.6-terra"): [
                LLMProviderError("fallback round 1", retryable=True),
                LLMProviderError("fallback round 2", retryable=True),
            ],
        },
    )

    with pytest.raises(LLMProviderError, match="fallback round 2"):
        list(
            _fallback_router().generate_json_stream(
                [LLMMessage(role="user", content="hi")], 0.5, agent="expert_b"
            )
        )

    assert len(calls) == 4  # 2 rounds x (primary + fallback)


def test_call_llm_json_falls_back_schema_to_json_object_to_text(monkeypatch) -> None:
    """Regression: json_schema 400 must try json_object before plain text.

    Some providers reject ``response_format: json_schema`` but still accept
    ``json_object``. The old code went straight from schema to ``json_mode=False``
    (plain text), losing the JSON guarantee and often producing unparseable output.
    """
    stub_llm_providers(monkeypatch, {"ds": make_provider_config(model_name="ds-flash")})
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        requests.append(body)
        rf = body.get("response_format", {})
        if rf.get("type") == "json_schema":
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "This response_format type is unavailable now",
                        "type": "invalid_request_error",
                    }
                },
            )
        if rf.get("type") == "json_object":
            return _json_response('{"answer": "from_json_object"}')
        # plain text
        return _json_response('{"answer": "from_text"}')

    # Isolate from the dynamic strict-schema rejection cache.
    _strict_schema_rejected.clear()

    result = call_llm_json(
        provider="ds",
        messages=[LLMMessage(role="system", content="只输出 json")],
        json_schema={"type": "object"},
        schema_name="TestSchema",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"answer": "from_json_object"}
    assert len(requests) == 2
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert requests[1]["response_format"]["type"] == "json_object"


def test_call_llm_json_falls_back_schema_rejection_to_text_when_json_object_also_fails(
    monkeypatch,
) -> None:
    """If both json_schema and json_object are rejected, fall back to plain text."""
    stub_llm_providers(monkeypatch, {"ds": make_provider_config(model_name="ds-flash")})
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        requests.append(body)
        rf = body.get("response_format", {})
        if rf.get("type") in {"json_schema", "json_object"}:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "response_format unavailable",
                        "type": "invalid_request_error",
                    }
                },
            )
        return _json_response('{"answer": "from_text"}')

    # Isolate from the dynamic strict-schema rejection cache.
    _strict_schema_rejected.clear()

    result = call_llm_json(
        provider="ds",
        messages=[LLMMessage(role="system", content="只输出 json")],
        json_schema={"type": "object"},
        schema_name="TestSchema",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result == {"answer": "from_text"}
    assert len(requests) == 3
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert requests[1]["response_format"]["type"] == "json_object"
    assert "response_format" not in requests[2]
