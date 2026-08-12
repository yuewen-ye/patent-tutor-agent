"""评估指标计算脚本。

计算 10 个指标（按单轮定义，多轮取算术平均值）：

M1 幻觉率（系统自评）：
  ① 专家互评异议率 = (🔴+🟡) / 总批注数 × 100%
  ② 裁判准确性评分 = 直接取 judge_report.md 中 准确性：X/5

M2 匹配度：
  ① 难度符合度 = L_low ≤ 题.difficulty ≤ L_high 的题数 / 总题数 × 100%
     - L_low: pl < 0.65 → L1; pl ≥ 0.65 → L2; 再封顶 difficulty_cap
     - 角色特例: weakness → L3, forward_probe → L1
     - L_high: 节点难度上限 (difficulty_cap)
  ② 资源形态评估（外部 LLM 优先，回退脚本计算）

M3 覆盖率：
  ① 本节知识点覆盖率（累计路径 + 祖先匹配）
  ② 薄弱点命中率
  ③ 混淆对覆盖率

M8 对话质量：
  异议闭环率（外部 LLM 判定）

M10 PII 合规：
  learner_profile_update.md / session_snapshot.json 正则白名单扫描

M11 动态迭代：
  动态迭代触发率（跨轮 pl 跃升判定）

M1/M9 外部 LLM 评估指标单独展示，不合并加权。

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

# 资源形态类型（与 resource_morphology_evaluator.md 定义的 13 种对齐，用于 M7 回退脚本计算）
RESOURCE_MORPHOLOGY_TYPES = {
    # 讲义类 (5)
    "knowledge_synthesis",
    "verbal_explanation",
    "summary_card",
    "mnemonic",
    "legal_anchor",
    # 实操指南类 (3)
    "worked_example",
    "anchor_scenario",
    "reflect_prompt",
    # 分阶题类 (1)
    "assessment",
    # 其他扩展类型 (4)
    "global_framework",
    "decision_flow",
    "common_pitfall",
    "predict_activate",
}

# 核心资源形态类别 —— 外部 LLM 评估时要求讲义/实操/分阶题三类均覆盖
RESOURCE_MORPHOLOGY_CORE_CATEGORIES = {
    "讲义类": {"knowledge_synthesis", "verbal_explanation", "summary_card", "mnemonic", "legal_anchor"},
    "实操指南类": {"worked_example", "anchor_scenario", "reflect_prompt"},
    "分阶题类": {"assessment"},
}

# 兼容别名：旧代码中 EMOTIONAL_BLOCK_TYPES 已重命名为 RESOURCE_MORPHOLOGY_TYPES
EMOTIONAL_BLOCK_TYPES = RESOURCE_MORPHOLOGY_TYPES

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
        "question_roles": [],         # 每个题目的角色 (source_tag): backward_review/forward_probe/weakness_probe
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

    # 3. 测评题目的难度标记和角色
    # 优先从 interactive_questions 结构化数据提取
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
                    # 提取 source_tag（角色）用于 M2 交叉校验
                    role = item.get("source_tag", item.get("role", ""))
                    result["question_roles"].append(role)
        except (json.JSONDecodeError, TypeError):
            pass
    # 回退：从正文匹配 **题目1（L1，...）** 或 **Q1（L1，...）**
    if not result["question_levels"]:
        for m in re.finditer(r"(?:题目|Q)\d+[（(]\s*(L[123])", text):
            result["question_levels"].append(m.group(1))
            result["question_roles"].append("")  # 回退时无角色信息

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


def _parse_learning_path_nodes(path_text: str) -> set[str]:
    """解析 learning_path.md 的全量节点集合。"""
    nodes = set()
    for m in re.finditer(r"\|\s*([^|\s]+)\s*\|", path_text):
        node_id = m.group(1).strip()
        if node_id and not node_id.startswith("---") and node_id != "节点":
            nodes.add(node_id)
    return nodes


def _expand_with_ancestors(nodes: set[str], dag: dict[str, Any]) -> set[str]:
    """扩展节点集：基于 knowledge-dag.json 的 predecessors 关系，覆盖子节点视为覆盖父节点。

    knowledge-dag.json 中每个节点有 predecessors 列表（前置依赖），
    即如果节点 A 的 predecessors 包含 B，说明 A 依赖于 B，B 是 A 的父节点。
    因此：覆盖子节点 A → 视为覆盖其父节点 B。
    """
    expanded = set(nodes)
    nodes_data = dag.get("nodes", [])

    # 构建 node_id -> predecessors 映射
    # 即 child_id -> [parent_id, parent_id, ...]
    predecessors_map: dict[str, list[str]] = {}
    for node in nodes_data:
        node_id = node.get("node_id", "")
        preds = node.get("predecessors", [])
        if node_id and preds:
            predecessors_map[node_id] = preds

    # 查找所有被覆盖节点的祖先（父节点、祖父节点...）
    def get_ancestors(node_id: str) -> set[str]:
        ancestors: set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            parents = predecessors_map.get(current, [])
            for parent in parents:
                if parent not in ancestors:
                    ancestors.add(parent)
                    queue.append(parent)
        return ancestors

    for node_id in list(nodes):
        ancestors = get_ancestors(node_id)
        expanded.update(ancestors)

    return expanded


def _load_knowledge_dag() -> dict[str, Any]:
    """加载 knowledge-dag.json，返回 dag 子对象（含 nodes）。

    knowledge-dag.json 顶层结构: {"meta": {...}, "dag": {"nodes": [...]}}
    本函数返回 data["dag"]，使调用方可直接访问 nodes。
    """
    try:
        data = json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
        return data.get("dag", {"nodes": [], "edges": []})
    except Exception:
        return {"nodes": [], "edges": []}


def _load_node_name_map() -> dict[str, str]:
    """加载 knowledge-dag.json 的 node_id → node_name 映射。"""
    try:
        data = json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
        dag_data = data.get("dag", {})
        return {
            node["node_id"]: node["node_name"]
            for node in dag_data.get("nodes", [])
        }
    except Exception:
        return {}


def _get_node_max_difficulty(path_text: str, node_id: str, node_name_map: dict[str, str]) -> str:
    """从 learning_path.md 获取指定节点的难度上限。"""
    difficulty_limits = _parse_learning_path(path_text)
    node_name = node_name_map.get(node_id, node_id)
    if node_name and node_name in difficulty_limits:
        return difficulty_limits[node_name]
    if difficulty_limits:
        return list(difficulty_limits.values())[0]
    return "L2"


def _extract_node_pls(profile_text: str) -> dict[str, float]:
    """从 learner_profile_update.md 提取 five_dimensions[node].pl。"""
    pls: dict[str, float] = {}
    try:
        data = json.loads(profile_text)
        if "five_dimensions" in data:
            for node_id, dims in data["five_dimensions"].items():
                if isinstance(dims, dict) and "pl" in dims:
                    pls[node_id] = float(dims["pl"])
    except json.JSONDecodeError:
        pass
    return pls


def _get_learner_difficulty_lower(
    profile_text: str | None,
    node_id: str,
    difficulty_cap: str = "L3",
    source_tag: str = "",
) -> str:
    """从 learner_profile_update.md 获取学员能力下限（与系统 _review_difficulty 对齐）。

    规则：
    - pl < 0.65 → L1
    - pl ≥ 0.65 → L2
    - 再封顶到 difficulty_cap: min(cap_rank, difficulty_rank)
    - 角色特例：
      - weakness / weakness_probe → 强制 L3
      - forward_probe → 强制 L1
      - backward_review → 不高于当前掌握（由调用方交叉校验）

    Args:
        profile_text: learner_profile_update.md 内容
        node_id: 当前教学节点 ID
        difficulty_cap: 节点难度上限（默认 L3）
        source_tag: 题目角色 (backward_review/forward_probe/weakness_probe)
    """
    source_tag_lower = source_tag.lower() if source_tag else ""

    # 角色特例：薄弱点 → L3
    if "weak" in source_tag_lower:
        return "L3"

    # 角色特例：forward probe → L1
    if "forward" in source_tag_lower and "probe" in source_tag_lower:
        return "L1"

    if not profile_text:
        base_diff = "L1"
    else:
        pls = _extract_node_pls(profile_text)
        pl = pls.get(node_id, 0.0)
        base_diff = "L1" if pl < 0.65 else "L2"

    # 封顶到 difficulty_cap
    cap_rank = DIFFICULTY_ORDER.get(difficulty_cap, 3)
    diff_rank = DIFFICULTY_ORDER.get(base_diff, 1)
    capped_rank = min(cap_rank, diff_rank)
    return f"L{capped_rank}"


def _check_difficulty_dropped(course_text: str, node_id: str) -> bool:
    """检查 course_package 中指定节点的习题是否降为 L1。"""
    course = _parse_course_package(course_text)
    # 如果题目难度都是 L1，视为下降
    if course["question_levels"] and all(q == "L1" for q in course["question_levels"]):
        return True
    return False


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


def _get_node_difficulty_cap(path_text: str, node_id: str, node_name_map: dict[str, str]) -> str:
    """从 learning_path.md 获取指定节点的 difficulty_cap（习题难度上限）。"""
    difficulty_limits = _parse_learning_path(path_text)
    node_name = node_name_map.get(node_id, node_id)
    if node_name and node_name in difficulty_limits:
        cap = difficulty_limits[node_name]
        if cap in ("L1", "L2", "L3"):
            return cap
    # 回退：返回第一个找到的难度上限
    if difficulty_limits:
        first_cap = list(difficulty_limits.values())[0]
        if first_cap in ("L1", "L2", "L3"):
            return first_cap
    return "L3"


def calc_matching_difficulty(
    course_text: str, path_text: str,
    node_name_map: dict[str, str],
    profile_update_text: str | None = None,
    current_node_id: str | None = None,
) -> MetricResult:
    """M2 难度适配准确率：双边区间匹配。

    公式：L_low ≤ 题.difficulty ≤ L_high 的题数 / 总题数 × 100%

    - L_high: 从 learning_path 获取的节点难度上限 (difficulty_cap)
    - L_low: 从 learner_profile_update 获取的学员能力下限
      - pl < 0.65 → L1; pl ≥ 0.65 → L2; 封顶 difficulty_cap
      - 角色特例: weakness → L3, forward_probe → L1
    - 角色交叉校验：
      - forward_probe 应为 L1
      - weakness_probe 应 ≥ L3
      - backward_review 不应高于当前掌握
    """
    course = _parse_course_package(course_text)

    # 获取当前节点 ID
    if not current_node_id:
        current_node_id = course["current_node_id"] or ""

    # 获取难度上限 (L_high)
    L_high = _get_node_difficulty_cap(path_text, current_node_id, node_name_map)
    high_val = DIFFICULTY_ORDER.get(L_high, 3)

    question_levels = course["question_levels"]
    question_roles = course.get("question_roles", [])

    if not question_levels:
        return MetricResult(
            name="难度符合度",
            value=0.0,
            unit="%",
            detail={
                "难度上限(L_high)": L_high,
                "节点难度上限(difficulty_cap)": L_high,
                "error": "未找到测评题目难度标记",
            },
        )

    matched = 0
    role_violations: list[str] = []
    role_details: list[dict[str, str]] = []

    for idx, q_diff in enumerate(question_levels):
        q_val = DIFFICULTY_ORDER.get(q_diff, 0)
        q_role = question_roles[idx] if idx < len(question_roles) else ""

        # 获取该题的 L_low（基于题目角色和学员状态）
        L_low = _get_learner_difficulty_lower(
            profile_update_text, current_node_id,
            difficulty_cap=L_high,
            source_tag=q_role,
        )
        low_val = DIFFICULTY_ORDER.get(L_low, 1)

        # 双边匹配：L_low ≤ 题.difficulty ≤ L_high
        is_matched = low_val <= q_val <= high_val
        if is_matched:
            matched += 1

        # 角色交叉校验
        q_role_lower = q_role.lower() if q_role else ""
        violation = None
        if "forward" in q_role_lower and "probe" in q_role_lower:
            if q_diff != "L1":
                violation = f"forward_probe 应为 L1，实际 {q_diff}"
        elif "weak" in q_role_lower:
            if q_val < 3:  # L3 = 3
                violation = f"weakness_probe 应 ≥ L3，实际 {q_diff}"
        elif "backward" in q_role_lower and "review" in q_role_lower:
            if q_val < low_val:
                violation = f"backward_review 难度({q_diff}) 低于学员能力下限({L_low})"

        if violation:
            role_violations.append(f"题{idx + 1}: {violation}")

        role_details.append({
            "题序号": str(idx + 1),
            "难度": q_diff,
            "角色": q_role or "无角色",
            "L_low": L_low,
            "L_high": L_high,
            "匹配": "✓" if is_matched else "✗",
        })

    rate = matched / len(question_levels) * 100

    return MetricResult(
        name="难度符合度",
        value=round(rate, 1),
        unit="%",
        detail={
            "学员适配下限(L_low)规则": "pl < 0.65→L1; pl ≥ 0.65→L2; 封顶 difficulty_cap",
            "节点难度上限(L_high/difficulty_cap)": L_high,
            "当前节点": current_node_id or "未知",
            "总题数": len(question_levels),
            "符合题数": matched,
            "双边匹配公式": "L_low ≤ 题.difficulty ≤ L_high",
            "角色交叉校验": f"通过 {len(question_levels) - len(role_violations)}/{len(question_levels)}",
            "角色违规": role_violations if role_violations else ["无违规"],
            "各题详情": role_details,
        },
    )


def calc_matching_emotional(course_text: str) -> MetricResult:
    """M7 回退脚本计算：资源形态评估。

    与外部 LLM 评估对齐：
    - 覆盖率 = 已出现的资源形态数 / 13 种已知类型
    - 三类核心形态（讲义/实操指南/分阶题）是否均覆盖
    - 综合分 = 覆盖率 * 0.4 + 核心覆盖 * 0.6
    """
    course = _parse_course_package(course_text)
    block_types = course["block_types"]

    if not block_types:
        return MetricResult(
            name="资源形态评估",
            value=0.0,
            unit="分",
            detail={"error": "未找到教学模块清单"},
        )

    # 统计出现的资源形态
    present_types = {bt for bt in block_types if bt in RESOURCE_MORPHOLOGY_TYPES}
    total_types = len(RESOURCE_MORPHOLOGY_TYPES)
    coverage_rate = round(len(present_types) / total_types * 100, 1)

    # 三类核心形态是否均覆盖
    core_coverage_flags = {
        cat: any(bt in present_types for bt in cat_types)
        for cat, cat_types in RESOURCE_MORPHOLOGY_CORE_CATEGORIES.items()
    }
    core_coverage_count = sum(1 for v in core_coverage_flags.values() if v)
    core_score = round(core_coverage_count / len(core_coverage_flags) * 100, 1)

    # 综合分（与外部 LLM 保持一致的加权）
    overall_score = round(coverage_rate * 0.4 + core_score * 0.6, 1)

    return MetricResult(
        name="资源形态评估",
        value=overall_score,
        unit="分",
        detail={
            "评估方式": "回退脚本（外部 LLM 结果不存在时）",
            "总板块数": len(block_types),
            "已识别资源形态数": len(present_types),
            "资源形态覆盖率(%)": coverage_rate,
            "已识别形态列表": sorted(present_types),
            "核心形态覆盖": core_coverage_flags,
            "核心形态得分(%)": core_score,
            "计算公式": f"{coverage_rate} × 0.4 + {core_score} × 0.6 = {overall_score}",
        },
    )


def calc_coverage_section(
    course_text: str, expected_content: dict[str, Any],
    learning_path_text: str = "",
    history_nodes: set[str] | None = None,
    node_name_map: dict[str, str] | None = None,
) -> MetricResult:
    """覆盖率①：本节知识点覆盖率（累计路径 + 祖先匹配）
    
    期望 = learning_path 全部节点（或 expected_content.section_kcs）
    实际 = 历史节点 ∪ 当前轮节点
    匹配 = 实际 ∩ 期望（支持祖先-后代关系）
    """
    course = _parse_course_package(course_text)
    current_nodes = set(course["knowledge_node_ids"])

    # 累计实际节点
    if history_nodes:
        actual_nodes = current_nodes | history_nodes
    else:
        actual_nodes = current_nodes

    # 期望节点：优先使用 learning_path 全量节点
    if learning_path_text:
        expected_nodes = _parse_learning_path_nodes(learning_path_text)
    else:
        expected_nodes = set(expected_content.get("section_kcs", []))

    if not expected_nodes:
        return MetricResult(
            name="本节知识点覆盖率",
            value=0.0,
            unit="%",
            detail={"note": "expected 中 section_kcs 为空或 learning_path 为空，跳过"},
        )

    # 祖先匹配：加载知识图谱进行扩展
    try:
        dag = _load_knowledge_dag()
        if not dag.get("nodes"):
            raise ValueError("知识图谱为空")
    except Exception:
        dag = {"nodes": [], "edges": []}

    expanded_actual = _expand_with_ancestors(actual_nodes, dag)

    intersection = expanded_actual & expected_nodes
    rate = len(intersection) / len(expected_nodes) * 100

    return MetricResult(
        name="本节知识点覆盖率",
        value=round(rate, 1),
        unit="%",
        detail={
            "实际覆盖(含祖先)": sorted(expanded_actual),
            "预设期望": sorted(expected_nodes),
            "交集": sorted(intersection),
            "累计节点": len(history_nodes) if history_nodes else 0,
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


# ── M6 产物完整率 ─────────────────────────────────────────────────────────────

# 五类产物的代表文件（全部存在且非空才算该轮完整）
# 结尾轮（最后一轮）不要求「诊断反馈」类文件
_ARTIFACT_CATEGORIES: list[tuple[str, list[str]]] = [
    ("规划产物", ["path_decision.md", "learning_path.md", "course_package.md"]),
    ("专家A产物", ["expert_a_draft.md", "expert_a_cross_review.md", "expert_a_revision.md"]),
    ("专家B产物", ["expert_b_draft.md", "expert_b_cross_review.md", "expert_b_revision.md"]),
    ("裁判产物", ["judge_report.md"]),
    ("诊断反馈产物", [
        "feedback/learner_profile_update.md",
        "feedback/grading_report.md",
        "feedback/feedback_report.md",
    ]),
]

# 结尾轮豁免的类别（最后一轮没有 feedback 环节）
_FINAL_ROUND_EXEMPT_CATEGORIES = {"诊断反馈产物"}


def check_artifact_completeness(
    round_dir: Path,
    round_num: int,
    is_final_round: bool = False,
) -> MetricResult:
    """M6 产物完整率：五类产物齐全且非空。

    结尾轮（如 round-03）不要求「诊断反馈产物」类的三个文件存在。
    """
    missing_categories: list[str] = []
    category_details: dict[str, dict[str, Any]] = {}

    for cat_name, files in _ARTIFACT_CATEGORIES:
        if is_final_round and cat_name in _FINAL_ROUND_EXEMPT_CATEGORIES:
            category_details[cat_name] = {"status": "exempt", "files": files}
            continue

        missing_files: list[str] = []
        for fname in files:
            fpath = round_dir / fname
            if not fpath.exists() or fpath.stat().st_size == 0:
                missing_files.append(fname)

        if missing_files:
            missing_categories.append(cat_name)
            category_details[cat_name] = {
                "status": "incomplete",
                "missing": missing_files,
            }
        else:
            category_details[cat_name] = {"status": "complete", "files": files}

    total_categories = len(_ARTIFACT_CATEGORIES)
    exempt_count = sum(
        1 for name, _ in _ARTIFACT_CATEGORIES
        if is_final_round and name in _FINAL_ROUND_EXEMPT_CATEGORIES
    )
    required = total_categories - exempt_count
    complete = required - len(missing_categories)
    rate = complete / required * 100 if required > 0 else 100.0

    return MetricResult(
        name="产物完整率",
        value=round(rate, 1),
        unit="%",
        detail={
            "轮次": round_num,
            "结尾轮": is_final_round,
            "需要检查的类别数": required,
            "完整类别数": complete,
            "缺失类别数": len(missing_categories),
            "缺失类别": missing_categories,
            "各类详情": category_details,
            "备注": "结尾轮（最后一轮）豁免诊断反馈类文件",
        },
    )


# ── M10 PII 泄露检测 ──────────────────────────────────────────────────────────

# PII 检测模式（正则表达式）
PII_PATTERNS: list[tuple[str, str]] = [
    ("身份证号", r"\b\d{17}[\dXx]\b"),
    ("手机号", r"\b1[3-9]\d{9}\b"),
    ("邮箱", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ("银行卡号", r"\b\d{16,19}\b"),
    ("地址（省/市/区）", r"[\u4e00-\u9fa5]{2,3}(省|市|自治区|特别行政区)[\u4e00-\u9fa5]{0,4}(区|县|市辖区)"),
    ("真实姓名模式", r"(?:张|王|李|赵|陈|刘|杨|黄|周|吴|徐|孙|马|朱|胡|郭|林|何|高|罗|郑|梁|谢|宋|唐|韩|曹|许|邓|萧|冯|曾|程|蔡|彭|潘|袁|于|董|余|苏|叶|吕|魏|蒋|田|杜|丁|沈|姜|范|江|傅|钟|卢|汪|戴|崔|任|陆|廖|姚|方|金|邱|夏|谭|石|贺|龚|雷|龙|段|郝|孔|邵|孟|万|段|钱|汤|尹|黎|易|常|武|乔|贺|赖|龚|文|黎|段)[\u4e00-\u9fa5]{1,3}(?:[-\s][\u4e00-\u9fa5]{1,2})?"),
]

# PII 白名单（已知安全的词，不应标记为 PII）
PII_WHITELIST: set[str] = {
    "专利", "商标", "著作权", "知识产权",
    "实施例", "对比文件", "现有技术",
    "小明", "小红", "张三", "李四", "王五",  # 通用占位名
    "A公司", "B公司", "C公司",  # 匿名公司
}

# 已知的测试/演示数据的脱敏 ID 模式
ANONYMIZED_ID_PATTERN = re.compile(r"^(profile_|learner_|multi-)[A-Z]+-\d+$")


def scan_pii_leaks(
    round_dir: Path,
    profile_letter: str,
    round_num: int,
) -> MetricResult:
    """M10 PII 泄露检测。

    扫描 learner_profile_update.md 和 session_snapshot.json 中的个人身份信息。
    采用正则白名单扫描：仅检测与 PII_PATTERNS 匹配且不在白名单中的内容。

    数据源：
      - learner_profile_update.md（feedback/ 或根目录）
      - session_snapshot.json

    Returns:
        MetricResult: PII 泄露指标，value = 泄露条目数（越低越好，0 为理想）
    """
    files_to_scan: list[tuple[str, str]] = []

    # 收集要扫描的文件
    profile_update_paths = [
        round_dir / "feedback" / "learner_profile_update.md",
        round_dir / "learner_profile_update.md",
    ]
    for p in profile_update_paths:
        if p.exists() and p.stat().st_size > 0:
            files_to_scan.append(("learner_profile_update.md", str(p)))

    snapshot_path = round_dir / "session_snapshot.json"
    if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
        files_to_scan.append(("session_snapshot.json", str(snapshot_path)))

    if not files_to_scan:
        return MetricResult(
            name="PII泄露条数",
            value=0.0,
            unit="条",
            detail={
                "说明": "无可扫描文件",
                "扫描文件数": 0,
                "profile_letter": profile_letter,
                "round_num": round_num,
            },
        )

    leaks: list[dict[str, str]] = []
    files_scanned = 0

    for file_label, file_path in files_to_scan:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        files_scanned += 1

        for pattern_name, pattern in PII_PATTERNS:
            for m in re.finditer(pattern, content):
                matched_text = m.group(0)

                # 白名单检查
                if matched_text in PII_WHITELIST:
                    continue

                # 匿名 ID 模式检查（如 profile_B-001）
                if ANONYMIZED_ID_PATTERN.match(matched_text):
                    continue

                # 检查上下文是否为已知安全场景
                start = max(0, m.start() - 20)
                end = min(len(content), m.end() + 20)
                context = content[start:end]
                if any(w in context for w in PII_WHITELIST):
                    continue

                leaks.append({
                    "file": file_label,
                    "pattern": pattern_name,
                    "match": matched_text,
                    "context": context.strip()[:80],
                })

    leak_count = len(leaks)
    # PII 指标 = 泄露条目数（越低越好）
    # 理想值为 0，阈值为 0（不应有任何真实 PII）

    return MetricResult(
        name="PII泄露条数",
        value=float(leak_count),
        unit="条",
        detail={
            "扫描文件数": files_scanned,
            "扫描文件列表": [f[0] for f in files_to_scan],
            "泄露总数": leak_count,
            "泄露详情": leaks[:20],  # 最多显示 20 条
            "说明": "检测 learner_profile_update.md 和 session_snapshot.json 中的真实个人信息",
            "检测模式": [p[0] for p in PII_PATTERNS],
            "白名单词数": len(PII_WHITELIST),
            "profile_letter": profile_letter,
            "round_num": round_num,
            "评估结论": "✅ 未检测到 PII" if leak_count == 0 else f"⚠️ 检测到 {leak_count} 条疑似 PII",
        },
    )


# ── M8 异议闭环率（由外部 LLM 评估） ──────────────────────────────────────────

def load_m8_external_result(profile_letter: str, round_num: int) -> MetricResult | None:
    """从外部 LLM 评估结果文件加载 M8 异议闭环率。

    外部 LLM 评估结果存储在 LLM/results/ 目录下，命名格式：
    objection_loop_{model}_{profile}_{round:02d}.json

    如果结果文件不存在，返回 None。
    """
    llm_results_dir = _EVAL_DIR / "LLM" / "results"

    # 查找匹配的结果文件
    pattern = f"objection_loop_*_{profile_letter}_{round_num:02d}.json"
    matching = sorted(llm_results_dir.glob(pattern))

    if not matching:
        return None

    try:
        data = json.loads(matching[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # 从 LLM 结果中提取指标
    m8_data = data.get("metrics", {})
    return MetricResult(
        name="异议闭环率",
        value=m8_data.get("value", 0),
        unit=m8_data.get("unit", "%"),
        detail=m8_data.get("detail", {
            "note": "外部 LLM 评估结果（解析异常）",
            "source_file": str(matching[0].name),
        }),
    )


# ── M7 资源形态评估（可选：外部 LLM 评估结果加载） ─────────────────────────────

def load_m7_external_result(profile_letter: str, round_num: int) -> MetricResult | None:
    """从外部 LLM 评估结果文件加载 M7 资源形态评估。

    如果外部评估结果不存在，返回 None（回退到 calculate.py 内部的脚本计算）。
    """
    llm_results_dir = _EVAL_DIR / "LLM" / "results"
    pattern = f"resource_morphology_*_{profile_letter}_{round_num:02d}.json"
    matching = sorted(llm_results_dir.glob(pattern))

    if not matching:
        return None

    try:
        data = json.loads(matching[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    m7_data = data.get("metrics", {})
    return MetricResult(
        name="资源形态评估",
        value=m7_data.get("value", 0),
        unit=m7_data.get("unit", "分"),
        detail=m7_data.get("detail", {
            "评估方式": "外部 LLM",
            "source_file": str(matching[0].name),
        }),
    )


# ── M1 专业知识谬误率 & M9 知识溯源可验证率（外部 LLM 评估） ─────────────────────

def load_m1_m9_external_result(profile_letter: str, round_num: int) -> tuple[MetricResult | None, MetricResult | None]:
    """从外部 LLM 评估结果文件加载 M1 和 M9 指标。

    两个指标由同一次 LLM 调用 (evaluate_m1_m9) 生成，保存在同一文件中。
    文件命名：statement_judge_{model}_{profile}_{round:02d}.json

    Returns:
        (m1_result, m9_result): 任一不存在则返回 None
    """
    llm_results_dir = _EVAL_DIR / "LLM" / "results"
    pattern = f"statement_judge_*_{profile_letter}_{round_num:02d}.json"
    matching = sorted(llm_results_dir.glob(pattern))

    if not matching:
        return None, None

    try:
        data = json.loads(matching[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None

    source_file = str(matching[0].name)

    # M1
    m1_data = data.get("m1_hallucination_rate", {})
    m1_result = MetricResult(
        name="专业知识谬误率",
        value=m1_data.get("value", 0),
        unit=m1_data.get("unit", "分"),
        detail={
            "评估方式": "外部 LLM",
            "抽样陈述数": m1_data.get("total", 0),
            "错误数": m1_data.get("incorrect", 0),
            "正确数": m1_data.get("correct", 0),
            "存疑数": m1_data.get("uncertain", 0),
            "100分制平均正确率": m1_data.get("score_based_avg"),
            "传统谬误率(%)": m1_data.get("verdict_based_rate"),
            "加权值(备用)": m1_data.get("weighted_value"),
            "source_file": source_file,
        },
    )

    # M9
    m9_data = data.get("m9_source_verifiable_rate", {})
    m9_result = MetricResult(
        name="知识溯源可验证率",
        value=m9_data.get("value", 0),
        unit=m9_data.get("unit", "分"),
        detail={
            "评估方式": "外部 LLM",
            "带来源陈述数": m9_data.get("total_with_source", 0),
            "完全验证数": m9_data.get("fully_verified", 0),
            "未验证数": m9_data.get("unverified", 0),
            "平均来源得分": m9_data.get("avg_source_score"),
            "平均相关性得分": m9_data.get("avg_relevance_score"),
            "传统溯源率(%)": m9_data.get("verdict_based_rate"),
            "source_file": source_file,
        },
    )

    return m1_result, m9_result


# ── M11 动态迭代 ──────────────────────────────────────────────────────────────

def calc_bkt_advancement(
    r01_profile: str | None,
    r02_profile: str | None,
    course_r02: str | None,
) -> MetricResult:
    """M11 动态迭代触发率（进阶）。
    
    进阶判定：pl 从 <0.30 升至 ≥0.30 且下一轮习题难度降为 L1
    """
    if not r01_profile or not r02_profile:
        return MetricResult(
            name="动态迭代触发率",
            value=0.0,
            unit="%",
            detail={"note": "缺少 r01 或 r02 的 learner_profile_update.md"},
        )
    
    # 1. 提取 r01 的节点 pl
    r01_pls = _extract_node_pls(r01_profile)
    
    # 2. 提取 r02 的节点 pl
    r02_pls = _extract_node_pls(r02_profile)
    
    if not r01_pls or not r02_pls:
        return MetricResult(
            name="动态迭代触发率",
            value=0.0,
            unit="%",
            detail={"note": "无法解析 learner_profile_update.md 中的 pl 数据"},
        )
    
    # 3. 识别"弱"状态的节点（pl < 0.30）
    weak_nodes = [nid for nid, pl in r01_pls.items() if pl < 0.30]
    
    if not weak_nodes:
        return MetricResult(
            name="动态迭代触发率",
            value=100.0,
            unit="%",
            detail={
                "r01弱状态节点数": 0,
                "note": "无弱状态节点",
            },
        )
    
    # 4. 识别"进阶"的节点
    advanced_nodes = []
    for node_id in weak_nodes:
        if node_id in r02_pls and r02_pls[node_id] >= 0.30:
            # 检查下一轮习题难度（如果有 course_r02）
            if course_r02 and _check_difficulty_dropped(course_r02, node_id):
                advanced_nodes.append(node_id)
            elif not course_r02:
                # 没有 course_r02 时，仅按 pl 跃升判定
                advanced_nodes.append(node_id)
    
    # 5. 计算进阶触发率
    rate = len(advanced_nodes) / len(weak_nodes) * 100
    
    return MetricResult(
        name="动态迭代触发率",
        value=round(rate, 1),
        unit="%",
        detail={
            "r01弱状态节点数": len(weak_nodes),
            "进阶节点数": len(advanced_nodes),
            "进阶节点": advanced_nodes,
            "r01弱节点列表": weak_nodes,
        },
    )


# ── 主入口 ──────────────────────────────────────────────────────────────────

def calculate_round(
    profile_letter: str,
    round_num: int,
    session_dir: Path | None = None,
    expected_path: Path | None = None,
    history_nodes: set[str] | None = None,
    prev_profile_update: str | None = None,
) -> RoundMetrics:
    """计算指定画像指定轮次的全部指标。

    从测试快照目录 ``backend/tests/evaluation/artifacts/multi-{letter}/round-{NN}/``
    读取产物文件。该目录由 ``save_round_artifacts`` 从系统产物目录（UUID 命名）
    复制并规范命名而来。
    
    新增参数：
    - history_nodes: 跨轮累计的 knowledge_points 节点集合（用于 M3 累计覆盖率）
    - prev_profile_update: 上一轮的 learner_profile_update.md 内容（用于 M11 动态迭代）
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
    
    # 读取反馈相关产物
    revision_a_text = None
    revision_b_text = None
    profile_update_text = None
    feedback_dir = round_dir / "feedback"
    if feedback_dir.exists():
        rev_a_path = round_dir / "expert_a_revision.md"
        if rev_a_path.exists():
            revision_a_text = _read_text(rev_a_path)
        rev_b_path = round_dir / "expert_b_revision.md"
        if rev_b_path.exists():
            revision_b_text = _read_text(rev_b_path)
        
        # learner_profile_update.md 可能在 feedback/ 或根目录
        profile_update_path = feedback_dir / "learner_profile_update.md"
        if profile_update_path.exists():
            profile_update_text = _read_text(profile_update_path)
        else:
            # 兼容：检查根目录
            alt_path = round_dir / "learner_profile_update.md"
            if alt_path.exists():
                profile_update_text = _read_text(alt_path)

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

    # 确定是否为结尾轮（通过检查 session_dir 中是否有更大的轮次）
    available_rounds = sorted(
        int(d.name.split("-")[1] if d.name.startswith("round-") else d.name.split("_")[1])
        for d in session_dir.iterdir()
        if d.is_dir() and (d.name.startswith("round-") or d.name.startswith("round_"))
    )
    is_final = round_num >= max(available_rounds) if available_rounds else True

    # M6 产物完整率
    rm.metrics.append(
        check_artifact_completeness(round_dir, round_num, is_final_round=is_final)
    )

    # 幻觉率（系统自评）
    rm.metrics.append(
        calc_hallucination_expert_review(review_a_text, review_b_text)
    )
    rm.metrics.append(calc_hallucination_judge_accuracy(judge_text))

    # 匹配度（双边区间）
    rm.metrics.append(
        calc_matching_difficulty(
            course_text, path_text, node_name_map,
            profile_update_text=profile_update_text,
        )
    )
    # M7 资源形态评估（优先外部 LLM 结果，回退脚本计算）
    m7_ext = load_m7_external_result(profile_letter, round_num)
    if m7_ext:
        rm.metrics.append(m7_ext)
    else:
        # 回退到脚本计算：仍使用情感使用度算法（block_type 占比），但指标名统一为"资源形态评估"
        m7_fallback = calc_matching_emotional(course_text)
        m7_fallback.name = "资源形态评估"
        rm.metrics.append(m7_fallback)

    # 覆盖率（累计 + 祖先匹配）
    rm.metrics.append(
        calc_coverage_section(
            course_text, expected_content,
            learning_path_text=path_text,
            history_nodes=history_nodes,
            node_name_map=node_name_map,
        )
    )
    rm.metrics.append(calc_coverage_weakness(course_text, expected_content))
    rm.metrics.append(
        calc_coverage_confusable(course_text, expected_content, node_name_map)
    )

    # 对话质量（M8 异议闭环率 — 尝试从外部 LLM 结果加载）
    m8_result = load_m8_external_result(profile_letter, round_num)
    if m8_result:
        rm.metrics.append(m8_result)

    # M1 专业知识谬误率 & M9 知识溯源可验证率（外部 LLM 评估）
    m1_result, m9_result = load_m1_m9_external_result(profile_letter, round_num)
    if m1_result:
        rm.metrics.append(m1_result)
    if m9_result:
        rm.metrics.append(m9_result)

    # 动态迭代（M11）
    if prev_profile_update:
        rm.metrics.append(
            calc_bkt_advancement(
                prev_profile_update,
                profile_update_text,
                course_text,
            )
        )

    # M10 PII 泄露检测
    rm.metrics.append(
        scan_pii_leaks(round_dir, profile_letter, round_num)
    )

    return rm


