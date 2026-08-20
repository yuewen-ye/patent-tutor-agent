"""Workflow wiring for optional complete PPTX generation."""

from __future__ import annotations

import pytest

from backend.app.graph.workflow import build_workflow

pytestmark = pytest.mark.unit


class _Client:
    def generate_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("not called when inspecting graph")

    def generate_structured_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("not called when inspecting graph")


def test_workflow_adds_pptx_stage_only_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("PATENT_TUTOR_PPTX_ENABLED", "true")
    enabled = build_workflow(llm_client=_Client(), slide_deck_enabled=True)
    enabled_edges = {(edge.source, edge.target) for edge in enabled.get_graph().edges}

    assert ("slide_deck", "generate_pptx") in enabled_edges
    assert ("generate_pptx", "__end__") in enabled_edges

    monkeypatch.setenv("PATENT_TUTOR_PPTX_ENABLED", "false")
    disabled = build_workflow(llm_client=_Client(), slide_deck_enabled=True)
    disabled_edges = {(edge.source, edge.target) for edge in disabled.get_graph().edges}

    assert ("slide_deck", "__end__") in disabled_edges
    assert "generate_pptx" not in {edge.target for edge in disabled.get_graph().edges}
