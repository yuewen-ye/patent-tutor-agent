"""Presentation generation service with an offline provider until vendor details exist."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from backend.app.presentation.contracts import (
    PresentationArtifact,
    PresentationCoursePackage,
    PresentationResult,
    PresentationSlide,
    PresentationSource,
)
from backend.app.presentation.mock_provider import generate_mock_pptx

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def build_presentation_source(course_package: dict[str, Any], course_slides: dict[str, Any]) -> PresentationSource:
    slides = []
    mapping = course_slides.get("slide_to_block_id") or {}
    for item in course_slides.get("slides") or []:
        if not isinstance(item, dict):
            continue
        narration = item.get("narration") or {}
        slides.append(
            PresentationSlide(
                id=str(item.get("id") or "slide"),
                order=int(item.get("order") or len(slides) + 1),
                type=str(item.get("type") or "bullet"),
                title=str(item.get("title") or ""),
                content=item.get("content") if isinstance(item.get("content"), dict) else {},
                narration=str(narration.get("text") or ""),
                source_block_id=str(mapping.get(item.get("id"))) if mapping.get(item.get("id")) else None,
            )
        )
    if not slides:
        raise ValueError("course_slides contains no slides")
    package = PresentationCoursePackage(
        title=str(course_package.get("title")) if course_package.get("title") else None,
        teaching_content=str(course_package.get("teaching_content")) if course_package.get("teaching_content") else None,
        legal_basis=course_package.get("legal_basis") if isinstance(course_package.get("legal_basis"), list) else [],
        block_plan=course_package.get("block_plan") if isinstance(course_package.get("block_plan"), dict) else None,
        assessment=course_package.get("assessment") if isinstance(course_package.get("assessment"), dict) else None,
    )
    return PresentationSource(course_package=package, slides=slides)


def _validate_pptx(content: bytes) -> None:
    if not content or not content.startswith(b"PK"):
        raise ValueError("provider did not return a PPTX zip package")
    try:
        with ZipFile(__import__("io").BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
                raise ValueError("provider returned an incomplete PPTX package")
    except BadZipFile as exc:
        raise ValueError("provider returned an invalid PPTX zip package") from exc


def generate_presentation_artifact(
    *, artifact_root: Path, session_id: str, course_package: dict[str, Any], course_slides: dict[str, Any]
) -> dict[str, Any]:
    source = build_presentation_source(course_package, course_slides)
    provider = os.getenv("PATENT_TUTOR_PPTX_PROVIDER", "mock").strip().lower() or "mock"
    if provider != "mock":
        return PresentationResult(
            status="degraded", provider=provider, source_slide_count=len(source.slides),
            speaker_notes_status="unknown", error_summary="PPTX provider adapter is not configured yet.",
        ).model_dump()
    content = generate_mock_pptx(source)
    _validate_pptx(content)
    safe_session = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_id).strip("-_") or "session"
    target_dir = artifact_root / "sessions" / safe_session / "presentation"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "course_deck.pptx"
    with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".course_deck-", suffix=".tmp", delete=False) as tmp:
        tmp.write(content)
        temp_path = Path(tmp.name)
    temp_path.replace(target)
    digest = hashlib.sha256(content).hexdigest()
    created_at = datetime.now(UTC).isoformat()
    artifact = PresentationArtifact(
        artifact_id=f"{safe_session}-course-deck",
        path=f"artifacts/sessions/{safe_session}/presentation/course_deck.pptx",
        title="完整课程 PowerPoint",
        mime_type=PPTX_MIME,
        sha256=digest,
        size_bytes=len(content),
        created_at=created_at,
    )
    (target_dir / "pptx_manifest.json").write_text(
        json.dumps({"artifact": artifact.model_dump(), "provider": provider, "source_slide_count": len(source.slides)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return PresentationResult(
        status="generated", provider=provider, source_slide_count=len(source.slides),
        speaker_notes_status="written", artifact=artifact,
    ).model_dump()
