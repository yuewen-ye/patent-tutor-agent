"""Brand/style theme packages inspired by ppt-master's layered design model."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.presentation.contracts import PresentationDesign


@dataclass(frozen=True)
class Theme:
    id: str
    background: str
    surface: str
    primary: str
    secondary: str
    accent: str
    warning: str
    success: str
    text: str
    muted: str
    grid: str
    font: str = "Aptos"
    cjk_font: str = "Microsoft YaHei"
    cover_style: str = "bar"
    card_style: str = "rounded"


THEMES: dict[str, Theme] = {
    "patent_exam_classic": Theme("patent_exam_classic", "F6F8FC", "FFFFFF", "123B66", "2F80B7", "20A4A8", "D97706", "198754", "172B4D", "60758A", "DDE7F0", cover_style="bar"),
    "legal_case_analysis": Theme("legal_case_analysis", "F4F7F4", "FFFFFF", "173F35", "397B68", "B77A22", "A63D40", "2E7D5B", "1D302A", "64766F", "DCE8E1", cover_style="split"),
    "technical_blueprint": Theme("technical_blueprint", "EEF5FB", "F9FCFF", "0B3B60", "1677A8", "39A7C7", "E07A2D", "2C8C69", "123047", "557287", "C9E3F1", cover_style="grid", card_style="square"),
    "minimal_academic": Theme("minimal_academic", "FFFFFF", "FAFAF8", "243447", "66788A", "8B5E34", "B45309", "46735B", "263238", "78858C", "E7E7E3", cover_style="minimal", card_style="flat"),
    "practice_workshop": Theme("practice_workshop", "FFF8F0", "FFFFFF", "6B2D16", "C55A2A", "0F8B8D", "C0392B", "2D8A57", "3D241B", "806F65", "F0D8C4", cover_style="split", card_style="rounded"),
    "patent_blue": Theme("patent_blue", "F6F8FC", "FFFFFF", "123B66", "2F80B7", "20A4A8", "D97706", "198754", "172B4D", "60758A", "DDE7F0"),
    "professional_green": Theme("professional_green", "F4F8F5", "FFFFFF", "14532D", "25855A", "0F766E", "B45309", "198754", "19352A", "607568", "D8E8DE"),
    "warm_orange": Theme("warm_orange", "FFF9F3", "FFFFFF", "7C2D12", "C2410C", "D97706", "B91C1C", "2D8A57", "3B2115", "806B5D", "F2DED0"),
}


def theme_for(design: PresentationDesign) -> Theme:
    return THEMES[design.theme]