# M1 外部LLM评估器维度（3个核心概念，由 judge_*.json 提供）
_M1_LLM_DIMENSIONS: list[tuple[str, str]] = [
    ("context_correctness", "上下文正确性(Context Correctness)"),
    ("correctness", "答案正确性(Correctness)"),
    ("hallucination", "幻觉评估(Hallucination)"),
]

# M2 匹配度外部LLM维度（从原 M1 移入的有用性/相关性）
_M2_LLM_DIMENSIONS: list[tuple[str, str]] = [
    ("helpfulness", "有用性(Helpfulness)"),
    ("relevance", "相关性(Relevance)"),
]


def _get_llm_dim_score(
    profile_letter: str,
    round_num: int,
    dim_key: str,
    llm_results: dict[str, Any] | None,
) -> tuple[float, str] | None:
    """从外部 LLM 评估结果获取指定维度的分数。"""
    if not llm_results:
        return None
    profile_data = llm_results.get(profile_letter, {})
    round_data = profile_data.get(round_num, {})
    judge_data = round_data.get("judge_eval", {})
    overall = judge_data.get("overall_evaluation", {})
    scores = overall.get("scores", {})
    dim_data = scores.get(dim_key, {})
    score = dim_data.get("score", 0)
    max_score = dim_data.get("max", 100)
    if score <= 0:
        return None
    return score, f"/{max_score}"


