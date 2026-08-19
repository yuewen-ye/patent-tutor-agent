"""Deterministic layout templates made from native editable PPT primitives."""

from __future__ import annotations

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

from backend.app.presentation.contracts import PresentationVisualSlide
from backend.app.presentation.renderer.canvas import Canvas
from backend.app.presentation.renderer.shapes import bullets, color, line, rect, text_box
from backend.app.presentation.renderer.theme import Theme


def _header(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    line(slide, canvas, canvas.margin_x, 0.34, 0.72, 0.07, theme.accent)
    text_box(slide, canvas, item.title, canvas.margin_x, 0.48, 11.4, 0.48, theme=theme, size=27, bold=True)
    text_box(slide, canvas, f"{page:02d}", 12.05, 0.5, 0.55, 0.3, theme=theme, size=10, fill=theme.muted, align=PP_ALIGN.RIGHT)


def render_title(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.primary, radius=False)
    rect(slide, canvas, 0.72, 1.05, 0.12, 4.85, theme.accent, radius=False)
    text_box(slide, canvas, item.title, 1.15, 1.55, 10.8, 1.5, theme=theme, size=38, bold=True, fill="FFFFFF")
    text_box(slide, canvas, item.subtitle or item.body or "个性化专利学习课件", 1.18, 3.35, 9.4, 0.7, theme=theme, size=19, fill="D9E8F4")
    if item.bullets:
        bullets(slide, canvas, item.bullets[:3], 1.18, 4.35, 7.4, 1.2, theme=Theme(**{**theme.__dict__, "text": "FFFFFF"}), size=16)
    text_box(slide, canvas, f"PATENT TUTOR · {page:02d}", 1.18, 6.55, 5, 0.28, theme=theme, size=10, fill="D9E8F4")


def render_content(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    _header(slide, canvas, item, theme, page)
    if item.body:
        rect(slide, canvas, canvas.margin_x, 1.22, canvas.content_width, 0.88, "EAF1F8")
        text_box(slide, canvas, item.body, 0.86, 1.39, 11.6, 0.5, theme=theme, size=18)
    bullets(slide, canvas, item.bullets[:6] or item.steps[:6], 0.86, 2.35, 11.35, 3.9, theme=theme, size=20)


def _column(slide, canvas: Canvas, title: str, items: list[str], x: float, theme: Theme, accent: str) -> None:
    rect(slide, canvas, x, 1.34, 5.78, 4.95, theme.surface)
    line(slide, canvas, x, 1.34, 5.78, 0.1, accent,)
    text_box(slide, canvas, title, x + 0.28, 1.62, 5.1, 0.4, theme=theme, size=19, bold=True, fill=accent)
    bullets(slide, canvas, items[:6], x + 0.24, 2.2, 5.2, 3.7, theme=theme, size=16)


def render_two_column(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    _header(slide, canvas, item, theme, page)
    _column(slide, canvas, item.left_title or "要点", item.left_items or item.bullets, 0.72, theme, theme.primary)
    _column(slide, canvas, item.right_title or "说明", item.right_items or item.steps, 6.84, theme, theme.accent)


def render_process(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    _header(slide, canvas, item, theme, page)
    steps = item.steps[:5] or item.bullets[:5]
    count = max(1, len(steps))
    width = min(2.15, 11.3 / count)
    gap = (11.3 - width * count) / max(1, count - 1)
    for index, step in enumerate(steps):
        x = 0.98 + index * (width + gap)
        rect(slide, canvas, x, 2.55, width, 1.45, theme.surface)
        rect(slide, canvas, x + 0.14, 2.35, 0.48, 0.48, theme.accent)
        text_box(slide, canvas, str(index + 1), x + 0.14, 2.43, 0.48, 0.25, theme=theme, size=13, bold=True, fill="FFFFFF", align=PP_ALIGN.CENTER)
        text_box(slide, canvas, step, x + 0.18, 2.98, width - 0.35, 0.75, theme=theme, size=15, bold=True, align=PP_ALIGN.CENTER)
        if index + 1 < count:
            connector = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + width), Inches(3.27), Inches(x + width + gap), Inches(3.27))
            connector.line.color.rgb = color(theme.accent)
            connector.line.width = Inches(0.025)


def render_summary(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    _header(slide, canvas, item, theme, page)
    takeaways = item.bullets[:5] or item.steps[:5]
    for index, takeaway in enumerate(takeaways):
        y = 1.35 + index * 0.9
        rect(slide, canvas, 0.86, y, 11.5, 0.64, "EAF1F8")
        rect(slide, canvas, 1.02, y + 0.12, 0.38, 0.38, theme.accent)
        text_box(slide, canvas, str(index + 1), 1.02, y + 0.17, 0.38, 0.18, theme=theme, size=10, bold=True, fill="FFFFFF", align=PP_ALIGN.CENTER)
        text_box(slide, canvas, takeaway, 1.62, y + 0.15, 10.3, 0.32, theme=theme, size=17)


def render_slide(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    handlers = {
        "title": render_title,
        "content": render_content,
        "two_column": render_two_column,
        "comparison": render_two_column,
        "process": render_process,
        "summary": render_summary,
    }
    handlers[item.layout](slide, canvas, item, theme, page)
