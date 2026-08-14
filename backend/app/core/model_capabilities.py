from __future__ import annotations

from typing import Literal

LLMRequestParameter = Literal["temperature"]

_PROVIDERS_WITHOUT_TEMPERATURE = frozenset({"luna", "terra"})
_MODEL_PREFIXES_WITHOUT_TEMPERATURE = ("gpt-5.6",)


def model_supports_request_parameter(
    *,
    provider: str,
    model_name: str | None,
    parameter: LLMRequestParameter,
) -> bool:
    """Return whether an OpenAI-compatible model accepts a request parameter.

    Provider aliases for GPT-5.6 are checked even when their model name comes from an
    environment variable and is therefore unavailable during YAML validation. The model-name
    check also protects custom gateway/provider combinations that route to a GPT-5.6 model.
    """

    if parameter != "temperature":
        raise ValueError(f"Unsupported LLM request parameter capability: {parameter}")

    normalized_provider = provider.strip().lower()
    normalized_model = (model_name or "").strip().lower()
    if normalized_provider in _PROVIDERS_WITHOUT_TEMPERATURE:
        return False
    return not normalized_model.startswith(_MODEL_PREFIXES_WITHOUT_TEMPERATURE)
