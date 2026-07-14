"""LangGraph API entry point for LangGraph Studio.

Usage:
    langgraph dev --config langgraph.json
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

from backend.app.graph.workflow import build_workflow  # noqa: E402
from backend.app.runtime_outputs.workflow_logging import configure_studio_terminal_logging  # noqa: E402

configure_studio_terminal_logging()

# Build without default checkpointer/store — LangGraph API handles persistence.
graph = build_workflow(
    use_default_checkpointing=False,
    artifact_root=Path(os.getenv("ARTIFACT_ROOT", "artifacts")),
    workflow_log_root=Path(os.getenv("WORKFLOW_LOG_ROOT", "artifacts")),
)

# Expose metadata
__all__ = ["graph"]
