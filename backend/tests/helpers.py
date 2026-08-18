"""Shared test helpers for workflow assertions."""

from __future__ import annotations

from typing import Any, cast

from backend.app.core.agent_runtime_config import ProviderRuntimeConfig
from backend.app.schemas.state import StateDict

_COMPLETED_STATE_KEYS = (
    "learner_profile",
    "learning_path",
    "expert_a_draft",
    "expert_b_draft",
    "course_package",
    "judge_report",
    "workflow_status",
    "artifacts",
)

def completed_state(state: StateDict) -> dict[str, Any]:
    """Assert that a workflow has completed with all expected state keys populated.

    Use this in tests after ``run_workflow()`` to narrow ``StateDict`` to
    ``dict[str, Any]``, eliminating Pyright/Pylance ``reportTypedDictNotRequiredAccess``
    warnings when directly indexing optional keys like ``state["expert_a_draft"]``.
    """
    for key in _COMPLETED_STATE_KEYS:
        assert key in state, f"Expected workflow to populate {key}"
    return cast(dict[str, Any], state)


def completed_teach_state(state: StateDict) -> dict[str, Any]:
    return completed_state(state)


# ---------------------------------------------------------------------------
# LLM provider stubbing (post channel-refactor: no built-in provider table)
# ---------------------------------------------------------------------------


def make_provider_config(
    *,
    model_name: str = "stub-model",
    base_url: str = "https://gateway.example/v1",
    api_key: str = "test-key",
    **kwargs: Any,
) -> ProviderRuntimeConfig:
    """Build a self-contained ProviderRuntimeConfig for tests (key inlined, no env needed)."""
    return ProviderRuntimeConfig(
        model_name=model_name, base_url=base_url, api_key=api_key, **kwargs
    )


def stub_llm_providers(
    monkeypatch: Any, configs: dict[str, ProviderRuntimeConfig]
) -> None:
    """Stub the yaml-backed provider lookup in ``backend.app.core.llm``.

    Makes the given channel names "defined" (validation passes) and resolves
    their base_url/model/api_key without touching env or config/agents.yaml.
    """
    import backend.app.core.llm as llm_module

    monkeypatch.setattr(
        llm_module,
        "provider_runtime_config",
        lambda name: configs.get(name, ProviderRuntimeConfig()),
    )
    monkeypatch.setattr(
        llm_module, "available_provider_names", lambda: sorted(configs)
    )
