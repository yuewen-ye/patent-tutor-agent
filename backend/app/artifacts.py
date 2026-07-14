"""Markdown artifact persistence for workflow runs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal, cast

from backend.app.schemas.state import MarkdownArtifact

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
    "exercise_answer_key",
    "final_learning",
    "dual_axis_snapshot",
    "questionnaire",
    "questionnaire_submission",
    "exercise_submission",
]

_CREATED_BY = {
    "learner_profile": "learner_state",
    "learning_path": "planner",
    "retrieval_context": "retrieve_context",
    "expert_a_draft": "expert_a",
    "expert_b_draft": "expert_b",
    "judge_report": "judge",
    "feedback_result": "learner_state",
    "chat_answer": "chat_answer",
    "dual_axis_snapshot": "planner",
    "expert_a_cross_review": "expert_a",
    "expert_b_cross_review": "expert_b",
    "expert_a_revision": "expert_a",
    "expert_b_revision": "expert_b",
    "final_learning_markdown": "publish_final_learning",
    "exercise_answer_key": "publish_final_learning",
    "learner_profile_update": "learner_state",
    "course_package": "expert_a",
    "grading_report": "learner_state",
}
_KIND_BY_FIELD: dict[str, ArtifactKind] = {
    "learner_profile": "learner_profile_report",
    "learning_path": "learning_path_plan",
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
    "final_learning_markdown": "final_learning",
    "exercise_answer_key": "exercise_answer_key",
    "learner_profile_update": "feedback_report",
    "course_package": "course_package",
    "grading_report": "feedback_report",
}
_TITLE_BY_FIELD = {
    "learner_profile": "学习者画像报告",
    "learning_path": "学习路径规划",
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
    "final_learning_markdown": "个性化学习课程",
    "exercise_answer_key": "练习题内部答案",
    "learner_profile_update": "学情画像更新",
    "course_package": "整合后的课程完整内容与习题",
    "grading_report": "练习评分报告",
}
_FILE_BY_FIELD = {
    "learner_profile": "learner_profile.md",
    "learning_path": "learning_path.md",
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
    "final_learning_markdown": "final_learning.md",
    "exercise_answer_key": "exercise_answer_key.md",
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
    "dual_axis_snapshot": "path",
    "feedback_result": "feedback",
    "exercise_answer_key": "internal",
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
    if field == "final_learning_markdown":
        return str(value)
    title = _TITLE_BY_FIELD[field]
    if field == "learning_path" and isinstance(value, list):
        return _learning_path_markdown(title, value)
    if field == "dual_axis_snapshot" and isinstance(value, dict):
        return _dual_axis_markdown(title, value)
    if field == "learner_profile" and isinstance(value, dict):
        return _profile_markdown(title, value)
    if field in {"expert_a_cross_review", "expert_b_cross_review"} and isinstance(value, dict):
        return _cross_review_markdown(title, value)
    if field == "judge_report" and isinstance(value, dict):
        return _judge_markdown(title, value)
    if field == "exercise_answer_key" and isinstance(value, list):
        return _answer_key_markdown(title, value)
    if field == "grading_report" and isinstance(value, list):
        return _grading_markdown(title, value)
    if isinstance(value, dict):
        body = _dict_markdown(value)
    elif isinstance(value, list):
        body = _list_markdown(value)
    else:
        body = str(value)
    return f"# {title}\n\n{body}\n"


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
    return "\n".join(lines).rstrip() + "\n"


def _learning_path_markdown(title: str, value: list[Any]) -> str:
    lines = [f"# {title}", "", "| 顺序 | 节点 | 时长 | 学习策略 | 前置节点 |", "|---:|---|---:|---|---|"]
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        prerequisites = ", ".join(item.get("prerequisites", [])) or "无"
        lines.append(
            f"| {index} | {item.get('node_name', '')} | {item.get('duration_min', '')} 分钟 | "
            f"{item.get('strategy', '')} | {prerequisites} |"
        )
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


def _answer_key_markdown(title: str, value: list[Any]) -> str:
    lines = [f"# {title}", "", "> 仅供评分与学情更新使用，不向学员课程页面发布。", ""]
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            lines.extend(
                [
                    f"## {index}. {item.get('question_id', '')}",
                    "",
                    f"- 答案：{item.get('answer', '')}",
                    f"- 解析：{item.get('explanation', '')}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _grading_markdown(title: str, value: list[Any]) -> str:
    lines = [f"# {title}", "", "| 题目 | 观测结果 | 评分状态 |", "|---|---|---|"]
    for item in value:
        if isinstance(item, dict):
            lines.append(
                f"| {item.get('question_id', '')} | {item.get('observed_correct', '')} | "
                f"{item.get('result', '')} |"
            )
    return "\n".join(lines) + "\n"


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
    created_by: str = "learner_state",
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
        "debate_round": state.get("debate_round"),
        "max_debate_rounds": state.get("max_debate_rounds"),
        "artifacts": state.get("artifacts", []),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
