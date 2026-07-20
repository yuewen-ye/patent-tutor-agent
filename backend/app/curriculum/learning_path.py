from __future__ import annotations

import heapq
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_ASSET_ROOT = Path(__file__).resolve().parent / "data"
_WEIGHTS = {"低": 0.35, "中": 0.6, "高": 0.8, "极高": 1.0}


@lru_cache(maxsize=1)
def _raw_knowledge_dag() -> dict[str, Any]:
    return json.loads((_ASSET_ROOT / "knowledge-dag.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _raw_confusion_pairs() -> dict[str, Any]:
    return json.loads((_ASSET_ROOT / "confusion-pairs.json").read_text(encoding="utf-8"))


def load_knowledge_dag() -> dict[str, Any]:
    raw = _raw_knowledge_dag()
    return {
        "version": raw["meta"]["version"],
        "meta": deepcopy(raw["meta"]),
        "nodes": deepcopy(raw["dag"]["nodes"]),
        "edges": deepcopy(raw["dag"]["edges"]),
    }


def load_confusion_pairs() -> dict[str, Any]:
    raw = _raw_confusion_pairs()
    pairs = []
    for pair in raw["confusion_pairs"]:
        normalized = deepcopy(pair)
        normalized["concept_a"] = pair["node_a"]
        normalized["concept_b"] = pair["node_b"]
        pairs.append(normalized)
    return {
        "version": raw["meta"]["version"],
        "meta": deepcopy(raw["meta"]),
        "confusion_pairs": pairs,
    }


def _build_node_name_index(knowledge: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """知识 DAG 的 节点名↔节点id 双向索引（用于把学员薄弱点解析到节点）。"""
    nodes = knowledge.get("nodes", [])
    name_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("node_id") or "")
        nm = str(n.get("node_name") or "")
        if nid:
            id_to_name[nid] = nm
        if nm:
            name_to_id[nm] = nid
    return name_to_id, id_to_name


def _resolve_weak_nodes(
    weak_points: list[Any], name_to_id: dict[str, str], id_to_name: dict[str, str]
) -> set[str]:
    """把学员薄弱点解析为节点 id 集合（支持中文名 / 英文 id / 名字子串）。"""
    resolved: set[str] = set()
    for w in weak_points or []:
        w = str(w)
        if not w:
            continue
        if w in name_to_id:
            resolved.add(name_to_id[w])
        elif w in id_to_name:
            resolved.add(w)
        else:
            for nm, nid in name_to_id.items():
                if nm and nm in w:
                    resolved.add(nid)
    return resolved


def _pair_weak_match(
    pair: dict[str, Any],
    weak_points: list[Any],
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
) -> tuple[bool, str]:
    """学员薄弱点是否与某混淆对相关（用节点名 / 英文 id / 标题做相似匹配）。

    返回 (是否命中, 命中原因)。命中条件：薄弱点解析到的节点落在混淆对
    node_a/node_b/related_nodes 中，或薄弱点文本包含混淆对的中文节点名/标题。
    这样写英文 id（novelty）或中文名（新颖性）都能命中，不必死等节点名子串。
    """
    concept_a = str(pair.get("concept_a") or pair.get("node_a", ""))
    concept_b = str(pair.get("concept_b") or pair.get("node_b", ""))
    related = [str(r) for r in (pair.get("related_nodes") or []) if r]
    pool = {concept_a, concept_b} | set(related)
    keywords = set(pool)
    for nid in pool:
        nm = id_to_name.get(nid)
        if nm:
            keywords.add(nm)
    title = pair.get("title")
    if title:
        keywords.add(str(title))
    weak_text = " ".join(str(w) for w in weak_points)
    text_matched = any(k and k in weak_text for k in keywords)
    resolved = _resolve_weak_nodes(weak_points, name_to_id, id_to_name)
    node_matched = bool(resolved & pool)
    if node_matched:
        hit = sorted(resolved & pool)
        return True, "学员薄弱点命中节点：" + ", ".join(hit)
    if text_matched:
        return True, "学员薄弱点描述命中混淆对"
    return False, "当前画像未命中"


def build_dual_axis_snapshot(
    *, profile: dict[str, Any], session_id: str
) -> dict[str, Any]:
    """构建双知识轴运行时快照。

    知识轴取知识 DAG 全量（静态结构）；混淆轴基于学习者真实学情动态激活：
    - 掌握度优先取 ``five_dimensions.knowledge[node_id].pl``（BKT 真实状态），
      回退到旧字段 ``profile["mastery"]``（concept→float）。
    - 薄弱点解析为节点 id（对齐 knowledge-dag 的 node_name / node_id），
      命中混淆对的 node_a/node_b/related_nodes 即视为激活。
    """
    knowledge = load_knowledge_dag()
    confusion = load_confusion_pairs()

    # ── 掌握度：优先 BKT 真实状态，回退旧 mastery 字段 ──
    fd = profile.get("five_dimensions") or {}
    bkt_knowledge = fd.get("knowledge", {}) or {}
    mastery: dict[str, float] = {}
    if isinstance(bkt_knowledge, dict):
        for _nid, _st in bkt_knowledge.items():
            if isinstance(_st, dict) and _st.get("pl") is not None:
                mastery[str(_nid)] = float(_st["pl"])
    if not mastery:
        _legacy = profile.get("mastery", {})
        if isinstance(_legacy, dict):
            mastery = {
                str(_k): float(_v) for _k, _v in _legacy.items() if _v is not None
            }

    # ── 薄弱点 → 节点 id 集合（用共享索引，支持中文名 / 英文 id / 名字子串）──
    name_to_id, id_to_name = _build_node_name_index(knowledge)
    weak_node_ids = _resolve_weak_nodes(profile.get("weak_points", []), name_to_id, id_to_name)

    runtime_pairs: list[dict[str, Any]] = []
    for pair in confusion["confusion_pairs"]:
        concept_a = str(pair.get("concept_a") or pair.get("node_a", ""))
        concept_b = str(pair.get("concept_b") or pair.get("node_b", ""))
        related = [str(_r) for _r in pair.get("related_nodes", []) if _r]
        pair_nodes = {concept_a, concept_b} | set(related)
        matched, match_reason = _pair_weak_match(
            pair, profile.get("weak_points", []), name_to_id, id_to_name
        )
        base_risk = float(pair.get("difficulty", 0.5))
        mastery_values = [
            mastery[_c] for _c in (concept_a, concept_b) if _c in mastery
        ]
        average_mastery = (
            sum(mastery_values) / len(mastery_values) if mastery_values else None
        )
        mastery_risk = (
            max(0.0, 1.0 - average_mastery) if average_mastery is not None else 0.0
        )
        is_active = bool(matched) or (average_mastery is not None and average_mastery < 0.8)
        risk = (
            min(1.0, base_risk + (0.2 if matched else 0.0) + 0.25 * mastery_risk)
            if is_active
            else 0.0
        )
        reasons: list[str] = []
        if matched:
            reasons.append(match_reason)
        if average_mastery is not None:
            reasons.append(f"BKT平均掌握度：{average_mastery:.2f}")
        runtime = deepcopy(pair)
        runtime.update(
            {
                "learner_risk": risk,
                "is_active": is_active,
                "adjustment_reason": "；".join(reasons) if reasons else "当前画像未命中",
            }
        )
        runtime_pairs.append(runtime)
    return {
        "session_id": session_id,
        "knowledge_axis_version": knowledge["version"],
        "confusion_axis_version": confusion["version"],
        "knowledge_axis": knowledge,
        "confusion_axis": runtime_pairs,
    }


def compute_learning_path(
    *, profile: dict[str, Any], learning_goal: str, max_nodes: int = 8
) -> list[dict[str, Any]]:
    graph = load_knowledge_dag()
    nodes = {str(node["node_id"]): node for node in graph["nodes"]}
    weak_points = profile.get("weak_points", []) or []
    weak_text = " ".join(str(item) for item in weak_points)
    name_to_id, id_to_name = _build_node_name_index(graph)
    weak_node_ids = _resolve_weak_nodes(weak_points, name_to_id, id_to_name)
    search_text = f"{learning_goal} {weak_text}"
    mastery = profile.get("mastery", {}) if isinstance(profile.get("mastery"), dict) else {}

    # 混淆对补全：薄弱点命中某混淆对任一端时，把该对整体（两端 + 相关节点）强制纳入
    # 路径，确保「辨析模块」两端齐备、common_pitfall 块能真正触发。
    confusion = load_confusion_pairs()
    confusion_companions: set[str] = set()
    for pair in confusion["confusion_pairs"]:
        pool = {str(pair.get("node_a")), str(pair.get("node_b"))} | {
            str(r) for r in (pair.get("related_nodes") or [])
        }
        if weak_node_ids & pool:
            confusion_companions |= {p for p in pool if p in nodes}

    targets = [node_id for node_id, node in nodes.items() if _matches_node(node, search_text)]
    if not targets:
        targets = sorted(confusion_companions)  # 关键词无命中时优先以混淆补全节点为起点
    if not targets:
        targets = sorted(nodes, key=lambda node_id: _node_cost(nodes[node_id], weak_text))[:3]

    required: set[str] = set(confusion_companions)
    # 展开混淆补全节点的先修祖先（保证路径拓扑完整、连贯）
    _stack = list(confusion_companions)
    while _stack and len(required) < max_nodes:
        _nid = _stack.pop()
        for _pred in nodes[_nid].get("predecessors", []):
            if _pred in nodes and _pred not in required:
                required.add(_pred)
                _stack.append(_pred)
    frontier: list[tuple[float, str]] = []
    for target in sorted(targets):
        heapq.heappush(frontier, (_node_cost(nodes[target], weak_text), target))
    while frontier and len(required) < max_nodes:
        _, node_id = heapq.heappop(frontier)
        if node_id in required or float(mastery.get(node_id, 0.0)) >= 0.8:
            continue
        required.add(node_id)
        for predecessor in nodes[node_id].get("predecessors", []):
            if predecessor in nodes and predecessor not in required:
                heapq.heappush(frontier, (_node_cost(nodes[predecessor], weak_text), predecessor))

    ordered = _topological_subset(nodes, required)
    return [
        {
            "node_id": node_id,
            "node_name": str(nodes[node_id]["node_name"]),
            "duration_min": max(10, round(float(nodes[node_id].get("estimated_hours", 1)) * 60)),
            "strategy": _strategy(nodes[node_id], weak_text),
            "prerequisites": [
                predecessor
                for predecessor in nodes[node_id].get("predecessors", [])
                if predecessor in required
            ],
            "target_ability": str(nodes[node_id].get("description", "")),
            "assessment": "完成本节点练习并达到 80% 掌握度",
        }
        for node_id in ordered
    ]


def _matches_node(node: dict[str, Any], text: str) -> bool:
    terms = [node.get("node_id"), node.get("node_name"), *node.get("tags", [])]
    return any(str(term).lower() in text.lower() for term in terms if term)


def _node_cost(node: dict[str, Any], weak_text: str) -> float:
    weakness = 1.0 if _matches_node(node, weak_text) else 0.25
    benefit = weakness * _WEIGHTS.get(str(node.get("exam_weight", "中")), 0.6)
    hours = float(node.get("estimated_hours", 1.0))
    difficulty = float(node.get("difficulty", 0.5))
    return hours * (1 + difficulty) / max(0.05, benefit)


def _topological_subset(nodes: dict[str, dict[str, Any]], selected: set[str]) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in ordered or node_id in visiting:
            return
        visiting.add(node_id)
        for predecessor in sorted(nodes[node_id].get("predecessors", [])):
            if predecessor in selected:
                visit(predecessor)
        visiting.remove(node_id)
        ordered.append(node_id)

    for selected_id in sorted(selected, key=lambda item: _node_cost(nodes[item], "")):
        visit(selected_id)
    return ordered


def _strategy(node: dict[str, Any], weak_text: str) -> str:
    if _matches_node(node, weak_text):
        return "先做易混淆概念对比，再用案例和法条巩固"
    return "按知识依赖学习，完成节点练习后再进入下一节点"


# ─────────────────────────────────────────────────────────────────────────────
# 确定性教学板块编排（spec v3 §3.3 触发表 / §3.4 冷启动 / §3.5 预算 / §3.6 排序）
#
# 背景：spec §3.7 把 default_block_plan 定为"辩论基线建议"，代码层此前从未落地，
# 导致 integration 的 LLM 自由生成 block_plan 并事后补 trigger 标签——出现"选的块
# 与画像对不上、trigger 张冠李戴"。本模块把 §3.3/§3.4/§3.5/§3.6 落地为确定性判定，
# 由 integration 在融合前算出"按规则应含哪些块 + 每块真实 trigger"，作为硬约束。
# ─────────────────────────────────────────────────────────────────────────────

_STRENGTH_THRESHOLD = 0.6  # spec §3.1：Felder 轴触发默认阈值

# spec §3.6 线性排序（守顺序型学员）。mnemonic 归入误区/口诀带，summary_card 挂尾部。
_BLOCK_ORDER: list[str] = [
    "global_framework",
    "anchor_scenario",
    "legal_anchor",
    "worked_example",
    "decision_flow",
    "verbal_explanation",
    "common_pitfall",
    "mnemonic",
    "predict_activate",
    "reflect_prompt",
    "assessment",
    "knowledge_synthesis",
    "summary_card",
]

# spec §3.5 超额裁剪优先级（保脚手架、弃装饰，从底部删）。
_ADAPTIVE_DROP_ORDER: list[str] = [
    "mnemonic",
    "global_framework",
    "reflect_prompt",
    "predict_activate",
    "verbal_explanation",
    "decision_flow",
    "common_pitfall",
    "worked_example",
    "anchor_scenario",
]

_MANDATORY_BLOCKS: tuple[str, ...] = ("legal_anchor", "knowledge_synthesis", "assessment")

_BLOCK_TITLE: dict[str, str] = {
    "legal_anchor": "法条锚定",
    "knowledge_synthesis": "知识综合",
    "assessment": "三类测评",
    "anchor_scenario": "场景导入",
    "global_framework": "全局框架",
    "worked_example": "案例演示",
    "decision_flow": "决策流程图",
    "verbal_explanation": "文字讲解",
    "predict_activate": "预测激活",
    "reflect_prompt": "反思提示",
    "mnemonic": "记忆口诀",
    "common_pitfall": "误区辨析",
    "summary_card": "速查卡",
}

# 互斥对（spec §3.5 / §10.9）：同一对只能留一个
_MUTEX_PAIRS: tuple[tuple[str, str], ...] = (
    ("decision_flow", "verbal_explanation"),
    ("predict_activate", "reflect_prompt"),
)


def _style_axis(style: dict[str, Any], axis: str) -> tuple[str, float]:
    ax = style.get(axis)
    if isinstance(ax, dict):
        chosen = str(ax.get("chosen") or "")
        try:
            strength = float(ax.get("strength") or 0.0)
        except (TypeError, ValueError):
            strength = 0.0
        return chosen, strength
    return "", 0.0


def _cog(cognition: dict[str, Any], level: str, default: float) -> float:
    try:
        return float(cognition.get(level, default))
    except (TypeError, ValueError):
        return default


def compute_default_block_plan(
    *,
    profile: dict[str, Any],
    current_node_id: str,
    weak_points: list[str] | None = None,
) -> dict[str, Any]:
    """按 spec v3 确定性推导当前节点应含的教学板块集合。

    返回结构::

        {
          "node": current_node_id,
          "required_blocks": [               # 已按 §3.6 排序
            {"block_type","trigger","adapts_to","mandatory": bool, "title"}
          ],
          "budget": {"adaptive_used","adaptive_max":6,"total","total_max":9},
        }

    仅依据真实画像信号（Felder 四轴 + Bloom 认知轴 + 当前节点 BKT + 混淆图 +
    子节点数）判定，不依赖 LLM。integration 据此对 LLM 产出的 block_plan 做校正。
    """
    fd = profile.get("five_dimensions") or {}
    style = fd.get("style") or {}
    cognition = fd.get("cognition") or {}
    knowledge = fd.get("knowledge") or {}
    affect = fd.get("affect") or {}
    if weak_points is None:
        weak_points = profile.get("weak_points") or []

    node_state = knowledge.get(current_node_id) or {}
    pl = node_state.get("pl") if isinstance(node_state, dict) else None
    if pl is not None:
        try:
            pl = float(pl)
        except (TypeError, ValueError):
            pl = None
    # §3.4 冷启动强制：任一 KC low_confidence 即触发（不限当前节点）
    low_conf = any(
        isinstance(kc, dict) and bool(kc.get("low_confidence"))
        for kc in knowledge.values()
    )
    affect_state = str(affect.get("primary_state") or affect.get("affect") or "")

    # 当前节点的子节点数 + 名称（用于 summary_card / common_pitfall 名称匹配）
    graph = load_knowledge_dag()
    node = next(
        (n for n in graph["nodes"] if str(n.get("node_id")) == current_node_id), {}
    )
    sub_nodes = node.get("knowledge_sub_nodes") or []
    node_name = str(node.get("node_name") or "")

    # 当前节点是否落在某混淆对（node_a/node_b/related_nodes）
    confusion = load_confusion_pairs()
    _name_to_id, _id_to_name = _build_node_name_index(graph)
    _weak_nodes = _resolve_weak_nodes(weak_points, _name_to_id, _id_to_name)
    in_confusion = False
    for pair in confusion["confusion_pairs"]:
        pool = {str(pair.get("node_a")), str(pair.get("node_b"))} | {
            str(r) for r in (pair.get("related_nodes") or [])
        }
        if current_node_id in pool:
            in_confusion = True
            break
    # 学员薄弱点解析后命中当前节点（鲁棒版 weak_name_hit：支持中文名 / 英文 id / 名字子串）
    weak_in_pair = current_node_id in _weak_nodes

    th = _STRENGTH_THRESHOLD
    # adaptive: block_type -> (trigger, adapts_to)
    adaptive: dict[str, tuple[str, list[str]]] = {}

    def add(bt: str, trigger: str, adapts_to: list[str]) -> None:
        if bt in adaptive:
            prev_trigger, prev_adapts = adaptive[bt]
            merged = prev_trigger if trigger in prev_trigger else f"{prev_trigger} / {trigger}"
            adaptive[bt] = (merged, sorted(set(prev_adapts) | set(adapts_to)))
        else:
            adaptive[bt] = (trigger, adapts_to)

    # anchor_scenario (§3.3)
    perc, perc_s = _style_axis(style, "perception")
    a_reasons: list[str] = []
    if perc == "sensing" and perc_s >= th:
        a_reasons.append(f"perception=sensing({perc_s:.2f})")
    if pl is not None and pl < 0.3:
        a_reasons.append(f"P(L)={pl:.2f}<0.3")
    if affect_state in ("confused", "anxious"):
        a_reasons.append(f"affect={affect_state}")
    if a_reasons:
        add("anchor_scenario", " / ".join(a_reasons), ["style.perception=sensing"])

    # global_framework (§3.3)
    und, und_s = _style_axis(style, "understanding")
    if und == "global" and und_s >= th:
        add("global_framework", f"understanding=global({und_s:.2f})", ["style.understanding=global"])

    # worked_example (§3.3)
    apply_v = _cog(cognition, "apply", 1.0)
    analyze_v = _cog(cognition, "analyze", 1.0)
    we_reasons: list[str] = []
    if apply_v < 0.4:
        we_reasons.append(f"cognition.apply={apply_v:.2f}<0.4")
    if analyze_v < 0.3:
        we_reasons.append(f"cognition.analyze={analyze_v:.2f}<0.3")
    if we_reasons:
        add("worked_example", " / ".join(we_reasons), ["cognition.apply<0.4"])

    # decision_flow / verbal_explanation 互斥 (§3.3)
    inp, inp_s = _style_axis(style, "input")
    if inp == "visual" and inp_s >= th:
        add("decision_flow", f"input=visual({inp_s:.2f})", ["style.input=visual"])
    elif inp == "verbal" and inp_s >= th:
        add("verbal_explanation", f"input=verbal({inp_s:.2f})", ["style.input=verbal"])

    # predict_activate / reflect_prompt 互斥 (§3.3)
    proc, proc_s = _style_axis(style, "processing")
    if proc == "active" and proc_s >= th:
        add("predict_activate", f"processing=active({proc_s:.2f})", ["style.processing=active"])
    elif proc == "reflective" and proc_s >= th:
        add("reflect_prompt", f"processing=reflective({proc_s:.2f})", ["style.processing=reflective"])

    # mnemonic (§3.3)
    remember_v = _cog(cognition, "remember", 0.0)
    mn_reasons: list[str] = []
    if remember_v >= 0.6 and apply_v < 0.4:
        mn_reasons.append(f"remember={remember_v:.2f}>=0.6 & apply<0.4")
    if und == "sequential" and und_s >= th:
        mn_reasons.append(f"understanding=sequential({und_s:.2f})")
    if mn_reasons:
        add("mnemonic", " / ".join(mn_reasons), ["style.understanding=sequential"])

    # common_pitfall (§3.3)：当前节点在混淆图，或薄弱点解析到该混淆对的节点
    if in_confusion or weak_in_pair:
        trigger = "graph.confusable_pair" if in_confusion else f"weak_points({node_name})"
        add("common_pitfall", trigger, ["graph.confusable_pair", "weak_points"])

    # summary_card (§3.4)：子节点 ≥3 默认挂尾部
    if len(sub_nodes) >= 3:
        add("summary_card", f"len(knowledge_sub_nodes)={len(sub_nodes)}>=3", ["*"])

    # 冷启动强制脚手架 (§3.4)：任一 KC low_confidence → 强制 anchor_scenario + worked_example
    if low_conf:
        if "anchor_scenario" not in adaptive:
            add("anchor_scenario", "cold_start(low_confidence)", ["style.perception=sensing"])
        else:
            t, a = adaptive["anchor_scenario"]
            adaptive["anchor_scenario"] = (f"{t} / cold_start", a)
        if "worked_example" not in adaptive:
            add("worked_example", "cold_start(low_confidence)", ["cognition.apply<0.4"])
        else:
            t, a = adaptive["worked_example"]
            adaptive["worked_example"] = (f"{t} / cold_start", a)
    cold_forced = {"anchor_scenario", "worked_example"} if low_conf else set()

    # 互斥去重 (§3.5)：保留先触发者（dict 已保证唯一，双向都在时按 drop 优先级删弱者）
    for a, b in _MUTEX_PAIRS:
        if a in adaptive and b in adaptive:
            # 保留在 drop_order 里更靠后（更该保留）的那个
            drop = a if _ADAPTIVE_DROP_ORDER.index(a) < _ADAPTIVE_DROP_ORDER.index(b) else b
            adaptive.pop(drop, None)

    # 预算裁剪 (§3.5)：自适应 ≤6，从底部按优先级删，不删冷启动强制块
    while len(adaptive) > 6:
        removed = False
        for bt in _ADAPTIVE_DROP_ORDER:
            if bt in adaptive and bt not in cold_forced:
                adaptive.pop(bt)
                removed = True
                break
        if not removed:
            break

    # 组装 required_blocks：必选三块 + 自适应块，按 §3.6 排序
    required: list[dict[str, Any]] = []
    for bt in _MANDATORY_BLOCKS:
        required.append(
            {
                "block_type": bt,
                "trigger": "mandatory",
                "adapts_to": ["*"],
                "mandatory": True,
                "title": _BLOCK_TITLE[bt],
            }
        )
    for bt, (trigger, adapts_to) in adaptive.items():
        required.append(
            {
                "block_type": bt,
                "trigger": trigger,
                "adapts_to": adapts_to,
                "mandatory": False,
                "title": _BLOCK_TITLE.get(bt, bt),
            }
        )
    required.sort(key=lambda b: _BLOCK_ORDER.index(b["block_type"]))

    return {
        "node": current_node_id,
        "required_blocks": required,
        "budget": {
            "adaptive_used": len(adaptive),
            "adaptive_max": 6,
            "total": len(required),
            "total_max": 9,
        },
    }


def reconcile_block_plan(
    *,
    llm_plan: dict[str, Any] | None,
    default_plan: dict[str, Any],
    current_node_id: str,
) -> dict[str, Any]:
    """用确定性 default_plan 校正 LLM 产出的 block_plan。

    - ``node`` 强制对齐 planner 权威当前节点；
    - 补齐 default 要求但 LLM 漏掉的块（骨架 payload）；
    - 删除 default 未要求的自适应块（防 LLM 自由发挥出规则外的块）；
    - 每块 ``trigger`` / ``adapts_to`` 用确定性值覆盖（消灭张冠李戴的事后标签）；
    - 保留 LLM 已产出块的 ``payload`` / ``title`` / ``chosen_by``；
    - 重排 ``order`` 与重算 ``budget``。
    """
    llm_blocks: list[dict[str, Any]] = []
    if isinstance(llm_plan, dict):
        raw_blocks = llm_plan.get("blocks")
        if isinstance(raw_blocks, list):
            llm_blocks = [b for b in raw_blocks if isinstance(b, dict)]
    by_type: dict[str, dict[str, Any]] = {}
    for b in llm_blocks:
        bt = str(b.get("block_type") or "")
        if bt and bt not in by_type:
            by_type[bt] = b

    reconciled: list[dict[str, Any]] = []
    for idx, spec_block in enumerate(default_plan["required_blocks"], start=1):
        bt = spec_block["block_type"]
        existing = by_type.get(bt, {})
        payload = existing.get("payload") if isinstance(existing.get("payload"), dict) else {}
        title = existing.get("title") or spec_block["title"]
        chosen_by = existing.get("chosen_by")
        if chosen_by not in ("[A]", "[B]", "[A+B融合]"):
            chosen_by = "[A+B融合]"
        reconciled.append(
            {
                "block_id": f"b{idx}",
                "block_type": bt,
                "title": title,
                "payload": payload or {},
                "chosen_by": chosen_by,
                "trigger": spec_block["trigger"],
                "rationale": existing.get("rationale") or _BLOCK_TITLE.get(bt, bt),
                "adapts_to": spec_block["adapts_to"],
                "source": existing.get("source"),
            }
        )

    adaptive_used = sum(1 for b in reconciled if b["adapts_to"] != ["*"])
    return {
        "node": current_node_id,
        "learner_id": (llm_plan or {}).get("learner_id") if isinstance(llm_plan, dict) else None,
        "blocks": reconciled,
        "order": [b["block_id"] for b in reconciled],
        "budget": {
            "adaptive_used": adaptive_used,
            "adaptive_max": 6,
            "total": len(reconciled),
            "total_max": 9,
        },
        "debate_resolved": True,
    }


def format_default_block_plan_directive(default_plan: dict[str, Any]) -> str:
    """把确定性 default_plan 渲染为注入 integration 提示词的硬约束文本。"""
    lines = [
        f"# 确定性板块编排约束（当前节点 {default_plan['node']}，spec §3.3/§3.4 规则算得，硬约束）",
        "你产出的 block_plan.blocks 必须且只能包含以下板块，block_plan.node 必须等于上述节点，"
        "每块 trigger 使用给定值，不得自创或张冠李戴：",
        "",
        "| block_type | 类型 | trigger（规则命中理由） |",
        "|---|---|---|",
    ]
    for b in default_plan["required_blocks"]:
        kind = "必选" if b["mandatory"] else "自适应"
        lines.append(f"| {b['block_type']} | {kind} | {b['trigger']} |")
    lines.append("")
    lines.append(
        "说明：以上板块集合由学员画像（Felder 四轴 + Bloom 认知轴 + 当前节点 BKT + "
        "混淆图 + 子节点数）按规则确定性算出。你只负责为每块填充高质量 payload 正文，"
        "不得增删板块或改动 trigger。"
    )
    return "\n".join(lines)
