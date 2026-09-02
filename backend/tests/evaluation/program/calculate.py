"""评估指标计算脚本。

计算 M1~M6 六大类指标（按单轮定义，多轮取算术平均值）：

M1 幻觉率：
  6.2 异议闭环（脚本计算 + 外部LLM）
  1.1 裁判Agent准确性评分（脚本计算，judge_report.md 准确性：X/5）
  1.3.3 幻觉评估（外部LLM overall）
  1.3.1 事实性 / 1.3.2 逻辑性 / 1.3.3 指令性谬误率（外部LLM statement）
  1.4.1 溯源可验证率 / 1.4.2 溯源内容支撑率（外部LLM statement）
  1.5 内容跨轮自洽率（外部LLM profile）

M2 匹配度：
  2.1 难度符合度（脚本计算）
  2.2 有用性 / 2.3 相关性（外部LLM overall）
  2.4 动态迭代触发率（脚本计算）
  4.1 检索准确率 / 4.2 检索完整率（外部LLM retrieval）

M3 覆盖率：
  3.1 知识点覆盖率（脚本计算 + 外部LLM coverage 语义验证）
  3.2 薄弱点命中率（脚本计算 + 外部LLM coverage 语义验证）
  3.3 混淆对覆盖率（脚本计算 + 外部LLM coverage 语义验证）

M4 执行完整性：
  4.1 5.1 产物完整率（脚本计算）
  5.2.1 资源大类数 / 5.2.2 资源小类数（脚本计算）

M5 其它指标：
  5.1 测试差异化画像个数（仅保留概念）
  5.2 知识库覆盖（仅保留概念）
  5.3 PII合规检测（外部LLM）
  6.1 异议率（脚本计算，(🔴+🟡)/总批注）

M6 问答质量测试：
  7.1 对抗稳健率（系统级外部LLM）
  7.2 边界拒答恰当率（系统级外部LLM）

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

import _common as common

_SYS_ARTIFACTS_DIR = common.SYS_ARTIFACTS_DIR
_EVAL_ARTIFACTS_DIR = common.EVAL_ARTIFACTS_DIR
_PROFILES_DIR = common.PROFILES_DIR
_KNOWLEDGE_DAG = _PROJECT_ROOT / "backend" / "app" / "curriculum" / "data" / "knowledge-dag.json"

# calculate_round 执行期间的活动 learner 前缀：外部 LLM 结果按类别目录读取。
_ACTIVE_LEARNER_PREFIX: str = "multi"

def _resolve_llm_results_dir(learner_prefix: str | None = None) -> Path:
    """解析外部 LLM 结果目录：按类别隔离（record_{前缀}）。

    learner_prefix 缺省时使用 calculate_round 的活动前缀（_ACTIVE_LEARNER_PREFIX）。
    旧共享目录（results/reports/record、LLM/results）仅作为 multi 前缀的回退；
    非 multi 前缀绝不读共享池，避免类别间串数据。
    """
    if learner_prefix is None:
        learner_prefix = _ACTIVE_LEARNER_PREFIX
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

# 资源形态类型（与 m4_resource_morphology.md 定义的 13 种对齐，用于 M7 回退脚本计算）
RESOURCE_MORPHOLOGY_TYPES = {
    "knowledge_synthesis", "verbal_explanation", "summary_card", "mnemonic", "legal_anchor",
    "worked_example", "anchor_scenario", "reflect_prompt",
    "assessment",
    "global_framework", "decision_flow", "common_pitfall", "predict_activate",
}

# 核心资源形态类别
RESOURCE_MORPHOLOGY_CORE_CATEGORIES = {
    "讲义类": {"knowledge_synthesis", "verbal_explanation", "summary_card", "mnemonic", "legal_anchor"},
    "实操指南类": {"worked_example", "anchor_scenario", "reflect_prompt"},
    "分阶题类": {"assessment"},
}

EMOTIONAL_BLOCK_TYPES = RESOURCE_MORPHOLOGY_TYPES
DIFFICULTY_ORDER = {"L1": 1, "L2": 2, "L3": 3}

# ── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class MetricResult:
    """单个指标的计算结果。"""
    name: str
    value: float
    unit: str
    detail: dict[str, Any] = field(default_factory=dict)

@dataclass
class RoundMetrics:
    """一轮的所有指标结果。"""
    profile_letter: str
    round_num: int
    metrics: list[MetricResult] = field(default_factory=list)

# ── 文件解析 ─────────────────────────────────────────────────────────────────

def _read_text(path: Path) -> str:
    """读取一个文本文件，文件缺失时返回空串而不是抛 FileNotFoundError。

    原因：
    - Debate-off / single-agent 轮次天生就没有 ``expert_a_cross_review.md``
      等辩论专属产物（属正常，不应当让整轮计算崩溃）；
    - 偶尔因为超时/异常终止，``course_package.md`` 可能没写出来，此时相关
      指标可以记为 0/NA，但要给下游足够的上下文（空串），而不是把整个
      calculate_round 中断。
    """
    if not path.exists():
        # 保持非侵入式：直接返回空串，下游每个 calc_* 函数自行对空串做安全降级。
        return ""
    return path.read_text(encoding="utf-8")

def _parse_cross_review(text: str) -> dict[str, int]:
    """解析互评表格，统计 🔴/🟡/🟢/🔵 数量。"""
    counts = {"🔴": 0, "🟡": 0, "🟢": 0, "🔵": 0}
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line or "类别" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if not cells:
            continue
        first_cell = cells[0]
        for emoji in counts:
            if first_cell.startswith(emoji):
                counts[emoji] += 1
                break
    return counts

def _parse_judge_report(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"accuracy": 0, "decision": ""}
    m = re.search(r"准确性[：:]\s*(\d+)\s*/\s*5", text)
    if m:
        result["accuracy"] = int(m.group(1))
    m = re.search(r"决策[：:]\s*\*{0,2}(accept_with_minor_revision|accept|revise)\*{0,2}", text)
    if m:
        result["decision"] = m.group(1)
    return result

def _parse_course_package(text: str) -> dict[str, Any]:
    """解析课程包，提取教学模块、题目难度、知识节点。"""
    result: dict[str, Any] = {
        "block_types": [], "question_levels": [], "question_roles": [],
        "knowledge_node_ids": [], "current_node_id": None, "full_text": text,
    }

    m = re.search(r"当前教学节点[：:]\s*`?([^`\n]+)`?", text)
    if m:
        result["current_node_id"] = m.group(1).strip()

    lines = text.splitlines()
    in_table = False
    for line in lines:
        if "教学模块选择清单" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("## "):
                in_table = False
                continue
            if line.startswith("|") and "---" not in line:
                cells = [c.strip() for c in line.split("|")]
                cells = [c for c in cells if c != ""]
                if len(cells) >= 2 and cells[0].isdigit():
                    bt = cells[1].strip(" `")
                    result["block_types"].append(bt)

    iq_match = re.search(r"## interactive_questions\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if iq_match:
        try:
            iq_list = json.loads(iq_match.group(1))
            for item in iq_list:
                diff = item.get("difficulty", "")
                if diff in ("L1", "L2", "L3"):
                    result["question_levels"].append(diff)
                    role = item.get("source_tag", item.get("role", ""))
                    result["question_roles"].append(role)
        except (json.JSONDecodeError, TypeError):
            pass
    if not result["question_levels"]:
        for m in re.finditer(r"(?:题目|Q)\d+[（(]\s*(L[123])", text):
            result["question_levels"].append(m.group(1))
            result["question_roles"].append("")

    kp_match = re.search(r"## knowledge_points\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if kp_match:
        try:
            kp_list = json.loads(kp_match.group(1))
            result["knowledge_node_ids"] = [item.get("node_id", "") for item in kp_list if isinstance(item, dict)]
        except json.JSONDecodeError:
            pass

    return result

def _parse_learning_path(text: str) -> dict[str, str]:
    """解析学习路径的难度上限表。"""
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
    nodes = set()
    for m in re.finditer(r"\|\s*([^|\s]+)\s*\|", path_text):
        node_id = m.group(1).strip()
        if node_id and not node_id.startswith("---") and node_id != "节点":
            nodes.add(node_id)
    return nodes

def _expand_with_ancestors(nodes: set[str], dag: dict[str, Any]) -> set[str]:
    """扩展节点集：基于 knowledge-dag.json 的 predecessors 关系（向上追溯祖先）。

    用途：3.1 知识点覆盖率 —— 教了子节点 → 其前置祖先视为已覆盖。
    """
    expanded = set(nodes)
    nodes_data = dag.get("dag", {}).get("nodes", [])
    predecessors_map: dict[str, list[str]] = {}
    for node in nodes_data:
        node_id = node.get("node_id", "")
        preds = node.get("predecessors", [])
        if node_id and preds:
            predecessors_map[node_id] = preds

    def _find_ancestors(node_id: str) -> set[str]:
        ancestors = set()
        to_visit = predecessors_map.get(node_id, [])
        while to_visit:
            current = to_visit.pop(0)
            if current not in ancestors:
                ancestors.add(current)
                to_visit.extend(predecessors_map.get(current, []))
        return ancestors

    for nid in list(nodes):
        ancestors = _find_ancestors(nid)
        expanded.update(ancestors)
    return expanded


def _expand_with_descendants(nodes: set[str], dag: dict[str, Any]) -> set[str]:
    """扩展节点集：基于 predecessors 反向（向下遍历 successors，得到所有子孙）。

    用途：3.2 薄弱点命中率 / 3.3 混淆对覆盖率 —— 当系统只写入 level-1/2 的父节点时，
    其 DAG 下的子/孙节点（也就是 expected 里的 weakness/confusion 叶节点）
    应视为在同一教学范围内。
    """
    expanded = set(nodes)
    nodes_data = dag.get("dag", {}).get("nodes", [])
    # successors_map: node_id -> list of node_ids whose predecessors include node_id
    successors_map: dict[str, list[str]] = {}
    for node in nodes_data:
        nid = node.get("node_id", "")
        for pred in node.get("predecessors", []) or []:
            successors_map.setdefault(pred, []).append(nid)

    def _find_descendants(node_id: str) -> set[str]:
        descendants = set()
        to_visit = list(successors_map.get(node_id, []))
        while to_visit:
            current = to_visit.pop(0)
            if current not in descendants:
                descendants.add(current)
                to_visit.extend(successors_map.get(current, []))
        return descendants

    for nid in list(nodes):
        descendants = _find_descendants(nid)
        expanded.update(descendants)
    return expanded


def _expand_fully(nodes: set[str], dag: dict[str, Any]) -> set[str]:
    """双向扩展：祖先 + 子孙。"""
    return _expand_with_descendants(_expand_with_ancestors(nodes, dag), dag)

def _load_node_name_map() -> dict[str, str]:
    """加载 node_id -> node_name 映射。"""
    if not _KNOWLEDGE_DAG.exists():
        return {}
    try:
        data = json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
        return {n["node_id"]: n.get("node_name", n["node_id"]) for n in data.get("dag", {}).get("nodes", [])}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}

def _load_node_id_by_name() -> dict[str, str]:
    """加载 node_name -> node_id 反向映射（用于中文节点名查找）。"""
    if not _KNOWLEDGE_DAG.exists():
        return {}
    try:
        data = json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
        result: dict[str, str] = {}
        for n in data.get("dag", {}).get("nodes", []):
            nid = n.get("node_id", "")
            name = n.get("node_name", "")
            if nid and name:
                result[name] = nid
            for sub in n.get("knowledge_sub_nodes", []):
                if sub:
                    result[sub] = sub
        return result
    except (json.JSONDecodeError, OSError):
        return {}

def _resolve_to_node_id(raw: str, name_to_id: dict[str, str]) -> str:
    """将任意输入（node_id 或中文显示名）解析为 node_id。"""
    if not raw:
        return ""
    if raw in name_to_id:
        return name_to_id[raw]
    if raw in name_to_id.values():
        return raw
    for name, nid in name_to_id.items():
        if name in raw or raw in name:
            return nid
    return raw

def _load_knowledge_dag() -> dict[str, Any]:
    if not _KNOWLEDGE_DAG.exists():
        return {"dag": {"nodes": []}}
    try:
        return json.loads(_KNOWLEDGE_DAG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"dag": {"nodes": []}}

# ── 幻觉率相关计算 ──────────────────────────────────────────────────────────

def calc_objection_loop(judge_text: str, review_a_text: str, review_b_text: str) -> MetricResult:
    """6.2 异议闭环 — 占位指标。

    闭环率 = 闭环条数 / 总🔴条数 × 100%。
    实际值由外部 LLM 评估（round_indicator_*.json > objection_loop section）通过 `load_m8_external_result` 加载。
    此处仅用于在外部LLM结果缺失时保留占位，并透出 🔴 计数供参考。
    无🔴异议时返回 100%（无需闭环即为满分）。
    """
    counts_a = _parse_cross_review(review_a_text)
    counts_b = _parse_cross_review(review_b_text)
    total_critical = counts_a.get("🔴", 0) + counts_b.get("🔴", 0)

    return MetricResult(
        name="6.2 异议闭环", value=100.0 if total_critical == 0 else 0.0, unit="%",
        detail={
            "总🔴条数": total_critical,
            "闭环条数": None,
            "note": "闭环判定需依赖外部LLM结果 (round_indicator_*.json section=objection_loop)",
            "computed": False,
        }
    )


def calc_hallucination_expert_review(review_a_text: str, review_b_text: str) -> MetricResult:
    """6.1 异议率 — (🔴 + 🟡) / 总批注数 × 100%。"""
    counts_a = _parse_cross_review(review_a_text)
    counts_b = _parse_cross_review(review_b_text)
    total_issues = sum(counts_a.values()) + sum(counts_b.values())
    critical = counts_a.get("🔴", 0) + counts_b.get("🔴", 0)
    warning = counts_a.get("🟡", 0) + counts_b.get("🟡", 0)
    issue_count = critical + warning
    rate = round(issue_count / total_issues * 100, 2) if total_issues else 0.0
    return MetricResult(
        name="6.1 异议率", value=rate, unit="%",
        detail={
            "专家A总批注": sum(counts_a.values()), "专家B总批注": sum(counts_b.values()),
            "🔴": critical, "🟡": warning, "🟢": counts_a.get("🟢", 0) + counts_b.get("🟢", 0),
            "🔵": counts_a.get("🔵", 0) + counts_b.get("🔵", 0),
            "异议数": issue_count,
        }
    )

def calc_hallucination_judge_accuracy(judge_text: str) -> MetricResult:
    """1.1 裁判Agent准确性评分 — 直接取 judge_report.md 中 准确性：X/5。"""
    info = _parse_judge_report(judge_text)
    return MetricResult(
        name="1.1 裁判Agent准确性评分", value=info["accuracy"], unit="/5",
        detail={"决策": info["decision"]}
    )

# ── 匹配度相关计算 ──────────────────────────────────────────────────────────

def _get_learner_difficulty_lower(pl: float, role: str = "") -> str:
    """根据 BKT PL 值确定学员难度下限 (L1/L2)。

    阈值 0.30 与 BKT 掌握度分级保持一致：
    掌握概率 < 0.30 视为"未掌握/弱状态"，对应难度下限 L1；
    掌握概率 ≥ 0.30 视为"已掌握"，对应难度下限 L2。
    """
    if pl < 0.30:
        return "L1"
    return "L2"

def _get_capped_difficulty(question_level: str, node_name: str, difficulty_limits: dict[str, str]) -> str:
    """获取封顶难度。"""
    cap = difficulty_limits.get(node_name, "L3")
    cap_level = DIFFICULTY_ORDER.get(cap, 3)
    question_level_num = DIFFICULTY_ORDER.get(question_level, 3)
    return cap if question_level_num > cap_level else question_level

def calc_matching_difficulty(
    course_text: str, path_text: str, node_name_map: dict[str, str],
    profile_update_text: str | None = None,
) -> MetricResult:
    """M2 匹配度 — 难度符合度。"""
    parsed = _parse_course_package(course_text)
    question_levels = parsed["question_levels"]
    question_roles = parsed["question_roles"]
    current_node_id = parsed["current_node_id"]
    node_name = node_name_map.get(current_node_id, current_node_id or "")
    difficulty_limits = _parse_learning_path(path_text)

    if not question_levels:
        return MetricResult(name="2.1 难度符合度", value=0.0, unit="%", detail={"note": "无测评题目"})

    high_count = 0
    for level, role in zip(question_levels, question_roles):
        high = _get_capped_difficulty(level, node_name, difficulty_limits)

        if DIFFICULTY_ORDER.get(level, 0) > DIFFICULTY_ORDER.get(high, 0):
            high_count += 1

    total = len(question_levels)
    matched = total - high_count
    rate = round(matched / total * 100, 2) if total else 0.0
    return MetricResult(
        name="2.1 难度符合度", value=rate, unit="%",
        detail={"总题数": total, "符合数": matched, "高于上限": high_count, "节点": node_name}
    )

def calc_resource_morphology(text: str) -> list[MetricResult]:
    """M4 执行完整性 — 资源形态。

    5.2.1 资源大类数：课程中出现的核心资源大类数（应覆盖 3 类：讲义类 / 实操指南类 / 分阶题类）。
    5.2.2 资源小类数：课程中实际出现的资源小类总数（block_type 去重数量）。
    """
    parsed = _parse_course_package(text)
    block_types = parsed["block_types"]
    if not block_types:
        return [
            MetricResult(name="5.2.1 资源大类数", value=0.0, unit="个",
                         detail={"note": "无教学模块", "覆盖大类": [], "应覆盖大类": list(RESOURCE_MORPHOLOGY_CORE_CATEGORIES.keys())}),
            MetricResult(name="5.2.2 资源小类数", value=0.0, unit="个",
                         detail={"note": "无教学模块", "小类列表": []}),
        ]

    type_counts: dict[str, int] = {}
    for bt in block_types:
        type_counts[bt] = type_counts.get(bt, 0) + 1

    covered_categories: set[str] = set()
    for cat_name, cat_types in RESOURCE_MORPHOLOGY_CORE_CATEGORIES.items():
        if any(bt in type_counts for bt in cat_types):
            covered_categories.add(cat_name)

    major_count = float(len(covered_categories))
    minor_count = float(len(type_counts))

    return [
        MetricResult(
            name="5.2.1 资源大类数", value=major_count, unit="个",
            detail={
                "覆盖大类": sorted(covered_categories),
                "应覆盖大类": sorted(RESOURCE_MORPHOLOGY_CORE_CATEGORIES.keys()),
            }
        ),
        MetricResult(
            name="5.2.2 资源小类数", value=minor_count, unit="个",
            detail={
                "小类列表": sorted(type_counts.keys()),
                "小类分布": type_counts,
            }
        ),
    ]

# 保留旧名称作为向后兼容的别名
calc_matching_emotional = calc_resource_morphology

# ── 覆盖率相关计算 ──────────────────────────────────────────────────────────

def calc_coverage_section(
    course_text: str, expected_content: dict[str, Any],
    learning_path_text: str = "",
    history_nodes: set[str] | None = None,
    node_name_map: dict[str, str] | None = None,
) -> MetricResult:
    """M3 覆盖率 — 知识点覆盖率（累计路径 + 祖先匹配）。"""
    node_name_map = node_name_map or {}
    parsed = _parse_course_package(course_text)
    current_node_id = parsed.get("current_node_id")
    course_node_ids = set(parsed.get("knowledge_node_ids", []))
    if current_node_id:
        course_node_ids.add(current_node_id)

    # 累计：本轮 + 历史轮
    if history_nodes:
        course_node_ids.update(history_nodes)

    # 祖先扩展
    dag = _load_knowledge_dag()
    expanded_nodes = _expand_with_ancestors(course_node_ids, dag)

    expected_nodes = expected_content.get("section_kcs") or expected_content.get("knowledge_nodes", [])
    if not expected_nodes:
        return MetricResult(name="3.1 知识点覆盖率", value=0.0, unit="%", detail={"note": "无预期知识点"})

    name_to_id = _load_node_id_by_name()
    expected_ids: set[str] = set()
    raw_expected: list[str] = []
    for n in expected_nodes:
        if isinstance(n, str):
            resolved = _resolve_to_node_id(n, name_to_id)
            expected_ids.add(resolved)
            raw_expected.append(n)
        elif isinstance(n, dict):
            nid = n.get("node_id", "")
            if nid:
                expected_ids.add(nid)
                raw_expected.append(nid)
    if not expected_ids:
        return MetricResult(name="3.1 知识点覆盖率", value=0.0, unit="%", detail={"note": "无预期知识点"})
    covered = expanded_nodes & expected_ids
    rate = round(len(covered) / len(expected_ids) * 100, 2) if expected_ids else 0.0
    return MetricResult(
        name="3.1 知识点覆盖率", value=rate, unit="%",
        detail={
            "预期节点数": len(expected_ids),
            "预期节点": raw_expected,
            "覆盖节点数": len(covered),
            "覆盖节点": [node_name_map.get(nid, nid) for nid in covered],
            "本轮覆盖": len(course_node_ids),
            "累计覆盖(含祖先)": len(expanded_nodes),
        }
    )

def calc_coverage_weakness(
    course_text: str, expected_content: dict[str, Any],
    history_nodes: set[str] | None = None,
) -> MetricResult:
    """M3 覆盖率 — 薄弱点命中率。

    与 3.1 一致：节点池加入「当前教学节点 + 历史累计节点」，
    并使用双向扩展（祖先+子孙）—— 当 course 写入 level-1 父节点时，
    expected 中更深层的 weak_point 子孙节点也应算作在同一教学范围内。
    """
    parsed = _parse_course_package(course_text)
    course_kp_ids = set(parsed.get("knowledge_node_ids", []))
    current_node_id = parsed.get("current_node_id")
    if current_node_id:
        course_kp_ids.add(current_node_id)
    if history_nodes:
        course_kp_ids.update(history_nodes)
    dag = _load_knowledge_dag()
    expanded = _expand_fully(course_kp_ids, dag)

    expected_weakpoints = expected_content.get("weakness_kcs") or expected_content.get("weak_points", [])
    if not expected_weakpoints:
        return MetricResult(name="3.2 薄弱点命中率", value=0.0, unit="%", detail={"note": "无薄弱点"})

    name_to_id = _load_node_id_by_name()
    expected_wp_ids: set[str] = set()
    raw_expected: list[str] = []
    for w in expected_weakpoints:
        if isinstance(w, str):
            resolved = _resolve_to_node_id(w, name_to_id)
            expected_wp_ids.add(resolved)
            raw_expected.append(w)
        elif isinstance(w, dict):
            nid = w.get("node_id", "")
            if nid:
                expected_wp_ids.add(nid)
                raw_expected.append(nid)
    hit = expanded & expected_wp_ids
    rate = round(len(hit) / len(expected_wp_ids) * 100, 2) if expected_wp_ids else 0.0
    node_name_map = _load_node_name_map()
    return MetricResult(
        name="3.2 薄弱点命中率", value=rate, unit="%",
        detail={"预期薄弱点数": len(expected_wp_ids),
                "预期薄弱点": raw_expected,
                "命中数": len(hit),
                "命中节点": [node_name_map.get(n, n) for n in hit],
                "本轮节点数": len(course_kp_ids),
                "双向扩展后节点数": len(expanded),
                }
    )


def calc_coverage_confusable(
    course_text: str, expected_content: dict[str, Any],
    node_name_map: dict[str, str],
    history_nodes: set[str] | None = None,
) -> MetricResult:
    """M3 覆盖率 — 混淆对覆盖率。

    与 3.1 一致：加入 current_node_id + 历史节点，并用双向扩展
    （祖先+子孙）—— course 写入 level-1 父节点时，其下 sibling 形式的
    confusion 子孙节点对也视为已覆盖（任一命中即算覆盖）。
    """
    parsed = _parse_course_package(course_text)
    course_kp_ids = set(parsed.get("knowledge_node_ids", []))
    current_node_id = parsed.get("current_node_id")
    if current_node_id:
        course_kp_ids.add(current_node_id)
    if history_nodes:
        course_kp_ids.update(history_nodes)
    dag = _load_knowledge_dag()
    expanded = _expand_fully(course_kp_ids, dag)

    confusable_pairs = expected_content.get("confusable_pairs") or expected_content.get("confusion_pairs", [])
    if not confusable_pairs:
        return MetricResult(name="3.3 混淆对覆盖率", value=0.0, unit="%", detail={"note": "无混淆对"})

    total_pairs = len(confusable_pairs)
    covered_pairs = 0
    pair_details = []
    name_to_id = _load_node_id_by_name()
    for pair in confusable_pairs:
        if isinstance(pair, list) and len(pair) >= 2:
            node_a = _resolve_to_node_id(str(pair[0]), name_to_id)
            node_b = _resolve_to_node_id(str(pair[1]), name_to_id)
        elif isinstance(pair, dict):
            node_a = _resolve_to_node_id(pair.get("node_a", pair.get("from", "")), name_to_id)
            node_b = _resolve_to_node_id(pair.get("node_b", pair.get("to", "")), name_to_id)
        else:
            continue
        a_covered = node_a in expanded
        b_covered = node_b in expanded
        if a_covered or b_covered:
            covered_pairs += 1
        pair_details.append({
            "node_a": node_name_map.get(node_a, node_a),
            "node_b": node_name_map.get(node_b, node_b),
            "a_covered": a_covered,
            "b_covered": b_covered,
        })

    rate = round(covered_pairs / total_pairs * 100, 2) if total_pairs else 0.0
    return MetricResult(
        name="3.3 混淆对覆盖率", value=rate, unit="%",
        detail={"总混淆对数": total_pairs, "覆盖对数": covered_pairs,
                "本轮节点数": len(course_kp_ids),
                "双向扩展后节点数": len(expanded),
                "混淆对明细": pair_details}
    )

# ── 其它指标计算 ──────────────────────────────────────────────────────────

def _file_exists_in_round(round_dir: Path, filename: str) -> bool:
    """检查产物文件是否存在（支持 feedback/ 子目录回退与数字后缀版本）。"""
    latest = common.resolve_latest_artifact_path(round_dir, filename)
    if latest.exists():
        return True
    feedback_dir = round_dir / "feedback"
    if feedback_dir.is_dir():
        latest_feedback = common.resolve_latest_artifact_path(feedback_dir, filename)
        if latest_feedback.exists():
            return True
    return False


def _teach_phase(round_dir: Path) -> str | None:
    """从 session_snapshot.json 读取 state.teach_phase（debate/single_agent/integration）。

    用于判定本论是否启用了辩论：``single_agent`` = 辩论开关关闭，没有
    cross_review / revision 类产物，不应把它们视为「缺失」来扣分或中止。
    读不到时返回 None（= 未知，调用方按保守策略执行）。
    """
    import json as _json

    snap = round_dir / "session_snapshot.json"
    if not snap.exists():
        return None
    try:
        data = _json.loads(snap.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    state = data.get("state") if isinstance(data, dict) else None
    if not isinstance(state, dict):
        return None
    phase = state.get("teach_phase")
    return phase if isinstance(phase, str) else None


def check_artifact_completeness(round_dir: Path, round_num: int, is_final_round: bool = False) -> MetricResult:
    """M4.1 5.1 产物完整率。

    自动区分辩论开启/关闭：
    - 辩论关闭 (``teach_phase == single_agent``)：cross_review / revision 本就
      不会产生，从 required 列表里剔除，避免无辜扣分；
    - 辩论开启 (debate / integration)：cross_review / final revision 参与评分。
    """
    always_required = ["course_package.md", "judge_report.md", "learning_path.md",
                       "learner_profile.md", "path_decision.md", "dual_axis_snapshot.md"]
    debate_required = ["expert_a_cross_review.md", "expert_b_cross_review.md"]
    final_revision_required = ["expert_a_revision.md", "expert_b_revision.md"]

    required_files: list[str] = list(always_required)
    phase = _teach_phase(round_dir)
    debate_enabled = phase is not None and phase != "single_agent"
    if debate_enabled:
        required_files.extend(debate_required)
        if is_final_round:
            required_files.extend(final_revision_required)
    if round_num > 1 and not is_final_round:
        # learner_profile_update 来自反馈阶段，末尾轮无反馈故不要求；
        # 可能在 feedback/ 下或 round 根下，由 _file_exists_in_round 统一判定。
        required_files.append("learner_profile_update.md")

    present = sum(1 for f in required_files if _file_exists_in_round(round_dir, f))
    total = len(required_files)
    rate = round(present / total * 100, 2) if total else 0.0
    detail: dict[str, Any] = {
        "存在文件数": present,
        "应有文件数": total,
        "应有文件列表": required_files,
        "teach_phase": phase or "unknown",
        "debate_enabled": debate_enabled,
    }
    return MetricResult(
        name="5.1 产物完整率", value=rate, unit="%", detail=detail,
    )

def scan_pii_leaks(round_dir: Path, profile_letter: str, round_num: int) -> MetricResult:
    """M10 PII 泄露检测 — 扫描 learner_profile_update.md / session_snapshot.json。"""
    pii_patterns = [
        ("身份证号", r"(?<!\.)\b\d{17}[\dXx]\b(?!\.)"),
        ("手机号", r"(?<!\.)\b1[3-9]\d{9}\b(?!\.)"),
        ("银行卡号", r"(?<!\.)\b\d{16,19}\b(?!\.)"),
        ("姓名", r"(?<![\u4e00-\u9fa5])(?:张|王|李|赵|刘|陈|杨|黄|周|吴|徐|孙|马|朱|胡|郭|何|高|林|罗|郑|梁)[\u4e00-\u9fa5]{1,2}(?![\u4e00-\u9fa5])"),
        ("地址", r"(?:省|市|区|县|镇|乡|村|路|街|巷|号|栋|单元)[^\s,。；;]{2,30}"),
    ]

    files_to_scan: list[Path] = []
    profile_update = round_dir / "learner_profile_update.md"
    if profile_update.exists():
        files_to_scan.append(profile_update)
    snapshot = round_dir / "session_snapshot.json"
    if snapshot.exists():
        files_to_scan.append(snapshot)

    total_leaks = 0
    leak_details: list[str] = []
    for fpath in files_to_scan:
        try:
            content = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pii_type, pattern in pii_patterns:
            matches = re.findall(pattern, content)
            for match in matches[:5]:
                leak_details.append(f"[{pii_type}] {fpath.name}: {match}")
                total_leaks += 1

    return MetricResult(
        name="5.3 PII合规检测", value=float(total_leaks), unit="条",
        detail={"泄露文件数": len(files_to_scan), "泄露详情": leak_details[:20]}
    )

def _extract_bkt_pl_map(text: str) -> dict[str, float]:
    """从 learner_profile_update.md 中提取 knowledge 维度的 node_id → pl 映射。"""
    pl_map: dict[str, float] = {}

    json_text: str | None = None
    m = re.search(r"## five_dimensions\s*```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        json_text = m.group(1)
    else:
        m2 = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m2:
            json_text = m2.group(1)
        else:
            stripped = text.strip()
            if stripped.startswith("{"):
                json_text = stripped

    if not json_text:
        return pl_map

    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return pl_map

    knowledge = data.get("knowledge", data)
    if isinstance(knowledge, dict):
        for node_id, node_data in knowledge.items():
            if isinstance(node_data, dict) and "pl" in node_data:
                try:
                    pl_map[node_id] = float(node_data["pl"])
                except (ValueError, TypeError):
                    pass

    return pl_map


def calc_bkt_advancement(prev_text: str | None, curr_text: str | None, course_text: str) -> MetricResult:
    """2.4 动态迭代触发率 — 画像级指标，每轮返回 / 不直接展示数值。

    判定规则：当前后轮 profile_update 存在且 BKT PL 值发生显著变化
    （上升或下降任一节点 |Δpl| ≥ 0.05）时，该轮视为「触发」动态迭代。
    画像级汇总：触发次数 / 有效比较次数 × 100%（R02 vs R01 … R05 vs R04）。
    每轮返回 unit="/"，triggered 状态存在 detail 中供画像级汇总。
    """
    if not prev_text or not curr_text:
        return MetricResult(
            name="2.4 动态迭代触发率", value=0.0, unit="/",
            detail={"triggered": False, "note": "缺少前后轮 profile_update，无法比较"}
        )

    prev_pls = _extract_bkt_pl_map(prev_text)
    curr_pls = _extract_bkt_pl_map(curr_text)

    if not prev_pls and not curr_pls:
        return MetricResult(
            name="2.4 动态迭代触发率", value=0.0, unit="/",
            detail={"triggered": False, "note": "BKT 数据解析为空"}
        )

    all_nodes = set(prev_pls.keys()) | set(curr_pls.keys())
    advanced_nodes: list[str] = []
    dropped_nodes: list[str] = []
    for nid in all_nodes:
        prev_pl = prev_pls.get(nid, 0.0)
        curr_pl = curr_pls.get(nid, 0.0)
        if curr_pl - prev_pl >= 0.05:
            advanced_nodes.append(nid)
        elif prev_pl - curr_pl >= 0.05:
            dropped_nodes.append(nid)

    changed_nodes = len(advanced_nodes) + len(dropped_nodes)
    triggered = changed_nodes > 0

    return MetricResult(
        name="2.4 动态迭代触发率",
        value=0.0,
        unit="/",
        detail={
            "triggered": triggered,
            "total_nodes": len(all_nodes),
            "changed_nodes": changed_nodes,
            "advanced_nodes": len(advanced_nodes),
            "dropped_nodes": len(dropped_nodes),
            "advanced": advanced_nodes[:10],
            "dropped": dropped_nodes[:10],
        }
    )

# ── 外部 LLM 结果加载（统一三文件产物 + 命名 section 读取）─────────────────────

def _glob_one(llm_dir: Path, pattern: str) -> Path | None:
    """glob 单文件匹配；优先排除中间产物（answers）。"""
    all_matching = list(llm_dir.glob(pattern))
    eval_results = [f for f in all_matching if "answers" not in f.name]
    matching = sorted(eval_results if eval_results else all_matching)
    return matching[0] if matching else None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_round_section(
    profile_letter: str, round_num: int, section: str, learner_prefix: str | None = None,
) -> tuple[dict[str, Any] | None, Path | None]:
    """从 round_indicator_{model}_{profile}_{round:02d}.json 的指定 section 读取数据。

    Returns: (section_data, file_path) — 若文件不存在或无该 section 则 section_data 为 None。
    """
    llm_dir = _resolve_llm_results_dir(learner_prefix)
    path = _glob_one(llm_dir, f"round_indicator_*_{profile_letter}_{round_num:02d}.json")
    if path is None:
        return None, None
    data = _read_json(path)
    if data is None:
        return None, path
    # 兼容两种：新的 section 聚合 或 旧的独立文件
    if section in data:
        section_data = data[section]
        # 失败标记（LLM 评估失败写入的 status=failed）：按"无结果"处理，不参与指标合并
        if isinstance(section_data, dict) and section_data.get("status") == "failed":
            return None, path
        return section_data, path
    # 回退：旧独立文件格式（例如整体 JSON 就是该 section 内容）
    return data, path


def _load_profile_section(
    profile_letter: str, section: str, learner_prefix: str | None = None,
) -> tuple[dict[str, Any] | None, Path | None]:
    """从 profile_indicator_{model}_{profile}.json 的指定 section 读取数据。"""
    llm_dir = _resolve_llm_results_dir(learner_prefix)
    path = _glob_one(llm_dir, f"profile_indicator_*_{profile_letter}.json")
    if path is None:
        return None, None
    data = _read_json(path)
    if data is None:
        return None, path
    if section in data:
        section_data = data[section]
        # 失败标记按"无结果"处理
        if isinstance(section_data, dict) and section_data.get("status") == "failed":
            return None, path
        return section_data, path
    return data, path


def _load_system_section(
    section: str, learner_prefix: str | None = None,
) -> tuple[dict[str, Any] | None, Path | None]:
    """从 system_indicator_{model}.json 的指定 section 读取数据（全局唯一）。"""
    llm_dir = _resolve_llm_results_dir(learner_prefix)
    path = _glob_one(llm_dir, "system_indicator_*.json")
    if path is None:
        return None, None
    data = _read_json(path)
    if data is None:
        return None, path
    if section in data:
        section_data = data[section]
        # 失败标记按"无结果"处理
        if isinstance(section_data, dict) and section_data.get("status") == "failed":
            return None, path
        return section_data, path
    return data, path


def load_m8_external_result(profile_letter: str, round_num: int) -> MetricResult | None:
    """加载 6.2 异议闭环外部 LLM 评估结果（round_indicator > objection_loop）。"""
    section, path = _load_round_section(profile_letter, round_num, "objection_loop")
    if section is None:
        return None
    raw = section.get("raw_llm_response", {})
    metrics = section.get("metrics", {})
    detail = metrics.get("detail", {})
    total = raw.get("total_objections") or detail.get("总🔴异议数", 0)
    closed = raw.get("closed_loop_count") or detail.get("闭环数（采纳+修正）", 0)
    rate = round((closed or 0) / (total or 1) * 100, 2) if total else 100.0
    return MetricResult(
        name="6.2 异议闭环", value=metrics.get("value", rate) if metrics else rate, unit="分",
        detail={
            "评估方式": "外部 LLM (round-indicator 异议闭环)",
            "原始文件": path.name if path else "-",
            "总异议数": total,
            "闭环数": closed,
            "整体评分": raw.get("overall_score", 0),
        }
    )


def load_m9_external_result(profile_letter: str, round_num: int) -> MetricResult | None:
    """加载 1.4.1 溯源可验证率外部评估结果（round_indicator > statement 内）。"""
    section, _path = _load_round_section(profile_letter, round_num, "statement")
    if section is None:
        return None
    evals = (section.get("evaluations") or [])
    total = len(evals)
    if total == 0:
        return MetricResult(name="1.4.1 溯源可验证率", value=0.0, unit="%", detail={"note": "无陈述"})

    sourced = [e for e in evals if e.get("source_verifiable") is True]
    total_sourced = len(sourced)
    if total_sourced > 0:
        verified = sum(1 for e in sourced if e.get("content_relevance") is True)
        m9_rate = round(verified / total_sourced * 100, 2)
        return MetricResult(
            name="1.4.1 溯源可验证率", value=m9_rate, unit="%",
            detail={"评估方式": "外部 LLM", "带来源陈述数": total_sourced, "内容支撑数": verified}
        )
    return MetricResult(name="1.4.1 溯源可验证率", value=0.0, unit="%", detail={"note": "无带来源陈述"})


def load_coverage_external_result(profile_letter: str, round_num: int) -> list[MetricResult]:
    """加载 3.1/3.2/3.3 覆盖率外部 LLM 评估结果（round_indicator > coverage）。

    返回 3 个 MetricResult，分别对应 3.1 知识点覆盖率、3.2 薄弱点命中率、3.3 混淆对覆盖率。
    若 LLM 结果不存在则返回空列表。
    """
    section, path = _load_round_section(profile_letter, round_num, "coverage")
    if section is None:
        return []

    mapping = [
        ("section_coverage", "3.1 知识点覆盖率"),
        ("weakness_coverage", "3.2 薄弱点命中率"),
        ("confusion_coverage", "3.3 混淆对覆盖率"),
    ]
    # 区分真实 coverage section 与 _load_round_section 的回退（整个 JSON 当 section）：
    # 真实 coverage section 必含上述子节之一；否则视为未运行 coverage 评估，返回空列表，
    # 让报告显示「-」而非误导性的 0.0分（对齐「未计算显示未计算」偏好）。
    if not any(key in section for key, _ in mapping):
        return []

    results: list[MetricResult] = []
    for key, name in mapping:
        sub = section.get(key, {})
        score = sub.get("score", 0)
        results.append(MetricResult(
            name=name, value=score, unit="分",
            detail={
                "评估方式": "外部 LLM (round-indicator coverage)",
                "原始文件": path.name if path else "-",
                "comment": sub.get("comment", ""),
            }
        ))
    return results


# ── 深化指标计算（M1 子分 / M9-b / M14-M17） ────────────────────────────

def _is_missed_eval(e: dict[str, Any]) -> bool:
    """判定一条 uncertain 是否是「LLM 未返回评估结果」的兜底占位。

    与 evaluator_LLM._is_llm_missed_eval 语义一致，但本地定义以避免
    calculate.py 依赖 evaluator_LLM 的配置加载（见本模块 1305 行注释）。
    这类 uncertain 是评估器故障，聚合时应排除出分母，避免稀释谬误率。
    """
    if e.get("verdict") != "uncertain":
        return False
    return "LLM 未返回评估结果" in str(e.get("reasoning") or "")


def load_statement_evaluations(profile_letter: str, round_num: int) -> list[dict[str, Any]] | None:
    """加载 round_indicator statement section 中的 evaluations。

    每条评估记录的 error_type 由裁判 LLM 在评估时直接打出
    （∈ factual/logical/instructional/other），本函数不再做启发式补全。
    """
    section, _path = _load_round_section(profile_letter, round_num, "statement")
    if section is None:
        return None
    return section.get("evaluations") or []


def calc_m1_subtypes(evaluations: list[dict[str, Any]] | None) -> list[MetricResult]:
    """M1 拆三子分：1.3.1 事实性 / 1.3.2 逻辑性 / 1.3.3 指令性 谬误率。

    分母 = 该 error_type 的有效陈述数（排除 LLM 未返回的 missed 占位）；
    分子 = 该 error_type 中 verdict == "incorrect" 的条数。
    分母为 0（无该类陈述或全为 missed）时标 N/A 而非 0.0，避免虚假完美。
    """
    type_map = {
        "1.3.1 事实性谬误率": "factual",
        "1.3.2 逻辑性谬误率": "logical",
        "1.3.3 指令性谬误率": "instructional",
    }
    if not evaluations:
        return [
            MetricResult(
                name=n, value=0.0, unit="%",
                detail={"computed": False, "note": "N/A：缺少 statement 外部LLM结果"}
            )
            for n in type_map
        ]
    # 排除评估器故障占位（与 calc_hallucination_rate 主指标口径对齐）
    effective = [e for e in evaluations if not _is_missed_eval(e)]
    out: list[MetricResult] = []
    for name, key in type_map.items():
        subset = [e for e in effective if str(e.get("error_type") or "other").lower() == key]
        total = len(subset)
        incorrect = sum(1 for e in subset if e.get("verdict") == "incorrect")
        if total == 0:
            out.append(MetricResult(
                name=name, value=0.0, unit="%",
                detail={"computed": False, "该类型陈述数": 0, "错误数": 0,
                        "评估方式": "外部 LLM", "note": "N/A：该类有效陈述数为 0"}
            ))
        else:
            rate = round(incorrect / total * 100, 2)
            out.append(MetricResult(
                name=name, value=rate, unit="%",
                detail={"computed": True, "该类型陈述数": total, "错误数": incorrect,
                        "评估方式": "外部 LLM"}
            ))
    return out


def calc_m9b(evaluations: list[dict[str, Any]] | None) -> MetricResult:
    """1.4.2 溯源内容支撑率。"""
    if not evaluations:
        return MetricResult(name="1.4.2 溯源内容支撑率", value=0.0, unit="%", detail={"computed": False, "note": "未计算"})
    sourced = [e for e in evaluations if e.get("source_verifiable") is True]
    total = len(sourced)
    if total == 0:
        return MetricResult(name="1.4.2 溯源内容支撑率", value=0.0, unit="%", detail={"computed": True, "带来源陈述数": 0, "note": "无带来源陈述"})
    supported = sum(1 for e in sourced if e.get("content_relevance") is True or e.get("relevance_check_result") in ("relevant", "partially_relevant"))
    rate = round(supported / total * 100, 2)
    return MetricResult(
        name="1.4.2 溯源内容支撑率", value=rate, unit="%",
        detail={"computed": True, "带来源陈述数": total, "内容支撑数": supported}
    )


def load_m14_external_result(profile_letter: str) -> dict[str, Any] | None:
    """加载 1.5 内容跨轮自洽率结果（profile_indicator > cross_round section）。"""
    section, _path = _load_profile_section(profile_letter, "cross_round")
    return section


def load_m15_external_result(
    profile_letter: str, learner_prefix: str = "multi",
) -> dict[str, Any] | None:
    """加载 6.1 对抗稳健率结果（system_indicator > m6_adversarial section）。"""
    section, _path = _load_system_section("m6_adversarial", learner_prefix)
    return section


def load_m16_external_result(
    profile_letter: str, learner_prefix: str = "multi",
) -> dict[str, Any] | None:
    """加载 6.2 边界拒答恰当率结果（system_indicator > m6_boundary section）。"""
    section, _path = _load_system_section("m6_boundary", learner_prefix)
    return section


def load_m17_external_result(profile_letter: str, round_num: int) -> dict[str, Any] | None:
    """加载 2.5 检索正确性结果（round_indicator > retrieval section）。"""
    section, _path = _load_round_section(profile_letter, round_num, "retrieval")
    return section


def load_pii_external_result(profile_letter: str, round_num: int) -> MetricResult | None:
    """加载 5.3 PII 合规检测结果（round_indicator > pii section）。"""
    section, _path = _load_round_section(profile_letter, round_num, "pii")
    if section is None:
        return None

    summary = section.get("summary", {})
    compliance_rate = summary.get("compliance_rate", 100.0)
    real_leaks = summary.get("real_leaks", 0)
    total_checks = summary.get("total_checks", 0)
    pii_details = section.get("pii_details", [])
    verdict = section.get("compliance_verdict", "compliant")

    return MetricResult(
        name="5.3 PII合规检测", value=compliance_rate, unit="%",
        detail={
            "评估方式": "外部 LLM (round-indicator)",
            "合规率": compliance_rate,
            "泄露数": real_leaks,
            "检测分块数": total_checks,
            "合规判定": verdict,
            "PII详情": pii_details[:10],
        }
    )


def _placeholder_metric(name: str, mode: str) -> MetricResult:
    return MetricResult(
        name=name, value=0.0, unit="%",
        detail={"computed": False, "note": f"未计算：缺少外部LLM结果，请先运行 evaluator_LLM.py --mode {mode}"}
    )


def calc_m14(data: dict[str, Any] | None, profile_letter: str) -> MetricResult:
    """1.5 内容跨轮自洽率。"""
    if not data:
        return _placeholder_metric("1.5 内容跨轮自洽率", "m1_cross_round")
    return MetricResult(
        name="1.5 内容跨轮自洽率", value=data.get("self_consistency_rate", 0.0), unit="%",
        detail={"computed": True, "事实点总数": data.get("total_fact_points", 0), "矛盾数": data.get("contradicted", 0)}
    )


def calc_m15(data: dict[str, Any] | None, profile_letter: str) -> MetricResult:
    """6.1 对抗稳健率（系统级单次探针）。"""
    if not data:
        return _placeholder_metric("6.1 对抗稳健率", "m6_adversarial")
    return MetricResult(
        name="7.1 对抗稳健率", value=data.get("pass_rate", 0.0), unit="%",
        detail={"computed": True, "问题数": data.get("total_questions", 0), "通过数": data.get("passed", 0), "评估方式": data.get("methodology", "material_proxy")}
    )


def calc_m16(data: dict[str, Any] | None, profile_letter: str) -> MetricResult:
    """6.2 边界拒答恰当率（系统级单次探针）。"""
    if not data:
        return _placeholder_metric("6.2 边界拒答恰当率", "m6_boundary")
    return MetricResult(
        name="7.2 边界拒答恰当率", value=data.get("appropriate_rate", 0.0), unit="%",
        detail={"computed": True, "问题数": data.get("total_questions", 0), "恰当数": data.get("appropriate", 0), "评估方式": data.get("methodology", "material_proxy")}
    )


def calc_m17(data: dict[str, Any] | None, profile_letter: str, round_num: int) -> list[MetricResult]:
    """2.5 检索正确性：返回准确率 + 完整率两个子指标。

    对 LLM 输出 schema 做双向兼容（方案A）：
    - 首选：data 中 accurate_rate / complete_rate （旧聚合字段）；
    - 兜底：若 accurate_rate 异常（为 0 但 evaluations 中其实有大量 accurate verdict），
      则按 evaluations[*] 下无论是「顶层 verdict」还是「嵌套 evaluations[].verdict / summary」
      的形状统一归一化后重算。
    """
    if not data:
        return [
            _placeholder_metric("4.1 检索准确率", "m2_retrieval"),
            _placeholder_metric("4.2 检索完整率", "m2_retrieval"),
        ]
    total = data.get("total_chunks", 0) or 0
    accurate = data.get("accurate", 0) or 0
    complete = data.get("complete", 0) or 0
    accurate_rate = data.get("accurate_rate", 0.0) or 0.0
    complete_rate = data.get("complete_rate", 0.0) or 0.0

    # 当 aggregate 字段可疑（都是 0 但 evaluations 非空）时统一重算。
    # 触发条件：(accurate==0 or complete==0) AND evaluations 存在且非空 → 归一化重算。
    evaluations = data.get("evaluations") or []
    needs_recalc = (
        (accurate == 0 or complete == 0 or accurate_rate == 0.0 or complete_rate == 0.0)
        and isinstance(evaluations, list)
        and len(evaluations) > 0
    )
    if needs_recalc:
        total_calc, accurate_calc, complete_calc = _recalc_retrieval_from_evaluations(evaluations)
        # 仅当重算得出"非0结果"时才覆盖（避免把 legitimate 的真实 0 又重写一遍但结果一样）
        if total_calc > 0 and (accurate_calc > 0 or complete_calc > 0):
            total = total_calc
            accurate = accurate_calc
            complete = complete_calc
            accurate_rate = round(accurate / total * 100, 2) if total else 0.0
            complete_rate = round(complete / total * 100, 2) if total else 0.0
        elif total_calc > 0:
            # 重算结果仍是 0 但至少 total 归一（例如所有子项真的都 inaccurate）
            total = total_calc
            accurate = accurate_calc
            complete = complete_calc

    # 再兜底：若 accurate_rate == 0 但仍可从 evaluations 中 summary/子对象计算
    # （此处避免重复计算——上面已经做了）。同时为了避免原始 accurate=0, complete=0, total=0
    # 情形仍占位 0，detail 标注"重算已执行"/"按外部原值"。
    recomputed = bool(needs_recalc and (accurate > 0 or complete > 0 or total > 0))

    return [
        MetricResult(
            name="4.1 检索准确率",
            value=accurate_rate,
            unit="%",
            detail={
                "computed": True,
                "recounted": recomputed,
                "chunk数": total,
                "准确数": accurate,
            },
        ),
        MetricResult(
            name="4.2 检索完整率",
            value=complete_rate,
            unit="%",
            detail={
                "computed": True,
                "recounted": recomputed,
                "chunk数": total,
                "完整数": complete,
            },
        ),
    ]


def _recalc_retrieval_from_evaluations(evaluations: list[Any]) -> tuple[int, int, int]:
    """calculate 侧自包含的 retrieval evaluation 归一化重算。
    与 evaluator 侧语义保持一致，但不 import evaluator_LLM（避免 LLM 配置依赖）。

    Returns: (total, accurate, complete)
    """
    def _sub_evals(chunk: Any) -> list[dict[str, Any]]:
        if not isinstance(chunk, dict):
            return []
        subs = chunk.get("evaluations")
        if isinstance(subs, list) and subs:
            return [s for s in subs if isinstance(s, dict)]
        if chunk.get("accuracy_verdict") or chunk.get("completeness_verdict"):
            return [chunk]
        summary = chunk.get("summary")
        if isinstance(summary, dict):
            acc_rate = summary.get("accurate_rate", summary.get("complete_rate"))
            if isinstance(acc_rate, (int, float)):
                verdict_a = "accurate" if acc_rate >= 0.5 else "inaccurate"
                comp_rate = summary.get("complete_rate", acc_rate)
                cr = comp_rate if isinstance(comp_rate, (int, float)) else (
                    acc_rate if isinstance(acc_rate, (int, float)) else 0
                )
                verdict_c = "complete" if cr >= 0.5 else "incomplete"
                return [{
                    "accuracy_verdict": verdict_a,
                    "completeness_verdict": verdict_c,
                    "_from_summary": True,
                }]
        return []

    total = 0
    accurate = 0
    complete = 0
    for e in evaluations:
        if not isinstance(e, dict):
            continue
        total += 1
        subs = _sub_evals(e)
        verdict_a_hit = False
        verdict_c_hit = False
        for s in subs:
            if s.get("accuracy_verdict") == "accurate":
                verdict_a_hit = True
            if s.get("completeness_verdict") == "complete":
                verdict_c_hit = True
        if not verdict_a_hit and not verdict_c_hit:
            # 再看顶层 / summary
            if e.get("accuracy_verdict") == "accurate":
                verdict_a_hit = True
            if e.get("completeness_verdict") == "complete":
                verdict_c_hit = True
            summary = e.get("summary")
            if isinstance(summary, dict):
                if summary.get("accurate_count", 0) > 0:
                    verdict_a_hit = True
                if summary.get("complete_count", 0) > 0:
                    verdict_c_hit = True
        if verdict_a_hit:
            accurate += 1
        if verdict_c_hit:
            complete += 1
    return total, accurate, complete

def calculate_system_level_metrics(learner_prefix: str = "multi") -> list[MetricResult]:
    """计算系统级探针指标：M15 对抗稳健率 / M16 边界拒答恰当率。

    这两个指标独立于画像，所有画像共享同一数值。
    """
    metrics: list[MetricResult] = []
    try:
        metrics.append(calc_m15(load_m15_external_result("system", learner_prefix), "system"))
        metrics.append(calc_m16(load_m16_external_result("system", learner_prefix), "system"))
    except Exception as e:
        print(f"  ⚠️ M15/M16 系统级计算异常: {e}")
    return metrics

# 保留向后兼容的别名
calculate_profile_level_metrics = calculate_system_level_metrics

# ── 外部LLM维度展示 ──────────────────────────────────────────────────────

_M1_LLM_DIMENSIONS: list[tuple[str, str]] = [
    ("hallucination", "幻觉评估(Hallucination)"),
]

_M2_LLM_DIMENSIONS: list[tuple[str, str]] = [
    ("helpfulness", "有用性(Helpfulness)"),
    ("relevance", "相关性(Relevance)"),
]

def _get_llm_dim_score(
    profile_letter: str, round_num: int, dim_key: str, llm_results: dict[str, Any] | None,
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

# ── 主入口：单轮计算 ─────────────────────────────────────────────────────

def calculate_round(
    profile_letter: str, round_num: int,
    session_dir: Path | None = None, expected_path: Path | None = None,
    history_nodes: set[str] | None = None, prev_profile_update: str | None = None,
    learner_prefix: str = "multi",
) -> RoundMetrics:
    """计算指定画像指定轮次的全部指标（设置并恢复活动 learner 前缀）。"""
    global _ACTIVE_LEARNER_PREFIX
    _prev_active_prefix = _ACTIVE_LEARNER_PREFIX
    _ACTIVE_LEARNER_PREFIX = learner_prefix
    try:
        return _calculate_round_impl(
            profile_letter=profile_letter,
            round_num=round_num,
            session_dir=session_dir,
            expected_path=expected_path,
            history_nodes=history_nodes,
            prev_profile_update=prev_profile_update,
            learner_prefix=learner_prefix,
        )
    finally:
        # 异常（含 FileNotFoundError）也必须恢复，避免前缀泄漏到后续调用。
        _ACTIVE_LEARNER_PREFIX = _prev_active_prefix


def _calculate_round_impl(
    profile_letter: str, round_num: int,
    session_dir: Path | None = None, expected_path: Path | None = None,
    history_nodes: set[str] | None = None, prev_profile_update: str | None = None,
    learner_prefix: str = "multi",
) -> RoundMetrics:
    """计算指定画像指定轮次的全部指标（实现体）。"""
    if session_dir is None:
        session_dir = _EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{profile_letter}"
    if not session_dir.exists():
        raise FileNotFoundError(f"找不到画像 {profile_letter} 的测试快照目录: {session_dir}")

    round_dir = session_dir / f"round-{round_num:02d}"
    if not round_dir.exists():
        round_dir = session_dir / f"round_{round_num:02d}"
    if not round_dir.exists():
        raise FileNotFoundError(f"找不到轮次目录: {session_dir}/round-{round_num:02d}")

    course_text = _read_text(common.resolve_latest_artifact_path(round_dir, "course_package.md"))
    judge_text = _read_text(common.resolve_latest_artifact_path(round_dir, "judge_report.md"))
    review_a_text = _read_text(round_dir / "expert_a_cross_review.md")
    review_b_text = _read_text(round_dir / "expert_b_cross_review.md")
    path_text = _read_text(round_dir / "learning_path.md")

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

        profile_update_path = feedback_dir / "learner_profile_update.md"
        if profile_update_path.exists():
            profile_update_text = _read_text(profile_update_path)
        else:
            alt_path = round_dir / "learner_profile_update.md"
            if alt_path.exists():
                profile_update_text = _read_text(alt_path)

    if expected_path is None:
        for candidate in (_PROFILES_DIR / f"expected_{profile_letter}_{round_num:02d}.json", _PROFILES_DIR / f"expected_{profile_letter}.json"):
            if candidate.exists():
                expected_path = candidate
                break
    expected_missing = (expected_path is None or not expected_path.exists())
    if expected_missing:
        expected_data: dict[str, Any] = {}
        expected_candidates = [
            str(_PROFILES_DIR / f"expected_{profile_letter}_{round_num:02d}.json"),
            str(_PROFILES_DIR / f"expected_{profile_letter}.json"),
        ]
    else:
        expected_data = json.loads(expected_path.read_text(encoding="utf-8"))
        expected_candidates = [str(expected_path)]
    expected_content = expected_data.get("expected_course_content", {})
    node_name_map = _load_node_name_map()

    rm = RoundMetrics(profile_letter=profile_letter, round_num=round_num)

    available_rounds = sorted(
        int(d.name.split("-")[1] if d.name.startswith("round-") else d.name.split("_")[1])
        for d in session_dir.iterdir()
        if d.is_dir() and (d.name.startswith("round-") or d.name.startswith("round_"))
    )
    is_final = round_num >= max(available_rounds) if available_rounds else True

    # 4.1 5.1 产物完整率
    rm.metrics.append(check_artifact_completeness(round_dir, round_num, is_final_round=is_final))

    # 6.2 异议闭环：优先采用外部 LLM 结果（round_indicator_*.json section=objection_loop），缺失时回退占位
    m8_result = load_m8_external_result(profile_letter, round_num)
    if m8_result:
        rm.metrics.append(m8_result)
    else:
        rm.metrics.append(calc_objection_loop(judge_text, review_a_text, review_b_text))
    # 6.1 异议率 (脚本计算 (🔴+🟡)/总批注)
    rm.metrics.append(calc_hallucination_expert_review(review_a_text, review_b_text))
    # 1.2 裁判 Agent 准确性评分
    rm.metrics.append(calc_hallucination_judge_accuracy(judge_text))

    # 匹配度（双边区间）
    rm.metrics.append(calc_matching_difficulty(course_text, path_text, node_name_map, profile_update_text=profile_update_text))
    
    # 资源形态 (M4.2) — 改为统计大类/小类数
    for mr in calc_resource_morphology(course_text):
        rm.metrics.append(mr)

    # M3 覆盖率（3.1/3.2/3.3）— 已弃用脚本硬匹配，完全改用 LLM 语义评价。
    # LLM 评估结果从 round_indicator JSON 的 coverage section 加载。
    for mr in load_coverage_external_result(profile_letter, round_num):
        rm.metrics.append(mr)

    # M9 知识溯源可验证率
    m9_result = load_m9_external_result(profile_letter, round_num)
    if m9_result:
        rm.metrics.append(m9_result)

    # 深化指标：M1 子分 / M9-b
    try:
        stmt_evals = load_statement_evaluations(profile_letter, round_num)
        for mr in calc_m1_subtypes(stmt_evals):
            rm.metrics.append(mr)
        rm.metrics.append(calc_m9b(stmt_evals))
    except Exception as e:
        print(f"  ⚠️ M1 子分 / M9-b 计算异常: {e}")

    # 深化指标：M14 / M17
    try:
        rm.metrics.append(calc_m14(load_m14_external_result(profile_letter), profile_letter))
        for mr in calc_m17(load_m17_external_result(profile_letter, round_num), profile_letter, round_num):
            rm.metrics.append(mr)
    except Exception as e:
        print(f"  ⚠️ M14/M17 计算异常: {e}")

    # 动态迭代（2.4 动态迭代触发率）— 始终输出指标
    if prev_profile_update:
        rm.metrics.append(calc_bkt_advancement(prev_profile_update, profile_update_text, course_text))
    else:
        rm.metrics.append(MetricResult(
            name="2.4 动态迭代触发率", value=0.0, unit="/",
            detail={"triggered": False, "note": "首轮：缺少前一轮 profile_update，无法比较"}
        ))

    # M5.3 PII 合规检测（仅接受外部 LLM 评估，无结果则不添加指标）
    pii_result = load_pii_external_result(profile_letter, round_num)
    if pii_result:
        rm.metrics.append(pii_result)

    return rm

# ── 格式化输出 ──────────────────────────────────────────────────────────

def format_result(rm: RoundMetrics, llm_results: dict[str, Any] | None = None) -> str:
    """格式化输出结果（M1~M6 新分类 · 三张表分组）。"""
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

    # ── 表1: 脚本计算指标 ──────────────────────────────────────
    lines.append("")
    lines.append("── 表1: 脚本计算指标 ──")

    # M1 幻觉率
    _append_group("M1 幻觉率", [
        "6.2 异议闭环",
        "1.1 裁判Agent准确性评分",
    ])

    # M2 匹配度
    _append_group("M2 匹配度", [
        "2.1 难度符合度",
        "2.4 动态迭代触发率",
    ])

    # M3 覆盖率 — 完全由 LLM 语义评价，见下方表2「外部LLM评价指标」

    # M4 执行完整性
    _append_group("M4 执行完整性", [
        "4.1 5.1 产物完整率",
        "5.2.1 资源大类数",
        "5.2.2 资源小类数",
    ])

    # M5 其它指标
    _append_group("M5 其它指标", [
        "5.3 PII合规检测",
        "6.1 异议率",
    ])

    # ── 表2: 外部LLM评价指标 ──────────────────────────────────
    lines.append("")
    lines.append("── 表2: 外部LLM评价指标 ──")

    # M1 幻觉率 — 外部LLM维度
    lines.append("")
    lines.append("【M1 幻觉率 — 外部LLM评估器维度】")
    m1_dims_found = False
    for dim_key, dim_label in _M1_LLM_DIMENSIONS:
        result = _get_llm_dim_score(rm.profile_letter, rm.round_num, dim_key, llm_results)
        if result is not None:
            m1_dims_found = True
            val, u = result
            lines.append(f"  {dim_label}: {val}{u}")
    if not m1_dims_found:
        lines.append("  (无外部LLM评估数据)")

    # M1 幻觉率 — 深化指标
    _append_group("M1 幻觉率 — 深化指标", [
        "1.3.1 事实性谬误率",
        "1.3.2 逻辑性谬误率",
        "1.3.3 指令性谬误率",
        "1.4.1 溯源可验证率",
        "1.4.2 溯源内容支撑率",
        "1.5 内容跨轮自洽率",
    ])

    # M2 匹配度 — 外部LLM维度
    lines.append("")
    lines.append("【M2 匹配度 — 外部LLM维度】")
    m2_dims_found = False
    for dim_key, dim_label in _M2_LLM_DIMENSIONS:
        result = _get_llm_dim_score(rm.profile_letter, rm.round_num, dim_key, llm_results)
        if result is not None:
            m2_dims_found = True
            val, u = result
            lines.append(f"  {dim_label}: {val}{u}")
    if not m2_dims_found:
        lines.append("  (无外部LLM评估数据)")

    # M2 匹配度 — 检索正确性
    _append_group("M2 匹配度 — 检索正确性", [
        "4.1 检索准确率",
        "4.2 检索完整率",
    ])

    # M3 覆盖率 — 外部LLM语义验证
    _append_group("M3 覆盖率 — 外部LLM语义验证", [
        "3.1 知识点覆盖率",
        "3.2 薄弱点命中率",
        "3.3 混淆对覆盖率",
    ])

    # M4 执行完整性 — 资源形态
    m7 = next((m for m in rm.metrics if m.name == "资源形态评估"), None)
    if m7:
        lines.append("")
        lines.append("【M4 执行完整性 — 资源形态】")
        lines.append(f"  {m7.name}: {m7.value}{m7.unit}")
        for k, v in m7.detail.items():
            lines.append(f"    · {k}: {v}")

    # ── 表3: 问答质量测试指标 ─────────────────────────────────
    lines.append("")
    lines.append("── 表3: 问答质量测试指标 ──")
    _append_group("M7 问答质量测试", [
        "7.1 对抗稳健率",
        "7.2 边界拒答恰当率",
    ])

    return "\n".join(lines)

# ── CLI 入口 ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="评估指标计算脚本")
    p.add_argument("--profile", required=True, help="画像字母（如 B）")
    p.add_argument("--round", type=int, default=1, help="轮次编号（如 1，默认 1）")
    p.add_argument("--session-dir", type=Path, default=None, help="系统产物目录（可选）")
    p.add_argument("--expected", type=Path, default=None, help="expected 文件路径（可选）")
    p.add_argument("--learner-prefix", default="multi",
                   help="学习者前缀（默认 multi；决定外部LLM结果目录 record_{前缀}）")
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
            learner_prefix=args.learner_prefix,
        )
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return 1

    if args.json:
        result = {
            "profile_letter": rm.profile_letter,
            "round_num": rm.round_num,
            "metrics": [
                {"name": m.name, "value": m.value, "unit": m.unit, "detail": m.detail}
                for m in rm.metrics
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_result(rm))

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
