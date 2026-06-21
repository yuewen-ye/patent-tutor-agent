"""Markdown artifact persistence for workflow runs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from backend.app.schemas.state import MarkdownArtifact

ArtifactKind = Literal[
    "learner_profile_report",
    "learning_path_plan",
    "retrieval_context",
    "expert_draft",
    "judge_report",
    "feedback_report",
    "final_answer",
    "chat_answer",
    "cross_review",
    "joint_synthesis",
]

_CREATED_BY = {
    "learner_profile": "diagnosis",
    "learning_path": "planner",
    "retrieval_context": "retrieve_context",
    "expert_a_draft": "expert_a",
    "expert_b_draft": "expert_b",
    "judge_report": "judge",
    "feedback_result": "feedback",
    "final_answer": "finalize",
    "chat_answer": "chat_answer",
    "cross_review_a": "cross_review_a",
    "cross_review_b": "cross_review_b",
    "revision_record_a": "expert_a_revise",
    "revision_record_b": "expert_b_revise",
    "joint_synthesis_output": "joint_synthesis",
    "lightweight_review_result": "lightweight_review",
}
_KIND_BY_FIELD: dict[str, ArtifactKind] = {
    "learner_profile": "learner_profile_report",
    "learning_path": "learning_path_plan",
    "retrieval_context": "retrieval_context",
    "expert_a_draft": "expert_draft",
    "expert_b_draft": "expert_draft",
    "judge_report": "judge_report",
    "feedback_result": "feedback_report",
    "final_answer": "final_answer",
    "chat_answer": "chat_answer",
    "cross_review_a": "cross_review",
    "cross_review_b": "cross_review",
    "revision_record_a": "expert_draft",
    "revision_record_b": "expert_draft",
    "joint_synthesis_output": "joint_synthesis",
    "lightweight_review_result": "judge_report",
}
_TITLE_BY_FIELD = {
    "learner_profile": "学习者画像报告",
    "learning_path": "学习路径规划",
    "retrieval_context": "RAG 检索上下文",
    "expert_a_draft": "专家 A 教学草稿",
    "expert_b_draft": "专家 B 教学草稿",
    "judge_report": "审核裁判报告",
    "feedback_result": "反馈分析报告",
    "final_answer": "个性化知识产权学习建议",
    "chat_answer": "快速问答回答",
    "cross_review_a": "专家 A 对 B 的交叉审查",
    "cross_review_b": "专家 B 对 A 的交叉审查",
    "revision_record_a": "专家 A 修订记录",
    "revision_record_b": "专家 B 修订记录",
    "joint_synthesis_output": "专家联合合成稿",
    "lightweight_review_result": "轻量互审报告",
}
_FILE_BY_FIELD = {
    "learner_profile": "learner_profile.md",
    "learning_path": "learning_path.md",
    "retrieval_context": "retrieval_context.md",
    "expert_a_draft": "expert_a_draft.md",
    "expert_b_draft": "expert_b_draft.md",
    "judge_report": "judge_report.md",
    "feedback_result": "feedback_report.md",
    "final_answer": "final_answer.md",
    "chat_answer": "chat_answer.md",
    "cross_review_a": "cross_review_a.md",
    "cross_review_b": "cross_review_b.md",
    "revision_record_a": "revision_record_a.md",
    "revision_record_b": "revision_record_b.md",
    "joint_synthesis_output": "joint_synthesis.md",
    "lightweight_review_result": "lightweight_review.md",
}
_ROUND_FIELDS = {
    "learner_profile",
    "learning_path",
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "feedback_result",
    "cross_review_a",
    "cross_review_b",
    "revision_record_a",
    "revision_record_b",
    "joint_synthesis_output",
    "lightweight_review_result",
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
    return base / _FILE_BY_FIELD[field]


def _artifact_absolute_path(
    artifact_root: Path, session_id: str, field: str, round_number: int
) -> Path:
    base = artifact_root / "sessions" / sanitize_session_id(session_id)
    if field in _ROUND_FIELDS:
        base = base / f"round-{round_number:02d}"
    return base / _FILE_BY_FIELD[field]


def _markdown_for(field: str, value: object) -> str:
    title = _TITLE_BY_FIELD[field]
    if isinstance(value, dict):
        body = _dict_markdown(value)
    elif isinstance(value, list):
        body = _list_markdown(value)
    else:
        body = str(value)
    return f"# {title}\n\n{body}\n"


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
    absolute_path = _artifact_absolute_path(artifact_root, session_id, field, round_number)
    relative_path = _artifact_relative_path(artifact_root, session_id, field, round_number)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_text(content, encoding="utf-8")
    artifact_id = f"{sanitize_session_id(session_id)}-round-{round_number:02d}-{field}"
    if field == "final_answer":
        artifact_id = f"{sanitize_session_id(session_id)}-{field}"
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


def write_manifest(*, artifact_root: Path, state: dict[str, Any], status: str) -> None:
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
