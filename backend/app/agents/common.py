"""Shared helpers for Agent node modules."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.core.llm import LLMMessage, LLMRole

Node = Callable[..., dict[str, Any]]


# ── 题型口径归一化（spec 规范枚举，兼容 LLM 偶发中文/旧值）──
# category：布鲁姆六级（规范英文）
_CATEGORY_MAP: dict[str, str] = {
    "记忆": "remember", "识记": "remember", "recall": "remember",
    "理解": "understand", "comprehension": "understand",
    "应用": "apply", "application": "apply",
    "分析": "analyze", "analysis": "analyze",
    "评价": "evaluate", "evaluation": "evaluate",
    "创造": "create", "creation": "create",
}
# difficulty：L1/L2/L3
_DIFFICULTY_MAP: dict[str, str] = {
    "易": "L1", "简单": "L1", "低": "L1", "easy": "L1",
    "中": "L2", "中等": "L2", "medium": "L2",
    "难": "L3", "困难": "L3", "高": "L3", "hard": "L3",
}
# source_tag：三类出题范围（与 planner question_scope 键名一致）
_SOURCE_TAG_MAP: dict[str, str] = {
    "向后复习": "backward_review", "回顾": "backward_review", "复习": "backward_review",
    "向前探测": "forward_probe", "前瞻": "forward_probe", "探测": "forward_probe",
    "薄弱点": "weakness_probe", "薄弱": "weakness_probe", "弱点": "weakness_probe",
}


def _norm_category(value: object) -> object:
    if isinstance(value, str):
        return _CATEGORY_MAP.get(value.strip(), value.strip().lower())
    return value


def _norm_difficulty(value: object) -> object:
    if isinstance(value, str):
        return _DIFFICULTY_MAP.get(value.strip(), value.strip().upper())
    return value


def _norm_source_tag(value: object) -> object:
    if isinstance(value, str):
        return _SOURCE_TAG_MAP.get(value.strip(), value.strip())
    return value


# 题干内联选项标记：A. / A、 / (A) / 1. 等行首
_OPTION_RE = re.compile(r"^\s*(?:[A-Da-d][\.、\)]|（[A-Da-d]）|\d+[\.、])\s*(.*)$")


def _extract_and_clean_options(question: str) -> tuple[list[str], str]:
    """把题干里内联的选项行抽成独立数组，并返回去除选项后的题干。

    仅当识别出 ≥2 个选项式行时才视为多选题（避免误伤普通编号列表）。
    """
    lines = question.split("\n")
    opts: list[str] = []
    kept: list[str] = []
    for line in lines:
        m = _OPTION_RE.match(line)
        if m and len(opts) < 8:
            opts.append(m.group(1).strip())
        else:
            kept.append(line)
    if len(opts) >= 2:
        return opts, "\n".join(kept).strip()
    return [], question.strip()

_LANGCHAIN_ROLE_TO_CHAT_ROLE: dict[str, LLMRole] = {
    "system": "system",
    "human": "user",
    "user": "user",
    "ai": "assistant",
    "assistant": "assistant",
}


def _chat_role(langchain_role: str) -> LLMRole:
    try:
        return _LANGCHAIN_ROLE_TO_CHAT_ROLE[langchain_role]
    except KeyError as exc:
        raise ValueError(f"Unsupported LangChain message role: {langchain_role}") from exc


def messages_from_prompt(prompt: ChatPromptTemplate, **values: object) -> list[LLMMessage]:
    return [
        LLMMessage(role=_chat_role(message.type), content=str(message.content))
        for message in prompt.format_messages(**values)
    ]


def schema_note(schema_name: str, example: str) -> str:
    return (
        f"你必须只输出 json，不要输出 Markdown。输出必须符合 {schema_name}。"
        "字段名必须与示例完全一致，必须使用 snake_case，不要改成 camelCase。"
        f"示例 json：{example.replace(chr(123), chr(123) * 2).replace(chr(125), chr(125) * 2)}"
    )


def normalize_key_aliases(raw: object, aliases: dict[str, str]) -> object:
    """Map known provider key variants to the internal contract field names.

    处理「重复键」边界：真实 LLM 可能同时输出中文键（如 问题）与英文键（problem）。
    - canonical 缺失或为空 → 用 alias 值填充 canonical；
    - canonical 已存在且非空 → 保留 canonical，丢弃重复的 alias，避免 extra 字段报错。
    """
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    for alias, canonical in aliases.items():
        if alias in normalized:
            if canonical not in normalized or not normalized.get(canonical):
                normalized[canonical] = normalized.pop(alias)
            else:
                normalized.pop(alias)
    return normalized


# ── ExpertDraft / BlockPlan 字段兜底（防御真实 LLM 输出形态） ──
_STYLE_MAP = {
    "conservative": "conservative",
    "conservative_precise": "conservative",
    "precise": "conservative",
    "accessible": "accessible",
    "accessible_restrained": "accessible",
    "restrained": "accessible",
    "fused": "fused",
    "fusion": "fused",
    "case_based": "fused",
    "exam_oriented": "fused",
    "blend": "fused",
    "hybrid": "fused",
}


def _norm_style(val: str) -> str:
    """style 兜底：旧 4 枚举 / 中文 → spec v3 的 conservative/accessible/fused。"""
    v = val.strip().lower()
    if v in _STYLE_MAP:
        return _STYLE_MAP[v]
    if any(k in v for k in ("保守", "严谨", "精准", "精确")):
        return "conservative"
    if any(k in v for k in ("易懂", "平实", "克制", "通俗", "人话")):
        return "accessible"
    if any(k in v for k in ("融合", "案例", "应试", "综合", "混合")):
        return "fused"
    return "conservative"


_BLOCK_TYPE_VALUES = {
    "legal_anchor", "knowledge_synthesis", "assessment", "anchor_scenario",
    "global_framework", "worked_example", "decision_flow", "verbal_explanation",
    "predict_activate", "reflect_prompt", "mnemonic", "common_pitfall", "summary_card",
}
_BLOCK_TYPE_CN = {
    "法条锚定": "legal_anchor", "法条": "legal_anchor",
    "知识综合": "knowledge_synthesis", "知识点整合": "knowledge_synthesis", "知识整合": "knowledge_synthesis",
    "测评": "assessment", "习题": "assessment", "练习": "assessment", "测试": "assessment",
    "锚定情境": "anchor_scenario", "情境": "anchor_scenario",
    "全局框架": "global_framework", "框架": "global_framework",
    "例题": "worked_example", "范例": "worked_example", "示例": "worked_example",
    "决策流程": "decision_flow", "决策流": "decision_flow",
    "人话翻译": "verbal_explanation", "口语化": "verbal_explanation", "平白解释": "verbal_explanation",
    "plain_language": "verbal_explanation",
    "预测激活": "predict_activate", "激活": "predict_activate",
    "反思提示": "reflect_prompt", "反思": "reflect_prompt",
    "记忆术": "mnemonic", "助记": "mnemonic",
    "常见坑": "common_pitfall", "易错": "common_pitfall", "陷阱": "common_pitfall",
    "总结卡": "summary_card", "小结": "summary_card", "总结": "summary_card",
}


def _norm_block_type(val: str) -> str:
    """block_type 兜底：英文归一 / 中文映射 / 模糊子串 → 13 值受控词表；兜底 knowledge_synthesis。"""
    v = val.strip().lower().replace(" ", "_").replace("-", "_")
    if v in _BLOCK_TYPE_VALUES:
        return v
    raw = val.strip()
    if raw in _BLOCK_TYPE_CN:
        return _BLOCK_TYPE_CN[raw]
    for k, mapped in _BLOCK_TYPE_CN.items():
        if k in raw:
            return mapped
    for t in _BLOCK_TYPE_VALUES:
        if t in v or v in t:
            return t
    return "knowledge_synthesis"


def _norm_chosen_by(val: object) -> object:
    """chosen_by 兜底：A/B/融合简写 → [A]/[B]/[A+B融合]；未知 → None（Optional 安全）。"""
    if val is None:
        return None
    v = str(val).strip()
    if v in ("[A]", "[B]", "[A+B融合]", "A+B融合"):
        return v if v != "A+B融合" else "[A+B融合]"
    if v in ("A", "专家A", "专家 A", "a"):
        return "[A]"
    if v in ("B", "专家B", "专家 B", "b"):
        return "[B]"
    if v in ("融合", "AB", "A/B", "both", "两者", "全部"):
        return "[A+B融合]"
    return None


def normalize_expert_draft_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "knowledgePoints": "knowledge_points",
            "legalBasis": "legal_basis",
            "teachingContent": "teaching_content",
            "interactiveQuestions": "interactive_questions",
            "draftStage": "draft_stage",
            "blockPlan": "block_plan",
            "knowledgeSynthesis": "knowledge_synthesis",
            "assessment": "assessment",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    # expert: 兼容 A/B 简写（提示词示例/归属标签 [A]/[B] 诱导）→ 全名，
    # 防止真实 LLM 偶发简写被 Literal 校验拒收（spec 要求 expert_a/expert_b/A+B融合）。
    exp = normalized.get("expert")
    if isinstance(exp, str):
        _EXP_MAP = {
            "A": "expert_a", "B": "expert_b",
            "专家A": "expert_a", "专家B": "expert_b",
            "专家 A": "expert_a", "专家 B": "expert_b",
            "a": "expert_a", "b": "expert_b",
            # 融合态变体（integration 阶段可能偶发简写）
            "A+B融合": "A+B融合", "A/B融合": "A+B融合", "A＋B融合": "A+B融合",
            "A+B": "A+B融合", "融合": "A+B融合",
            "fused": "A+B融合", "fusion": "A+B融合",
        }
        normalized["expert"] = _EXP_MAP.get(exp.strip(), exp.strip())
    # style: 兼容旧枚举 / 中文（spec v3 仅 conservative/accessible/fused）
    st = normalized.get("style")
    if isinstance(st, str):
        normalized["style"] = _norm_style(st)
    for field in ("knowledge_points", "legal_basis", "risks", "interactive_questions"):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = [value]
    # legal_basis: 兼容 str / {article,source} 两种形态（spec v3 用对象数组）
    lb = normalized.get("legal_basis")
    if isinstance(lb, list):
        normalized["legal_basis"] = [
            {"article": item} if isinstance(item, str) else item for item in lb
        ]
    # risks: 兼容 str / {risk,related_node_id} 两种形态（spec v3 用对象数组）
    rk = normalized.get("risks")
    if isinstance(rk, list):
        normalized["risks"] = [
            {"risk": item} if isinstance(item, str) else item for item in rk
        ]
    # knowledge_points: 字符串数组 → 对象数组容错
    kps = normalized.get("knowledge_points")
    if isinstance(kps, list):
        normalized["knowledge_points"] = [
            {"node_id": "", "kc_name": kp} if isinstance(kp, str) else kp for kp in kps
        ]
    # interactive_questions: stem → question 别名兼容（spec v3 用 stem）。
    # 无论 LLM 是否同时给出 question，都必须保证 stem 不残留（否则触发 Extra 校验）；缺 qid 按序补全。
    iqs = normalized.get("interactive_questions")
    if isinstance(iqs, list):
        cleaned = []
        for idx, iq in enumerate(iqs, start=1):
            if isinstance(iq, dict):
                if "stem" in iq:
                    # question 优先；stem 仅作兜底补充，处理后务必删除避免 Extra 校验
                    if not iq.get("question"):
                        iq["question"] = iq.pop("stem")
                    else:
                        iq.pop("stem")
                # 题型口径归一化：category/difficulty/source_tag 中英文→规范枚举
                if "category" in iq:
                    iq["category"] = _norm_category(iq["category"])
                if "difficulty" in iq:
                    iq["difficulty"] = _norm_difficulty(iq["difficulty"])
                if "source_tag" in iq:
                    iq["source_tag"] = _norm_source_tag(iq["source_tag"])
                # options：若题干内联了选项且未单独给出，则抽取到独立数组
                _existing_opts = iq.get("options")
                if isinstance(_existing_opts, list) and _existing_opts:
                    pass  # 已有独立 options 数组，保留
                else:
                    _q = iq.get("question") or ""
                    if isinstance(_q, str):
                        _opts, _cleaned_q = _extract_and_clean_options(_q)
                        if _opts:
                            iq["options"] = _opts
                            iq["question"] = _cleaned_q
                if not iq.get("qid"):
                    iq["qid"] = f"q{idx}"
                cleaned.append(iq)
            else:
                cleaned.append(iq)
        normalized["interactive_questions"] = cleaned
    # assessment: items 缺 qid 时按序补全（draft 传 null，integration 阶段补全）
    asm = normalized.get("assessment")
    if isinstance(asm, dict):
        items = asm.get("items")
        if isinstance(items, list):
            for idx, it in enumerate(items, start=1):
                if isinstance(it, dict) and not it.get("qid"):
                    it["qid"] = f"q{idx}"
            asm["items"] = items
        normalized["assessment"] = asm
    elif isinstance(asm, list):
        for idx, it in enumerate(asm, start=1):
            if isinstance(it, dict) and not it.get("qid"):
                it["qid"] = f"q{idx}"
        normalized["assessment"] = {"items": asm}

    # knowledge_synthesis: coverage / confusable_pairs 兼容真实 LLM 偶发的 str 列表 → 对象数组
    # （revision 阶段 LLM 可能把 coverage 写成 ["kp-01","kp-02",...] 而非 [{...}]，触发 dict_type 校验失败）
    ks = normalized.get("knowledge_synthesis")
    if isinstance(ks, dict):
        cov = ks.get("coverage")
        if cov is None:
            ks["coverage"] = []
        elif isinstance(cov, str):
            ks["coverage"] = [{"node_id": cov}]
        elif isinstance(cov, list):
            ks["coverage"] = [
                {"node_id": c} if isinstance(c, str) else c for c in cov
            ]
        cp = ks.get("confusable_pairs")
        if cp is None:
            ks["confusable_pairs"] = None
        elif isinstance(cp, str):
            ks["confusable_pairs"] = [{"pair": cp}]
        elif isinstance(cp, list):
            ks["confusable_pairs"] = [
                {"pair": c} if isinstance(c, str) else c for c in cp
            ]
        normalized["knowledge_synthesis"] = ks
    elif isinstance(ks, str):
        normalized["knowledge_synthesis"] = {
            "coverage": [{"node_id": ks}],
            "confusable_pairs": [],
        }

    # block_plan: 兼容 list[BlockPlan] 旧形态 → 包成 BlockPlanPackage，并兜底 blocks 内 block_type/chosen_by
    bp = normalized.get("block_plan")
    if isinstance(bp, list):
        normalized["block_plan"] = {"blocks": bp}
    pkg = normalized.get("block_plan")
    if isinstance(pkg, dict):
        _ALLOWED_BLOCK_KEYS = {
            "block_id",
            "block_type",
            "title",
            "payload",
            "chosen_by",
            "trigger",
            "rationale",
            "adapts_to",
            "source",
        }
        cleaned_blocks = []
        for _blk in pkg.get("blocks", []):
            if not isinstance(_blk, dict):
                cleaned_blocks.append(_blk)
                continue
            # 语义恢复：真实 LLM 常把 legal_anchor 当布尔标志塞进 block，
            # 而它其实是 block_type 的合法取值；若 block_type 缺失则恢复之
            if not _blk.get("block_type") and _blk.get("legal_anchor") in (
                True,
                "true",
                "True",
                1,
            ):
                _blk["block_type"] = "legal_anchor"
            # 白名单：丢弃 block 内除合法字段外的所有垃圾键（如 legal_anchor 标志位）
            _blk = {k: v for k, v in _blk.items() if k in _ALLOWED_BLOCK_KEYS}
            if isinstance(_blk.get("block_type"), str):
                _blk["block_type"] = _norm_block_type(_blk["block_type"])
            if _blk.get("chosen_by") is not None:
                _blk["chosen_by"] = _norm_chosen_by(_blk["chosen_by"])
            cleaned_blocks.append(_blk)
        pkg["blocks"] = cleaned_blocks
    exercises = normalized.get("exercises")
    if isinstance(exercises, str):
        normalized["exercises"] = [{"question": exercises}]
    elif isinstance(exercises, list):
        normalized["exercises"] = [
            {"question": item} if isinstance(item, str) else item for item in exercises
        ]
    return normalized


def extract_planning_directive(state: dict[str, Any]) -> str:
    """从 path_decision 提取路径规划指令（question_scope / iteration_directive），供专家消费。

    提示词要求专家从 learning_path 读取这些指令，但 planner 实际写入 path_decision，
    故在此桥接，确保专家草稿阶段能拿到出题范围与迭代指令。
    """
    pd = state.get("path_decision") or {}
    qs = pd.get("question_scope")
    it = pd.get("iteration_directive")
    if not qs and not it:
        return "（未提供路径规划指令）"
    parts: list[str] = []
    if qs:
        parts.append(f"question_scope（三类出题范围）：{json.dumps(qs, ensure_ascii=False)}")
    if it:
        parts.append(f"iteration_directive（迭代指令）：{json.dumps(it, ensure_ascii=False)}")
    return "\n".join(parts)


def normalize_cross_review_payload(raw: object) -> object:
    """Normalize LLM output for CrossReview, mapping Chinese/camelCase aliases
    to canonical English snake_case field names, and ensuring required fields exist."""
    # ── top-level key aliases ──
    normalized = normalize_key_aliases(
        raw,
        {
            # camelCase variants
            "reviewOpinions": "review_opinions",
            "overallAssessment": "overall_assessment",
            "positiveConfirmation": "positive_confirmation",
            "legalBasis": "legal_basis",
            # Chinese variants
            "总体评价": "overall_assessment",
            "正面确认": "positive_confirmation",
        },
    )
    if not isinstance(normalized, dict):
        return normalized

    # reviewer / target: 兼容 A/B 简写（归属标签 [A]/[B] 诱导）→ 全名
    _AGENT_MAP = {
        "A": "expert_a", "B": "expert_b",
        "专家A": "expert_a", "专家B": "expert_b",
        "专家 A": "expert_a", "专家 B": "expert_b",
        "a": "expert_a", "b": "expert_b",
    }
    for _f in ("reviewer", "target"):
        _v = normalized.get(_f)
        if isinstance(_v, str):
            normalized[_f] = _AGENT_MAP.get(_v.strip(), _v.strip())

    # ── review_opinions: normalize each item，超 max_length(7) 截断兜底 ──
    opinions = normalized.get("review_opinions")
    if isinstance(opinions, list):
        normalized["review_opinions"] = [
            _normalize_review_opinion(op) for op in opinions
        ][:7]

    # ── guarantee overall_assessment exists ──
    if "overall_assessment" not in normalized and isinstance(opinions, list) and opinions:
        normalized["overall_assessment"] = "基于上述意见的综合评价"

    return normalized


def _normalize_review_opinion(op: object) -> object:
    if not isinstance(op, dict):
        return op
    normalized = normalize_key_aliases(
        op,
        {
            # camelCase variants
            "targetWrote": "target_wrote",
            "legalBasis": "legal_basis",
            # Chinese variants — LLM often outputs Chinese keys
            "问题": "problem",
            "建议": "suggestion",
            "位置": "location",
            "原文": "target_wrote",
            "依据": "basis",
            "法条依据": "legal_basis",
            "类别": "category",
        },
    )
    # ── category: 中文/英文 → emoji Literal（ReviewOpinion.category 严格 5 值）──
    _CAT_MAP = {
        "必须修改": "🔴", "阻断": "🔴", "red": "🔴", "错误": "🔴",
        "建议修改": "🟡", "yellow": "🟡", "可优化": "🟡",
        "正面确认": "🟢", "green": "🟢", "正确": "🟢",
        "适配性偏差": "🔵", "blue": "🔵",
        "需桥接": "🌉", "bridge": "🌉", "交整合仲裁": "🌉",
    }
    _cat = normalized.get("category")
    if isinstance(_cat, str):
        normalized["category"] = _CAT_MAP.get(_cat.strip(), _cat.strip())

    # ── guarantee required fields with fallback ──
    if "problem" not in normalized:
        # Try to infer from content if LLM omitted it
        suggestion_val = normalized.get("suggestion", "")
        if suggestion_val:
            normalized["problem"] = f"需改进：{suggestion_val}"
        else:
            normalized["problem"] = "未明确指出问题"
    if "suggestion" not in normalized:
        problem_val = normalized.get("problem", "")
        normalized["suggestion"] = f"建议修正：{problem_val}" if problem_val else "建议补充完善"
    # ── legal_basis: str → list ──
    lb = normalized.get("legal_basis")
    if isinstance(lb, str):
        normalized["legal_basis"] = [lb]
    # ── 白名单过滤：丢弃 ReviewOpinion 合法字段之外的垃圾键 ──
    # 真实 LLM 偶发在意见字符串里嵌未转义引号，JSON 虽解析成功却把句子片段
    # 错拆成额外键（如 "  表述为": "  不够准确…"），extra="forbid" 会拒收。
    # 别名/中文键已在上文映射到 canonical，此处只保留已知字段即可安全兜底。
    _ALLOWED = {
        "category", "location", "target_wrote",
        "problem", "suggestion", "basis", "legal_basis",
    }
    normalized = {k: v for k, v in normalized.items() if k in _ALLOWED}
    return normalized


def load_prompt(module_file: str, name: str = "system.md") -> str:
    """Load a system prompt file co-located with the agent module.

    Args:
        module_file: Pass ``__file__`` from the calling module so the
                     prompt file is resolved relative to that module.
        name:        Prompt filename (default ``"system.md"``).

    Returns:
        The file contents as a single string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompt_path = Path(module_file).resolve().parent / name
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Agent prompt file not found: {prompt_path}.\n"
            f"Create '{name}' with the system prompt content for this agent."
        )
    return prompt_path.read_text(encoding="utf-8").strip()
