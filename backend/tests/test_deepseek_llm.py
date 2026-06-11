import json
import os

import httpx

from backend.app.core.llm import DeepSeekChatClient, LLMMessage


def test_deepseek_client_posts_openai_compatible_json_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"ok": true, "answer": "structured"}',
                        }
                    }
                ]
            },
        )

    client = DeepSeekChatClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.generate_json(
        messages=[
            LLMMessage(role="system", content="Output json only."),
            LLMMessage(role="user", content="Return an object."),
        ],
        temperature=0.2,
    )

    assert result == {"ok": True, "answer": "structured"}
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": "Output json only."},
            {"role": "user", "content": "Return an object."},
        ],
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
    }


def test_deepseek_client_loads_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    client = DeepSeekChatClient.from_env(
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    )

    assert client.api_key == "env-key"
    assert client.model == "deepseek-v4-pro"


def test_deepseek_from_env_normalizes_socks_proxy(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setenv("HTTP_PROXY", "socks://127.0.0.1:64193/")
    monkeypatch.setenv("HTTPS_PROXY", "socks://127.0.0.1:64193/")

    DeepSeekChatClient.from_env(
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    )

    assert os.environ["HTTP_PROXY"] == "socks5://127.0.0.1:64193/"
    assert os.environ["HTTPS_PROXY"] == "socks5://127.0.0.1:64193/"


def test_deepseek_client_wraps_http_status_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request detail"}})

    client = DeepSeekChatClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.generate_json(messages=[LLMMessage(role="system", content="json")], temperature=0.0)
    except Exception as exc:
        assert "bad request detail" in str(exc)
    else:
        raise AssertionError("expected provider error")
