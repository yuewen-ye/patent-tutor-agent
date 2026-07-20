"""Markdown artifact persistence for workflow runs."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal, cast

from backend.app.schemas.state import MarkdownArtifact

_MANIFEST_LOCK = threading.RLock()

ArtifactKind = Literal[
    "learner_profile_report",
    "learning_path_plan",
    "retrieval_context",
    "expert_draft",
    "judge_report",
    "feedback_report",
    "chat_answer",
    "cross_review",
    "expert_revision",
    "course_package",
    "dual_axis_snapshot",
    "questionnaire",
    "questionnaire_submission",
    "exercise_submission",
]

_CREATED_BY = {
    "learner_profile": "diagnosis_feedback",
    "learning_path": "planner",
    "path_decision": "planner",
    "retrieval_context": "retrieve_context",
    "expert_a_draft": "expert_a",
    "expert_b_draft": "expert_b",
    "judge_report": "judge",
    "feedback_result": "diagnosis_feedback",
    "chat_answer": "chat_answer",
    "dual_axis_snapshot": "planner",
    "expert_a_cross_review": "expert_a",
    "expert_b_cross_review": "expert_b",
    "expert_a_revision": "expert_a",
    "expert_b_revision": "expert_b",
    "learner_profile_update": "diagnosis_feedback",
    "course_package": "expert_a",
    "grading_report": "diagnosis_feedback",
}
_KIND_BY_FIELD: dict[str, ArtifactKind] = {
    "learner_profile": "learner_profile_report",
    "learning_path": "learning_path_plan",
    "path_decision": "learning_path_plan",
    "retrieval_context": "retrieval_context",
    "expert_a_draft": "expert_draft",
    "expert_b_draft": "expert_draft",
    "judge_report": "judge_report",
    "feedback_result": "feedback_report",
    "chat_answer": "chat_answer",
    "dual_axis_snapshot": "dual_axis_snapshot",
    "expert_a_cross_review": "cross_review",
    "expert_b_cross_review": "cross_review",
    "expert_a_revision": "expert_revision",
    "expert_b_revision": "expert_revision",
    "learner_profile_update": "feedback_report",
    "course_package": "course_package",
    "grading_report": "feedback_report",
}
_TITLE_BY_FIELD = {
    "learner_profile": "学习者画像报告",
    "learning_path": "学习路径规划",
    "path_decision": "学习路径决策指令",
    "retrieval_context": "RAG 检索上下文",
    "expert_a_draft": "专家 A 教学草稿",
    "expert_b_draft": "专家 B 教学草稿",
    "judge_report": "审核裁判报告",
    "feedback_result": "反馈分析报告",
    "chat_answer": "快速问答回答",
    "dual_axis_snapshot": "双知识轴快照",
    "expert_a_cross_review": "专家 A 对专家 B 的互评",
    "expert_b_cross_review": "专家 B 对专家 A 的互评",
    "expert_a_revision": "专家 A 修订稿",
    "expert_b_revision": "专家 B 修订稿",
    "learner_profile_update": "学情画像更新",
    "course_package": "整合后的课程完整内容与习题",
    "grading_report": "练习评分报告",
}
_FILE_BY_FIELD = {
    "learner_profile": "learner_profile.md",
    "learning_path": "learning_path.md",
    "path_decision": "path_decision.md",
    "retrieval_context": "retrieval_context.md",
    "expert_a_draft": "expert_a_draft.md",
    "expert_b_draft": "expert_b_draft.md",
    "judge_report": "judge_report.md",
    "feedback_result": "feedback_report.md",
    "chat_answer": "chat_answer.md",
    "dual_axis_snapshot": "dual_axis_snapshot.md",
    "expert_a_cross_review": "expert_a_cross_review.md",
    "expert_b_cross_review": "expert_b_cross_review.md",
    "expert_a_revision": "expert_a_revision.md",
    "expert_b_revision": "expert_b_revision.md",
    "learner_profile_update": "learner_profile_update.md",
    "course_package": "course_package.md",
    "grading_report": "grading_report.md",
}
_ROUND_FIELDS = {
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "expert_a_cross_review",
    "expert_b_cross_review",
    "expert_a_revision",
    "expert_b_revision",
    "course_package",
}

_DIRECTORIES = {
    "learner_profile": "profile",
    "learning_path": "path",
    "path_decision": "path",
    "dual_axis_snapshot": "path",
    "feedback_result": "feedback",
    "learner_profile_update": "feedback",
    "grading_report": "feedback",
}


def sanitize_session_id(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id).strip("-_")
    return safe or "session"


def _artifact_relative_path(
    artifact_root: Path, session_id: str, field: str, round_number: int
) -> Path:
    root_name = artifact_root.name or "artifacts"
    base = Path(root_name) / "sessions" / sanitize_session_id(session_id)
    if field in _ROUND_FIELDS:
        base = base / f"round-{round_number:02d}"
    elif field in _DIRECTORIES:
        base = base / _DIRECTORIES[field]
    return base / _FILE_BY_FIELD[field]


def _artifact_absolute_path(
    artifact_root: Path, session_id: str, field: str, round_number: int
) -> Path:
    base = artifact_root / "sessions" / sanitize_session_id(session_id)
    if field in _ROUND_FIELDS:
        base = base / f"round-{round_number:02d}"
    elif field in _DIRECTORIES:
        base = base / _DIRECTORIES[field]
    return base / _FILE_BY_FIELD[field]


def _deduplicated_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}-{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _markdown_for(field: str, value: object) -> str:
    title = _TITLE_BY_FIELD[field]
    if field == "learning_path" and isinstance(value, list):
        return _learning_path_markdown(title, value)
    if field == "path_decision" and isinstance(value, dict):
        return _path_decision_markdown(title, value)
    if field == "dual_axis_snapshot" and isinstance(value, dict):
        return _dual_axis_markdown(title, value)
    if field == "learner_profile" and isinstance(value, dict):
        return _profile_markdown(title, value)
    if field in {"expert_a_cross_review", "expert_b_cross_review"} and isinstance(value, dict):
        return _cross_review_markdown(title, value)
    if field == "judge_report" and isinstance(value, dict):
        return _judge_markdown(title, value)
    if field == "grading_report" and isinstance(value, list):
        return _grading_markdown(title, value)
    if field == "course_package" and isinstance(value, dict):
        return _course_package_markdown(title, value)
    if field in {"expert_a_draft", "expert_b_draft"} and isinstance(value, dict):
        return _expert_draft_markdown(title, value)
    if isinstance(value, dict):
        body = _dict_markdown(value)
    elif isinstance(value, list):
        body = _list_markdown(value)
    else:
        body = str(value)
    return f"# {title}\n\n{body}\n"


def _five_dimensions_markdown(fd: dict[str, Any]) -> str:
    """渲染扩展五维画像（BKT 概率快照），对齐规划版 02_学情画像.md 的结构。"""
    lines: list[str] = ["## 扩展五维画像（BKT 概率快照）", ""]

    knowledge = fd.get("knowledge") or {}
    if knowledge:
        lines.extend([
            "### 一、知识掌握度（knowledge · BKT P(L)）",
            "",
            "| 知识节点 | P(L) | 置信区间 | 观测数 | 低置信 |",
            "|---|---:|---|---:|:--:|",
        ])
        for node_id, st in knowledge.items():
            if not isinstance(st, dict):
                continue
            ci = f"[{st.get('ci_low', '?')}, {st.get('ci_high', '?')}]"
            obs = st.get("observations", 0)
            low = "是" if st.get("low_confidence") else ""
            lines.append(f"| {node_id} | {st.get('pl', '?')} | {ci} | {obs} | {low} |")
        lines.append("")

    cognition = fd.get("cognition") or {}
    if cognition:
        lines.extend([
            "### 二、认知能力层级（cognition · Bloom 六级）",
            "",
            "| 层级 | 分值 |",
            "|---|---:|",
        ])
        for lvl in ("remember", "understand", "apply", "analyze", "evaluate", "create"):
            if lvl in cognition:
                lines.append(f"| {lvl} | {cognition[lvl]} |")
        method = cognition.get("method")
        if method:
            lines.append("")
            lines.append(f"> 推断方法：{method}")
        lines.append("")

    style = fd.get("style") or {}
    if style:
        lines.extend([
            "### 三、学习风格（style · Felder-Silverman 四轴）",
            "",
            "| 轴 | 取向 | 强度 |",
            "|---|---|---:|",
        ])
        for axis in ("perception", "input", "processing", "understanding"):
            ax = style.get(axis)
            if isinstance(ax, dict):
                lines.append(f"| {axis} | {ax.get('chosen', '')} | {ax.get('strength', '')} |")
        lines.append("")

    progress = fd.get("progress") or {}
    if progress:
        lines.extend([
            "### 四、进度状态（progress）",
            "",
            f"- 已完成节点：{', '.join(progress.get('completed_nodes', []) or []) or '无'}",
            f"- 当前节点：{progress.get('current_node') or '无'}",
            f"- 待完成节点：{', '.join(progress.get('pending_nodes', []) or []) or '无'}",
        ])
        avg = progress.get("avg_time_per_node_min")
        lines.append(f"- 每节点平均耗时：{avg} 分钟" if avg is not None else "- 每节点平均耗时：无")
        ratio = progress.get("overall_completion_ratio")
        lines.append(f"- 总体完成比例：{ratio if ratio is not None else '无'}")
        lines.append("")

    affect = fd.get("affect") or {}
    if affect:
        lines.extend([
            "### 五、情感倾向（affect）",
            "",
            f"- 主状态：{affect.get('primary_state')}",
            f"- 置信度：{affect.get('confidence')}",
        ])
        signals = affect.get("signals") or []
        if signals:
            lines.append(f"- 信号：{'；'.join(signals)}")
        lines.append("")

    return "\n".join(lines)


def _profile_markdown(title: str, value: dict[str, Any]) -> str:
    labels = {
        "education_background": "教育与专业背景",
        "knowledge_level": "当前知识水平",
        "learning_style": "学习偏好",
        "weak_points": "薄弱点",
        "learning_goal": "学习目标",
        "error_pattern": "错误模式",
        "confidence": "画像置信度",
    }
    lines = [f"# {title}", ""]
    for key, label in labels.items():
        item = value.get(key)
        if item in (None, [], {}):
            continue
        lines.extend([f"## {label}", ""])
        if isinstance(item, list):
            lines.extend(f"- {entry}" for entry in item)
        else:
            lines.append(str(item))
        lines.append("")
    fd = value.get("five_dimensions")
    if fd:
        lines.append(_five_dimensions_markdown(fd))
    return "\n".join(lines).rstrip() + "\n"


def _learning_path_markdown(title: str, value: list[Any]) -> str:
    lines = [f"# {title}", ""]
    if not value:
        return "\n".join(lines) + "（暂无路径）\n"
    lines.extend([
        "| 顺序 | 节点 | 时长 | 学习策略 | 前置节点 | 难度上限 |",
        "|---:|---|---:|---|---|---:|",
    ])
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        prerequisites = ", ".join(item.get("prerequisites", [])) or "无"
        lines.append(
            f"| {index} | {item.get('node_name', '')} | {item.get('duration_min', '')} 分钟 | "
            f"{item.get('strategy', '')} | {prerequisites} | {item.get('difficulty_cap') or '—'} |"
        )
    lines.append("")
    lines.extend([
        "## 习题难度上限（分阶结论）",
        "",
        "| 节点 | 难度上限 |",
        "|---|---:|",
    ])
    for item in value:
        if isinstance(item, dict):
            lines.append(f"| {item.get('node_name', '')} | {item.get('difficulty_cap') or '—'} |")
    lines.append("")
    lines.append(
        "> 难度上限按掌握概率 P(L) 分阶：P(L)<0.15→L1；0.15≤P(L)<0.30→L2；P(L)≥0.30→L3；薄弱点强制≥L3。"
    )
    return "\n".join(lines) + "\n"


def _path_decision_markdown(title: str, value: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    qs = value.get("question_scope") or {}
    if qs:
        lines.extend(["## 出题范围（question_scope）", ""])
        for key, label in (
            ("backward_review", "向后复习验证型"),
            ("forward_probe", "向前探索探测型"),
            ("weakness_probe", "薄弱点探测型"),
        ):
            items = qs.get(key) or []
            if not items:
                continue
            lines.extend([f"### {label}", "", "| 节点 | 难度 | 目标 |", "|---|---|---|"])
            for it in items:
                if isinstance(it, dict):
                    lines.append(
                        f"| {it.get('node_id', '')} | {it.get('difficulty', '')} | {it.get('goal', '')} |"
                    )
            lines.append("")
    it_dir = value.get("iteration_directive") or {}
    if it_dir:
        lines.extend([
            "## 下一轮迭代预判（iteration_directive）",
            "",
            f"- 类型：{it_dir.get('type', '')}",
            f"- 触发：{it_dir.get('trigger', '')}",
            f"- 动作：{it_dir.get('action', '')}",
            "",
        ])
    if lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _dual_axis_markdown(title: str, value: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 知识轴版本：{value.get('knowledge_axis_version', '')}",
        f"- 混淆轴版本：{value.get('confusion_axis_version', '')}",
        "",
        "## 当前激活的混淆风险",
        "",
        "| 易混淆对 | 风险 | 调整原因 |",
        "|---|---:|---|",
    ]
    for pair in value.get("confusion_axis", []):
        if isinstance(pair, dict) and pair.get("is_active"):
            lines.append(
                f"| {pair.get('title', pair.get('pair_id', ''))} | "
                f"{float(pair.get('learner_risk', 0)):.2f} | {pair.get('adjustment_reason', '')} |"
            )
    if lines[-1] == "|---|---:|---|":
        lines.append("| 无 | 0.00 | 当前画像未激活静态混淆对 |")
    return "\n".join(lines) + "\n"


def _cross_review_markdown(title: str, value: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        f"## 总体评价\n\n{value.get('overall_assessment', '')}",
        "",
        "## 批改意见",
        "",
        "| 类别 | 位置 | 问题 | 修改建议 |",
        "|---|---|---|---|",
    ]
    for opinion in value.get("review_opinions", []):
        if isinstance(opinion, dict):
            lines.append(
                f"| {opinion.get('category', '')} | {opinion.get('location', '')} | "
                f"{opinion.get('problem', '')} | {opinion.get('suggestion', '')} |"
            )
    return "\n".join(lines) + "\n"


def _judge_markdown(title: str, value: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 决策：**{value.get('decision', '')}**",
        f"- 准确性：{value.get('accuracy_score', '')}/5",
        f"- 学员适配：{value.get('adaptation_score', '')}/5",
        f"- 学员适配准确率（adaptation_rate）：{value.get('adaptation_rate', '')}",
        f"- 完整性：{value.get('completeness_score', '')}/5",
        "",
        "## 审核理由",
        "",
        str(value.get("rationale", "")),
    ]
    requests = value.get("revision_requests", [])
    if requests:
        lines.extend(["", "## 必须修改项", ""])
        for request in requests:
            if isinstance(request, dict):
                lines.append(
                    f"- [{request.get('target', 'both')}] {request.get('required_change', '')}"
                )
    return "\n".join(lines) + "\n"


def _grading_markdown(title: str, value: list[Any]) -> str:
    lines = [f"# {title}", "", "| 题目 | 观测结果 | 评分状态 |", "|---|---|---|"]
    for item in value:
        if isinstance(item, dict):
            lines.append(
                f"| {item.get('question_id', '')} | {item.get('observed_correct', '')} | "
                f"{item.get('result', '')} |"
            )
    return "\n".join(lines) + "\n"


_MANDATORY_BLOCK_TYPES = {"legal_anchor", "knowledge_synthesis", "assessment"}

# 有可读 payload 内容的全部 13 个受控块类型（用于展开『各模块详细内容』）
BLOCK_CONTENT_BLOCK_TYPES = {
    "legal_anchor", "knowledge_synthesis", "assessment",
    "anchor_scenario", "global_framework", "worked_example",
    "decision_flow", "verbal_explanation", "predict_activate",
    "reflect_prompt", "mnemonic", "common_pitfall", "summary_card",
}


def _payload_digest(payload: Any, block_type: str = "") -> str:
    """从 block.payload 抽一句人读摘要，用于"对应正文段"列。

    优先按 block_type 抽取该模块的关键内容字段（充实后 payload 才有意义）；
    退化时回退到通用自由文本键。
    """
    if isinstance(payload, dict):
        # 按模块类型抽取最能体现"写了什么"的字段
        key_by_type = {
            "anchor_scenario": "scenario",
            "worked_example": "problem",
            "decision_flow": "question",
            "verbal_explanation": "spoken",
            "predict_activate": "prompt",
            "reflect_prompt": "question",
            "mnemonic": "device",
            "common_pitfall": "misconception",
            "summary_card": "one_line",
            "global_framework": "big_picture",
            "knowledge_synthesis": "framework",
            "legal_anchor": "articles",
            "assessment": "items",
        }
        pick = key_by_type.get(block_type)
        if pick and pick in payload:
            v = payload[pick]
            s = _to_text(v)
            if s:
                s = s.replace("\n", " ")
                return s[:46] + ("…" if len(s) > 46 else "")
        # 回退：通用自由文本键
        for key in ("summary", "text", "content", "body", "desc", "description", "case"):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                s = v.strip().replace("\n", " ")
                return s[:46] + ("…" if len(s) > 46 else "")
        # 再回退：列表型字段取首条
        for key in ("framework", "steps", "mapping", "cards", "topics", "articles"):
            v = payload.get(key)
            if isinstance(v, list) and v:
                s = _to_text(v[0])
                if s:
                    s = s.replace("\n", " ")
                    return s[:46] + ("…" if len(s) > 46 else "")
        if payload:
            return "（见正文对应板块）"
    elif isinstance(payload, str) and payload.strip():
        s = payload.strip().replace("\n", " ")
        return s[:46] + ("…" if len(s) > 46 else "")
    return "—"


def _to_text(v: Any) -> str:
    """把可能是 str / dict / list 的值拍平成一句文本。"""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        # 优先取常见文本键
        for k in ("concept", "术语", "article", "summary", "desc", "description", "推理", "question"):
            if k in v and isinstance(v[k], str):
                return v[k]
        # 否则取第一个字符串值
        for val in v.values():
            if isinstance(val, str) and val.strip():
                return val
        return ""
    if isinstance(v, list):
        if v and isinstance(v[0], str):
            return v[0]
        if v and isinstance(v[0], dict):
            return _to_text(v[0])
    return ""


def _mermaid_escape(s: Any) -> str:
    """清洗文本用于 Mermaid 节点标签（去换行/引号/竖线并截断）。"""
    return str(s).replace("\n", " ").replace('"', "'").replace("|", "/")[:60]


def _mermaid_decision_flow(payload: dict[str, Any]) -> str:
    """把 decision_flow 的 steps/end_states 渲染成 Mermaid 流程图。"""
    q = str(payload.get("question") or "决策问题")
    steps = payload.get("steps") or []
    ends = payload.get("end_states") or []
    lines = ["```mermaid", "flowchart TD", f'  START(["{_mermaid_escape(q)}"])']
    prev = "START"
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            cond = str(s.get("条件") or s.get("condition") or f"步骤{i + 1}")
            goto = str(s.get("走向") or s.get("branch") or "")
        else:
            cond = str(s)
            goto = ""
        nid = f"S{i + 1}"
        lines.append(f'  {nid}{{"{_mermaid_escape(cond)}"}}')
        if goto:
            lines.append(f"  {prev} -->|{_mermaid_escape(goto)}| {nid}")
        else:
            lines.append(f"  {prev} --> {nid}")
        prev = nid
    for j, e in enumerate(ends):
        eid = f"E{j + 1}"
        lines.append(f'  {eid}(["{_mermaid_escape(e)}"])')
        lines.append(f"  {prev} --> {eid}")
    lines.append("```")
    return "\n".join(lines)


def _render_block_payload(block_type: str, p: dict[str, Any]) -> str:
    """把单个 block 的 payload 渲染成可读 Markdown 文字。"""
    if block_type == "anchor_scenario":
        parts = []
        if p.get("scenario"):
            parts.append(f"> {p['scenario']}")
        if p.get("why_anchor"):
            parts.append(f"**锚定**：{p['why_anchor']}")
        if p.get("think_prompt"):
            parts.append(f"**先想一想**：{p['think_prompt']}")
        return "\n\n".join(parts)
    if block_type == "legal_anchor":
        lines = []
        arts = p.get("articles") or []
        summaries = p.get("plain_summary") or []
        for i, a in enumerate(arts):
            if isinstance(a, dict):
                art = a.get("article", "")
                summ = summaries[i] if i < len(summaries) else (a.get("summary") or "")
                lines.append(f"- **{art}**：{summ}")
            elif isinstance(a, str):
                lines.append(f"- {a}")
        if p.get("why_it_matters"):
            lines.append(f"\n**为何重要**：{p['why_it_matters']}")
        return "\n".join(lines)
    if block_type == "worked_example":
        lines = []
        if p.get("problem"):
            lines.append(f"**案情/例题**：{p['problem']}")
        if p.get("applicable_rule"):
            lines.append(f"**适用规则**：{p['applicable_rule']}")
        steps = p.get("steps") or []
        if steps:
            lines.append("**分步推演**：")
            for i, s in enumerate(steps, 1):
                if isinstance(s, dict):
                    r = s.get("推理") or s.get("reasoning") or ""
                    c = s.get("小结") or s.get("conclusion") or ""
                    lines.append(f"{i}. {r} → *{c}*")
                else:
                    lines.append(f"{i}. {s}")
        if p.get("conclusion"):
            lines.append(f"**结论**：{p['conclusion']}")
        if p.get("takeaway"):
            lines.append(f"**本题要点**：{p['takeaway']}")
        return "\n".join(lines)
    if block_type == "decision_flow":
        head = f"**决策问题**：{p.get('question')}\n\n" if p.get("question") else ""
        return head + _mermaid_decision_flow(p)
    if block_type == "verbal_explanation":
        parts = []
        if p.get("spoken"):
            parts.append(p["spoken"])
        terms = p.get("key_terms") or []
        if terms:
            parts.append("**点破术语**：" + "；".join(_to_text(t) for t in terms))
        if p.get("analogy"):
            parts.append(f"**类比**：{p['analogy']}")
        return "\n\n".join(parts)
    if block_type == "predict_activate":
        parts = []
        if p.get("prompt"):
            parts.append(f"**预测/激活**：{p['prompt']}")
        if p.get("activate"):
            parts.append(f"**激活旧知**：{p['activate']}")
        if p.get("reveal_hint"):
            parts.append(f"**揭晓方向**：{p['reveal_hint']}")
        return "\n\n".join(parts)
    if block_type == "reflect_prompt":
        parts = []
        if p.get("question"):
            parts.append(f"**反思问题**：{p['question']}")
        w = p.get("what_to_notice") or []
        if w:
            parts.append("**关注要点**：" + "；".join(_to_text(x) for x in w))
        if p.get("connect"):
            parts.append(f"**连接**：{p['connect']}")
        return "\n\n".join(parts)
    if block_type == "mnemonic":
        parts = []
        if p.get("device"):
            parts.append(f"**记忆锚**：{p['device']}")
        m = p.get("mapping") or []
        if m:
            parts.append("**映射**：")
            for x in m:
                parts.append(f"- {_to_text(x)}")
        if p.get("when_recall"):
            parts.append(f"**何时用**：{p['when_recall']}")
        return "\n".join(parts)
    if block_type == "common_pitfall":
        parts = []
        if p.get("misconception"):
            parts.append(f"**常见误解**：{p['misconception']}")
        if p.get("why_wrong"):
            parts.append(f"**为什么错**：{p['why_wrong']}")
        if p.get("distinguisher"):
            parts.append(f"**区分判据**：{p['distinguisher']}")
        if p.get("related_node"):
            parts.append(f"**关联节点**：{p['related_node']}")
        return "\n\n".join(parts)
    if block_type == "summary_card":
        parts = []
        cards = p.get("cards") or []
        if cards:
            parts.append("**要点卡**：")
            for c in cards:
                if isinstance(c, dict):
                    parts.append(f"- **{c.get('概念', c.get('concept', ''))}**：{c.get('一句话', c.get('summary', ''))}")
                else:
                    parts.append(f"- {c}")
        if p.get("must_recite"):
            parts.append("**必背**：" + "；".join(_to_text(x) for x in p["must_recite"]))
        if p.get("one_line"):
            parts.append(f"**一句话总结**：{p['one_line']}")
        return "\n".join(parts)
    if block_type == "global_framework":
        parts = []
        if p.get("position"):
            parts.append(f"**位置**：{p['position']}")
        if p.get("prereq"):
            parts.append("**前置**：" + "；".join(_to_text(x) for x in p["prereq"]))
        if p.get("leads_to"):
            parts.append("**后继**：" + "；".join(_to_text(x) for x in p["leads_to"]))
        if p.get("big_picture"):
            parts.append(f"**大局观**：{p['big_picture']}")
        return "\n\n".join(parts)
    if block_type == "knowledge_synthesis":
        parts = []
        fw = p.get("framework") or []
        if fw:
            parts.append("**知识框架**：")
            for x in fw:
                parts.append(f"- {_to_text(x)}")
        kr = p.get("key_relations") or []
        if kr:
            parts.append("**概念关系**：" + "；".join(_to_text(x) for x in kr))
        mk = p.get("must_know") or []
        if mk:
            parts.append("**必记**：" + "；".join(_to_text(x) for x in mk))
        return "\n".join(parts)
    if block_type == "assessment":
        parts = []
        cov = p.get("coverage") or {}
        if cov:
            present = [k for k, v in cov.items() if v]
            parts.append(f"**三类覆盖**：{('、'.join(present)) if present else '未声明'}")
        items = p.get("items") or []
        if items:
            parts.append("**题目**：")
            for it in items:
                if isinstance(it, dict):
                    parts.append(f"- {it.get('qid', '')}：{it.get('summary', '')}")
                else:
                    parts.append(f"- {it}")
        return "\n".join(parts)
    return _dict_markdown(p) if p else ""


def _render_block_details(blocks: list[dict[str, Any]]) -> str:
    """把所有选中块的 payload 展开成可连续阅读的『各模块详细内容』段。"""
    out: list[str] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        bt = str(b.get("block_type") or "")
        if bt not in BLOCK_CONTENT_BLOCK_TYPES:
            continue
        payload = b.get("payload")
        if not isinstance(payload, dict) or not payload:
            continue
        title = str(b.get("title") or bt)
        rendered = _render_block_payload(bt, payload)
        if not rendered.strip():
            continue
        out.append(f"### {title}（{bt}）")
        out.append("")
        out.append(rendered)
        out.append("")
    return "\n".join(out).rstrip() + "\n" if out else ""


def _course_package_markdown(title: str, value: dict[str, Any]) -> str:
    """整合稿渲染：顶部先给「教学模块选择清单」表格，再输出教学正文与其余字段。"""
    lines: list[str] = [f"# {title}", ""]

    block_plan = value.get("block_plan")
    blocks = block_plan.get("blocks") if isinstance(block_plan, dict) else None
    if isinstance(blocks, list) and blocks:
        node = block_plan.get("node") or value.get("node") or "—"
        budget = block_plan.get("budget") or {}
        lines.extend([
            "## 教学模块选择清单",
            "",
            f"- 当前教学节点：`{node}`",
            (
                f"- 板块预算：自适应 {budget.get('adaptive_used', '?')}/"
                f"{budget.get('adaptive_max', 6)}，"
                f"总计 {budget.get('total', len(blocks))}/{budget.get('total_max', 9)}"
                if budget else f"- 板块数：{len(blocks)}"
            ),
            "",
            "| # | 模块 (block_type) | 类型 | 触发原因 (trigger) | 对应正文段 | 归属 |",
            "|---:|---|:--:|---|---|:--:|",
        ])
        for idx, b in enumerate(blocks, start=1):
            if not isinstance(b, dict):
                continue
            bt = str(b.get("block_type") or "")
            kind = "必选" if bt in _MANDATORY_BLOCK_TYPES else "自适应"
            trigger = str(b.get("trigger") or "—").replace("|", "\\|")
            title_seg = str(b.get("title") or bt).replace("|", "\\|")
            digest = _payload_digest(b.get("payload"), bt).replace("|", "\\|")
            owner = str(b.get("chosen_by") or "—")
            seg = f"{title_seg}｜{digest}" if digest not in ("—", "") else title_seg
            lines.append(
                f"| {idx} | `{bt}` | {kind} | {trigger} | {seg} | {owner} |"
            )
        lines.append("")

    teaching = value.get("teaching_content")

    # 教学正文：把 IRAC 散文（主线概述）与各模块的详细内容**穿插**在一起，
    # 而非把模块内容堆在文件最后。各模块按 block_plan 顺序展开为子节
    # （图文穿插，decision_flow 出 Mermaid 流程图），assessment 强制置末。
    if isinstance(blocks, list) and blocks:
        # 非测评块按 block_plan.order 排序，测评块统一挪到最后
        order_index = {str(b.get("block_id")): i for i, b in enumerate(blocks)}
        ordered = sorted(
            blocks,
            key=lambda b: order_index.get(str(b.get("block_id")), 999),
        )
        non_ass = [b for b in ordered if str(b.get("block_type")) != "assessment"]
        ass = [b for b in ordered if str(b.get("block_type")) == "assessment"]
        seq = non_ass + ass
        detail = _render_block_details(seq)
    else:
        detail = ""

    if teaching or detail:
        lines.extend(["## 教学正文", ""])
        if teaching:
            lines.extend([str(teaching), ""])
        if detail:
            # 模块详细内容作为教学正文的子节穿插其中（不再独立成段堆最后）
            lines.extend([detail, ""])

    # 其余字段沿用通用 dict 渲染（跳过已单独渲染的 title/teaching_content）
    rest = {
        k: v
        for k, v in value.items()
        if k not in ("teaching_content", "markdown_artifact", "block_plan") and v not in (None, [], {})
    }
    if rest:
        lines.extend(["## 结构化数据", "", _dict_markdown(rest)])

    return "\n".join(lines).rstrip() + "\n"


def _expert_draft_markdown(title: str, value: dict[str, Any]) -> str:
    """专家 A/B 草稿渲染：与 course_package 同样的『模块穿插 + 测评末 + Mermaid』标准。

    - 当草稿含结构化 block_plan（初稿即按确定性块大纲产出）时，教学正文按块顺序
      穿插展开，decision_flow 出 Mermaid，assessment 置末。
    - 当草稿尚无 block_plan（旧形态：初稿传 null）时，退化为「散文 + 结构化字段」，
      并在文末提示最终由 integration 补全。
    """
    lines: list[str] = [f"# {title}", ""]

    expert = value.get("expert")
    style = value.get("style")
    if expert or style:
        meta = []
        if expert:
            meta.append(f"专家：{expert}")
        if style:
            meta.append(f"风格：{style}")
        lines.append("> " + " ｜ ".join(meta))
        lines.append("")

    block_plan = value.get("block_plan")
    blocks = block_plan.get("blocks") if isinstance(block_plan, dict) else None
    teaching = value.get("teaching_content")

    if isinstance(blocks, list) and blocks:
        # 教学模块选择清单（展示该专家主张的块）
        node = block_plan.get("node") or value.get("node") or "—"
        budget = block_plan.get("budget") or {}
        lines.extend([
            "## 教学模块选择清单",
            "",
            f"- 当前教学节点：`{node}`",
            (
                f"- 板块预算：自适应 {budget.get('adaptive_used', '?')}/"
                f"{budget.get('adaptive_max', 6)}，"
                f"总计 {budget.get('total', len(blocks))}/{budget.get('total_max', 9)}"
                if budget else f"- 板块数：{len(blocks)}"
            ),
            "",
            "| # | 模块 (block_type) | 类型 | 触发原因 (trigger) | 对应正文段 | 归属 |",
            "|---:|---|:--:|---|---|:--:|",
        ])
        for idx, b in enumerate(blocks, start=1):
            if not isinstance(b, dict):
                continue
            bt = str(b.get("block_type") or "")
            kind = "必选" if bt in _MANDATORY_BLOCK_TYPES else "自适应"
            trigger = str(b.get("trigger") or "—").replace("|", "\\|")
            title_seg = str(b.get("title") or bt).replace("|", "\\|")
            digest = _payload_digest(b.get("payload"), bt).replace("|", "\\|")
            owner = str(b.get("chosen_by") or "—")
            seg = f"{title_seg}｜{digest}" if digest not in ("—", "") else title_seg
            lines.append(
                f"| {idx} | `{bt}` | {kind} | {trigger} | {seg} | {owner} |"
            )
        lines.append("")

        # 穿插教学正文：非测评块按 order，测评块置末
        order_index = {str(b.get("block_id")): i for i, b in enumerate(blocks)}
        ordered = sorted(blocks, key=lambda b: order_index.get(str(b.get("block_id")), 999))
        non_ass = [b for b in ordered if str(b.get("block_type")) != "assessment"]
        ass = [b for b in ordered if str(b.get("block_type")) == "assessment"]
        detail = _render_block_details(non_ass + ass)
    else:
        detail = ""

    if teaching or detail:
        lines.extend(["## 教学正文", ""])
        if teaching:
            lines.extend([str(teaching), ""])
        if detail:
            lines.extend([detail, ""])

    # 其余结构化字段（知识点 / 法条依据 / 风险 / 测评题等）
    rest = {
        k: v
        for k, v in value.items()
        if k not in ("teaching_content", "markdown_artifact", "block_plan", "expert", "style")
        and v not in (None, [], {})
    }
    if rest:
        lines.extend(["## 结构化字段", "", _dict_markdown(rest)])
    elif not blocks:
        lines.append("> 本草稿尚未含结构化 block_plan，最终由 integration 阶段按确定性规则补全。")

    return "\n".join(lines).rstrip() + "\n"


def _dict_markdown(value: dict[str, Any]) -> str:
    lines: list[str] = []
    preferred = [
        "title",
        "content",
        "teaching_content",
        "rationale",
        "next_action",
        "profile_update_hint",
    ]
    for key in preferred:
        if value.get(key):
            lines.append(f"## {key}\n\n{value[key]}")
    for key, item in value.items():
        if key in preferred or key == "markdown_artifact" or item in (None, [], {}):
            continue
        rendered = json.dumps(item, ensure_ascii=False, indent=2)
        lines.append(f"## {key}\n\n```json\n{rendered}\n```")
    return "\n\n".join(lines) or "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def _list_markdown(value: list[Any]) -> str:
    if not value:
        return "[]"
    parts = []
    for index, item in enumerate(value, start=1):
        rendered = json.dumps(item, ensure_ascii=False, indent=2)
        parts.append(f"## Item {index}\n\n```json\n{rendered}\n```")
    return "\n\n".join(parts)


def write_field_artifact(
    *, artifact_root: Path, session_id: str, field: str, value: object, round_number: int
) -> dict[str, Any]:
    if field not in _KIND_BY_FIELD:
        raise ValueError(f"Unsupported artifact field: {field}")
    content = _markdown_for(field, value)
    absolute_path = _deduplicated_path(
        _artifact_absolute_path(artifact_root, session_id, field, round_number)
    )
    relative_path = _artifact_relative_path(artifact_root, session_id, field, round_number)
    if absolute_path.name != relative_path.name:
        relative_path = relative_path.with_name(absolute_path.name)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_text(content, encoding="utf-8")
    artifact_id = f"{sanitize_session_id(session_id)}-round-{round_number:02d}-{field}"
    if absolute_path.stem != Path(_FILE_BY_FIELD[field]).stem:
        artifact_id = f"{artifact_id}-{absolute_path.stem.rsplit('-', 1)[-1]}"
    artifact = MarkdownArtifact(
        artifact_id=artifact_id,
        kind=_KIND_BY_FIELD[field],
        path=relative_path.as_posix(),
        created_by=cast(Any, _CREATED_BY[field]),
        title=_TITLE_BY_FIELD[field],
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        created_at=datetime.now(UTC).isoformat(),
    ).model_dump()
    return artifact


def attach_markdown_artifact(value: object, artifact: dict[str, Any]) -> object:
    if isinstance(value, dict):
        updated = dict(value)
        updated["markdown_artifact"] = artifact
        return updated
    return value


def write_process_markdown(
    *,
    artifact_root: Path,
    session_id: str,
    relative_path: str,
    content: str,
    kind: str = "questionnaire",
    title: str = "过程产物",
    created_by: str = "diagnosis_feedback",
) -> dict[str, Any]:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".md":
        raise ValueError("Invalid process artifact path.")
    absolute = artifact_root / "sessions" / sanitize_session_id(session_id) / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_text(content, encoding="utf-8")
    root_name = artifact_root.name or "artifacts"
    artifact_path = Path(root_name) / "sessions" / sanitize_session_id(session_id) / relative
    return MarkdownArtifact(
        artifact_id=f"{sanitize_session_id(session_id)}-{relative.stem}",
        kind=cast(Any, kind),
        path=artifact_path.as_posix(),
        created_by=cast(Any, created_by),
        title=title,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        created_at=datetime.now(UTC).isoformat(),
    ).model_dump()


def write_manifest(*, artifact_root: Path, state: Mapping[str, Any], status: str) -> None:
    session_id = sanitize_session_id(str(state["session_id"]))
    path = artifact_root / "sessions" / session_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "session_id": state["session_id"],
        "status": status,
        "artifacts": state.get("artifacts", []),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    with _MANIFEST_LOCK:
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
