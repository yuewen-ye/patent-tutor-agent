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
    "warm_orange": Theme(
        "warm_orange",
        background="FFF7ED",  # 前端渐变底色奶油
        surface="FFFFFF",
        primary="5C3A26",  # 前端主文字深咖棕
        secondary="8B5A3C",  # 前端副标题中棕
        accent="D9773E",  # 前端主橙渐变起点
        warning="B91C1C",
        success="2D8A57",
        text="5C3A26",  # 同 primary，保证正文一致
        muted="9A4A1C",  # 前端 muted 暖深棕
        grid="FFE8D0",  # 前端浅杏底（卡片/分组背景）
        cover_style="split",
        card_style="rounded",
    ),
    "warm_orange_premium": Theme(
        "warm_orange_premium",
        background="7B3F00",  # 深橙棕全幅底
        surface="8B4513",  # 稍浅卡片底
        primary="FFFFFF",  # 白字
        secondary="F5DEB3",  # 小麦色副文字
        accent="FFD700",  # 金色强调
        warning="FF6B6B",
        success="4ADE80",
        text="FFFFFF",
        muted="D2B48C",  # 米色小字
        grid="A0522D",  # 棕褐网格底纹
        cover_style="tabbed",
        card_style="rounded",
    ),
}


def theme_for(design: PresentationDesign) -> Theme:
    return THEMES[design.theme]
