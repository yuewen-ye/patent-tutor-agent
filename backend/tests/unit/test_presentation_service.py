"""Offline PPTX presentation generation tests."""

from __future__ import annotations

from zipfile import ZipFile

import pytest

from backend.app.presentation.service import (
    build_presentation_source,
    generate_presentation_artifact,
)

pytestmark = pytest.mark.unit


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


def test_mock_presentation_writes_valid_pptx_with_notes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PATENT_TUTOR_PPTX_PROVIDER", "mock")

    result = generate_presentation_artifact(
        artifact_root=tmp_path,
        session_id="session-1",
        course_package=_course_package(),
        course_slides=_course_slides(),
    )

    assert result["status"] == "generated"
    assert result["speaker_notes_status"] == "written"
    artifact = result["artifact"]
    assert artifact is not None
    path = tmp_path / "sessions/session-1/presentation/course_deck.pptx"
    with ZipFile(path) as pptx:
        assert "ppt/presentation.xml" in pptx.namelist()
        assert "ppt/notesSlides/notesSlide1.xml" in pptx.namelist()


def test_unknown_provider_degrades_without_writing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PATENT_TUTOR_PPTX_PROVIDER", "future-vendor")

    result = generate_presentation_artifact(
        artifact_root=tmp_path,
        session_id="session-1",
        course_package=_course_package(),
        course_slides=_course_slides(),
    )

    assert result["status"] == "degraded"
    assert result["artifact"] is None
