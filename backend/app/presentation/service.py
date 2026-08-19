"""LLM-designed, deterministically rendered complete PowerPoint artifacts."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from pptx import Presentation

from backend.app.agents.common import generate_validated_json, load_prompt
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.presentation.contracts import (
    PresentationArtifact,
    PresentationCoursePackage,
    PresentationDesign,
    PresentationResult,
    PresentationSlide,
    PresentationSource,
)
from backend.app.presentation.pptx_renderer import render_pptx

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_PRESENTATION_SYSTEM = load_prompt(__file__)


def build_presentation_source(
    course_package: dict[str, Any], course_slides: dict[str, Any]
) -> PresentationSource:
    slides: list[PresentationSlide] = []
    mapping = course_slides.get("slide_to_block_id") or {}
    for item in course_slides.get("slides") or []:
        if not isinstance(item, dict):
            continue
        narration = item.get("narration") or {}
        slide_id = str(item.get("id") or f"slide_{len(slides) + 1:03d}")
        slides.append(
            PresentationSlide(
                id=slide_id,
                order=int(item.get("order") or len(slides) + 1),
                type=str(item.get("type") or "bullet"),
                title=str(item.get("title") or ""),
                content=item.get("content") if isinstance(item.get("content"), dict) else {},
                narration=str(narration.get("text") or ""),
                source_block_id=str(mapping[slide_id]) if mapping.get(slide_id) else None,
            )
        )
    if not slides:
        raise ValueError("course_slides contains no slides")
    package = PresentationCoursePackage(
        title=str(course_package.get("title")) if course_package.get("title") else None,
        teaching_content=(
            str(course_package.get("teaching_content"))
            if course_package.get("teaching_content")
            else None
        ),
        legal_basis=(course_package.get("legal_basis") if isinstance(course_package.get("legal_basis"), list) else []),
        block_plan=(course_package.get("block_plan") if isinstance(course_package.get("block_plan"), dict) else None),
        assessment=(course_package.get("assessment") if isinstance(course_package.get("assessment"), dict) else None),
    )
    return PresentationSource(course_package=package, slides=slides)


def _validate_design(design: PresentationDesign, source: PresentationSource) -> PresentationDesign:
    expected = [(slide.id, slide.order) for slide in source.slides]
    actual = [(slide.id, slide.order) for slide in design.slides]
    if actual != expected:
        raise ValueError("PresentationDesign must preserve every source slide id and order")
    return design


def _validate_pptx(content: bytes, design: PresentationDesign) -> None:
    """Run package, Office parser, editable-shape and notes delivery checks."""
    if not content or not content.startswith(b"PK"):
        raise ValueError("renderer did not return a PPTX zip package")
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            required = {"[Content_Types].xml", "ppt/presentation.xml", "ppt/theme/theme1.xml"}
            if not required.issubset(names):
                raise ValueError("renderer returned an incomplete PPTX package")
            notes = {name for name in names if name.startswith("ppt/notesSlides/notesSlide")}
            if len(notes) != len(design.slides):
                raise ValueError("renderer did not emit speaker notes for every slide")
    except BadZipFile as exc:
        raise ValueError("renderer returned an invalid PPTX zip package") from exc
    presentation = Presentation(BytesIO(content))
    if len(presentation.slides) != len(design.slides):
        raise ValueError("renderer output slide count differs from PresentationDesign")
    for source, rendered in zip(design.slides, presentation.slides, strict=True):
        text = " ".join(shape.text for shape in rendered.shapes if hasattr(shape, "text"))
        if source.title not in text:
            raise ValueError(f"renderer lost title for slide {source.id}")
        if not rendered.shapes:
            raise ValueError(f"renderer emitted no editable shapes for slide {source.id}")
        if source.speaker_notes not in rendered.notes_slide.notes_text_frame.text:
            raise ValueError(f"renderer lost speaker notes for slide {source.id}")


def generate_presentation_artifact(
    *,
    artifact_root: Path,
    session_id: str,
    course_package: dict[str, Any],
    course_slides: dict[str, Any],
    llm_client: LLMClient,
) -> dict[str, Any]:
    source = build_presentation_source(course_package, course_slides)
    messages = [
        LLMMessage(role="system", content=_PRESENTATION_SYSTEM),
        LLMMessage(
            role="user",
            content="请基于下列权威素材设计完整 PowerPoint：\n"
            + json.dumps(source.model_dump(), ensure_ascii=False, separators=(",", ":")),
        ),
    ]
    design = generate_validated_json(
        llm_client,
        messages=messages,
        temperature=agent_temperature("generate_pptx", 0.2),
        agent="generate_pptx",
        output_model=PresentationDesign,
        schema_name="PresentationDesign",
    )
    _validate_design(design, source)
    content = render_pptx(design)
    _validate_pptx(content, design)
    safe_session = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_id)
    safe_session = safe_session.strip("-_") or "session"
    target_dir = artifact_root / "sessions" / safe_session / "presentation"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "course_deck.pptx"
    with tempfile.NamedTemporaryFile(
        dir=target_dir, prefix=".course_deck-", suffix=".tmp", delete=False
    ) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    temp_path.replace(target)
    artifact = PresentationArtifact(
        artifact_id=f"{safe_session}-course-deck",
        path=f"artifacts/sessions/{safe_session}/presentation/course_deck.pptx",
        title="完整课程 PowerPoint",
        mime_type=PPTX_MIME,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        created_at=datetime.now(UTC).isoformat(),
    )
    (target_dir / "pptx_manifest.json").write_text(
        json.dumps(
            {
                "artifact": artifact.model_dump(),
                "source_slide_count": len(source.slides),
                "design_theme": design.theme,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return PresentationResult(
        status="generated",
        provider="configured_llm",
        source_slide_count=len(source.slides),
        speaker_notes_status="written",
        artifact=artifact,
    ).model_dump()
