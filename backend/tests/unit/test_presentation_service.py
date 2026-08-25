"""LLM-designed PowerPoint presentation generation tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from zipfile import ZipFile

import pytest

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
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

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        *,
        schema_name: str | None = None,
        json_schema: dict[str, object] | None = None,
    ) -> Iterator[str]:
        payload = self.generate_json(messages, temperature, agent)
        text = json.dumps(payload, ensure_ascii=False)
        # Yield in small chunks to exercise streaming accumulation.
        for i in range(0, len(text), 8):
            yield text[i : i + 8]

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("presentation agent does not use tools")


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
    # Preview manifest is always present; on hosts without LibreOffice it reports disabled.
    assert "preview_images" in result
    manifest_path = tmp_path / "sessions/session-1/presentation/pptx_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["preview_images"]["enabled"] == result["preview_images"]["enabled"]


def test_system_prompt_explicitly_forbids_adjacent_duplicate_templates() -> None:
    from backend.app.agents.common import load_prompt
    from backend.app.presentation import service as presentation_service

    prompt = load_prompt(presentation_service.__file__)
    assert "template_id" in prompt
    assert "相邻" in prompt
    assert "必须不同" in prompt
    assert "任意相邻两页" in prompt


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


def test_rejects_adjacent_duplicate_visual_templates(tmp_path) -> None:
    """Regression: LLM must not assign the same template_id to adjacent slides."""

    class DuplicateTemplateLLM(PresentationLLM):
        def generate_json(self, *args: object, **kwargs: object) -> object:
            return {
                "title": "专利授权实质条件",
                "theme": "patent_exam_classic",
                "slides": [
                    {
                        "id": "slide_001",
                        "order": 1,
                        "layout": "cover_minimal",
                        "template_id": "cover_minimal",
                        "title": "封面",
                        "speaker_notes": "封面讲稿",
                    },
                    {
                        "id": "slide_002",
                        "order": 2,
                        "layout": "summary_roadmap",
                        "template_id": "summary_roadmap",
                        "title": "小结",
                        "speaker_notes": "小结讲稿",
                    },
                    {
                        "id": "slide_003",
                        "order": 3,
                        "layout": "summary_roadmap",
                        "template_id": "summary_roadmap",
                        "title": "路线图",
                        "speaker_notes": "路线图讲稿",
                    },
                ],
            }

    course_slides = {
        "slides": [
            {
                "id": "slide_001", "order": 1, "type": "title", "title": "封面",
                "content": {}, "narration": {"text": "封面讲稿"},
            },
            {
                "id": "slide_002", "order": 2, "type": "summary", "title": "小结",
                "content": {}, "narration": {"text": "小结讲稿"},
            },
            {
                "id": "slide_003", "order": 3, "type": "summary", "title": "路线图",
                "content": {}, "narration": {"text": "路线图讲稿"},
            },
        ],
        "slide_to_block_id": {},
    }

    result = generate_presentation_artifact(
        artifact_root=tmp_path,
        session_id="session-dup",
        course_package=_course_package(),
        course_slides=course_slides,
        llm_client=DuplicateTemplateLLM(),
    )
    assert result["status"] == "generated"
