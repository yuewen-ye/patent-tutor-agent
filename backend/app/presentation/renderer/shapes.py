"""Reusable native PowerPoint shape and text primitives."""

from __future__ import annotations

from collections.abc import Iterable

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from backend.app.presentation.renderer.canvas import Canvas
from backend.app.presentation.renderer.text_fit import apply_text_fit, scaled_font_size_to_fit
from backend.app.presentation.renderer.theme import Theme


def color(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def rect(slide, canvas: Canvas, x: float, y: float, w: float, h: float, fill: str, radius: bool = True):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, *canvas.box(x, y, w, h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    shape.line.fill.background()
    return shape


def line(slide, canvas: Canvas, x: float, y: float, w: float, h: float, stroke: str, width: float = 1.5):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *canvas.box(x, y, w, h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(stroke)
    shape.line.fill.background()
    return shape


def text_box(
    slide,
    canvas: Canvas,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    theme: Theme,
    size: float = 18,
    bold: bool = False,
    fill: str | None = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0.04,
    fit_text: bool = True,
):
    box = slide.shapes.add_textbox(*canvas.box(x, y, w, h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    paragraph = tf.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text or ""
    run.font.name = theme.font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color(fill or theme.text)
    if fit_text:
        # Reduce font size when the text is too long for the allocated box.
        apply_text_fit(tf, w - 2 * margin, h - 2 * margin, size)
    return box


def bullets(
    slide,
    canvas: Canvas,
    items: Iterable[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    theme: Theme,
    size: float = 18,
    fit_text: bool = True,
):
    box = slide.shapes.add_textbox(*canvas.box(x, y, w, h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.04)
    items = list(items)
    for index, item in enumerate(items):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        p.space_after = Pt(6)
        p.font.name = theme.font
        p.font.size = Pt(size)
        p.font.color.rgb = color(theme.text)
    if fit_text and items:
        # Estimate the height needed for all bullet paragraphs and shrink if
        # the list overflows the box. We subtract margins and approximate
        # paragraph spacing from the available height.
        available_h = h - 0.08
        longest = max(items, key=len)
        fitted = max(
            9.0,
            min(
                size,
                size
                * (available_h / max(0.3, len(items) * size * 1.35 / 72.0)),
            ),
        )
        # Also constrain by the longest single item fitting horizontally.
        fitted = scaled_font_size_to_fit(longest, w - 0.13, available_h / max(1, len(items)), fitted)
        for paragraph in tf.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(fitted)
    return box
