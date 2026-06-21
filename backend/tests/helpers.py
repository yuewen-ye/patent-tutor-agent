"""Shared test helpers for workflow assertions."""

from __future__ import annotations

from typing import Any, cast

from backend.app.schemas.state import StateDict

_COMPLETED_STATE_KEYS = (
    "learner_profile",
    "learning_path",
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "feedback_result",
    "final_answer",
    "artifacts",
    "debate_round",
    "max_debate_rounds",
)

# P0.1: Additional fields for the 5-stage teach-path workflow
_TEACH_PATH_KEYS = (
    "cross_review_a",
    "cross_review_b",
    "revision_record_a",
    "revision_record_b",
    "joint_synthesis_output",
)


def completed_state(state: StateDict) -> dict[str, Any]:
    """Assert that a workflow has completed with all expected state keys populated.

    Use this in tests after ``run_workflow()`` to narrow ``StateDict`` to
    ``dict[str, Any]``, eliminating Pyright/Pylance ``reportTypedDictNotRequiredAccess``
    warnings when directly indexing optional keys like ``state["final_answer"]``.
    """
    for key in _COMPLETED_STATE_KEYS:
        assert key in state, f"Expected workflow to populate {key}"
    return cast(dict[str, Any], state)


def completed_teach_state(state: StateDict) -> dict[str, Any]:
    """Assert teach-path workflow completion including P0.1 fields."""
    completed = completed_state(state)
    for key in _TEACH_PATH_KEYS:
        assert key in completed, f"Expected teach workflow to populate {key}"
    return completed
