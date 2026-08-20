"""LLM-designed PowerPoint presentation generation tests."""

from __future__ import annotations

from zipfile import ZipFile

import pytest

from backend.app.core.llm import LLMMessage
from backend.app.presentation.service import (
    build_presentation_source,
    generate_presentation_artifact,
)

pytestmark = pytest.mark.unit


class PresentationLLM:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(agent)
        return {
            "title": "新颖性入门",
            "theme": "patent_blue",
            "slides": [
                {
                    "id": "slide_001",
                    "order": 1,
                    "layout": "title",
                    "title": "新颖性入门",
                    "subtitle": "专利三性之一",
                    "speaker_notes": "今天学习专利新颖性。",
                }
            ],
        }

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict,
        agent: str | None = None,
    ) -> object:
        return self.generate_json(messages, temperature, agent)


def _course_package() -> dict:
    return {
        "title": "新颖性入门",
        "teaching_content": "新颖性要求技术方案未被现有技术公开。",
        "legal_basis": [{"article": "专利法第二十二条", "source": "专利法"}],
        "block_plan": {"blocks": [{"block_id": "rule", "title": "规则"}]},
    }


def _course_slides() -> dict:
    return {
        "slides": [
            {
                "id": "slide_001", "order": 1, "type": "title", "title": "新颖性入门",
                "content": {"subtitle": "专利三性之一"},
                "narration": {"text": "今天学习专利新颖性。"},
            }
        ],
        "slide_to_block_id": {"slide_001": "rule"},
    }


def test_presentation_source_includes_course_package_and_slides() -> None:
    source = build_presentation_source(_course_package(), _course_slides())

    assert source.course_package.teaching_content
    assert source.course_package.legal_basis
    assert source.slides[0].source_block_id == "rule"
    assert source.slides[0].narration == "今天学习专利新颖性。"


def test_llm_presentation_writes_valid_pptx_with_notes(tmp_path) -> None:
    llm = PresentationLLM()
    result = generate_presentation_artifact(
        artifact_root=tmp_path,
        session_id="session-1",
        course_package=_course_package(),
        course_slides=_course_slides(),
        llm_client=llm,
    )

    assert llm.calls == ["generate_pptx"]
    assert result["status"] == "generated"
    assert result["speaker_notes_status"] == "written"
    path = tmp_path / "sessions/session-1/presentation/course_deck.pptx"
    with ZipFile(path) as pptx:
        assert "ppt/presentation.xml" in pptx.namelist()
        assert "ppt/notesSlides/notesSlide1.xml" in pptx.namelist()


def test_rejects_llm_design_that_changes_source_slide_order(tmp_path) -> None:
    class InvalidPresentationLLM(PresentationLLM):
        def generate_json(self, *args: object, **kwargs: object) -> object:
            return {"title": "错误", "slides": []}

    with pytest.raises(ValueError):
        generate_presentation_artifact(
            artifact_root=tmp_path,
            session_id="session-1",
            course_package=_course_package(),
            course_slides=_course_slides(),
            llm_client=InvalidPresentationLLM(),
        )
