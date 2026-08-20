"""Reusable PPT Master-inspired layout registry and patent teaching templates."""

from __future__ import annotations

from pptx.enum.text import PP_ALIGN

from backend.app.presentation.contracts import PresentationVisualSlide
from backend.app.presentation.renderer.canvas import Canvas
from backend.app.presentation.renderer.components import (
    comparison_matrix,
    exam_question_card,
    irac_flow,
    legal_citation_card,
    patent_timeline,
)
from backend.app.presentation.renderer.decor import apply_decor
from backend.app.presentation.renderer.semantic import render_element
from backend.app.presentation.renderer.shapes import bullets, line, rect, text_box
from backend.app.presentation.renderer.theme import Theme


def header(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    line(slide, canvas, canvas.margin_x, 0.34, 0.72, 0.07, theme.accent)
    text_box(slide, canvas, item.title, canvas.margin_x, 0.48, 11.4, 0.48, theme=theme, size=27, bold=True)
    text_box(slide, canvas, f"{page:02d}", 12.05, 0.5, 0.55, 0.3, theme=theme, size=10, fill=theme.muted, align=PP_ALIGN.RIGHT)
    apply_decor(slide, canvas, theme, page)


def cover(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    if theme.cover_style == "minimal":
        text_box(slide, canvas, item.title, 1.0, 2.0, 11.0, 1.1, theme=theme, size=40, bold=True, align=PP_ALIGN.CENTER)
        line(slide, canvas, 4.2, 3.35, 4.9, 0.06, theme.accent)
        text_box(slide, canvas, item.subtitle or item.body or "专利学习课件", 2.0, 3.7, 9.3, 0.6, theme=theme, size=19, fill=theme.muted, align=PP_ALIGN.CENTER)
    else:
        rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.primary, radius=False)
        if theme.cover_style == "grid":
            for x in range(14):
                line(slide, canvas, x, 0, 0.01, canvas.height, theme.secondary, 0)
            for y in range(8):
                line(slide, canvas, 0, y, canvas.width, 0.01, theme.secondary, 0)
        if theme.cover_style == "split":
            rect(slide, canvas, 8.8, 0, 4.6, canvas.height, theme.secondary, radius=False)
        rect(slide, canvas, 0.72, 1.05, 0.12, 4.85, theme.accent, radius=False)
        text_box(slide, canvas, item.title, 1.15, 1.55, 10.8, 1.5, theme=theme, size=38, bold=True, fill="FFFFFF")
        text_box(slide, canvas, item.subtitle or item.body or "个性化专利学习课件", 1.18, 3.35, 9.4, 0.7, theme=theme, size=19, fill="D9E8F4")
        if item.bullets:
            bullets(slide, canvas, item.bullets[:3], 1.18, 4.35, 7.4, 1.2, theme=Theme(**{**theme.__dict__, "text": "FFFFFF"}), size=16)
    text_box(slide, canvas, f"PATENT TUTOR · {page:02d}", 1.18, 6.55, 5, 0.28, theme=theme, size=10, fill="D9E8F4" if theme.cover_style != "minimal" else theme.muted)


def content(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    if item.body:
        rect(slide, canvas, canvas.margin_x, 1.22, canvas.content_width, 0.88, theme.grid)
        text_box(slide, canvas, item.body, 0.86, 1.39, 11.6, 0.5, theme=theme, size=18)
    bullets(slide, canvas, item.bullets[:6] or item.steps[:6], 0.86, 2.35, 11.35, 3.9, theme=theme, size=20)


def two_column(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    for x, title, items, accent in [(0.72, item.left_title or "要点", item.left_items or item.bullets, theme.primary), (6.84, item.right_title or "说明", item.right_items or item.steps, theme.accent)]:
        rect(slide, canvas, x, 1.34, 5.78, 4.95, theme.surface, radius=theme.card_style != "square")
        line(slide, canvas, x, 1.34, 5.78, 0.1, accent)
        text_box(slide, canvas, title, x + 0.28, 1.62, 5.1, 0.4, theme=theme, size=19, bold=True, fill=accent)
        bullets(slide, canvas, items[:6], x + 0.24, 2.2, 5.2, 3.7, theme=theme, size=16)


def process(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    steps = item.steps[:5] or item.bullets[:5]
    patent_timeline(slide, canvas, theme, steps, 0.85, 2.0, 11.6)


def summary(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    for index, takeaway in enumerate(item.bullets[:5] or item.steps[:5]):
        y = 1.35 + index * 0.9
        rect(slide, canvas, 0.86, y, 11.5, 0.64, theme.grid)
        rect(slide, canvas, 1.02, y + 0.12, 0.38, 0.38, theme.accent)
        text_box(slide, canvas, str(index + 1), 1.02, y + 0.17, 0.38, 0.18, theme=theme, size=10, bold=True, fill="FFFFFF", align=PP_ALIGN.CENTER)
        text_box(slide, canvas, takeaway, 1.62, y + 0.15, 10.3, 0.32, theme=theme, size=17)


def rule_card(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    meaning = item.right_title or (item.right_items[0] if item.right_items else None)
    legal_citation_card(
        slide,
        canvas,
        theme,
        0.82,
        1.55,
        5.15,
        4.5,
        item.legal_reference or item.left_title or "法律依据",
        item.legal_summary or item.body or "请基于课程权威内容理解本页规则。",
        meaning,
    )
    rect(slide, canvas, 6.35, 1.55, 5.95, 4.5, theme.surface)
    text_box(slide, canvas, "记忆要点", 6.7, 1.9, 5.2, 0.35, theme=theme, size=18, bold=True, fill=theme.primary)
    bullets(slide, canvas, item.bullets[:5], 6.6, 2.45, 5.2, 2.8, theme=theme, size=16)
    if item.warning:
        text_box(slide, canvas, f"注意：{item.warning}", 6.7, 5.5, 5.1, 0.3, theme=theme, size=12, fill=theme.warning)


def irac(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    irac_flow(slide, canvas, theme, [("Issue", item.issue or item.left_title or "争点"), ("Rule", item.rule or item.body or "规则"), ("Application", item.application or (item.left_items[0] if item.left_items else "适用")), ("Conclusion", item.conclusion or (item.right_items[0] if item.right_items else "结论"))], 0.72, 1.85, 11.9, 3.35)


def matrix(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    rows = list(zip(item.left_items, item.right_items, strict=False)) or [(item.body or "方案要素", "对比对象")]
    comparison_matrix(slide, canvas, theme, item.left_title or "权利要求/方案", item.right_title or "现有技术", rows[:5], 0.8, 1.55, 11.7, 4.7)


def checklist(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    header(slide, canvas, item, theme, page)
    exam_question_card(slide, canvas, theme, item.body or item.subtitle or item.title, item.bullets or item.steps, item.warning, 1.1, 1.45, 11.1, 4.9)


def render_slide(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    template = item.template_id or item.layout
    handlers = {
        "title": cover, "cover_minimal": cover, "cover_split": cover,
        "content": content, "content_bullet_grid": content,
        "content_rule_card": rule_card, "legal_citation_focus": rule_card,
        "two_column": two_column, "case_analysis_split": two_column, "comparison": matrix, "comparison_matrix": matrix,
        "process": process, "timeline_process": process, "irac_flow": irac,
        "exam_checklist": checklist, "summary": summary, "summary_roadmap": summary,
        "hero_statement": cover, "evidence_stack": content, "decision_tree": process, "concept_map": two_column,
    }
    handlers.get(template, content)(slide, canvas, item, theme, page)
    if item.visual_elements:
        for index, element in enumerate(item.visual_elements[:2]):
            render_element(slide, canvas, theme, element, 0.85 + (index % 2) * 6.0, 5.35, 5.55, 1.25)
