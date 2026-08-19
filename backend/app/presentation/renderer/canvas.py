"""16:9 canvas and safe-area geometry."""

from __future__ import annotations

from dataclasses import dataclass

from pptx.util import Inches


@dataclass(frozen=True)
class Canvas:
    width: float = 13.333
    height: float = 7.5
    margin_x: float = 0.62
    margin_top: float = 0.48
    margin_bottom: float = 0.42

    @property
    def content_width(self) -> float:
        return self.width - 2 * self.margin_x

    @property
    def content_height(self) -> float:
        return self.height - self.margin_top - self.margin_bottom

    def box(self, x: float, y: float, width: float, height: float) -> tuple[int, int, int, int]:
        return tuple(Inches(value) for value in (x, y, width, height))  # type: ignore[return-value]
