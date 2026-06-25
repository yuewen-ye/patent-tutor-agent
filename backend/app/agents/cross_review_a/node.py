"""Expert A cross-review node — reviews Expert B's draft for legal accuracy."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import CrossReview, StateDict, completed_event

_CROSS_REVIEW_PROMPT = load_prompt(__file__)


def build_expert_a_cross_review_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "CrossReview",
                    '{"reviewer":"expert_a","target":"expert_b",'
                    '"review_opinions":[{"category":"🔴","location":"第X段",'
                    '"target_wrote":"B的原文","problem":"问题描述",'
                    '"suggestion":"修正建议","basis":"法条依据"}],'
                    '"positive_confirmation":"正面确认","overall_assessment":"总体评价"}',
                )
                + _CROSS_REVIEW_PROMPT,
            ),
            (
                "user",
                "专家 B 的教学草稿：\n{expert_b_draft}\n\n"
                "学习者画像：{learner_profile}\n"
                "检索上下文：{retrieval_context}\n\n"
                "请逐条审查专家 B 的草稿，输出 CrossReview 格式的审查意见。",
            ),
        ]
    )

    def cross_review_a_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_b_draft=state.get("expert_b_draft", {}),
                learner_profile=state.get("learner_profile", {}),
                retrieval_context=state.get("retrieval_context", []),
            ),
            temperature=0.3,
            agent="cross_review_a",
        )
        review = CrossReview.model_validate(
            normalize_key_aliases(
                raw,
                {
                    "reviewOpinions": "review_opinions",
                    "positiveConfirmation": "positive_confirmation",
                    "overallAssessment": "overall_assessment",
                    "targetWrote": "target_wrote",
                },
            )
        )
        return {
            "cross_review_a": review.model_dump(),
            "events": [completed_event("cross_review_a", "cross-reviewed expert B draft")],
        }

    return cross_review_a_node
