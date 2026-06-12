import pytest

from backend.app.core.llm import LLMMessage, LLMProvider, LLMProviderError, call_llm_json


@pytest.mark.parametrize("provider", ["deepseek", "qwen", "kimi"])
def test_configured_provider_can_call_real_chat_api(provider: LLMProvider) -> None:
    try:
        result = call_llm_json(
            provider=provider,
            messages=[
                LLMMessage(role="system", content="只输出 JSON，不要输出 Markdown。"),
                LLMMessage(role="user", content='请返回 {"ok": true}'),
            ],
            temperature=0.0,
        )
    except LLMProviderError as exc:
        if "429" in str(exc) or "rate limit" in str(exc).lower():
            pytest.skip(f"{provider} provider is currently rate limited")
        raise

    assert isinstance(result, dict)
    assert result.get("ok") is True
