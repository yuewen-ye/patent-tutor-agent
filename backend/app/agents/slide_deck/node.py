"""SlideDeck node: turns the integrated course_package into structured PPT slides + narration.

The node reads the authoritative ``course_package`` (ExpertDraft dict) from state, asks the
LLM to split it into a structured ``SlideDeck`` (per-slide display content + narration text),
then writes the result to ``course_slides`` and emits a completed event. Audio synthesis is a
separate later stage (TTS service) that backfills ``narration.audio_url`` / ``duration_sec``.
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.agents.common import Node, generate_validated_json_stream, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import SlideDeck, StateDict, completed_event

_SLIDE_DECK_SYSTEM = load_prompt(__file__)


def _course_package_input(course_package: dict[str, Any]) -> dict[str, Any]:
    """Compact the course_package into a prompt-friendly payload.

    We keep the structured fields (knowledge_points, legal_basis, irac, block_plan,
    assessment) plus the teaching body, dropping bulky exercise/artifact internals.
    """
    input_dict: dict[str, Any] = {}
    for key in (
        "title",
        "style",
        "knowledge_points",
        "legal_basis",
        "irac",
        "block_plan",
        "knowledge_synthesis",
        "assessment",
        "teaching_content",
    ):
        value = course_package.get(key)
        if value not in (None, "", [], {}):
            input_dict[key] = value
    return input_dict


def build_slide_deck_node(llm_client: LLMClient) -> Node:
    def slide_deck_node(
        state: StateDict,
        runtime: Any = None,
    ) -> dict[str, Any]:
        course_package = state.get("course_package") or {}
        if not course_package:
            raise RuntimeError(
                "slide_deck: state 缺少 course_package，无法生成结构化课件。"
            )
        messages = [
            LLMMessage(role="system", content=_SLIDE_DECK_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    "请把以下课程整合稿改造成结构化课件（SlideDeck）。"
                    "忠实保留知识点与法条，页面内容精炼、讲稿口语化：\n\n"
                    f"{json.dumps(_course_package_input(course_package), ensure_ascii=False)}"
                ),
            ),
        ]
        deck = generate_validated_json_stream(
            llm_client,
            messages=messages,
            temperature=agent_temperature("slide_deck", 0.3),
            agent="slide_deck",
            output_model=SlideDeck,
            schema_name="SlideDeck",
        )
        return {
            "course_slides": deck.model_dump(),
            # The graph wrapper/final stage owns the session-level completion status.
            "events": [
                completed_event(
                    "slide_deck",
                    f"generated structured course deck with {len(deck.slides)} slides",
                )
            ],
        }

    return slide_deck_node
