"""Expert A revision node — responds to Expert B's cross-review."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import RevisionRecord, StateDict, completed_event

_REVISE_PROMPT = load_prompt(__file__, "revise_system.md")


def build_expert_a_revise_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "RevisionRecord",
                    '{"agent":"expert_a","revisions":[{"review_id":1,'
                    '"review_category":"🟡","review_summary":"审查摘要",'
                    '"response":"回应说明","status":"accepted"}],'
                    '"unresolved_disputes":[],"modified_paragraphs":["段落"],'
                    '"modification_tags":["[经B审查修正]"]}',
                )
                + _REVISE_PROMPT,
            ),
            (
                "user",
                "我（专家 A）的原始草稿：\n{expert_a_draft}\n\n"
                "专家 B 对我的审查意见：\n{cross_review_b}\n\n"
                "Judge 打回意见（如有）：\n{judge_report}\n\n"
                "检索上下文：{retrieval_context}\n\n"
                "请逐条回应 B 的审查意见，输出 RevisionRecord 格式。",
            ),
        ]
    )

    def _normalize_revision(raw_obj: object) -> object:
        """Normalize LLM output: extract modified_paragraphs from individual
        revision items up to the record level, and remove from items."""
        if not isinstance(raw_obj, dict):
            return raw_obj
        normalized = dict(raw_obj)
        # Collect modified_paragraphs from individual revision items
        all_modified: list[str] = []
        revisions = normalized.get("revisions")
        if isinstance(revisions, list):
            for rev in revisions:
                if isinstance(rev, dict) and "modified_paragraphs" in rev:
                    paragraphs = rev.pop("modified_paragraphs")
                    if isinstance(paragraphs, list):
                        all_modified.extend(str(p) for p in paragraphs)
        # Only set at record level if not already present
        if all_modified and not normalized.get("modified_paragraphs"):
            normalized["modified_paragraphs"] = all_modified
        return normalized

    def expert_a_revise_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                cross_review_b=state.get("cross_review_b", {}),
                judge_report=state.get("judge_report", {}),
                retrieval_context=state.get("retrieval_context", []),
            ),
            temperature=0.4,
            agent="expert_a_revise",
        )
        normalized = _normalize_revision(
            normalize_key_aliases(
                raw,
                {
                    "unresolvedDisputes": "unresolved_disputes",
                    "modifiedParagraphs": "modified_paragraphs",
                    "modificationTags": "modification_tags",
                    "reviewId": "review_id",
                    "reviewCategory": "review_category",
                    "reviewSummary": "review_summary",
                },
            )
        )
        record = RevisionRecord.model_validate(normalized)
        return {
            "revision_record_a": record.model_dump(),
            "events": [completed_event(
                "expert_a_revise",
                "revised draft based on expert B or Judge review",
            )],
        }

    return expert_a_revise_node
