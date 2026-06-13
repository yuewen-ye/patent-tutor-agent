"""Smoke-test each LLM provider individually with real API calls.

Requires valid .env with API keys for the providers being tested.
"""

from __future__ import annotations

import pytest
from typing import cast

from backend.app.core.llm import LLMConfigurationError, LLMMessage, LLMProvider, LLMProviderError, call_llm_json

pytestmark = pytest.mark.integration

MESSAGES = [
    LLMMessage(role="system", content="You are a JSON API. Reply ONLY with valid JSON, no explanation."),
    LLMMessage(role="user", content='Return exactly: {"model":"<your model name>","ok":true}'),
]


@pytest.mark.parametrize("provider", ["deepseek", "qwen", "glm"])
def test_provider_returns_valid_json(provider: str) -> None:
    try:
        result = call_llm_json(provider=cast(LLMProvider, provider), messages=MESSAGES, temperature=0.1)
    except LLMConfigurationError as exc:
        pytest.skip(f"{provider} not configured: {exc}")
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(kw in message for kw in ("429", "rate limit", "401", "unauthorized")):
            pytest.skip(f"{provider} unavailable: {exc}")
        raise

    assert isinstance(result, dict)
    assert result.get("ok") is True
