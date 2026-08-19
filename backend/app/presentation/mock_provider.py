"""Offline mock presentation provider used before a real vendor is configured."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from backend.app.presentation.contracts import PresentationSource


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_mock_pptx(source: PresentationSource) -> bytes:
    """Create a small valid OOXML package with slide text and speaker notes."""
    slides = []
    notes = []
    rels = []
    for index, slide in enumerate(source.slides, start=1):
        text = "\n".join(
            [slide.title, *[str(value) for value in slide.content.values()], slide.narration]
        )
        slides.append(
            f'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            f'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            f'<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{_xml(text)}</a:t>'
            f'</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
        )
        notes.append(
            f'<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            f'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            f'<p:notes><a:p><a:r><a:t>{_xml(slide.narration)}</a:t></a:r></a:p></p:notes>'
        )
        rels.append(f"<Relationship Id=\"rId{index}\" Target=\"slides/slide{index}.xml\"/>")

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")
        archive.writestr("ppt/presentation.xml", "<p:presentation xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"/>")
        archive.writestr("ppt/slides/_rels/slides.xml.rels", "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">" + "".join(rels) + "</Relationships>")
        for index, slide_xml in enumerate(slides, start=1):
            archive.writestr(f"ppt/slides/slide{index}.xml", slide_xml)
            archive.writestr(f"ppt/notesSlides/notesSlide{index}.xml", notes[index - 1])
    return buffer.getvalue()