def format_result(
    rm: RoundMetrics,
    llm_results: dict[str, Any] | None = None,
) -> str:
    """格式化输出结果。

    Args:
        rm: 轮次指标计算结果
        llm_results: 外部 LLM 评估结果（可选），用于展示 M1 的 5 个评估器维度
    """
    lines = [
        f"\n{'=' * 60}",
        f"画像: profile_{rm.profile_letter}  轮次: round-{rm.round_num:02d}",
        f"{'=' * 60}",
    ]

    def _append_group(title: str, metric_names: list[str]) -> None:
        lines.append("")
        lines.append(f"【{title}】")
        found = False
        for m in rm.metrics:
            if m.name in metric_names:
                found = True
                lines.append(f"  {m.name}: {m.value}{m.unit}")
                for k, v in m.detail.items():
                    lines.append(f"    · {k}: {v}")
        if not found:
            lines.append("  (无数据)")

    _append_group("幻觉率 — 系统自评", ["专家互评异议率", "裁判准确性评分", "异议闭环率"])
    _append_group("匹配度 — 难度符合度", ["难度符合度"])

    # M7 资源形态评估（独立主指标）
    m7 = next((m for m in rm.metrics if m.name == "资源形态评估"), None)
    if m7:
        lines.append("")
        lines.append("【M7 资源形态】")
        lines.append(f"  {m7.name}: {m7.value}{m7.unit}")
        for k, v in m7.detail.items():
            lines.append(f"    · {k}: {v}")

    # M6 产物完整率
    m6 = next((m for m in rm.metrics if m.name == "产物完整率"), None)
    if m6:
        lines.append("")
        lines.append("【M6 产物完整率】")
        lines.append(f"  {m6.name}: {m6.value}{m6.unit}")
        for k, v in m6.detail.items():
            lines.append(f"    · {k}: {v}")

    _append_group(
        "M3 覆盖率",
        ["本节知识点覆盖率", "薄弱点命中率", "混淆对覆盖率"],
    )

    # M1 陈述级外部LLM
    _append_group("M1 幻觉率 — 陈述级外部LLM", ["专业知识谬误率", "知识溯源可验证率"])

    # M1 外部LLM评估器维度（3个核心概念）
    lines.append("")
    lines.append("【M1 幻觉率 — 外部LLM评估器维度(3概念)】")
    m1_dims_found = False
    for dim_key, dim_label in _M1_LLM_DIMENSIONS:
        result = _get_llm_dim_score(
            rm.profile_letter, rm.round_num, dim_key, llm_results
        )
        if result is not None:
            m1_dims_found = True
            val, u = result
            lines.append(f"  {dim_label}: {val}{u}")
    if not m1_dims_found:
        lines.append("  (无外部LLM评估数据，请先运行外部LLM评估)")

    # M2 外部LLM维度（有用性/相关性）
    lines.append("")
    lines.append("【M2 匹配度 — 外部LLM维度】")
    m2_dims_found = False
    for dim_key, dim_label in _M2_LLM_DIMENSIONS:
        result = _get_llm_dim_score(
            rm.profile_letter, rm.round_num, dim_key, llm_results
        )
        if result is not None:
            m2_dims_found = True
            val, u = result
            lines.append(f"  {dim_label}: {val}{u}")
    if not m2_dims_found:
        lines.append("  (无外部LLM评估数据)")

    # M1 其他吸收指标
    _append_group("M1 幻觉率 — 知识溯源(M9吸收)", ["知识溯源可验证率"])
    _append_group("M1 幻觉率 — PII合规检测(M10吸收)", ["PII泄露条数"])
    _append_group("M2 匹配度 — 动态迭代(M11吸收)", ["动态迭代触发率"])

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
