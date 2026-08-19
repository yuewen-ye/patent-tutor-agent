"""Presentation theme tokens inspired by PPT Master style/brand separation."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.presentation.contracts import PresentationDesign


@dataclass(frozen=True)
class Theme:
    background: str
    surface: str
    primary: str
    secondary: str
    accent: str
    warning: str
    text: str
    muted: str
    font: str = "Aptos"
    cjk_font: str = "Microsoft YaHei"


def theme_for(design: PresentationDesign) -> Theme:
    palettes = {
        "patent_blue": Theme("F6F8FC", "FFFFFF", "123B66", "2F80B7", "20A4A8", "D97706", "172B4D", "60758A"),
        "professional_green": Theme("F4F8F5", "FFFFFF", "14532D", "25855A", "0F766E", "B45309", "19352A", "607568"),
        "warm_orange": Theme("FFF9F3", "FFFFFF", "7C2D12", "C2410C", "D97706", "B91C1C", "3B2115", "806B5D"),
    }
    return palettes[design.theme]
