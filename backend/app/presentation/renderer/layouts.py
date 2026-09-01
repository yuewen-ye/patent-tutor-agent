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
from backend.app.presentation.renderer.effects import maybe_render_visual_effects
from backend.app.presentation.renderer.semantic import render_element
from backend.app.presentation.renderer.shapes import bullets, line, rect, text_box
from backend.app.presentation.renderer.theme import Theme


def _premium_tab_header(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 深色主题 tab 导航头：顶部 tab 条 + 当前页高亮。"""
    tab_labels = item.tabs or ["项目背景", "产品介绍", "商业模式", "团队介绍", "未来规划"]
    current_tab = item.current_tab or item.title or tab_labels[0]
    # 顶部 tab 条背景
    rect(slide, canvas, 0, 0, canvas.width, 0.55, "#5C3A26", radius=False)
    # 左侧 logo/品牌区
    rect(slide, canvas, 0.3, 0.1, 1.8, 0.35, theme.accent, radius=False)
    text_box(slide, canvas, "PATENT TUTOR", 0.35, 0.12, 1.7, 0.3, theme=theme, size=9, bold=True, fill=theme.primary)
    # Tab 渲染
    _tab_x = 2.3
    for label in tab_labels[:6]:
        _w = max(1.4, len(label) * 0.22 + 0.3)
        _is_active = label == current_tab
        if _is_active:
            rect(slide, canvas, _tab_x, 0.05, _w, 0.45, theme.accent, radius=False)
        text_box(slide, canvas, label, _tab_x, 0.12, _w, 0.3, theme=theme, size=11, bold=_is_active, fill=theme.primary if _is_active else theme.muted, align=PP_ALIGN.CENTER)
        _tab_x += _w + 0.08
    # 标题行
    line(slide, canvas, 0, 0.55, canvas.width, 0.04, theme.accent)
    text_box(slide, canvas, item.title, 0.6, 0.68, 10.5, 0.55, theme=theme, size=26, bold=True, fill=theme.primary)
    text_box(slide, canvas, f"{page:02d}", 12.2, 0.7, 0.7, 0.3, theme=theme, size=10, fill=theme.muted, align=PP_ALIGN.RIGHT)


def _premium_cover(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 封面：深色全幅底 + 大标题 + tab 导航 + 统计卡片。"""
    # 深色全幅底
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    # 左侧装饰条
    rect(slide, canvas, 0.72, 0.85, 0.12, 5.3, theme.accent, radius=False)
    # 右侧装饰面板
    rect(slide, canvas, 9.5, 0, 3.83, canvas.height, theme.surface, radius=False)
    # 右上 tab 导航
    tab_labels = item.tabs or ["项目背景", "产品介绍", "商业模式", "团队介绍", "未来规划"]
    _tab_y = 0.4
    for idx, label in enumerate(tab_labels[:5]):
        _ty = _tab_y + idx * 0.6
        rect(slide, canvas, 9.7, _ty, 3.3, 0.45, theme.grid if idx == 0 else theme.background, radius=False)
        text_box(slide, canvas, label, 9.75, _ty + 0.08, 3.2, 0.3, theme=theme, size=12, bold=idx == 0, fill=theme.primary if idx == 0 else theme.muted)
    # 主标题
    text_box(slide, canvas, item.title, 1.15, 1.35, 8.0, 1.5, theme=theme, size=42, bold=True, fill=theme.primary)
    # 副标题
    text_box(slide, canvas, item.subtitle or item.body or "专利教学课件", 1.18, 3.15, 7.5, 0.7, theme=theme, size=20, fill=theme.secondary)
    # 元数据行（参赛赛道/组别/负责人）
    _meta_y = 4.25
    meta_items = item.bullets or []
    for idx, meta in enumerate(meta_items[:3]):
        _mx = 1.18 + idx * 2.6
        rect(slide, canvas, _mx, _meta_y, 2.4, 0.55, theme.surface, radius=False)
        text_box(slide, canvas, str(meta)[:20], _mx + 0.1, _meta_y + 0.12, 2.2, 0.32, theme=theme, size=11, fill=theme.primary)
    # 底部页脚
    text_box(slide, canvas, f"PATENT TUTOR · {page:02d}", 1.18, 6.65, 5, 0.28, theme=theme, size=10, fill=theme.muted)


def _premium_content(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 内容页：深色底 + tab 头 + 正文卡 + 要点列表。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    _premium_tab_header(slide, canvas, item, theme, page)
    # 主体内容卡
    rect(slide, canvas, 0.6, 1.65, 12.1, 5.45, theme.surface, radius=False)
    # 正文区
    if item.body:
        text_box(slide, canvas, item.body, 0.9, 1.95, 11.5, 0.7, theme=Theme(**{**theme.__dict__, "text": theme.secondary}), size=16)
    # 要点列表（两列）
    items = item.bullets[:6] or item.steps[:6]
    if items:
        _cols = min(2, len(items))
        _col_w = 5.5
        for idx, it in enumerate(items):
            _col = idx % _cols
            _row = idx // _cols
            _cx = 0.9 + _col * (_col_w + 0.3)
            _cy = 2.8 + _row * 0.9
            rect(slide, canvas, _cx, _cy, _col_w, 0.65, theme.grid, radius=False)
            rect(slide, canvas, _cx + 0.1, _cy + 0.1, 0.35, 0.35, theme.accent, radius=False)
            text_box(slide, canvas, str(idx + 1), _cx + 0.1, _cy + 0.12, 0.35, 0.2, theme=theme, size=10, bold=True, fill=theme.background, align=PP_ALIGN.CENTER)
            text_box(slide, canvas, str(it), _cx + 0.55, _cy + 0.15, _col_w - 0.65, 0.35, theme=theme, size=14, fill=theme.primary)


def _premium_section_divider(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 章节分隔页：大数字 + 标题 + 装饰条。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    # 大装饰数字
    _section_num = str(item.section_number or page)
    text_box(slide, canvas, _section_num, 0.6, 0.8, 12.0, 3.5, theme=theme, size=200, bold=True, fill=theme.accent)
    # 右侧装饰面板
    rect(slide, canvas, 9.2, 0, 4.13, canvas.height, theme.surface, radius=False)
    # 章节标题
    text_box(slide, canvas, item.title, 0.6, 4.3, 8.5, 1.2, theme=theme, size=38, bold=True, fill=theme.primary)
    text_box(slide, canvas, item.subtitle or item.body or "", 0.6, 5.5, 8.0, 0.5, theme=theme, size=18, fill=theme.secondary)
    # 装饰条
    line(slide, canvas, 0.6, 4.1, 8.5, 0.06, theme.accent)
    # 右侧 tab
    tab_labels = item.tabs or ["项目背景", "产品介绍", "商业模式", "团队介绍", "未来规划"]
    for idx, label in enumerate(tab_labels[:5]):
        _ty = 1.5 + idx * 0.6
        rect(slide, canvas, 9.4, _ty, 3.5, 0.45, theme.grid, radius=False)
        text_box(slide, canvas, label, 9.45, _ty + 0.08, 3.4, 0.3, theme=theme, size=12, fill=theme.primary)
    text_box(slide, canvas, f"PATENT TUTOR · {page:02d}", 0.6, 6.65, 5, 0.28, theme=theme, size=10, fill=theme.muted)


def _premium_stat_overview(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 数据概览：统计卡片 + 要点列表。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    _premium_tab_header(slide, canvas, item, theme, page)
    # 统计卡片区
    stats = item.stats or []
    _stat_w = 3.8
    for idx, stat in enumerate(stats[:3]):
        _sx = 0.6 + idx * (_stat_w + 0.3)
        _sy = 1.65
        rect(slide, canvas, _sx, _sy, _stat_w, 1.8, theme.surface, radius=False)
        # 大数字
        text_box(slide, canvas, str(stat.get("value", stat.get("number", "?"))), _sx + 0.2, _sy + 0.25, _stat_w - 0.4, 0.9, theme=theme, size=44, bold=True, fill=theme.accent)
        # 标签
        text_box(slide, canvas, str(stat.get("label", stat.get("title", ""))), _sx + 0.2, _sy + 1.2, _stat_w - 0.4, 0.3, theme=theme, size=14, fill=theme.primary, align=PP_ALIGN.CENTER)
        # 单位
        if stat.get("unit"):
            text_box(slide, canvas, str(stat.get("unit", "")), _sx + 0.2, _sy + 1.5, _stat_w - 0.4, 0.2, theme=theme, size=11, fill=theme.muted, align=PP_ALIGN.CENTER)
    # 要点列表（下方）
    items = item.bullets[:4] or item.steps[:4]
    if items:
        _iy = 3.85
        for idx, it in enumerate(items):
            rect(slide, canvas, 0.6 + idx * 3.1, _iy, 2.9, 2.85, theme.surface, radius=False)
            rect(slide, canvas, 0.7 + idx * 3.1, _iy + 0.1, 0.35, 0.35, theme.accent, radius=False)
            text_box(slide, canvas, str(idx + 1), 0.7 + idx * 3.1, _iy + 0.12, 0.35, 0.2, theme=theme, size=10, bold=True, fill=theme.background, align=PP_ALIGN.CENTER)
            text_box(slide, canvas, str(it)[:60], 0.7 + idx * 3.1 + 0.45, _iy + 0.55, 2.35, 2.1, theme=theme, size=14, fill=theme.primary)


def _premium_certificate_gallery(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 证书/成果展示：证书网格 + 统计卡片。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    _premium_tab_header(slide, canvas, item, theme, page)
    # 统计卡片（顶部）
    stats = item.stats or []
    _stat_w = 3.8
    for idx, stat in enumerate(stats[:3]):
        _sx = 0.6 + idx * (_stat_w + 0.3)
        _sy = 1.65
        rect(slide, canvas, _sx, _sy, _stat_w, 1.5, theme.surface, radius=False)
        text_box(slide, canvas, str(stat.get("value", stat.get("number", "?"))), _sx + 0.2, _sy + 0.15, _stat_w - 0.4, 0.7, theme=theme, size=36, bold=True, fill=theme.accent)
        text_box(slide, canvas, str(stat.get("label", stat.get("title", ""))), _sx + 0.2, _sy + 0.95, _stat_w - 0.4, 0.3, theme=theme, size=13, fill=theme.primary, align=PP_ALIGN.CENTER)
    # 证书网格（2行 × 3列）
    certs = item.certificates or item.bullets or []
    for idx, cert in enumerate(certs[:6]):
        _row = idx // 3
        _col = idx % 3
        _cx = 0.6 + _col * 4.2
        _cy = 3.4 + _row * 1.6
        rect(slide, canvas, _cx, _cy, 4.0, 1.4, theme.surface, radius=False)
        # 证书图标区
        rect(slide, canvas, _cx + 0.15, _cy + 0.15, 0.9, 0.9, theme.accent, radius=False)
        text_box(slide, canvas, "🏆", _cx + 0.15, _cy + 0.2, 0.9, 0.8, theme=theme, size=28, align=PP_ALIGN.CENTER)
        # 证书名称
        text_box(slide, canvas, str(cert)[:40], _cx + 1.2, _cy + 0.2, 2.7, 0.6, theme=theme, size=13, fill=theme.primary)
        text_box(slide, canvas, str(cert)[40:80] if len(str(cert)) > 40 else "", _cx + 1.2, _cy + 0.8, 2.7, 0.5, theme=theme, size=11, fill=theme.muted)


def _premium_two_column(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 双栏布局：左文字 + 右图示。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    _premium_tab_header(slide, canvas, item, theme, page)
    # 左栏
    rect(slide, canvas, 0.6, 1.65, 6.0, 5.45, theme.surface, radius=False)
    text_box(slide, canvas, item.left_title or item.title or "核心要点", 0.9, 1.9, 5.4, 0.5, theme=theme, size=20, bold=True, fill=theme.primary)
    left_items = item.left_items or item.bullets[:4]
    for idx, li in enumerate(left_items[:4]):
        _ly = 2.55 + idx * 1.1
        rect(slide, canvas, 0.9, _ly, 5.4, 0.9, theme.grid, radius=False)
        text_box(slide, canvas, str(li)[:30], 1.1, _ly + 0.2, 5.0, 0.5, theme=theme, size=14, fill=theme.primary)
    # 右栏
    rect(slide, canvas, 7.0, 1.65, 5.7, 5.45, theme.surface, radius=False)
    text_box(slide, canvas, item.right_title or "数据展示", 7.3, 1.9, 5.1, 0.5, theme=theme, size=20, bold=True, fill=theme.primary)
    right_items = item.right_items or item.steps[:4]
    for idx, ri in enumerate(right_items[:4]):
        _ry = 2.55 + idx * 1.1
        rect(slide, canvas, 7.3, _ry, 5.1, 0.9, theme.accent if idx == 0 else theme.grid, radius=False)
        text_box(slide, canvas, str(ri)[:30], 7.5, _ry + 0.2, 4.7, 0.5, theme=theme, size=14, fill=theme.background if idx == 0 else theme.primary)


def _premium_summary(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    """Premium 总结页：数字编号列表 + 金句 callout。"""
    rect(slide, canvas, 0, 0, canvas.width, canvas.height, theme.background, radius=False)
    _premium_tab_header(slide, canvas, item, theme, page)
    # 左侧编号列表
    items = item.bullets[:5] or item.steps[:5]
    for idx, it in enumerate(items):
        _ly = 1.8 + idx * 0.95
        rect(slide, canvas, 0.6, _ly, 8.5, 0.8, theme.surface, radius=False)
        rect(slide, canvas, 0.75, _ly + 0.15, 0.5, 0.5, theme.accent, radius=False)
        text_box(slide, canvas, str(idx + 1), 0.75, _ly + 0.18, 0.5, 0.3, theme=theme, size=14, bold=True, fill=theme.background, align=PP_ALIGN.CENTER)
        text_box(slide, canvas, str(it)[:50], 1.35, _ly + 0.2, 7.6, 0.4, theme=theme, size=15, fill=theme.primary)
    # 右侧金句 callout
    if item.body or item.subtitle:
        rect(slide, canvas, 9.4, 1.8, 3.5, 4.7, theme.accent, radius=False)
        text_box(slide, canvas, "核心结论", 9.5, 2.0, 3.2, 0.4, theme=theme, size=16, bold=True, fill=theme.background)
        text_box(slide, canvas, item.body or item.subtitle or "", 9.5, 2.5, 3.2, 3.8, theme=theme, size=16, fill=theme.background)


def header(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    line(slide, canvas, canvas.margin_x, 0.34, 0.72, 0.07, theme.accent)
    text_box(slide, canvas, item.title, canvas.margin_x, 0.48, 11.4, 0.48, theme=theme, size=27, bold=True)
    text_box(slide, canvas, f"{page:02d}", 12.05, 0.5, 0.55, 0.3, theme=theme, size=10, fill=theme.muted, align=PP_ALIGN.RIGHT)
    apply_decor(slide, canvas, theme, page)


def cover(slide, canvas: Canvas, item: PresentationVisualSlide, theme: Theme, page: int) -> None:
    _has_visuals = bool(item.visual_elements)
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
            # 有 visual_elements 时 bullets 区域缩窄（4.35→5.35），给下方图示让路
            _bullets_h = 0.9 if _has_visuals else 1.2
            bullets(slide, canvas, item.bullets[:3], 1.18, 4.35, 7.4, _bullets_h, theme=Theme(**{**theme.__dict__, "text": "FFFFFF"}), size=16)
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
    # Premium 深色主题：优先使用 premium 布局
    _is_premium = theme.id == "warm_orange_premium"
    if _is_premium:
        premium_handlers = {
            "title": _premium_cover, "cover_minimal": _premium_cover, "cover_split": _premium_cover,
            "content": _premium_content, "content_bullet_grid": _premium_content,
            "content_rule_card": _premium_content, "legal_citation_focus": _premium_content,
            "two_column": _premium_two_column, "case_analysis_split": _premium_two_column,
            "comparison": _premium_two_column, "comparison_matrix": _premium_two_column,
            "process": _premium_content, "timeline_process": _premium_content, "irac_flow": _premium_two_column,
            "exam_checklist": _premium_content,
            "summary": _premium_summary, "summary_roadmap": _premium_summary,
            "hero_statement": _premium_section_divider,
            "evidence_stack": _premium_content, "decision_tree": _premium_content,
            "concept_map": _premium_two_column,
            # 新增 premium 专用模板
            "premium_cover": _premium_cover,
            "premium_content": _premium_content,
            "premium_section_divider": _premium_section_divider,
            "premium_stat_overview": _premium_stat_overview,
            "premium_certificate_gallery": _premium_certificate_gallery,
            "premium_two_column": _premium_two_column,
            "premium_summary": _premium_summary,
        }
        handler = premium_handlers.get(template)
        if handler:
            handler(slide, canvas, item, theme, page)
            return
    if maybe_render_visual_effects(slide, canvas, item, theme, page, template):
        return
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
        # cover / hero_statement 布局：bullets 区域在 y=4.35~5.55，
        # visual_elements 必须放到 bullets 下方避免遮挡；其余布局保持原位置。
        _is_cover_layout = template in ("hero_statement", "cover_minimal", "cover_split", "title")
        for index, element in enumerate(item.visual_elements[:2]):
            if _is_cover_layout:
                _has_bullets = bool(item.bullets or item.steps)
                if _has_bullets:
                    # bullets 缩为 0.9 高、visual_elements 放到 y=5.65 起、高 1.0
                    render_element(slide, canvas, theme, element, 0.85 + (index % 2) * 6.0, 5.65, 5.55, 1.0)
                else:
                    render_element(slide, canvas, theme, element, 0.85 + (index % 2) * 6.0, 5.35, 5.55, 1.25)
            else:
                render_element(slide, canvas, theme, element, 0.85 + (index % 2) * 6.0, 5.35, 5.55, 1.25)
