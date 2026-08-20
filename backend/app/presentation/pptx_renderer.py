"""High-quality native PPTX renderer.

The renderer follows the PPT Master separation of validated design data, reusable theme/layout
primitives, and delivery validation. It deliberately emits native editable PowerPoint shapes.
"""

from __future__ import annotations

from backend.app.presentation.contracts import PresentationDesign
from backend.app.presentation.renderer import render_design


def render_pptx(design: PresentationDesign) -> bytes:
    return render_design(design)
