import pytest

from backend.app.core.llm import LLMMessage, LLMProvider, call_llm_json


@pytest.mark.parametrize("provider", ["deepseek", "qwen", "kimi"])
def test_configured_provider_can_call_real_chat_api(provider: LLMProvider) -> None:
    result = call_llm_json(
        provider=provider,
        messages=[
            LLMMessage(role="system", content="只输出 JSON，不要输出 Markdown。"),
            LLMMessage(role="user", content='请返回 {"ok": true}'),
        ],
        temperature=0.0,
    )

    assert isinstance(result, dict)
    assert result.get("ok") is True
