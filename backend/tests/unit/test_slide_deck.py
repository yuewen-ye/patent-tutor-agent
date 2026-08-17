"""Unit tests for the SlideDeck agent node (course_package -> structured slides)."""

from __future__ import annotations

import pytest

from backend.app.agents.slide_deck.node import build_slide_deck_node
from backend.app.core.llm import LLMMessage
from backend.app.schemas.state import SlideDeck

pytestmark = pytest.mark.unit


class FakeSlideDeckLLMClient:
    """Returns a fixed valid SlideDeck payload."""

    def __init__(self, payload: dict | None = None) -> None:
        self.calls: list[str] = []
        self.payload = payload or {
            "slides": [
                {
                    "id": "slide_001",
                    "order": 1,
                    "type": "title",
                    "title": "新颖性入门",
                    "content": {"subtitle": "专利三性之一"},
                    "narration": {"text": "今天我们来学习新颖性。"},
                },
                {
                    "id": "slide_002",
                    "order": 2,
                    "type": "summary",
                    "title": "小结",
                    "content": {"takeaways": ["新颖性=与现有技术不同"]},
                    "narration": {"text": "最后我们总结一下要点。"},
                },
            ],
            "slide_to_block_id": {},
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(agent or "")
        return self.payload

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict,
        agent: str | None = None,
    ) -> object:
        self.calls.append(agent or "")
        return self.payload


def _course_package() -> dict:
    return {
        "expert": "A+B融合",
        "style": "fused",
        "knowledge_points": [{"node_id": "novelty", "kc_name": "新颖性"}],
        "legal_basis": [{"article": "专利法第二十二条", "source": "专利法"}],
        "teaching_content": "新颖性是专利授权的核心条件之一……",
        "irac": {"issue": "何谓新颖性", "rule": "专利法22条", "application": "比对现有技术", "conclusion": "无抵触即新颖"},
    }


def test_slide_deck_builds_from_course_package() -> None:
    client = FakeSlideDeckLLMClient()
    node = build_slide_deck_node(client)

    updates = node({"session_id": "s1", "user_input": "学新颖性", "course_package": _course_package()})

    assert "course_slides" in updates
    deck = SlideDeck.model_validate(updates["course_slides"])
    assert len(deck.slides) == 2
    assert deck.slides[0].type == "title"
    assert deck.slides[0].narration.text
    assert deck.slides[0].narration.audio_url is None  # TTS 未合成前为空
    assert updates["events"]


def test_slide_deck_requires_course_package() -> None:
    client = FakeSlideDeckLLMClient()
    node = build_slide_deck_node(client)
    with pytest.raises(RuntimeError, match="course_package"):
        node({"session_id": "s1", "user_input": "x"})
