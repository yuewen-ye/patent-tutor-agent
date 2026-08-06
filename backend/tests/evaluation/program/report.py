"""评估报告生成脚本。

支持两种生成模式：

1. **完整报告**（默认/主控调用）：遍历所有有运行数据的画像，汇总成一份 Markdown 报告。
   - 入口：``generate_full_report()``
   - 输出：``backend/tests/evaluation/results/reports/report_full.md``

2. **单画像报告**（CLI 指定 --profile）：仅生成指定画像的报告。
   - 入口：``generate_report(profile_letter)``
   - 输出：``backend/tests/evaluation/results/reports/report_{letter}.md``

报告结构（完整报告）：
  1. 概览（画像列表、各画像轮次数）
  2. 指标说明（公式 + 数据来源）
  3. 横向对比表（所有画像的平均值对比）
  4. 各画像详情（每个画像的轮次表 + 各轮明细）
  5. 总体评估（所有画像所有轮次的总体平均）

CLI 用法：
  uv run python backend/tests/evaluation/program/report.py                      # 完整报告
  uv run python backend/tests/evaluation/program/report.py --profile B          # 单画像报告
  uv run python backend/tests/evaluation/program/report.py --output report.md   # 指定输出
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parents[2]
for _p in (_THIS_DIR, _EVAL_DIR, _PROJECT_ROOT):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import eval_common as common  # noqa: E402
import calculate  # noqa: E402


# ── 常量 ─────────────────────────────────────────────────────────────────────

REPORTS_DIR = _EVAL_DIR / "results" / "reports"

# 指标分类（按 calculate.py 顺序，与 doc/指标草案.md 对齐）
METRIC_CATEGORIES: list[tuple[str, list[str]]] = [
    ("幻觉率 — 系统自评", ["专家互评异议率", "裁判准确性评分"]),
    ("匹配度", ["难度符合度", "情感状态适配度"]),
    ("覆盖率", ["本节知识点覆盖率", "薄弱点命中率", "混淆对覆盖率"]),
]

# 指标说明：name -> (计算公式, 数据来源)
METRIC_META: dict[str, tuple[str, str]] = {
    "专家互评异议率": (
        "(🔴+🟡) / 总批注数 × 100%",
        "expert_a_cross_review.md + expert_b_cross_review.md",
    ),
    "裁判准确性评分": (
        "直接取 X/5",
        "judge_report.md",
    ),
    "难度符合度": (
        "题目难度≤上限的题数 / 总题数 × 100%",
        "course_package.md (Q难度) + learning_path.md (难度上限表)",
    ),
    "情感状态适配度": (
        "情感支持板块数 / 总板块数 × 100%",
        "course_package.md (教学模块清单 block_type)",
    ),
    "本节知识点覆盖率": (
        "|实际覆盖 ∩ 预设期望| / |预设期望| × 100%",
        "course_package.md (knowledge_points.node_id) + expected_*.json (section_kcs)",
    ),
    "薄弱点命中率": (
        "命中的薄弱点数 / 总薄弱点数 × 100%",
        "course_package.md (全文匹配) + expected_*.json (weakness_kcs)",
    ),
    "混淆对覆盖率": (
        "命中的混淆对数 / 总预设混淆对数 × 100%",
        "course_package.md (全文匹配 node_name) + expected_*.json (confusable_pairs)",
    ),
}


# ── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class ProfileReport:
    """单个画像的报告数据。"""
    profile_letter: str
    session_dir: Path
    rounds: list[calculate.RoundMetrics] = field(default_factory=list)


@dataclass
class ReportContext:
    """单画像报告渲染上下文。"""
    profile_letter: str
    session_dir: Path
    rounds: list[calculate.RoundMetrics]
    generated_at: str


@dataclass
class FullReportContext:
    """完整报告渲染上下文（多画像汇总）。"""
    profiles: list[ProfileReport]
    generated_at: str


# ── 路径查找 ─────────────────────────────────────────────────────────────────

def _find_session_dir(
    profile_letter: str, learner_prefix: str = "multi",
) -> Path | None:
    """查找测试快照目录（multi-{letter}）。"""
    candidate = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{profile_letter}"
    return candidate if candidate.exists() else None


def _list_available_rounds(session_dir: Path) -> list[int]:
    """列出测试快照目录中已有的教学轮次编号。"""
    rounds: list[int] = []
    if not session_dir.exists():
        return rounds
    # 兼容 round-* (新) 和 round_* (旧) 两种命名
    for d in session_dir.glob("round*"):
        if d.is_dir():
            name = d.name
            try:
                if name.startswith("round-"):
                    rounds.append(int(name.split("-")[1]))
                elif name.startswith("round_"):
                    rounds.append(int(name.split("_")[1]))
            except (ValueError, IndexError):
                continue
    return sorted(rounds)


def _list_profiles_with_data(learner_prefix: str = "multi") -> list[str]:
    """列出所有有测试快照数据的画像字母（按字母序）。"""
    letters: list[str] = []
    for d in common.EVAL_ARTIFACTS_DIR.glob(f"{learner_prefix}-*"):
        if d.is_dir():
            letter = d.name.split("-", 1)[1]
            if _list_available_rounds(d):
                letters.append(letter)
    return sorted(letters)


# ── 格式化 ───────────────────────────────────────────────────────────────────

def _format_value(value: float, unit: str) -> str:
    """格式化指标值。"""
    if unit == "/5":
        return f"{value:.1f}/5"
    return f"{value:.1f}{unit}"


def _format_detail(v: Any) -> str:
    """格式化 detail 字段值（可能是 list/dict/scalar）。"""
    if isinstance(v, (list, dict)):
        import json
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _all_metric_names(profiles: list[ProfileReport]) -> list[str]:
    """收集所有出现过的指标名（按 calculate.py 顺序去重）。"""
    names: list[str] = []
    seen: set[str] = set()
    for p in profiles:
        for rm in p.rounds:
            for m in rm.metrics:
                if m.name not in seen:
                    names.append(m.name)
                    seen.add(m.name)
    return names


def _metric_avg_for_profile(
    profile: ProfileReport, metric_name: str,
) -> tuple[float, str] | None:
    """计算单个画像某指标的跨轮平均值。"""
    values_with_unit: list[tuple[float, str]] = []
    for rm in profile.rounds:
        m = next((x for x in rm.metrics if x.name == metric_name), None)
        if m is not None:
            values_with_unit.append((m.value, m.unit))
    if not values_with_unit:
        return None
    avg = sum(v for v, _ in values_with_unit) / len(values_with_unit)
    return avg, values_with_unit[0][1]


# ── 单画像报告生成 ───────────────────────────────────────────────────────────

def _calculate_profile(
    profile_letter: str,
    session_dir: Path,
) -> ProfileReport:
    """对单个画像逐轮计算指标。"""
    pr = ProfileReport(
        profile_letter=profile_letter,
        session_dir=session_dir,
    )
    rounds_nums = _list_available_rounds(session_dir)
    for r in rounds_nums:
        try:
            rm = calculate.calculate_round(
                profile_letter=profile_letter,
                round_num=r,
                session_dir=session_dir,
            )
            pr.rounds.append(rm)
        except FileNotFoundError as exc:
            print(f"  ⚠️ [profile_{profile_letter}] round-{r:02d} 跳过: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️ [profile_{profile_letter}] round-{r:02d} 异常: {type(exc).__name__}: {exc}")
    return pr


def generate_report(
    profile_letter: str,
    *,
    session_dir: Path | None = None,
    learner_prefix: str = "multi",
    output_path: Path | None = None,
) -> Path | None:
    """生成指定画像的完整评估报告（Markdown）。

    Returns: 实际写入的报告文件路径；失败返回 None。
    """
    if session_dir is None:
        session_dir = _find_session_dir(profile_letter, learner_prefix)
    if session_dir is None:
        print(f"  ❌ 找不到画像 {profile_letter} 的测试快照目录")
        return None

    pr = _calculate_profile(profile_letter, session_dir)
    if not pr.rounds:
        print(f"  ❌ 画像 {profile_letter} 无可用的指标数据")
        return None

    ctx = ReportContext(
        profile_letter=profile_letter,
        session_dir=session_dir,
        rounds=pr.rounds,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    md = _render_markdown_single(ctx)

    if output_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / f"report_{profile_letter}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return output_path


# ── 完整报告生成（多画像汇总） ───────────────────────────────────────────────

def generate_full_report(
    *,
    learner_prefix: str = "multi",
    output_path: Path | None = None,
) -> Path | None:
    """生成所有有运行数据画像的完整评估报告（Markdown）。

    Returns: 实际写入的报告文件路径；失败（无数据）返回 None。
    """
    letters = _list_profiles_with_data(learner_prefix)
    if not letters:
        print("  ❌ 没有找到任何有运行数据的画像")
        return None

    print(f"  发现 {len(letters)} 个有数据的画像：{', '.join(letters)}")
    profiles: list[ProfileReport] = []
    for letter in letters:
        session_dir = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
        print(f"  [profile_{letter}] 计算中...")
        pr = _calculate_profile(letter, session_dir)
        if pr.rounds:
            profiles.append(pr)
        else:
            print(f"  [profile_{letter}] ⚠️ 无可用轮次数据，已跳过")

    if not profiles:
        print("  ❌ 所有画像均无可用数据")
        return None

    ctx = FullReportContext(
        profiles=profiles,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    md = _render_markdown_full(ctx)

    if output_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / "report_full.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return output_path


# ── Markdown 渲染：单画像 ────────────────────────────────────────────────────

def _render_markdown_single(ctx: ReportContext) -> str:
    """渲染单画像 Markdown 报告。"""
    lines: list[str] = []
    rounds = ctx.rounds

    lines.append(f"# 评估报告 — profile_{ctx.profile_letter}")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 画像：`profile_{ctx.profile_letter}`")
    lines.append(f"- 测试快照目录：`{ctx.session_dir}`")
    lines.append(f"- 测试轮次数：{len(rounds)}")
    lines.append(f"- 轮次列表：{', '.join(f'round-{rm.round_num:02d}' for rm in rounds)}")
    lines.append(f"- 报告生成时间：{ctx.generated_at}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 一、指标说明
    lines.append("## 一、指标说明")
    lines.append("")
    lines.append("| 指标 | 计算公式 | 数据来源 |")
    lines.append("|---|---|---|")
    for _, metric_names in METRIC_CATEGORIES:
        for name in metric_names:
            formula, source = METRIC_META.get(name, ("-", "-"))
            lines.append(f"| `{name}` | {formula} | {source} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 二、指标汇总表
    lines.append("## 二、指标汇总")
    lines.append("")
    header = "| 指标 | " + " | ".join(f"R{rm.round_num:02d}" for rm in rounds) + " | 平均 |"
    sep = "|---|" + "|".join("---" for _ in rounds) + "|---|"
    lines.append(header)
    lines.append(sep)

    all_metric_names: list[str] = []
    seen: set[str] = set()
    for rm in rounds:
        for m in rm.metrics:
            if m.name not in seen:
                all_metric_names.append(m.name)
                seen.add(m.name)

    for name in all_metric_names:
        row = [f"`{name}`"]
        values: list[float] = []
        unit = ""
        for rm in rounds:
            m = next((x for x in rm.metrics if x.name == name), None)
            if m is None:
                row.append("-")
            else:
                row.append(_format_value(m.value, m.unit))
                values.append(m.value)
                unit = m.unit
        if values:
            avg = sum(values) / len(values)
            row.append(_format_value(avg, unit))
        else:
            row.append("-")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 三、各轮详情
    lines.append("## 三、各轮详情")
    lines.append("")
    for rm in rounds:
        lines.append(f"### round-{rm.round_num:02d}")
        lines.append("")
        for category_name, metric_names in METRIC_CATEGORIES:
            lines.append(f"**{category_name}**")
            lines.append("")
            for name in metric_names:
                m = next((x for x in rm.metrics if x.name == name), None)
                if m is None:
                    continue
                lines.append(f"- **{m.name}**: {_format_value(m.value, m.unit)}")
                for k, v in m.detail.items():
                    lines.append(f"    - {k}: {_format_detail(v)}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # 四、总体评估
    lines.append("## 四、总体评估")
    lines.append("")
    for category_name, metric_names in METRIC_CATEGORIES:
        lines.append(f"**{category_name}**")
        lines.append("")
        for name in metric_names:
            values_with_unit: list[tuple[float, str]] = []
            for rm in rounds:
                m = next((x for x in rm.metrics if x.name == name), None)
                if m is not None:
                    values_with_unit.append((m.value, m.unit))
            if not values_with_unit:
                continue
            avg = sum(v for v, _ in values_with_unit) / len(values_with_unit)
            unit = values_with_unit[0][1]
            lines.append(f"- **{name}** 平均 {_format_value(avg, unit)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_报告由 report.py 自动生成 @ {ctx.generated_at}_")
    lines.append("")
    return "\n".join(lines)


# ── Markdown 渲染：完整报告（多画像） ────────────────────────────────────────

def _render_markdown_full(ctx: FullReportContext) -> str:
    """渲染完整 Markdown 报告（多画像汇总）。"""
    lines: list[str] = []
    profiles = ctx.profiles
    all_names = _all_metric_names(profiles)

    # ── 标题与概览 ───────────────────────────────────────────────────────────
    lines.append("# 评估报告 — 完整汇总")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 画像数：{len(profiles)}")
    lines.append(f"- 画像列表：{', '.join(f'profile_{p.profile_letter}' for p in profiles)}")
    total_rounds = sum(len(p.rounds) for p in profiles)
    lines.append(f"- 总轮次数：{total_rounds}")
    lines.append(f"- 报告生成时间：{ctx.generated_at}")
    lines.append("")
    lines.append("各画像轮次明细：")
    lines.append("")
    lines.append("| 画像 | 轮次数 | 轮次列表 |")
    lines.append("|---|---|---|")
    for p in profiles:
        rounds_str = ", ".join(f"R{rm.round_num:02d}" for rm in p.rounds) or "-"
        lines.append(f"| profile_{p.profile_letter} | {len(p.rounds)} | {rounds_str} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 一、指标说明 ─────────────────────────────────────────────────────────
    lines.append("## 一、指标说明")
    lines.append("")
    lines.append("| 指标 | 计算公式 | 数据来源 |")
    lines.append("|---|---|---|")
    for _, metric_names in METRIC_CATEGORIES:
        for name in metric_names:
            formula, source = METRIC_META.get(name, ("-", "-"))
            lines.append(f"| `{name}` | {formula} | {source} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 二、横向对比表（各画像平均值，转置：画像为行） ─────────────────────
    lines.append("## 二、画像横向对比（各画像跨轮平均值）")
    lines.append("")
    # 表头：画像 | 指标1 | 指标2 | ...
    header = "| 画像 | " + " | ".join(f"`{name}`" for name in all_names) + " |"
    sep = "|---|" + "|".join("---" for _ in all_names) + "|"
    lines.append(header)
    lines.append(sep)

    # 每个画像一行
    for p in profiles:
        row = [f"profile_{p.profile_letter}"]
        for name in all_names:
            result = _metric_avg_for_profile(p, name)
            if result is None:
                row.append("-")
            else:
                avg, u = result
                row.append(_format_value(avg, u))
        lines.append("| " + " | ".join(row) + " |")

    # 各指标总体平均行（保留每列平均，不要画像平均）
    grand_row = ["**总体平均**"]
    for name in all_names:
        all_values: list[float] = []
        unit = ""
        for p in profiles:
            result = _metric_avg_for_profile(p, name)
            if result is not None:
                all_values.append(result[0])
                unit = result[1]
        if all_values:
            grand_avg = sum(all_values) / len(all_values)
            grand_row.append(_format_value(grand_avg, unit))
        else:
            grand_row.append("-")
    lines.append("| " + " | ".join(grand_row) + " |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 三、各画像详情 ───────────────────────────────────────────────────────
    lines.append("## 三、各画像详情")
    lines.append("")
    for p in profiles:
        lines.append(f"### profile_{p.profile_letter}")
        lines.append("")
        lines.append(f"- 测试快照目录：`{p.session_dir}`")
        lines.append(f"- 轮次数：{len(p.rounds)}")
        lines.append("")

        # 3.1 该画像的轮次汇总表
        lines.append("#### 轮次汇总")
        lines.append("")
        header = "| 指标 | " + " | ".join(f"R{rm.round_num:02d}" for rm in p.rounds) + " | 平均 |"
        sep = "|---|" + "|".join("---" for _ in p.rounds) + "|---|"
        lines.append(header)
        lines.append(sep)

        p_names: list[str] = []
        p_seen: set[str] = set()
        for rm in p.rounds:
            for m in rm.metrics:
                if m.name not in p_seen:
                    p_names.append(m.name)
                    p_seen.add(m.name)

        for name in p_names:
            row = [f"`{name}`"]
            values: list[float] = []
            unit = ""
            for rm in p.rounds:
                m = next((x for x in rm.metrics if x.name == name), None)
                if m is None:
                    row.append("-")
                else:
                    row.append(_format_value(m.value, m.unit))
                    values.append(m.value)
                    unit = m.unit
            if values:
                avg = sum(values) / len(values)
                row.append(_format_value(avg, unit))
            else:
                row.append("-")
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")

        # 3.2 该画像各轮明细
        lines.append("#### 各轮明细")
        lines.append("")
        for rm in p.rounds:
            lines.append(f"**round-{rm.round_num:02d}**")
            lines.append("")
            for category_name, metric_names in METRIC_CATEGORIES:
                for name in metric_names:
                    m = next((x for x in rm.metrics if x.name == name), None)
                    if m is None:
                        continue
                    lines.append(f"- **{m.name}**: {_format_value(m.value, m.unit)}")
                    for k, v in m.detail.items():
                        lines.append(f"    - {k}: {_format_detail(v)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── 四、总体评估 ─────────────────────────────────────────────────────────
    lines.append("## 四、总体评估（所有画像所有轮次）")
    lines.append("")
    for category_name, metric_names in METRIC_CATEGORIES:
        lines.append(f"**{category_name}**")
        lines.append("")
        lines.append("| 指标 | 总体平均 | 各画像平均 |")
        lines.append("|---|---|---|")
        for name in metric_names:
            per_profile_avgs: list[float] = []
            unit = ""
            for p in profiles:
                result = _metric_avg_for_profile(p, name)
                if result is not None:
                    per_profile_avgs.append(result[0])
                    unit = result[1]
            if not per_profile_avgs:
                continue
            grand_avg = sum(per_profile_avgs) / len(per_profile_avgs)
            per_profile_str = ", ".join(
                f"{v:.1f}" for v in per_profile_avgs
            )
            lines.append(
                f"| `{name}` | {_format_value(grand_avg, unit)} | {per_profile_str} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_报告由 report.py 自动生成 @ {ctx.generated_at}_")
    lines.append("")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="评估报告生成脚本")
    p.add_argument("--profile", default=None,
                   help="画像字母（如 B）。省略则生成所有画像的完整报告。")
    p.add_argument("--session-dir", type=Path, default=None, help="测试快照目录（可选）")
    p.add_argument("--output", type=Path, default=None, help="报告输出路径（可选）")
    p.add_argument("--learner-prefix", default="multi")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.profile:
        output = generate_report(
            profile_letter=args.profile,
            session_dir=args.session_dir,
            learner_prefix=args.learner_prefix,
            output_path=args.output,
        )
    else:
        output = generate_full_report(
            learner_prefix=args.learner_prefix,
            output_path=args.output,
        )

    if output is None:
        return 1
    print(f"✅ 报告已生成: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
