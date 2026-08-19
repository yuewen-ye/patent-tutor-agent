"""Deterministic OOXML rendering for the LLM-authored presentation design."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from backend.app.presentation.contracts import PresentationDesign, PresentationVisualSlide


def _xml(value: str) -> str:
    return (
        str(value).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
    )


def _text(slide: PresentationVisualSlide) -> str:
    parts = [slide.title]
    for value in (slide.subtitle, slide.body, slide.left_title, slide.right_title):
        if value:
            parts.append(value)
    parts.extend(slide.bullets)
    parts.extend(slide.steps)
    parts.extend(slide.left_items)
    parts.extend(slide.right_items)
    return "\n".join(parts)


def render_pptx(design: PresentationDesign) -> bytes:
    """Render a valid, editable OOXML package with slide text and speaker notes."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>",
        )
        archive.writestr(
            "ppt/presentation.xml",
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )
        for index, slide in enumerate(design.slides, start=1):
            text = _xml(_text(slide))
            notes = _xml(slide.speaker_notes)
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t>"
                "</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>",
            )
            archive.writestr(
                f"ppt/notesSlides/notesSlide{index}.xml",
                '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                f"<p:notes><a:p><a:r><a:t>{notes}</a:t></a:r></a:p></p:notes>",
            )
    return buffer.getvalue()
