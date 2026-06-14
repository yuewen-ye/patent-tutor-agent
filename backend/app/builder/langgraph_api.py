"""LangGraph API entry point for LangGraph Studio.

Usage:
    langgraph dev --config langgraph.json
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from backend.app.graph.workflow import build_workflow  # noqa: E402

# Build without default checkpointer/store — LangGraph API handles persistence.
graph = build_workflow(use_default_checkpointing=False)

# Expose metadata
__all__ = ["graph"]
