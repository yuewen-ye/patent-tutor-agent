"""评估报告生成脚本 — v3（M1~M6 新分类 · 三张表 · 每画像五段式）

报告结构：
  完整报告（多画像汇总）:
    1. 概览
    2. 指标说明
    3. 三张主表 — 脚本计算指标 / 外部LLM评价指标 / 问答质量测试指标
       每张表 X轴 = 指标, Y轴 = 各画像 + 平均值
    4. 各画像详情（画像信息 / 三张表 / 外部LLM文字评价 / 各轮明细）
    5. 证据表

  单画像报告:
    1. 概览
    2. 指标说明
    3. 画像指标汇总表（X轴=指标, Y轴=轮次+平均值）
    4. 各轮详细指标说明（含 MetricResult.detail 原始数据）
    5. 证据表

CLI 用法:
  uv run python backend/tests/evaluation/program/report.py
  uv run python backend/tests/evaluation/program/report.py --profile B
  uv run python backend/tests/evaluation/program/report.py --output report.md
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

import _common as common  # noqa: E402
import calculate  # noqa: E402

REPORTS_DIR = _EVAL_DIR / "results" / "reports"

def _resolve_llm_results_dir(learner_prefix: str = "multi") -> Path:
    """解析外部 LLM 结果目录：按类别隔离（record_{前缀}）。

    旧共享目录仅作为 multi 前缀的回退；非 multi 前缀绝不读共享池。
    """
    new_dir = common.llm_results_dir(learner_prefix)
    if learner_prefix != "multi" or new_dir.exists():
        return new_dir
    alt_dir = _EVAL_DIR / "results" / "reports" / "record"
    if alt_dir.exists():
        return alt_dir
    old_dir = _EVAL_DIR / "LLM" / "results"
    if old_dir.exists():
        return old_dir
    return new_dir

# ── LLM 维度映射（标签 → 内部 key） ────────────────────────────────────────

_LLM_DIM_KEY_MAP: dict[str, str] = {
    "上下文正确性(Context Correctness)": "context_correctness",
    "答案正确性(Correctness)": "correctness",
    "幻觉评估(Hallucination)": "hallucination",
    "有用性(Helpfulness)": "helpfulness",
    "相关性(Relevance)": "relevance",
}

# M1 外部LLM评估器维度（3概念）
_M1_LLM_DIMS: list[str] = [
    "上下文正确性",
    "答案正确性",
    "幻觉评估",
]

# M2 外部LLM评估器维度（2维度）
_M2_LLM_DIMS: list[str] = [
    "有用性",
    "相关性",
]

# ── 报告三张主表的指标分组 ────────────────────────────────────────────────

# 表1: 脚本计算指标（无需LLM，确定性计算）
_SCRIPT_METRICS: list[tuple[str, list[str]]] = [
    ("M1 幻觉率", [
        "1.1 闭环率",
        "1.2 裁判Agent准确性评分",
    ]),
    ("M2 匹配度", [
        "2.1 难度符合度",
        "2.4 动态迭代触发率",
    ]),
    ("M3 覆盖率", [
        "3.1 本节知识点覆盖率",
        "3.2 薄弱点命中率",
        "3.3 混淆对覆盖率",
    ]),
    ("M4 执行完整性", [
        "4.1 产物完整率",
        "4.2.1 资源大类数",
        "4.2.2 资源小类数",
    ]),
    ("M5 其它指标", [
        "5.3 PII合规检测",
        "5.4 异议率",
    ]),
]

# 表2: 外部LLM评价指标（需外部LLM评估结果）
_LLM_METRICS: list[tuple[str, list[str]]] = [
    ("M1 幻觉率", [
        "1.3.1 上下文正确性",
        "1.3.2 答案正确性",
        "1.3.3 幻觉评估",
        "1.4.1 事实性谬误率",
        "1.4.2 逻辑性谬误率",
        "1.4.3 指令性谬误率",
        "1.5.1 知识溯源可验证率",
        "1.5.2 溯源内容支撑率",
        "1.6 跨轮自洽率",
    ]),
    ("M2 匹配度", [
        "2.2 有用性",
        "2.3 相关性",
        "2.5 检索准确率",
        "2.5 检索完整率",
    ]),
]

# 表3: 问答质量测试指标（系统级单次测量）
_QA_METRICS: list[tuple[str, list[str]]] = [
    ("M6 问答质量测试", [
        "6.1 对抗稳健率",
        "6.2 边界拒答恰当率",
    ]),
]

# 完整报告三张主表（分组名 + 指标列表）
THREE_TABLES: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("脚本计算指标", _SCRIPT_METRICS),
    ("外部LLM评价指标", _LLM_METRICS),
    ("问答质量测试指标", _QA_METRICS),
]

# 所有指标的扁平有序列表（用于查找和遍历）
ALL_METRIC_NAMES: list[str] = []
for _table_name, groups in THREE_TABLES:
    for _group_name, metrics in groups:
        for m in metrics:
            if m not in ALL_METRIC_NAMES:
                ALL_METRIC_NAMES.append(m)

# 系统级指标（问答质量测试表，所有画像共享同一数值）
SYSTEM_LEVEL_METRICS: list[str] = [
    "6.1 对抗稳健率",
    "6.2 边界拒答恰当率",
]

# 独立于画像的系统级指标（展示时需独立处理）
INDEPENDENT_SYSTEM_METRICS: list[str] = [
    "6.1 对抗稳健率",
    "6.2 边界拒答恰当率",
]

# ── 指标说明：name → (计算公式, 数据来源) ──────────────────────────────────

METRIC_META: dict[str, tuple[str, str]] = {
    # M1 幻觉率
    "1.1 闭环率": (
        "闭环条数 / 总🔴条数 × 100%（外部LLM判定）",
        "round_indicator_{model}_{profile}_{round}.json > objection_loop（round-indicator.md 外部LLM评估）",
    ),
    "1.2 裁判Agent准确性评分": (
        "直接取 X/5",
        "judge_report.md",
    ),
    "1.3.1 上下文正确性": (
        "外部LLM评估：事实准确性+关键信息完整性（0-100分）",
        "round_indicator_{model}_{profile}_{round}.json > overall.scores.context_correctness（round-indicator.md 外部LLM评估）",
    ),
    "1.3.2 答案正确性": (
        "外部LLM评估：生成内容与专利法/实践/逻辑的一致性（0-100分）",
        "round_indicator_{model}_{profile}_{round}.json > overall.scores.correctness（round-indicator.md 外部LLM评估）",
    ),
    "1.3.3 幻觉评估": (
        "外部LLM评估：与客观事实/可验证数据/逻辑推理相违背的内容比例（0-100分）",
        "round_indicator_{model}_{profile}_{round}.json > overall.scores.hallucination（round-indicator.md 外部LLM评估）",
    ),
    "1.4.1 事实性谬误率": (
        "事实性错误陈述数 / 事实性陈述总数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > statement（round-indicator.md 外部LLM评估）",
    ),
    "1.4.2 逻辑性谬误率": (
        "逻辑性错误陈述数 / 逻辑性陈述总数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > statement（round-indicator.md 外部LLM评估）",
    ),
    "1.4.3 指令性谬误率": (
        "指令性错误陈述数 / 指令性陈述总数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > statement（round-indicator.md 外部LLM评估）",
    ),
    "1.5.1 知识溯源可验证率": (
        "完全验证的带来源陈述数 / 带来源陈述总数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > statement（round-indicator.md 外部LLM评估）",
    ),
    "1.5.2 溯源内容支撑率": (
        "内容支撑的带来源陈述数 / 带来源陈述总数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > statement（round-indicator.md 外部LLM评估）",
    ),
    "1.6 跨轮自洽率": (
        "1 - 矛盾事实点数 / 总事实点数 × 100%",
        "profile_indicator_{model}_{profile}.json > cross_round（profile-indicator.md 外部LLM评估）",
    ),
    # M2 匹配度
    "2.1 难度符合度": (
        "L_low ≤ 题.difficulty ≤ L_high 的题数 / 总题数 × 100%（双边区间）",
        "course_package.md + learning_path.md + learner_profile_update.md",
    ),
    "2.2 有用性": (
        "外部LLM评估：内容对学员的实际帮助程度，含清晰性/友好性（0-100分）",
        "round_indicator_{model}_{profile}_{round}.json > overall.scores.helpfulness（round-indicator.md 外部LLM评估）",
    ),
    "2.3 相关性": (
        "外部LLM评估：内容与学习主题的聚焦程度，无冗余/跑题（0-100分）",
        "round_indicator_{model}_{profile}_{round}.json > overall.scores.relevance（round-indicator.md 外部LLM评估）",
    ),
    "2.4 动态迭代触发率": (
        "每轮：是否触发动态迭代（|Δpl| ≥ 0.05 的节点变化），画像级：触发轮次数 / 有效轮次数 × 100%",
        "learner_profile_update.md（跨轮比对，分母 n-1）",
    ),
    "2.5 检索准确率": (
        "准确检索chunk数 / 总检索chunk数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > retrieval（round-indicator.md 外部LLM评估）",
    ),
    "2.5 检索完整率": (
        "完整检索chunk数 / 总检索chunk数 × 100%",
        "round_indicator_{model}_{profile}_{round}.json > retrieval（round-indicator.md 外部LLM评估）",
    ),
    # M3 覆盖率
    "3.1 本节知识点覆盖率": (
        "|累计实际(含祖先) ∩ learning_path 全量| / |learning_path 全量| × 100%",
        "course_package.md + learning_path.md + knowledge-dag.json",
    ),
    "3.2 薄弱点命中率": (
        "命中的薄弱点数 / 总薄弱点数 × 100%",
        "course_package.md + expected_*.json",
    ),
    "3.3 混淆对覆盖率": (
        "命中的混淆对数 / 总预设混淆对数 × 100%",
        "course_package.md + expected_*.json",
    ),
    # M4 执行完整性
    "4.1 产物完整率": (
        "存在文件数 / 应有文件数 × 100%",
        "round-*/ 目录下的产物文件",
    ),
    "4.2.1 资源大类数": (
        "统计课程中覆盖的资源大类总数",
        "course_package.md（脚本解析）",
    ),
    "4.2.2 资源小类数": (
        "统计课程中实际使用的资源小类总数",
        "course_package.md（脚本解析）",
    ),
    # M5 其它指标
    "5.3 PII合规检测": (
        "LLM 评估课程内容中的 PII 合规性（替代原正则扫描）",
        "round_indicator_{model}_{profile}_{round}.json > pii（round-indicator.md 外部LLM评估）",
    ),
    "5.4 异议率": (
        "(🔴+🟡) / 总批注数 × 100%",
        "expert_a_cross_review.md + expert_b_cross_review.md",
    ),
    # M6 问答质量测试
    "6.1 对抗稳健率": (
        "通过对抗探针题数 / 总对抗探针题数 × 100%（系统级独立评估）",
        "system_indicator_{model}.json > m6_adversarial（system-indicator.md 系统级外部LLM评估）",
    ),
    "6.2 边界拒答恰当率": (
        "恰当拒答题数 / 总边界探针题数 × 100%（系统级独立评估）",
        "system_indicator_{model}.json > m6_boundary（system-indicator.md 系统级外部LLM评估）",
    ),
}

# 指标名规范化映射：calculate.MetricResult.name → 统一展示名
_RENAME_MAP: dict[str, str] = {
    "1.1 闭环率": "1.1 闭环率",
    "1.2 裁判Agent准确性评分": "1.2 裁判Agent准确性评分",
    "5.4 异议率": "5.4 异议率",
    "上下文正确性(Context Correctness)": "1.3.1 上下文正确性",
    "答案正确性(Correctness)": "1.3.2 答案正确性",
    "幻觉评估(Hallucination)": "1.3.3 幻觉评估",
    "1.4.1 事实性谬误率": "1.4.1 事实性谬误率",
    "1.4.2 逻辑性谬误率": "1.4.2 逻辑性谬误率",
    "1.4.3 指令性谬误率": "1.4.3 指令性谬误率",
    "1.5.1 知识溯源可验证率": "1.5.1 知识溯源可验证率",
    "1.5.2 溯源内容支撑率": "1.5.2 溯源内容支撑率",
    "1.6 跨轮自洽率": "1.6 跨轮自洽率",
    "2.1 难度符合度": "2.1 难度符合度",
    "有用性(Helpfulness)": "2.2 有用性",
    "相关性(Relevance)": "2.3 相关性",
    "2.4 动态迭代触发率": "2.4 动态迭代触发率",
    "2.5 检索准确率": "2.5 检索准确率",
    "2.5 检索完整率": "2.5 检索完整率",
    "3.1 本节知识点覆盖率": "3.1 本节知识点覆盖率",
    "3.2 薄弱点命中率": "3.2 薄弱点命中率",
    "3.3 混淆对覆盖率": "3.3 混淆对覆盖率",
    "4.1 产物完整率": "4.1 产物完整率",
    "4.2.1 资源大类数": "4.2.1 资源大类数",
    "4.2.2 资源小类数": "4.2.2 资源小类数",
    "5.3 PII合规检测": "5.3 PII合规检测",
    "6.1 对抗稳健率": "6.1 对抗稳健率",
    "6.2 边界拒答恰当率": "6.2 边界拒答恰当率",
}

# 反向映射：展示名 → 计算侧名称（用于在 calculate.py 返回的列表中查找）
_DISPLAY_TO_OLD: dict[str, str] = {v: k for k, v in _RENAME_MAP.items()}

# 直接映射：展示名 → LLM 维度 key（用于把 1.3.1 等展示名翻译回 LLM 维度）
_DISPLAY_TO_LLM_DIM: dict[str, str] = {
    "1.3.1 上下文正确性": "上下文正确性(Context Correctness)",
    "1.3.2 答案正确性": "答案正确性(Correctness)",
    "1.3.3 幻觉评估": "幻觉评估(Hallucination)",
    "2.2 有用性": "有用性(Helpfulness)",
    "2.3 相关性": "相关性(Relevance)",
}

# ── 证据表 ──────────────────────────────────────────────────────────────────

REFERENCE_DIR = _EVAL_DIR / "doc" / "reference"

EVIDENCE_TABLES: list[tuple[str, str]] = [
    ("M4 差异化画像对照表", "M4_画像对照表.md"),
    ("M5 知识库切片清单", "M5_知识库切片清单.md"),
    ("M6 智能体职责分工与产物完整率", "M6_智能体职责分工与产物完整率.md"),
    ("M7 资源形态清单", "M7_资源形态清单.md"),
]


def _append_evidence_tables(lines: list[str]) -> None:
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 五、证据表")
    lines.append("")
    for title, filename in EVIDENCE_TABLES:
        filepath = REFERENCE_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").strip()
            lines.append(f"### {title}")
            lines.append("")
            lines.append(content)
            lines.append("")
        else:
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"_（证据文件 {filename} 不存在，跳过）_")
            lines.append("")


# ── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class ProfileReport:
    profile_letter: str
    session_dir: Path
    rounds: list[calculate.RoundMetrics] = field(default_factory=list)


@dataclass
class ReportContext:
    profile_letter: str
    session_dir: Path
    rounds: list[calculate.RoundMetrics]
    generated_at: str
    llm_results: dict[str, Any] = field(default_factory=dict)
    profile_level_metrics: list[calculate.MetricResult] = field(default_factory=list)


@dataclass
class FullReportContext:
    profiles: list[ProfileReport]
    generated_at: str
    llm_eval_results: dict[str, Any] = field(default_factory=dict)
    profile_level_metrics: list[calculate.MetricResult] = field(default_factory=list)


# ── 外部 LLM 评估结果读取 ─────────────────────────────────────────────────────


def _is_failed_marker(section_data: Any) -> bool:
    """LLM 评估失败写入的失败标记（status=failed）→ 报告按无结果处理。"""
    return isinstance(section_data, dict) and section_data.get("status") == "failed"


def _load_llm_eval_results(learner_prefix: str = "multi") -> dict[str, Any]:
    """从新的聚合产物目录加载评估结果。

    统一文件体系（每个提示词对应一份聚合 JSON）：
    - 轮次级：round_indicator_{model}_{profile}_{round:02d}.json
      内含 section：overall / statement / retrieval / resource_morphology / pii / objection_loop
    - 画像级：profile_indicator_{model}_{profile}.json
      内含 section：cross_round
    - 系统级：system_indicator_{model}.json
      内含 section：m6_adversarial / m6_boundary
    """
    results: dict[str, Any] = {}
    llm_dir = _resolve_llm_results_dir(learner_prefix)
    if not llm_dir.exists():
        return results

    def _store(profile_id: str, round_num: int, key: str, data: Any) -> None:
        if profile_id not in results:
            results[profile_id] = {}
        if round_num not in results[profile_id]:
            results[profile_id][round_num] = {}
        results[profile_id][round_num][key] = data

    # 轮次级：round_indicator_{model}_{profile}_{round:02d}.json
    for json_file in sorted(llm_dir.glob("round_indicator_*_*_*.json")):
        # 排除 pii / statement / resource / retrieval / objection 等旧拆分名；
        # 新的聚合名格式是 round_indicator_{model}_{profile}_{NN}.json 共 4 段
        stem = json_file.stem
        parts = stem.split("_")
        # round_indicator_{model}_{profile}_{NN} 共 5 段下划线切出的部分?
        # round_indicator_A_B_01 → split("_") = ["round","indicator","A","B","01"]
        if len(parts) != 5:
            continue
        if parts[0] != "round" or parts[1] != "indicator":
            continue
        if not parts[4].isdigit():
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        metadata = data.get("metadata", {})
        profile_id = metadata.get("profile_id", "") or parts[3]
        round_num = metadata.get("round", 0) or int(parts[4])
        if not profile_id or not round_num:
            continue
        # overall → judge_eval
        if "overall" in data and not _is_failed_marker(data["overall"]):
            _store(profile_id, round_num, "judge_eval",
                   {"metadata": metadata, "overall_evaluation": data["overall"]})
        # statement → statement_eval
        if "statement" in data and not _is_failed_marker(data["statement"]):
            _store(profile_id, round_num, "statement_eval",
                   {"metadata": metadata, **data["statement"]})
        # resource_morphology → m7_resource
        if "resource_morphology" in data and not _is_failed_marker(data["resource_morphology"]):
            _store(profile_id, round_num, "m7_resource",
                   {"metadata": metadata, "raw_llm_response": data["resource_morphology"]})
        # retrieval → m2_retrieval
        if "retrieval" in data and not _is_failed_marker(data["retrieval"]):
            _store(profile_id, round_num, "m2_retrieval",
                   {"metadata": metadata, **data["retrieval"]})
        # pii → pii_compliance
        if "pii" in data and not _is_failed_marker(data["pii"]):
            _store(profile_id, round_num, "pii_compliance",
                   {"metadata": metadata, **data["pii"]})
        # objection_loop → objection_eval（用于 1.1 闭环率，若 calculate.py 需要）
        if "objection_loop" in data and not _is_failed_marker(data["objection_loop"]):
            _store(profile_id, round_num, "objection_eval",
                   {"metadata": metadata, **data["objection_loop"]})

    # 画像级：profile_indicator_{model}_{profile}.json
    for json_file in sorted(llm_dir.glob("profile_indicator_*_*.json")):
        stem = json_file.stem
        parts = stem.split("_")
        # profile_indicator_{model}_{profile} → ["profile","indicator", model, profile]
        if len(parts) != 4:
            continue
        if parts[0] != "profile" or parts[1] != "indicator":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        metadata = data.get("metadata", {})
        profile_id = metadata.get("profile_id", "") or parts[3]
        if not profile_id:
            continue
        if "cross_round" in data and not _is_failed_marker(data["cross_round"]):
            if profile_id not in results:
                results[profile_id] = {}
            results[profile_id]["_m14"] = {"metadata": metadata, **data["cross_round"]}

    # 系统级：system_indicator_{model}.json
    for json_file in sorted(llm_dir.glob("system_indicator_*.json")):
        stem = json_file.stem
        # 排除旧的带 _system / _boundary / _adversarial 后缀名
        # system_indicator_{model} → 三段式
        parts = stem.split("_")
        if len(parts) != 3:
            continue
        if parts[0] != "system" or parts[1] != "indicator":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "system" not in results:
            results["system"] = {}
        if "m6_adversarial" in data and not _is_failed_marker(data["m6_adversarial"]):
            results["system"]["_m15"] = data["m6_adversarial"]
        if "m6_boundary" in data and not _is_failed_marker(data["m6_boundary"]):
            results["system"]["_m16"] = data["m6_boundary"]

    return results


def _load_profile_level_metrics(
    profile_letter: str | None = None, learner_prefix: str = "multi",
) -> list[calculate.MetricResult]:
    """加载系统级指标（M6 问答质量测试），独立于画像。"""
    return calculate.calculate_system_level_metrics(learner_prefix=learner_prefix)


def _has_llm_eval_for(profile_letter: str, round_num: int,
                      llm_results: dict[str, Any]) -> bool:
    return profile_letter in llm_results and round_num in llm_results[profile_letter]


def _has_judge_eval_for(profile_letter: str, round_num: int,
                        llm_results: dict[str, Any]) -> bool:
    return (_has_llm_eval_for(profile_letter, round_num, llm_results) and
            "judge_eval" in llm_results[profile_letter][round_num])


def _has_m7_eval_for(profile_letter: str, round_num: int,
                     llm_results: dict[str, Any]) -> bool:
    return (_has_llm_eval_for(profile_letter, round_num, llm_results) and
            "m7_resource" in llm_results[profile_letter][round_num])


def _get_llm_overall_scores(profile_letter: str, round_num: int,
                             llm_results: dict[str, Any]) -> dict[str, Any] | None:
    if not _has_judge_eval_for(profile_letter, round_num, llm_results):
        return None
    data = llm_results[profile_letter][round_num]["judge_eval"]
    overall = data.get("overall_evaluation", {})
    return overall.get("scores", {})


def _get_llm_overall_summary(profile_letter: str, round_num: int,
                               llm_results: dict[str, Any]) -> dict[str, Any]:
    if not _has_judge_eval_for(profile_letter, round_num, llm_results):
        return {}
    data = llm_results[profile_letter][round_num]["judge_eval"]
    overall = data.get("overall_evaluation", {})
    return {
        "summary": overall.get("overall_score", {}).get("summary", ""),
        "highlights": overall.get("highlights", []),
        "issues": overall.get("issues", []),
        "suggestions": overall.get("suggestions", []),
    }


def _get_m7_resource_scores(profile_letter: str, round_num: int,
                             llm_results: dict[str, Any]) -> dict[str, Any] | None:
    if not _has_m7_eval_for(profile_letter, round_num, llm_results):
        return None
    data = llm_results[profile_letter][round_num]["m7_resource"]
    raw = data.get("raw_llm_response", {})
    score = raw.get("overall_score", 0)
    if score == 0:
        return None
    return {"value": score, "unit": "分",
            "coverage_score": raw.get("coverage_score", 0),
            "fit_score": raw.get("fit_score", 0)}


# ── 路径查找 ─────────────────────────────────────────────────────────────────

def _find_session_dir(
    profile_letter: str, learner_prefix: str = "multi",
) -> Path | None:
    candidate = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{profile_letter}"
    return candidate if candidate.exists() else None


def _list_available_rounds(session_dir: Path) -> list[int]:
    rounds: list[int] = []
    if not session_dir.exists():
        return rounds
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
    letters: list[str] = []
    for d in common.EVAL_ARTIFACTS_DIR.glob(f"{learner_prefix}-*"):
        if d.is_dir():
            letter = d.name.split("-", 1)[1]
            if _list_available_rounds(d):
                letters.append(letter)
    return sorted(letters)


# ── 格式化 ───────────────────────────────────────────────────────────────────

def _format_value(value: float, unit: str) -> str:
    if unit == "/":
        return "/"
    if unit == "/5":
        return f"{value:.1f}/5"
    return f"{value:.1f}{unit}"


def _format_detail(v: Any) -> str:
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _display_to_old_name(display_name: str) -> str:
    return _DISPLAY_TO_OLD.get(display_name, display_name)


def _get_metric_value_for_round(
    profile_letter: str,
    round_num: int,
    display_name: str,
    llm_results: dict[str, Any],
    round_metrics: list[calculate.MetricResult],
    profile_level_metrics: list[calculate.MetricResult] | None = None,
) -> tuple[float, str] | None:
    """获取特定画像特定轮次的指标值（支持新旧名称映射）。"""
    old_name = _display_to_old_name(display_name)

    # LLM 评估器维度（展示名 → LLM 维度 key）
    llm_dim_key = _DISPLAY_TO_LLM_DIM.get(display_name) or _DISPLAY_TO_LLM_DIM.get(old_name)
    if llm_dim_key and llm_dim_key in _LLM_DIM_KEY_MAP:
        dim_key = _LLM_DIM_KEY_MAP[llm_dim_key]
        overall = _get_llm_overall_scores(profile_letter, round_num, llm_results)
        if overall:
            dim_data = overall.get(dim_key, {})
            score = dim_data.get("score", 0)
            max_score = dim_data.get("max", 100)
            if score > 0:
                return score, f"/{max_score}"
        return None

    # 查找规则计算指标
    for m in round_metrics:
        if m.name == old_name or m.name == display_name or _RENAME_MAP.get(m.name, m.name) == display_name:
            return m.value, m.unit

    # 查找外部 LLM 指标 (M7 资源形态)
    if old_name == "资源形态评估":
        m7_scores = _get_m7_resource_scores(profile_letter, round_num, llm_results)
        if m7_scores:
            return m7_scores.get("value", 0), m7_scores.get("unit", "分")

    # M14 跨轮自洽率（每画像一次，跨轮共享）
    if display_name == "1.6 跨轮自洽率":
        m14_data = llm_results.get(profile_letter, {}).get("_m14")
        if m14_data:
            return m14_data.get("self_consistency_rate", 0.0), "%"

    # M17 检索准确率/完整率（每画像每轮）
    if display_name in ("2.5 检索准确率", "2.5 检索完整率"):
        m17_data = llm_results.get(profile_letter, {}).get(round_num, {}).get("m2_retrieval")
        if m17_data:
            if display_name == "2.5 检索准确率":
                return m17_data.get("accurate_rate", 0.0), "%"
            elif display_name == "2.5 检索完整率":
                return m17_data.get("complete_rate", 0.0), "%"

    # 系统级指标（问答质量测试表）
    if profile_level_metrics:
        for m in profile_level_metrics:
            mapped = _RENAME_MAP.get(m.name, m.name)
            if mapped == display_name:
                return m.value, m.unit

    return None


def _metric_avg_for_profile(
    profile: ProfileReport,
    display_name: str,
    llm_results: dict[str, Any] | None = None,
    profile_level_metrics: list[calculate.MetricResult] | None = None,
) -> tuple[float, str] | None:
    """计算单个画像某指标的跨轮平均值（跳过 unit='/' 的轮次）。"""
    values_with_unit: list[tuple[float, str]] = []

    for rm in profile.rounds:
        result = _get_metric_value_for_round(
            profile.profile_letter, rm.round_num, display_name,
            llm_results or {}, rm.metrics, profile_level_metrics,
        )
        if result is not None and result[1] != "/":
            values_with_unit.append(result)

    if not values_with_unit:
        # 系统级指标（跨轮都返回同一个值）
        if profile_level_metrics:
            for m in profile_level_metrics:
                mapped = _RENAME_MAP.get(m.name, m.name)
                if mapped == display_name:
                    return m.value, m.unit
        return None
    avg = sum(v for v, _ in values_with_unit) / len(values_with_unit)
    return avg, values_with_unit[0][1]


def _collect_metric_names_for_table(
    table_metric_groups: list[tuple[str, list[str]]],
) -> list[str]:
    names: list[str] = []
    for _group, metrics in table_metric_groups:
        for m in metrics:
            names.append(m)
    return names


# ── Markdown 渲染：指标说明表 ────────────────────────────────────────────────

def _render_metric_meta_table() -> list[str]:
    lines: list[str] = []
    lines.append("| 指标 | 计算公式 | 数据来源 |")
    lines.append("|---|---|---|")
    for table_name, groups in THREE_TABLES:
        for group_name, metrics in groups:
            for name in metrics:
                formula, source = METRIC_META.get(name, ("-", "-"))
                suffix = "（系统级）" if name in SYSTEM_LEVEL_METRICS else ""
                lines.append(f"| `{name}`{suffix} | {formula} | {source} |")
    return lines


# ── Markdown 渲染：单张指标对比表 ────────────────────────────────────────────

def _render_comparison_table(
    table_metric_groups: list[tuple[str, list[str]]],
    profiles: list[ProfileReport],
    llm_results: dict[str, Any],
    profile_level_metrics: list[calculate.MetricResult],
) -> list[str]:
    """渲染一张指标对比表：X轴=指标, Y轴=各画像+平均值。"""
    lines: list[str] = []
    metric_names = _collect_metric_names_for_table(table_metric_groups)

    # 表头
    header = "| 指标 | " + " | ".join(f"`profile_{p.profile_letter}`" for p in profiles) + " | **总体平均** |"
    sep = "|---|" + "|".join("---" for _ in profiles) + "|---|"
    lines.append(header)
    lines.append(sep)

    # 数据行（按分组组织）
    for group_name, metrics in table_metric_groups:
        group_header = f"| **{group_name}** |" + "|".join("   " for _ in profiles) + "|   |"
        lines.append(group_header)
        for name in metrics:
            row = [f"`{name}`"]
            per_profile_avgs: list[float] = []
            unit = ""
            for p in profiles:
                result = _metric_avg_for_profile(
                    p, name, llm_results, profile_level_metrics,
                )
                if result is None:
                    row.append("-")
                else:
                    val, u = result
                    row.append(_format_value(val, u))
                    per_profile_avgs.append(val)
                    unit = u
            if per_profile_avgs:
                grand_avg = sum(per_profile_avgs) / len(per_profile_avgs)
                row.append(_format_value(grand_avg, unit))
            else:
                row.append("-")
            lines.append("| " + " | ".join(row) + " |")

    return lines


# ── Markdown 渲染：系统级指标表（两列格式） ────────────────────────────────────

def _render_system_level_table(
    table_metric_groups: list[tuple[str, list[str]]],
    profile_level_metrics: list[calculate.MetricResult],
) -> list[str]:
    """渲染系统级指标表：两列格式（指标 + 数值）。

    系统级指标（M6）独立于画像，所有画像共享同一数值。
    """
    lines: list[str] = []

    # 表头
    lines.append("| 指标 | **数值** |")
    lines.append("|---|---|")

    # 数据行（按分组组织）
    for group_name, metrics in table_metric_groups:
        group_header = f"| **{group_name}** | |"
        lines.append(group_header)
        for name in metrics:
            # 从 profile_level_metrics 中查找值
            value = "-"
            for m in profile_level_metrics:
                mapped = _RENAME_MAP.get(m.name, m.name)
                if mapped == name or m.name == name:
                    value = _format_value(m.value, m.unit)
                    break
            row = f"| `{name}` | {value} |"
            lines.append(row)

    return lines


# ── Markdown 渲染：M6 详细说明模块 ────────────────────────────────────────────

def _render_m6_detail_section(
    profile_level_metrics: list[calculate.MetricResult],
    llm_results: dict[str, Any] | None = None,
) -> list[str]:
    """渲染 M6 问答质量测试的详细说明模块。"""
    lines: list[str] = []

    lines.append("### 4.5 M6 问答质量测试详情")
    lines.append("")
    lines.append("M6 问答质量测试为**系统级独立评估**，所有画像共享同一结果。")
    lines.append("")

    # M6.1 对抗稳健率
    adv_metric = None
    bnd_metric = None
    for m in profile_level_metrics:
        mapped = _RENAME_MAP.get(m.name, m.name)
        if mapped == "6.1 对抗稳健率":
            adv_metric = m
        elif mapped == "6.2 边界拒答恰当率":
            bnd_metric = m

    # 获取 M6 原始评估数据
    sys_data = (llm_results or {}).get("system", {})
    adv_raw = sys_data.get("_m15", {})
    bnd_raw = sys_data.get("_m16", {})

    if adv_metric:
        lines.append("#### 6.1 对抗稳健率")
        lines.append("")
        lines.append(f"- **数值**: {_format_value(adv_metric.value, adv_metric.unit)}")
        lines.append(f"- **计算公式**: 通过对抗探针题数 / 总对抗探针题数 × 100%")
        lines.append(f"- **数据来源**: `system_indicator_*_system.json`（系统级外部LLM评估）")
        if adv_metric.detail:
            detail = adv_metric.detail
            if isinstance(detail, dict):
                total = detail.get("问题数", 0)
                passed = detail.get("通过数", 0)
                lines.append(f"- **统计**: 共 {total} 题，通过 {passed} 题")
        lines.append("")
        lines.append("**说明**: 本指标衡量系统在面对对抗性/陷阱性问题时的稳健程度。")
        lines.append("系统应能识别并正确处理这些精心设计的诱导性问题，而非被误导给出错误答案。")
        lines.append("")

        # 展示未通过的题目
        adv_evals = adv_raw.get("evaluations", []) if isinstance(adv_raw, dict) else []
        failed = [e for e in adv_evals if not e.get("passed", False)]
        if failed:
            lines.append(f"**未通过题目详情**（共 {len(failed)} 题）:")
            lines.append("")
            for i, ev in enumerate(failed, 1):
                question = ev.get("question", "")
                answer = ev.get("answer", "")
                reason = ev.get("reason", "")
                lines.append(f"**{i}. {question}**")
                lines.append(f"- 系统回答: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                if reason:
                    lines.append(f"- 未通过原因: {reason}")
                lines.append("")

    if bnd_metric:
        lines.append("#### 6.2 边界拒答恰当率")
        lines.append("")
        lines.append(f"- **数值**: {_format_value(bnd_metric.value, bnd_metric.unit)}")
        lines.append(f"- **计算公式**: 恰当拒答题数 / 总边界探针题数 × 100%")
        lines.append(f"- **数据来源**: `system_indicator_*_system.json`（系统级外部LLM评估）")
        if bnd_metric.detail:
            detail = bnd_metric.detail
            if isinstance(detail, dict):
                total = detail.get("问题数", 0)
                appropriate = detail.get("恰当数", 0)
                lines.append(f"- **统计**: 共 {total} 题，恰当拒答 {appropriate} 题")
        lines.append("")
        lines.append("**说明**: 本指标衡量系统在面对超出能力范围或边界问题时，能否恰当拒答而非编造信息。")
        lines.append("恰当拒答包括：坦诚告知用户该问题超出范围、引导用户查阅官方渠道、或提供有限但准确的信息。")
        lines.append("")

        # 展示未通过的题目
        bnd_evals = bnd_raw.get("evaluations", []) if isinstance(bnd_raw, dict) else []
        failed = [e for e in bnd_evals if not e.get("appropriate", False)]
        if failed:
            lines.append(f"**未通过题目详情**（共 {len(failed)} 题）:")
            lines.append("")
            for i, ev in enumerate(failed, 1):
                question = ev.get("question", "")
                answer = ev.get("answer", "")
                reason = ev.get("reason", "")
                lines.append(f"**{i}. {question}**")
                lines.append(f"- 系统回答: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                if reason:
                    lines.append(f"- 未通过原因: {reason}")
                lines.append("")

    if not adv_metric and not bnd_metric:
        lines.append("_（M6 指标数据未就绪，请先运行系统级探针和外部LLM评估）_")
        lines.append("")

    return lines


# ── Markdown 渲染：画像单表（轮次对比） ──────────────────────────────────────

def _render_profile_round_table(
    table_metric_groups: list[tuple[str, list[str]]],
    profile: ProfileReport,
    llm_results: dict[str, Any],
    profile_level_metrics: list[calculate.MetricResult],
) -> list[str]:
    """渲染画像的一张表：X轴=指标, Y轴=各轮次+平均值。"""
    lines: list[str] = []
    rounds = profile.rounds
    metric_names = _collect_metric_names_for_table(table_metric_groups)

    # 表头
    header = "| 指标 | " + " | ".join(f"R{rm.round_num:02d}" for rm in rounds) + " | 平均 |"
    sep = "|---|" + "|".join("---" for _ in rounds) + "|---|"
    lines.append(header)
    lines.append(sep)

    for group_name, metrics in table_metric_groups:
        group_header = f"| **{group_name}** |" + "|".join("   " for _ in rounds) + "|   |"
        lines.append(group_header)
        for name in metrics:
            row = [f"`{name}`"]
            values: list[float] = []
            skip_rounds: list[int] = []
            unit = ""
            for rm in rounds:
                result = _get_metric_value_for_round(
                    profile.profile_letter, rm.round_num, name,
                    llm_results, rm.metrics, profile_level_metrics,
                )
                if result is None:
                    row.append("-")
                else:
                    val, u = result
                    row.append(_format_value(val, u))
                    if u == "/":
                        skip_rounds.append(rm.round_num)
                    else:
                        values.append(val)
                        unit = u
            if values:
                avg = sum(values) / len(values)
                row.append(_format_value(avg, unit))
            else:
                # 系统级指标跨轮共享同一值
                sys_result = _metric_avg_for_profile(
                    profile, name, llm_results, profile_level_metrics,
                )
                if sys_result is not None:
                    val, u = sys_result
                    for i in range(len(rounds)):
                        if rounds[i].round_num not in skip_rounds:
                            row[i + 1] = _format_value(val, u)
                    row.append(_format_value(val, u))
                else:
                    row.append("-")
            lines.append("| " + " | ".join(row) + " |")

    return lines


# ── Markdown 渲染：单画像报告 ────────────────────────────────────────────────

def _render_markdown_single(ctx: ReportContext) -> str:
    """渲染单画像 Markdown 报告（五段式）。"""
    lines: list[str] = []
    rounds = ctx.rounds
    llm_results = ctx.llm_results or {}
    profile_letter = ctx.profile_letter
    profile_level_metrics = ctx.profile_level_metrics or []

    lines.append(f"# 评估报告 — profile_{profile_letter}")
    lines.append("")
    lines.append("## 一、概览")
    lines.append("")
    lines.append(f"- 画像：`profile_{profile_letter}`")
    lines.append(f"- 测试快照目录：`{ctx.session_dir}`")
    lines.append(f"- 测试轮次数：{len(rounds)}")
    lines.append(f"- 轮次列表：{', '.join(f'round-{rm.round_num:02d}' for rm in rounds)}")
    lines.append(f"- 报告生成时间：{ctx.generated_at}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 二、指标说明
    lines.append("## 二、指标说明")
    lines.append("")
    lines.extend(_render_metric_meta_table())
    lines.append("")
    lines.append("---")
    lines.append("")

    # 三、画像指标汇总表（三张表）
    lines.append("## 三、画像指标汇总")
    lines.append("")
    for table_name, table_groups in THREE_TABLES:
        lines.append(f"### {table_name}")
        lines.append("")
        if table_name == "问答质量测试指标":
            # 系统级指标使用两列格式
            lines.extend(_render_system_level_table(
                table_groups, profile_level_metrics,
            ))
        else:
            lines.extend(_render_profile_round_table(
                table_groups,
                ProfileReport(profile_letter, ctx.session_dir, rounds),
                llm_results, profile_level_metrics,
            ))
        lines.append("")

    # 四、五段式详情
    lines.append("## 四、画像详情")
    lines.append("")

    # 4.1 脚本计算指标
    lines.append("### 4.1 脚本计算指标")
    lines.append("")
    lines.extend(_render_profile_round_table(
        _SCRIPT_METRICS,
        ProfileReport(profile_letter, ctx.session_dir, rounds),
        llm_results, profile_level_metrics,
    ))
    lines.append("")

    # 4.2 外部LLM评价指标
    lines.append("### 4.2 外部LLM评价指标")
    lines.append("")
    lines.extend(_render_profile_round_table(
        _LLM_METRICS,
        ProfileReport(profile_letter, ctx.session_dir, rounds),
        llm_results, profile_level_metrics,
    ))
    lines.append("")

    # 4.3 外部LLM文字评价（如有）
    lines.append("### 4.3 外部LLM文字评价")
    lines.append("")
    has_text_eval = False
    for rm in rounds:
        summary = _get_llm_overall_summary(profile_letter, rm.round_num, llm_results)
        if summary and (summary.get("summary") or summary.get("highlights") or summary.get("issues")):
            has_text_eval = True
            lines.append(f"**round-{rm.round_num:02d}**")
            lines.append("")
            if summary.get("summary"):
                lines.append(f"- **总体评价**: {summary['summary']}")
            if summary.get("highlights"):
                lines.append(f"- **亮点**: {', '.join(summary['highlights'][:5])}")
            if summary.get("issues"):
                lines.append(f"- **问题**: {', '.join(summary['issues'][:5])}")
            if summary.get("suggestions"):
                lines.append(f"- **建议**: {', '.join(summary['suggestions'][:5])}")
            lines.append("")
    if not has_text_eval:
        lines.append("_（无外部LLM文字评价数据，请先运行外部LLM评估）_")
        lines.append("")

    # 4.4 各轮详细指标说明
    lines.append("### 4.4 各轮详细指标说明")
    lines.append("")
    for rm in rounds:
        lines.extend(_render_round_detail_section(
            profile_letter, rm, llm_results, profile_level_metrics,
        ))

    # 4.5 M6 问答质量测试详情（系统级独立展示）
    lines.append("")
    lines.extend(_render_m6_detail_section(profile_level_metrics, llm_results))

    # 五、证据表
    _append_evidence_tables(lines)

    lines.append("---")
    lines.append("")
    lines.append(f"_报告由 report.py v3 自动生成 @ {ctx.generated_at}_")
    lines.append("")
    return "\n".join(lines)


# ── Markdown 渲染：单轮详细指标说明 ──────────────────────────────────────────

def _render_round_detail_section(
    profile_letter: str,
    rm: calculate.RoundMetrics,
    llm_results: dict[str, Any],
    profile_level_metrics: list[calculate.MetricResult],
) -> list[str]:
    """渲染单轮的详细指标说明（展示 MetricResult.detail 原始数据）。"""
    lines: list[str] = []
    round_num = rm.round_num

    lines.append(f"**round-{round_num:02d}**")
    lines.append("")

    # 脚本计算指标详情
    for group_name, metrics in _SCRIPT_METRICS:
        group_header_shown = False
        for name in metrics:
            old_name = _display_to_old_name(name)
            metric = None
            for m in rm.metrics:
                if m.name == old_name or _RENAME_MAP.get(m.name, m.name) == name:
                    metric = m
                    break
            if metric is None:
                continue

            if not group_header_shown:
                lines.append(f"**{group_name}**")
                lines.append("")
                group_header_shown = True

            lines.append(f"- **{name}**: {_format_value(metric.value, metric.unit)}")
            detail = metric.detail or {}
            for k, v in detail.items():
                if isinstance(v, (list, dict)):
                    lines.append(f"    - {k}: {_format_detail(v)}")
                else:
                    lines.append(f"    - {k}: {v}")

    # 外部LLM评价指标详情（如果有）
    llm_detail_shown = False
    for group_name, metrics in _LLM_METRICS:
        group_header_shown = False
        for name in metrics:
            result = _get_metric_value_for_round(
                profile_letter, round_num, name,
                llm_results, rm.metrics, profile_level_metrics,
            )
            if result is None:
                continue

            if not llm_detail_shown:
                lines.append("**外部LLM评价指标详情**")
                lines.append("")
                llm_detail_shown = True

            if not group_header_shown:
                lines.append(f"- **{group_name}**:")
                group_header_shown = True

            val, u = result
            lines.append(f"    - {name}: {_format_value(val, u)}")

    # 外部LLM文字评价详情
    summary = _get_llm_overall_summary(profile_letter, round_num, llm_results)
    if summary and (summary.get("summary") or summary.get("issues")):
        lines.append("")
        lines.append("**外部LLM文字评价**")
        lines.append("")
        if summary.get("summary"):
            lines.append(f"- 总体评价: {summary['summary']}")
        if summary.get("highlights"):
            lines.append(f"- 亮点: {', '.join(str(h) for h in summary['highlights'][:5])}")
        if summary.get("issues"):
            lines.append(f"- 问题: {', '.join(str(i) for i in summary['issues'][:5])}")
        if summary.get("suggestions"):
            lines.append(f"- 建议: {', '.join(str(s) for s in summary['suggestions'][:5])}")

    lines.append("")
    return lines


# ── Markdown 渲染：完整报告 ──────────────────────────────────────────────────

def _render_markdown_full(ctx: FullReportContext) -> str:
    """渲染完整 Markdown 报告（多画像汇总，三张主表）。"""
    lines: list[str] = []
    profiles = ctx.profiles
    llm_results = ctx.llm_eval_results
    profile_level_metrics = ctx.profile_level_metrics

    lines.append("# 评估报告 — 完整汇总（v3）")
    lines.append("")
    lines.append("## 一、概览")
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

    # 二、指标说明
    lines.append("## 二、指标说明")
    lines.append("")
    lines.extend(_render_metric_meta_table())
    lines.append("")
    lines.append("---")
    lines.append("")

    # 三、三张主表
    lines.append("## 三、指标横向对比（三张主表）")
    lines.append("")
    for table_name, table_groups in THREE_TABLES:
        lines.append(f"### {table_name}")
        lines.append("")
        if table_name == "问答质量测试指标":
            # 系统级指标使用两列格式
            lines.extend(_render_system_level_table(
                table_groups, profile_level_metrics,
            ))
        else:
            lines.extend(_render_comparison_table(
                table_groups, profiles, llm_results, profile_level_metrics,
            ))
        lines.append("")

    lines.append("---")
    lines.append("")

    # 四、各画像详情
    lines.append("## 四、各画像详情")
    lines.append("")
    for p in profiles:
        letter = p.profile_letter
        lines.append(f"### profile_{letter}")
        lines.append("")
        lines.append(f"- 测试快照目录：`{p.session_dir}`")
        lines.append(f"- 轮次数：{len(p.rounds)}")
        lines.append("")

        # 三张表（M6 问答质量测试为系统级指标，不在画像详情中重复渲染）
        for table_name, table_groups in THREE_TABLES:
            if table_name == "问答质量测试指标":
                continue
            lines.append(f"#### {table_name}")
            lines.append("")
            lines.extend(_render_profile_round_table(
                table_groups, p, llm_results, profile_level_metrics,
            ))
            lines.append("")

        # 外部LLM文字评价
        lines.append("#### 外部LLM文字评价")
        lines.append("")
        has_text = False
        for rm in p.rounds:
            summary = _get_llm_overall_summary(letter, rm.round_num, llm_results)
            if summary and (summary.get("summary") or summary.get("highlights") or summary.get("issues")):
                has_text = True
                lines.append(f"- **R{rm.round_num:02d}**: {summary.get('summary', '')}")
        if not has_text:
            lines.append("_（无外部LLM文字评价数据）_")
        lines.append("")

        # 各轮详细指标说明
        lines.append("#### 各轮明细")
        lines.append("")
        for rm in p.rounds:
            lines.extend(_render_round_detail_section(
                letter, rm, llm_results, profile_level_metrics,
            ))

        lines.append("---")
        lines.append("")

    # 五、M6 问答质量测试详情（系统级独立展示）
    lines.append("## 五、M6 问答质量测试详情")
    lines.append("")
    lines.extend(_render_m6_detail_section(profile_level_metrics, llm_results))

    # 六、证据表
    _append_evidence_tables(lines)

    lines.append("---")
    lines.append("")
    lines.append(f"_报告由 report.py v3 自动生成 @ {ctx.generated_at}_")
    lines.append("")
    return "\n".join(lines)


# ── 核心计算：单画像 ────────────────────────────────────────────────────────

def _calculate_profile(
    profile_letter: str,
    session_dir: Path,
    max_round: int | None = None,
    learner_prefix: str = "multi",
) -> ProfileReport:
    pr = ProfileReport(
        profile_letter=profile_letter,
        session_dir=session_dir,
    )
    rounds_nums = _list_available_rounds(session_dir)
    if max_round is not None:
        rounds_nums = [r for r in rounds_nums if r <= max_round]

    prev_profile_update: str | None = None
    for r in rounds_nums:
        try:
            rm = calculate.calculate_round(
                profile_letter=profile_letter,
                round_num=r,
                session_dir=session_dir,
                prev_profile_update=prev_profile_update,
                learner_prefix=learner_prefix,
            )
            pr.rounds.append(rm)

            curr_update_path = session_dir / f"round-{r:02d}" / "feedback" / "learner_profile_update.md"
            if curr_update_path.exists():
                prev_profile_update = calculate._read_text(curr_update_path)
            else:
                prev_profile_update = None
        except FileNotFoundError as exc:
            print(f"  ⚠️ [profile_{profile_letter}] round-{r:02d} 跳过: {exc}")
        except Exception as exc:
            print(f"  ⚠️ [profile_{profile_letter}] round-{r:02d} 异常: {type(exc).__name__}: {exc}")
    return pr


# ── 生成：单画像 ────────────────────────────────────────────────────────────

def generate_report(
    profile_letter: str,
    *,
    session_dir: Path | None = None,
    learner_prefix: str = "multi",
    output_path: Path | None = None,
) -> Path | None:
    if session_dir is None:
        session_dir = _find_session_dir(profile_letter, learner_prefix)
    if session_dir is None:
        print(f"  ❌ 找不到画像 {profile_letter} 的测试快照目录")
        return None

    pr = _calculate_profile(profile_letter, session_dir, learner_prefix=learner_prefix)
    if not pr.rounds:
        print(f"  ❌ 画像 {profile_letter} 无可用的指标数据")
        return None

    llm_results = _load_llm_eval_results(learner_prefix)
    profile_level_metrics = _load_profile_level_metrics(learner_prefix=learner_prefix)

    ctx = ReportContext(
        profile_letter=profile_letter,
        session_dir=session_dir,
        rounds=pr.rounds,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        llm_results=llm_results,
        profile_level_metrics=profile_level_metrics,
    )
    md = _render_markdown_single(ctx)

    if output_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / f"report_{profile_letter}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return output_path


# ── 生成：完整报告 ──────────────────────────────────────────────────────────

def generate_full_report(
    *,
    learner_prefix: str = "multi",
    max_round: int | None = None,
    profile_ids: list[str] | None = None,
    output_path: Path | None = None,
) -> Path | None:
    if profile_ids is not None:
        letters = []
        for pid in profile_ids:
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
        pr = _calculate_profile(
            letter, session_dir, max_round=max_round, learner_prefix=learner_prefix,
        )
        if pr.rounds:
            profiles.append(pr)
        else:
            print(f"  [profile_{letter}] ⚠️ 无可用轮次数据，已跳过")

    if not profiles:
        print("  ❌ 所有画像均无可用数据")
        return None

    llm_eval_results = _load_llm_eval_results(learner_prefix)
    profile_level_metrics = _load_profile_level_metrics(learner_prefix=learner_prefix)

    ctx = FullReportContext(
        profiles=profiles,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        llm_eval_results=llm_eval_results,
        profile_level_metrics=profile_level_metrics,
    )
    md = _render_markdown_full(ctx)

    if output_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / "report_full.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    return output_path


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="评估报告生成脚本 v3（M1~M6 新分类）")
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