"""评估指标计算脚本。

计算 6 个指标（按单轮定义，多轮取算术平均值）：

幻觉率：
  ① 专家互评异议率 = (🔴+🟡) / 总批注数 × 100%
  ② 裁判准确性评分 = 直接取 judge_report.md 中 准确性：X/5

匹配度：
  ① 难度符合度 = 题目难度≤上限的题数 / 总题数 × 100%
  ② 情感使用度 = 情感支持板块数 / 总板块数 × 100%

覆盖率：
  ① 本节知识点覆盖率 = |实际覆盖 ∩ 预设期望| / |预设期望| × 100%
  ② 薄弱点命中率 = 命中的薄弱点数 / 总薄弱点数 × 100%（weakness_kcs 为空时跳过）
  ③ 混淆对覆盖率 = 命中的混淆对数 / 总预设混淆对数 × 100%（confusable_pairs 为空时跳过）

CLI 用法：
  uv run python backend/tests/evaluation/program/calculate.py --profile B --round 1
  uv run python backend/tests/evaluation/program/calculate.py --profile B --round 1 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
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

_SYS_ARTIFACTS_DIR = common.SYS_ARTIFACTS_DIR
_EVAL_ARTIFACTS_DIR = common.EVAL_ARTIFACTS_DIR
_PROFILES_DIR = common.PROFILES_DIR
_KNOWLEDGE_DAG = _PROJECT_ROOT / "backend" / "app" / "curriculum" / "data" / "knowledge-dag.json"

# 情感支持板块类型
EMOTIONAL_BLOCK_TYPES = {
    "anchor_scenario", "worked_example", "decision_flow",
    "mnemonic", "summary_card", "analogy",
}

# 难度排序
DIFFICULTY_ORDER = {"L1": 1, "L2": 2, "L3": 3}


# ── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class MetricResult:
    """单个指标的计算结果。"""
    name: str
    value: float            # 百分比（0-100）或分数（1-5）
    unit: str               # "%" 或 "/5"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoundMetrics:
    """一轮的所有指标结果。"""
    profile_letter: str
    round_num: int
    metrics: list[MetricResult] = field(default_factory=list)


# ── 文件解析 ─────────────────────────────────────────────────────────────────

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_cross_review(text: str) -> dict[str, int]:
    """解析互评表格，统计 🔴/🟡/🟢/🔵 数量。

    表格格式：
    | 类别 | 位置 | 问题 | 修改建议 |
    |---|---|---|---|
    | 🔴 | ... | ... | ... |
    """
    counts = {"🔴": 0, "🟡": 0, "🟢": 0, "🔵": 0}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        # 跳过分隔行和表头
        if "---" in line or "类别" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]  # 去掉空元素
        if not cells:
            continue
        # 第一个 cell 是类别列
        first_cell = cells[0]
        for emoji in counts:
            if first_cell.startswith(emoji):
                counts[emoji] += 1
                break
    return counts


def _parse_judge_report(text: str) -> dict[str, Any]:
    """解析裁判报告，提取准确性评分和决策。"""
    result: dict[str, Any] = {"accuracy": 0, "decision": ""}
    # 准确性：5/5
    m = re.search(r"准确性[：:]\s*(\d+)\s*/\s*5", text)
    if m:
        result["accuracy"] = int(m.group(1))
    # 决策：accept / accept_with_minor_revision / revise
    m = re.search(
        r"决策[：:]\s*\*{0,2}(accept_with_minor_revision|accept|revise)\*{0,2}",
        text,
    )
    if m:
        result["decision"] = m.group(1)
    return result


def _parse_course_package(text: str) -> dict[str, Any]:
    """解析课程包，提取教学模块、题目难度、知识节点。"""
    result: dict[str, Any] = {
        "block_types": [],           # 教学模块清单中的 block_type 列
        "question_levels": [],       # 测评题目的难度标记 L1/L2/L3
        "knowledge_node_ids": [],    # 结构化数据中的 node_id
        "current_node_id": None,     # 当前教学节点
        "full_text": text,
    }

    # 1. 当前教学节点
    m = re.search(r"当前教学节点[：:]\s*`?([^`\n]+)`?", text)
    if m:
        result["current_node_id"] = m.group(1).strip()

    # 2. 教学模块清单表格
    lines = text.splitlines()
    in_table = False
    for line in lines:
        if "教学模块选择清单" in line:
            in_table = True
            continue
        if in_table:
            # 只有遇到下一个 ## 标题才退出表格（跳过表头前的列表/空行）
            if line.startswith("## "):
                in_table = False
                continue
            if line.startswith("|") and "---" not in line:
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c != ""]
                # 数据行：第一列是序号（数字）
                if len(cells) >= 2 and cells[0].isdigit():
                    # 第二列是 `block_type`，去掉反引号
                    bt = cells[1].strip(" `")
                    result["block_types"].append(bt)

    # 3. 测评题目的难度标记
    # 优先从 interactive_questions 结构化数据提取 difficulty 字段
    iq_match = re.search(
        r"## interactive_questions\s*```json\s*(\[.*?\])\s*```",
        text,
        re.DOTALL,
    )
    if iq_match:
        try:
            iq_list = json.loads(iq_match.group(1))
            for item in iq_list:
                diff = item.get("difficulty", "")
                if diff in ("L1", "L2", "L3"):
                    result["question_levels"].append(diff)
        except (json.JSONDecodeError, TypeError):
            pass
    # 回退：从正文匹配 **题目1（L1，...）** 或 **Q1（L1，...）**
    if not result["question_levels"]:
        for m in re.finditer(r"(?:题目|Q)\d+[（(]\s*(L[123])", text):
            result["question_levels"].append(m.group(1))

    # 4. 结构化数据中的 knowledge_points
    kp_match = re.search(
        r"## knowledge_points\s*```json\s*(\[.*?\])\s*```",
        text,
        re.DOTALL,
    )
    if kp_match:
        try:
            kp_list = json.loads(kp_match.group(1))
            result["knowledge_node_ids"] = [
                item.get("node_id", "")
                for item in kp_list
                if isinstance(item, dict)
            ]
        except json.JSONDecodeError:
            pass

    return result


def _parse_learning_path(text: str) -> dict[str, str]:
    """解析学习路径的难度上限表，返回 {node_name: 难度上限}。"""
    difficulty_limits: dict[str, str] = {}
    lines = text.splitlines()
    in_difficulty_table = False
    for line in lines:
        if "习题难度上限" in line:
            in_difficulty_table = True
            continue
        if in_difficulty_table:
            if line.startswith("|") and "---" not in line and "节点" not in line:
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c != ""]
                if len(cells) >= 2:
                    difficulty_limits[cells[0]] = cells[1]
            elif in_difficulty_table and not line.startswith("|") and line.strip():
                if not line.startswith(">"):
                    in_difficulty_table = False
    return difficulty_limits


def _load_node_name_map() -> dict[str, str]:
    """加载 knowledge-dag.json 的 node_id → node_name 映射。"""
    try:
        data = json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
        return {
            node["node_id"]: node["node_name"]
            for node in data.get("nodes", [])
        }
    except Exception:
        return {}


# ── 指标计算 ─────────────────────────────────────────────────────────────────

def calc_hallucination_expert_review(
    review_a_text: str, review_b_text: str,
) -> MetricResult:
    """幻觉率①：专家互评异议率 = (🔴+🟡) / 总批注数 × 100%"""
    counts_a = _parse_cross_review(review_a_text)
    counts_b = _parse_cross_review(review_b_text)

    total = sum(counts_a.values()) + sum(counts_b.values())
    issues = counts_a["🔴"] + counts_a["🟡"] + counts_b["🔴"] + counts_b["🟡"]
    rate = (issues / total * 100) if total > 0 else 0.0

    return MetricResult(
        name="专家互评异议率",
        value=round(rate, 1),
        unit="%",
        detail={
            "总批注数": total,
            "异议数(🔴+🟡)": issues,
            "expert_a": counts_a,
            "expert_b": counts_b,
        },
    )


def calc_hallucination_judge_accuracy(judge_text: str) -> MetricResult:
    """幻觉率②：裁判准确性评分 = 直接取 X/5"""
    judge = _parse_judge_report(judge_text)
    return MetricResult(
        name="裁判准确性评分",
        value=float(judge["accuracy"]),
        unit="/5",
        detail={
            "评分": f"{judge['accuracy']}/5",
            "决策": judge["decision"] or "未知",
        },
    )


def calc_matching_difficulty(
    course_text: str, path_text: str,
    node_name_map: dict[str, str],
) -> MetricResult:
    """匹配度①：难度符合度 = 题目难度≤上限的题数 / 总题数 × 100%"""
    course = _parse_course_package(course_text)
    difficulty_limits = _parse_learning_path(path_text)

    # 获取当前节点的中文名，用于在难度上限表中查找
    current_node_id = course["current_node_id"]
    current_node_name = node_name_map.get(current_node_id, "") if current_node_id else ""

    # 获取难度上限
    difficulty_limit = "L2"  # 默认
    if current_node_name and current_node_name in difficulty_limits:
        difficulty_limit = difficulty_limits[current_node_name]
    elif difficulty_limits:
        difficulty_limit = list(difficulty_limits.values())[0]

    limit_val = DIFFICULTY_ORDER.get(difficulty_limit, 2)

    question_levels = course["question_levels"]
    if not question_levels:
        return MetricResult(
            name="难度符合度",
            value=0.0,
            unit="%",
            detail={"error": "未找到测评题目难度标记"},
        )

    matched = sum(
        1 for q in question_levels if DIFFICULTY_ORDER.get(q, 0) <= limit_val
    )
    rate = matched / len(question_levels) * 100

    return MetricResult(
        name="难度符合度",
        value=round(rate, 1),
        unit="%",
        detail={
            "难度上限": difficulty_limit,
            "当前节点": current_node_name or current_node_id or "未知",
            "总题数": len(question_levels),
            "符合题数": matched,
            "各题难度": question_levels,
        },
    )


def calc_matching_emotional(course_text: str) -> MetricResult:
    """匹配度②：情感使用度 = 情感支持板块数 / 总板块数 × 100%"""
    course = _parse_course_package(course_text)
    block_types = course["block_types"]

    if not block_types:
        return MetricResult(
            name="情感使用度",
            value=0.0,
            unit="%",
            detail={"error": "未找到教学模块清单"},
        )

    emotional_count = sum(1 for bt in block_types if bt in EMOTIONAL_BLOCK_TYPES)
    rate = emotional_count / len(block_types) * 100

    return MetricResult(
        name="情感使用度",
        value=round(rate, 1),
        unit="%",
        detail={
            "总板块数": len(block_types),
            "情感支持板块数": emotional_count,
            "板块列表": block_types,
        },
    )


def calc_coverage_section(
    course_text: str, expected_content: dict[str, Any],
) -> MetricResult:
    """覆盖率①：本节知识点覆盖率 = |实际覆盖 ∩ 预设期望| / |预设期望| × 100%"""
    course = _parse_course_package(course_text)
    actual_nodes = set(course["knowledge_node_ids"])
    expected_nodes = set(expected_content.get("section_kcs", []))

    if not expected_nodes:
        return MetricResult(
            name="本节知识点覆盖率",
            value=0.0,
            unit="%",
            detail={"note": "expected 中 section_kcs 为空，跳过"},
        )

    intersection = actual_nodes & expected_nodes
    rate = len(intersection) / len(expected_nodes) * 100

    return MetricResult(
        name="本节知识点覆盖率",
        value=round(rate, 1),
        unit="%",
        detail={
            "实际覆盖": sorted(actual_nodes),
            "预设期望": sorted(expected_nodes),
            "交集": sorted(intersection),
        },
    )


def calc_coverage_weakness(
    course_text: str, expected_content: dict[str, Any],
) -> MetricResult:
    """覆盖率②：薄弱点命中率 = 命中的薄弱点数 / 总薄弱点数 × 100%"""
    weakness_kcs = expected_content.get("weakness_kcs", [])

    if not weakness_kcs:
        return MetricResult(
            name="薄弱点命中率",
            value=0.0,
            unit="%",
            detail={"note": "expected 中 weakness_kcs 为空，跳过"},
        )

    hit_list = [w for w in weakness_kcs if w in course_text]
    miss_list = [w for w in weakness_kcs if w not in course_text]
    rate = len(hit_list) / len(weakness_kcs) * 100

    return MetricResult(
        name="薄弱点命中率",
        value=round(rate, 1),
        unit="%",
        detail={
            "总薄弱点数": len(weakness_kcs),
            "命中数": len(hit_list),
            "命中": hit_list,
            "未命中": miss_list,
        },
    )


def calc_coverage_confusable(
    course_text: str, expected_content: dict[str, Any],
    node_name_map: dict[str, str],
) -> MetricResult:
    """覆盖率③：混淆对覆盖率 = 命中的混淆对数 / 总预设混淆对数 × 100%"""
    pairs = expected_content.get("confusable_pairs", [])

    if not pairs:
        return MetricResult(
            name="混淆对覆盖率",
            value=0.0,
            unit="%",
            detail={"note": "expected 中 confusable_pairs 为空，跳过"},
        )

    hit_pairs: list[list[str]] = []
    miss_pairs: list[list[str]] = []

    for pair in pairs:
        if len(pair) != 2:
            continue
        name_a = node_name_map.get(pair[0], pair[0])
        name_b = node_name_map.get(pair[1], pair[1])
        if name_a is None or name_b is None:
            continue
        # 检查两个中文名是否都在 course_package 全文中出现
        if name_a in course_text and name_b in course_text:
            hit_pairs.append(pair)
        else:
            miss_pairs.append(pair)

    rate = len(hit_pairs) / len(pairs) * 100

    return MetricResult(
        name="混淆对覆盖率",
        value=round(rate, 1),
        unit="%",
        detail={
            "总混淆对数": len(pairs),
            "命中数": len(hit_pairs),
            "命中": hit_pairs,
            "未命中": miss_pairs,
        },
    )


# ── 主入口 ──────────────────────────────────────────────────────────────────

def calculate_round(
    profile_letter: str,
    round_num: int,
    session_dir: Path | None = None,
    expected_path: Path | None = None,
) -> RoundMetrics:
    """计算指定画像指定轮次的全部指标。

    从测试快照目录 ``backend/tests/evaluation/artifacts/multi-{letter}/round-{NN}/``
    读取产物文件。该目录由 ``save_round_artifacts`` 从系统产物目录（UUID 命名）
    复制并规范命名而来。
    """
    # 1. 查找测试快照目录（multi-{letter}）
    if session_dir is None:
        session_dir = _EVAL_ARTIFACTS_DIR / f"multi-{profile_letter}"
    if not session_dir.exists():
        raise FileNotFoundError(
            f"找不到画像 {profile_letter} 的测试快照目录: {session_dir}"
        )

    # 2. 定位轮次目录（优先 round-NN 连字符，兼容 round_NN 下划线）
    round_dir = session_dir / f"round-{round_num:02d}"
    if not round_dir.exists():
        round_dir = session_dir / f"round_{round_num:02d}"
    if not round_dir.exists():
        raise FileNotFoundError(
            f"找不到轮次目录: {session_dir}/round-{round_num:02d}"
            f"（也试了 round_{round_num:02d}）"
        )

    # 3. 读取产物文件（全部从 round 目录读，包括 learning_path.md）
    course_text = _read_text(round_dir / "course_package.md")
    judge_text = _read_text(round_dir / "judge_report.md")
    review_a_text = _read_text(round_dir / "expert_a_cross_review.md")
    review_b_text = _read_text(round_dir / "expert_b_cross_review.md")
    path_text = _read_text(round_dir / "learning_path.md")

    # 4. 读取 expected 文件（优先新格式 expected_X_NN.json，兼容旧格式 expected_X.json）
    if expected_path is None:
        for candidate in (
            _PROFILES_DIR / f"expected_{profile_letter}_{round_num:02d}.json",
            _PROFILES_DIR / f"expected_{profile_letter}.json",
        ):
            if candidate.exists():
                expected_path = candidate
                break
    if expected_path is None or not expected_path.exists():
        raise FileNotFoundError(
            f"找不到 expected 文件（已尝试 expected_{profile_letter}_{round_num:02d}.json "
            f"和 expected_{profile_letter}.json）"
        )

    expected_data = json.loads(expected_path.read_text(encoding="utf-8"))
    expected_content = expected_data.get("expected_course_content", {})

    # 5. 加载 node_id → node_name 映射
    node_name_map = _load_node_name_map()

    # 6. 计算全部指标
    rm = RoundMetrics(profile_letter=profile_letter, round_num=round_num)

    # 幻觉率
    rm.metrics.append(
        calc_hallucination_expert_review(review_a_text, review_b_text)
    )
    rm.metrics.append(calc_hallucination_judge_accuracy(judge_text))

    # 匹配度
    rm.metrics.append(
        calc_matching_difficulty(course_text, path_text, node_name_map)
    )
    rm.metrics.append(calc_matching_emotional(course_text))

    # 覆盖率
    rm.metrics.append(calc_coverage_section(course_text, expected_content))
    rm.metrics.append(calc_coverage_weakness(course_text, expected_content))
    rm.metrics.append(
        calc_coverage_confusable(course_text, expected_content, node_name_map)
    )

    return rm


def format_result(rm: RoundMetrics) -> str:
    """格式化输出结果。"""
    lines = [
        f"\n{'=' * 60}",
        f"画像: profile_{rm.profile_letter}  轮次: round-{rm.round_num:02d}",
        f"{'=' * 60}",
        "",
        "【幻觉率 — 系统自评】",
    ]

    for m in rm.metrics[:2]:
        lines.append(f"  {m.name}: {m.value}{m.unit}")
        for k, v in m.detail.items():
            lines.append(f"    · {k}: {v}")

    lines.append("")
    lines.append("【匹配度】")

    for m in rm.metrics[2:4]:
        lines.append(f"  {m.name}: {m.value}{m.unit}")
        for k, v in m.detail.items():
            lines.append(f"    · {k}: {v}")

    lines.append("")
    lines.append("【覆盖率】")

    for m in rm.metrics[4:]:
        lines.append(f"  {m.name}: {m.value}{m.unit}")
        for k, v in m.detail.items():
            lines.append(f"    · {k}: {v}")

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="评估指标计算脚本")
    p.add_argument("--profile", required=True, help="画像字母（如 B）")
    p.add_argument("--round", type=int, default=1, help="轮次编号（如 1，默认 1）")
    p.add_argument("--session-dir", type=Path, default=None, help="系统产物目录（可选）")
    p.add_argument("--expected", type=Path, default=None, help="expected 文件路径（可选）")
    p.add_argument("--json", action="store_true", help="输出 JSON 格式")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        rm = calculate_round(
            profile_letter=args.profile,
            round_num=args.round,
            session_dir=args.session_dir,
            expected_path=args.expected,
        )
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return 1

    if args.json:
        result = {
            "profile_letter": rm.profile_letter,
            "round_num": rm.round_num,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "detail": m.detail,
                }
                for m in rm.metrics
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_result(rm))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
