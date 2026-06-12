"""Runtime context passed to LangGraph nodes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowContext:
    learner_id: str | None = None
