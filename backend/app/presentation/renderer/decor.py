"""Deterministic decorative layer for varied, non-empty slide compositions."""

from __future__ import annotations

from backend.app.presentation.renderer.canvas import Canvas
from backend.app.presentation.renderer.shapes import line, rect, text_box
from backend.app.presentation.renderer.theme import Theme


def apply_decor(slide, canvas: Canvas, theme: Theme, page: int, *, section: str | None = None) -> None:
    """Add restrained brand geometry, page marker, and visual rhythm."""
    if theme.id == "technical_blueprint":
        for x in range(14):
            line(slide, canvas, x, 0, 0.008, canvas.height, theme.grid, 0)
        for y in range(8):
            line(slide, canvas, 0, y, canvas.width, 0.008, theme.grid, 0)
    elif theme.id == "minimal_academic":
        line(slide, canvas, canvas.margin_x, 7.02, canvas.content_width, 0.02, theme.grid, 0)
    else:
        rect(slide, canvas, 12.78, 0, 0.55, 0.12, theme.accent, radius=False)
        rect(slide, canvas, 12.98, 0.12, 0.35, 0.08, theme.secondary, radius=False)
    if section:
        text_box(slide, canvas, section.upper(), canvas.margin_x, 6.92, 3.5, 0.2, theme=theme, size=8, fill=theme.muted)
    text_box(slide, canvas, f"{page:02d}", 12.2, 6.88, 0.55, 0.2, theme=theme, size=8, fill=theme.muted)


def add_callout(slide, canvas: Canvas, theme: Theme, title: str, text: str, x: float, y: float, w: float, h: float, *, warning: bool = False) -> None:
    accent = theme.warning if warning else theme.accent
    rect(slide, canvas, x, y, w, h, theme.surface)
    line(slide, canvas, x, y, 0.1, h, accent, 0)
    text_box(slide, canvas, title, x + 0.25, y + 0.18, w - 0.5, 0.28, theme=theme, size=13, bold=True, fill=accent)
    text_box(slide, canvas, text, x + 0.25, y + 0.58, w - 0.5, h - 0.75, theme=theme, size=14)
