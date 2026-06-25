"""Expert B revision node — responds to Expert A's cross-review."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import RevisionRecord, StateDict, completed_event

_REVISE_PROMPT = load_prompt(__file__, "revise_system.md")


def build_expert_b_revise_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "RevisionRecord",
                    '{"agent":"expert_b","revisions":[{"review_id":1,'
                    '"review_category":"🔴","review_summary":"审查摘要",'
                    '"response":"回应说明","status":"accepted"}],'
                    '"unresolved_disputes":[],"modified_paragraphs":["段落"],'
                    '"modification_tags":["[经A审查修正]"]}',
                )
                + _REVISE_PROMPT,
            ),
            (
                "user",
                "我（专家 B）的原始草稿：\n{expert_b_draft}\n\n"
                "专家 A 对我的审查意见：\n{cross_review_a}\n\n"
                "Judge 打回意见（如有）：\n{judge_report}\n\n"
                "学习者画像：{learner_profile}\n\n"
                "请逐条回应 A 的审查意见，输出 RevisionRecord 格式。",
            ),
        ]
    )

    def _normalize_revision(raw_obj: object) -> object:
        """Normalize LLM output: extract modified_paragraphs from individual
        revision items up to the record level, and remove from items."""
        if not isinstance(raw_obj, dict):
            return raw_obj
        normalized = dict(raw_obj)
        all_modified: list[str] = []
        revisions = normalized.get("revisions")
        if isinstance(revisions, list):
            for rev in revisions:
                if isinstance(rev, dict) and "modified_paragraphs" in rev:
                    paragraphs = rev.pop("modified_paragraphs")
                    if isinstance(paragraphs, list):
                        all_modified.extend(str(p) for p in paragraphs)
        if all_modified and not normalized.get("modified_paragraphs"):
            normalized["modified_paragraphs"] = all_modified
        return normalized

    def expert_b_revise_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_b_draft=state.get("expert_b_draft", {}),
                cross_review_a=state.get("cross_review_a", {}),
                judge_report=state.get("judge_report", {}),
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=0.7,
            agent="expert_b_revise",
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
            "revision_record_b": record.model_dump(),
            "events": [completed_event(
                "expert_b_revise",
                "revised draft based on expert A or Judge review",
            )],
        }

    return expert_b_revise_node
