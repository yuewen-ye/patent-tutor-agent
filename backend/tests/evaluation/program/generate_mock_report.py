"""生成模拟评估报告脚本。

用于生成一份包含所有指标的模拟报告，所有数据用 '-' 替代。
"""

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parents[2]

sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_EVAL_DIR))

import report
from datetime import datetime

def generate_mock_report():
    """生成一份模拟报告。"""
    profiles = ["B", "C", "M"]
    rounds = [1, 2]
    
    lines = []
    lines.append("# 评估报告 — 完整汇总 (模拟数据)")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 画像数：{len(profiles)}")
    lines.append(f"- 画像列表：{', '.join(f'profile_{p}' for p in profiles)}")
    lines.append(f"- 总轮次数：{len(profiles) * len(rounds)}")
    lines.append(f"- 报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("各画像轮次明细：")
    lines.append("")
    lines.append("| 画像 | 轮次数 | 轮次列表 |")
    lines.append("|---|---|---|")
    for p in profiles:
        rounds_str = ", ".join(f"R{r:02d}" for r in rounds)
        lines.append(f"| profile_{p} | {len(rounds)} | {rounds_str} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 指标说明
    lines.append("## 一、指标说明")
    lines.append("")
    lines.append("| 指标 | 计算公式 | 数据来源 |")
    lines.append("|---|---|---|")
    for _, metric_names in report.METRIC_CATEGORIES:
        for name in metric_names:
            formula, source = report.METRIC_META.get(name, ("-", "-"))
            lines.append(f"| `{name}` | {formula} | {source} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 横向对比表
    lines.append("## 二、画像横向对比（各画像跨轮平均值）")
    lines.append("")
    
    all_metric_names = []
    for _, metric_names in report.METRIC_CATEGORIES:
        all_metric_names.extend(metric_names)
    
    header = "| 画像 | " + " | ".join(f"`{name}`" for name in all_metric_names) + " |"
    sep = "|---|" + "|".join("---" for _ in all_metric_names) + "|"
    lines.append(header)
    lines.append(sep)

    for p in profiles:
        row = [f"profile_{p}"]
        for _ in all_metric_names:
            row.append("-")
        lines.append("| " + " | ".join(row) + " |")

    grand_row = ["**总体平均**"]
    for _ in all_metric_names:
        grand_row.append("-")
    lines.append("| " + " | ".join(grand_row) + " |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 各画像详情
    lines.append("## 三、各画像详情")
    lines.append("")
    for p in profiles:
        lines.append(f"### profile_{p}")
        lines.append("")
        lines.append(f"- 测试快照目录：`artifacts/multi-{p}`")
        lines.append(f"- 轮次数：{len(rounds)}")
        lines.append("")

        # 轮次汇总
        lines.append("#### 轮次汇总（所有指标）")
        lines.append("")
        
        header = "| 指标 | " + " | ".join(f"R{r:02d}" for r in rounds) + " | 平均 |"
        sep = "|---|" + "|".join("---" for _ in rounds) + "|---|"
        lines.append(header)
        lines.append(sep)

        for name in all_metric_names:
            row = [f"`{name}`"]
            for _ in rounds:
                row.append("-")
            row.append("-")
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")

        # 外部 LLM 评分
        lines.append("#### 外部 LLM 评分轮次汇总")
        lines.append("")
        
        llm_dim_labels = [label for _, label in report.LLM_SCORING_DIMENSIONS]
        llm_header = ["指标"] + [f"R{r:02d}" for r in rounds] + ["平均"]
        lines.append("| " + " | ".join(llm_header) + " |")
        lines.append("|---|" + "|".join("---" for _ in rounds) + "|---|")

        for dim_label in llm_dim_labels:
            row_cells = [f"`{dim_label}`"]
            for _ in rounds:
                row_cells.append("-")
            row_cells.append("-")
            lines.append("| " + " | ".join(row_cells) + " |")
        
        # 总体评分
        row_cells = ["`总体评分`"]
        for _ in rounds:
            row_cells.append("-")
        row_cells.append("-")
        lines.append("| " + " | ".join(row_cells) + " |")
        
        lines.append("")

        # 各轮明细
        lines.append("#### 各轮明细")
        lines.append("")
        for r in rounds:
            lines.append(f"**round-{r:02d}**")
            lines.append("")
            for category_name, metric_names in report.METRIC_CATEGORIES:
                lines.append(f"**{category_name}**")
                lines.append("")
                for name in metric_names:
                    lines.append(f"- **{name}**: -")
                lines.append("")

        # 外部 LLM 评估详情
        lines.append("#### 外部 LLM 评估详情")
        lines.append("")
        for r in rounds:
            lines.append(f"**R{r:02d}** (模拟模型 @ 2024-01-01 00:00:00)")
            lines.append("")
            lines.append("- **总体评分**: -/-")
            lines.append("")
            lines.append("**各维度评分**:")
            lines.append("")
            for dim_label in llm_dim_labels:
                lines.append(f"- {dim_label}: -/-")
            lines.append("")
            lines.append("**分块评分**:")
            lines.append("")
            lines.append("| 分块 | 标题 | 主要评分 |")
            lines.append("|---|---|---|")
            lines.append("| 1 | 模拟分块 | - |")
            lines.append("")
            lines.append("**亮点**:")
            lines.append("- -")
            lines.append("")
            lines.append("**问题**:")
            lines.append("- -")
            lines.append("")
            lines.append("**建议**:")
            lines.append("- -")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 总体评估
    lines.append("## 四、总体评估（所有画像所有轮次）")
    lines.append("")
    for category_name, metric_names in report.METRIC_CATEGORIES:
        lines.append(f"**{category_name}**")
        lines.append("")
        lines.append("| 指标 | 总体平均 | 各画像平均 |")
        lines.append("|---|---|---|")
        for name in metric_names:
            lines.append(f"| `{name}` | - | - |")
        lines.append("")

    # 证据表
    lines.append("## 五、证据表")
    lines.append("")
    lines.append("| 证据名称 | 状态 |")
    lines.append("|---|---|")
    lines.append("| M4 差异化画像对照表 | - |")
    lines.append("| M5 知识库切片清单 | - |")
    lines.append("| M6 智能体职责分工与产物完整率 | - |")
    lines.append("| M7 资源形态清单 | - |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_报告由 report.py 自动生成 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    
    return "\n".join(lines)

if __name__ == "__main__":
    mock_report = generate_mock_report()
    
    # 保存到 results/reports 目录
    output_dir = _EVAL_DIR / "results" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "report_mock.md"
    
    output_path.write_text(mock_report, encoding="utf-8")
    print(f"✅ 模拟报告已生成: {output_path}")