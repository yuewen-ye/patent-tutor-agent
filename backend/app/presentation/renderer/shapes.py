"""Reusable native PowerPoint shape and text primitives."""

from __future__ import annotations

from collections.abc import Iterable

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from backend.app.presentation.renderer.canvas import Canvas
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
    run.text = text
    run.font.name = theme.font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color(fill or theme.text)
    return box


def bullets(slide, canvas: Canvas, items: Iterable[str], x: float, y: float, w: float, h: float, *, theme: Theme, size: float = 18):
    box = slide.shapes.add_textbox(*canvas.box(x, y, w, h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.04)
    for index, item in enumerate(items):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        p.space_after = Pt(8)
        p.font.name = theme.font
        p.font.size = Pt(size)
        p.font.color.rgb = color(theme.text)
    return box
