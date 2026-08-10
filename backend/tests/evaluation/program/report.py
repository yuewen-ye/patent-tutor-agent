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
import json
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
    ("匹配度", ["难度符合度", "情感使用度"]),
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
    "情感使用度": (
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
    llm_eval_results: dict[str, Any] = field(default_factory=dict)


# ── 外部 LLM 评估结果读取 ─────────────────────────────────────────────────────

LLM_EVAL_RESULTS_DIR = _EVAL_DIR / "LLM" / "results"

# 外部 LLM 评分维度（与 evaluator_system.md 对齐）
LLM_SCORING_DIMENSIONS: list[tuple[str, str]] = [
    ("goal_coverage", "目标覆盖度"),
    ("factual_accuracy", "事实/法律准确性"),
    ("case_accuracy", "案例准确性"),
    ("factual_consistency", "事实一致性"),
    ("pedagogical_clarity", "教学清晰度"),
    ("difficulty_fit", "难度适配性"),
    ("learner_fit", "学员匹配度"),
    ("knowledge_completeness", "知识完整性"),
    ("weakness_addressing", "薄弱点针对性"),
]


def _load_llm_eval_results() -> dict[str, Any]:
    """加载所有外部 LLM 评估结果。

    Returns:
        dict 结构: {profile_letter: {round_num: json_data, ...}, ...}
    """
    results: dict[str, Any] = {}

    if not LLM_EVAL_RESULTS_DIR.exists():
        return results

    for json_file in sorted(LLM_EVAL_RESULTS_DIR.glob("judge_*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            metadata = data.get("metadata", {})
            profile_id = metadata.get("profile_id", "")
            round_num = metadata.get("round", 0)

            if profile_id and round_num:
                if profile_id not in results:
                    results[profile_id] = {}
                results[profile_id][round_num] = data
        except (json.JSONDecodeError, KeyError):
            continue

    return results


def _has_llm_eval_for(profile_letter: str, round_num: int,
                      llm_results: dict[str, Any]) -> bool:
    """检查指定画像指定轮次是否有外部 LLM 评估结果。"""
    return profile_letter in llm_results and round_num in llm_results[profile_letter]


def _get_llm_overall_scores(profile_letter: str, round_num: int,
                             llm_results: dict[str, Any]) -> dict[str, Any] | None:
    """获取指定画像指定轮次的整体评估分数。"""
    if not _has_llm_eval_for(profile_letter, round_num, llm_results):
        return None

    data = llm_results[profile_letter][round_num]
    overall = data.get("overall_evaluation", {})
    return overall.get("scores", {})


def _get_llm_chunk_scores(profile_letter: str, round_num: int,
                           llm_results: dict[str, Any]) -> list[dict[str, Any]]:
    """获取指定画像指定轮次的分块评估分数。"""
    if not _has_llm_eval_for(profile_letter, round_num, llm_results):
        return []

    data = llm_results[profile_letter][round_num]
    return data.get("chunk_evaluations", [])


def _get_llm_summary(profile_letter: str, round_num: int,
                      llm_results: dict[str, Any]) -> dict[str, Any]:
    """获取指定画像指定轮次的评估总结。"""
    if not _has_llm_eval_for(profile_letter, round_num, llm_results):
        return {}

    data = llm_results[profile_letter][round_num]
    overall = data.get("overall_evaluation", {})
    return overall.get("summary", {})


def _get_llm_metadata(profile_letter: str, round_num: int,
                       llm_results: dict[str, Any]) -> dict[str, Any]:
    """获取指定画像指定轮次的元数据。"""
    if not _has_llm_eval_for(profile_letter, round_num, llm_results):
        return {}

    data = llm_results[profile_letter][round_num]
    return data.get("metadata", {})


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
    max_round: int | None = None,
) -> ProfileReport:
    """对单个画像逐轮计算指标。

    Args:
        profile_letter: 画像字母
        session_dir: 测试快照目录
        max_round: 最大轮次上限（None 表示全部）
    """
    pr = ProfileReport(
        profile_letter=profile_letter,
        session_dir=session_dir,
    )
    rounds_nums = _list_available_rounds(session_dir)
    if max_round is not None:
        rounds_nums = [r for r in rounds_nums if r <= max_round]
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
    max_round: int | None = None,
    profile_ids: list[str] | None = None,
    output_path: Path | None = None,
) -> Path | None:
    """生成完整评估报告（多画像汇总）。

    Args:
        learner_prefix: 学习者前缀（默认 multi）
        max_round: 最大轮次上限（None 表示全部轮次）
        profile_ids: 指定画像 ID 列表（如 ["profile_B", "profile_C"]），None 表示自动发现
        output_path: 输出路径（None 表示默认路径）

    Returns: 实际写入的报告文件路径；失败（无数据）返回 None。
    """
    # 确定要处理的画像列表
    if profile_ids is not None:
        letters = []
        for pid in profile_ids:
            # 提取字母：profile_B -> B
            letter = pid.split("_")[-1] if "_" in pid else pid
            letters.append(letter)
    else:
        letters = _list_profiles_with_data(learner_prefix)

    if not letters:
        print("  ❌ 没有找到任何有运行数据的画像")
        return None

    max_desc = f"≤ R{max_round:02d}" if max_round is not None else "全部轮次"
    print(f"  发现 {len(letters)} 个画像，{max_desc}：{', '.join(letters)}")

    profiles: list[ProfileReport] = []
    for letter in letters:
        session_dir = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
        if not session_dir.exists():
            print(f"  [profile_{letter}] ⚠️ 测试快照目录不存在，已跳过")
            continue
        rounds = _list_available_rounds(session_dir)
        if max_round is not None:
            rounds = [r for r in rounds if r <= max_round]
        if not rounds:
            print(f"  [profile_{letter}] ⚠️ 无符合条件的轮次数据，已跳过")
            continue
        print(f"  [profile_{letter}] 计算 {len(rounds)} 个轮次...")
        pr = _calculate_profile(letter, session_dir, max_round=max_round)
        if pr.rounds:
            profiles.append(pr)
        else:
            print(f"  [profile_{letter}] ⚠️ 无可用轮次数据，已跳过")

    if not profiles:
        print("  ❌ 所有画像均无可用数据")
        return None

    # 加载外部 LLM 评估结果
    llm_eval_results = _load_llm_eval_results()
    llm_eval_count = sum(
        len(rounds) for rounds in llm_eval_results.values()
    )
    if llm_eval_results:
        print(f"  发现 {llm_eval_count} 条外部 LLM 评估结果")

    ctx = FullReportContext(
        profiles=profiles,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        llm_eval_results=llm_eval_results,
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
    llm_results = ctx.llm_eval_results  # 从 ctx 获取外部 LLM 结果

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

    # ── 二-2、外部 LLM 评分横向对比 ────────────────────────────────────────
    if llm_results:
        lines.append("### 外部 LLM 评分横向对比（各画像跨轮平均值）")
        lines.append("")
        lines.append(f"_数据来源: {LLM_EVAL_RESULTS_DIR} 下的 judge_*.json 文件_")
        lines.append("")

        llm_dim_keys = [key for key, _ in LLM_SCORING_DIMENSIONS]
        llm_dim_labels = [label for _, label in LLM_SCORING_DIMENSIONS]

        # 表头：画像 | 各维度 | 总体评分
        llm_header_cells = ["画像"]
        llm_header_cells.extend(llm_dim_labels)
        llm_header_cells.append("总体评分")
        lines.append("| " + " | ".join(llm_header_cells) + " |")
        lines.append("|---|" + "|".join("---" for _ in llm_header_cells[1:]) + "|")

        # 每个画像一行：计算跨轮平均
        for p in profiles:
            letter = p.profile_letter
            row_cells = [f"profile_{letter}"]

            for dim_key in llm_dim_keys:
                scores: list[float] = []
                for rm in p.rounds:
                    overall = _get_llm_overall_scores(
                        letter, rm.round_num, llm_results
                    )
                    if overall:
                        dim_data = overall.get(dim_key, {})
                        score = dim_data.get("score", 0)
                        if score > 0:
                            scores.append(score)
                if scores:
                    avg = sum(scores) / len(scores)
                    max_score = 5  # 除了 overall_score 都是 5 分制
                    row_cells.append(f"{avg:.1f}/{max_score}")
                else:
                    row_cells.append("-")

            # 总体评分列
            overall_totals: list[float] = []
            for rm in p.rounds:
                overall = _get_llm_overall_scores(
                    letter, rm.round_num, llm_results
                )
                if overall:
                    total_data = overall.get("overall_score", {})
                    total = total_data.get("score", 0)
                    if total > 0:
                        overall_totals.append(total)
            if overall_totals:
                avg_total = sum(overall_totals) / len(overall_totals)
                row_cells.append(f"{avg_total:.1f}/100")
            else:
                row_cells.append("-")

            lines.append("| " + " | ".join(row_cells) + " |")

        # 总体平均行
        grand_cells = ["**总体平均**"]
        for dim_key in llm_dim_keys:
            all_scores: list[float] = []
            for p in profiles:
                letter = p.profile_letter
                for rm in p.rounds:
                    overall = _get_llm_overall_scores(
                        letter, rm.round_num, llm_results
                    )
                    if overall:
                        dim_data = overall.get(dim_key, {})
                        score = dim_data.get("score", 0)
                        if score > 0:
                            all_scores.append(score)
            if all_scores:
                grand_avg = sum(all_scores) / len(all_scores)
                grand_cells.append(f"{grand_avg:.1f}/5")
            else:
                grand_cells.append("-")

        # 总体评分列的总体平均
        all_overall_totals: list[float] = []
        for p in profiles:
            letter = p.profile_letter
            for rm in p.rounds:
                overall = _get_llm_overall_scores(
                    letter, rm.round_num, llm_results
                )
                if overall:
                    total_data = overall.get("overall_score", {})
                    total = total_data.get("score", 0)
                    if total > 0:
                        all_overall_totals.append(total)
        if all_overall_totals:
            grand_total = sum(all_overall_totals) / len(all_overall_totals)
            grand_cells.append(f"{grand_total:.1f}/100")
        else:
            grand_cells.append("-")

        lines.append("| " + " | ".join(grand_cells) + " |")
        lines.append("")

    # ── 三、各画像详情 ───────────────────────────────────────────────────────
    lines.append("## 三、各画像详情")
    lines.append("")
    for p in profiles:
        letter = p.profile_letter
        lines.append(f"### profile_{letter}")
        lines.append("")
        lines.append(f"- 测试快照目录：`{p.session_dir}`")
        lines.append(f"- 轮次数：{len(p.rounds)}")
        lines.append("")

        # 3.1 该画像的轮次汇总表（原有指标）
        lines.append("#### 轮次汇总（规则计算指标）")
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

        # 3.2 外部 LLM 评分轮次汇总
        has_llm = any(
            _has_llm_eval_for(letter, rm.round_num, llm_results)
            for rm in p.rounds
        )
        if has_llm:
            lines.append("#### 外部 LLM 评分轮次汇总")
            lines.append("")

            llm_dim_keys = [key for key, _ in LLM_SCORING_DIMENSIONS]
            llm_dim_labels = [label for _, label in LLM_SCORING_DIMENSIONS]

            # 表头
            llm_header = ["指标"]
            for rm in p.rounds:
                llm_header.append(f"R{rm.round_num:02d}")
            llm_header.append("平均")
            lines.append("| " + " | ".join(llm_header) + " |")
            lines.append("|---|" + "|".join("---" for _ in p.rounds) + "|---|")

            # 各维度
            for dim_key, dim_label in LLM_SCORING_DIMENSIONS:
                row_cells = [f"`{dim_label}`"]
                scores: list[float] = []
                for rm in p.rounds:
                    overall = _get_llm_overall_scores(
                        letter, rm.round_num, llm_results
                    )
                    if overall:
                        dim_data = overall.get(dim_key, {})
                        score = dim_data.get("score", 0)
                        max_score = dim_data.get("max", 5)
                        if score > 0:
                            row_cells.append(f"{score}/{max_score}")
                            scores.append(score)
                        else:
                            row_cells.append("-")
                    else:
                        row_cells.append("-")
                if scores:
                    avg = sum(scores) / len(scores)
                    row_cells.append(f"{avg:.1f}/5")
                else:
                    row_cells.append("-")
                lines.append("| " + " | ".join(row_cells) + " |")

            # 总体评分行
            row_cells = ["`总体评分`"]
            overall_totals: list[float] = []
            for rm in p.rounds:
                overall = _get_llm_overall_scores(
                    letter, rm.round_num, llm_results
                )
                if overall:
                    total_data = overall.get("overall_score", {})
                    total = total_data.get("score", 0)
                    max_total = total_data.get("max", 100)
                    if total > 0:
                        row_cells.append(f"{total}/{max_total}")
                        overall_totals.append(total)
                    else:
                        row_cells.append("-")
                else:
                    row_cells.append("-")
            if overall_totals:
                avg_total = sum(overall_totals) / len(overall_totals)
                row_cells.append(f"{avg_total:.1f}/100")
            else:
                row_cells.append("-")
            lines.append("| " + " | ".join(row_cells) + " |")

            lines.append("")

        # 3.3 该画像各轮明细（原有指标）
        lines.append("#### 各轮明细（规则计算指标）")
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

        # 3.4 外部 LLM 评估详情
        if has_llm:
            lines.append("#### 外部 LLM 评估详情")
            lines.append("")

            llm_dim_keys = [key for key, _ in LLM_SCORING_DIMENSIONS]
            llm_dim_labels = {key: label for key, label in LLM_SCORING_DIMENSIONS}

            for rm in p.rounds:
                round_num = rm.round_num
                if not _has_llm_eval_for(letter, round_num, llm_results):
                    continue

                meta = _get_llm_metadata(letter, round_num, llm_results)
                lines.append(f"**R{round_num:02d}** "
                           f"({meta.get('model', '?')} @ {meta.get('timestamp', '?')})")
                lines.append("")

                # 总体评分
                overall_scores = _get_llm_overall_scores(
                    letter, round_num, llm_results
                )
                if overall_scores:
                    overall_data = overall_scores.get("overall_score", {})
                    lines.append(f"- **总体评分**: {overall_data.get('score', '-')}/"
                               f"{overall_data.get('max', 100)} — "
                               f"{overall_data.get('comment', '')}")

                    # 各维度评分
                    lines.append("")
                    lines.append("**各维度评分**:")
                    lines.append("")
                    for dim_key in llm_dim_keys:
                        dim_data = overall_scores.get(dim_key, {})
                        score = dim_data.get("score", 0)
                        max_score = dim_data.get("max", 5)
                        comment = dim_data.get("comment", "")
                        if score > 0:
                            lines.append(f"- {llm_dim_labels.get(dim_key, dim_key)}: "
                                       f"{score}/{max_score} — {comment}")

                # 分块评估
                chunks = _get_llm_chunk_scores(letter, round_num, llm_results)
                if chunks:
                    lines.append("")
                    lines.append("**分块评分**:")
                    lines.append("")
                    lines.append("| 分块 | 标题 | 主要评分 |")
                    lines.append("|---|---|---|")
                    for chunk in chunks:
                        chunk_idx = chunk.get("chunk_index", 0)
                        chunk_title = chunk.get("chunk_title", f"分块{chunk_idx + 1}")
                        chunk_eval = chunk.get("evaluation", {})
                        chunk_scores = chunk_eval.get("scores", {})

                        # 取第一个非 0 的评分
                        first_score = "-"
                        for dim_key in llm_dim_keys:
                            dim_data = chunk_scores.get(dim_key, {})
                            if dim_data.get("score", 0) > 0:
                                first_score = (f"{llm_dim_labels.get(dim_key, dim_key)}: "
                                             f"{dim_data['score']}/{dim_data.get('max', 5)}")
                                break

                        lines.append(
                            f"| {chunk_idx + 1} | {chunk_title} | {first_score} |"
                        )

                # 评估总结
                summary = _get_llm_summary(letter, round_num, llm_results)
                if summary:
                    lines.append("")
                    if summary.get("highlights"):
                        lines.append("**亮点**:")
                        for h in summary["highlights"]:
                            lines.append(f"- {h}")
                    if summary.get("issues"):
                        lines.append("")
                        lines.append("**问题**:")
                        for issue in summary["issues"]:
                            lines.append(f"- {issue}")
                    if summary.get("suggestions"):
                        lines.append("")
                        lines.append("**建议**:")
                        for s in summary["suggestions"]:
                            lines.append(f"- {s}")

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
