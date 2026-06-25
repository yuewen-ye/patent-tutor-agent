"""Expert B cross-review node — reviews Expert A's draft for accessibility."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import CrossReview, StateDict, completed_event

_CROSS_REVIEW_PROMPT = load_prompt(__file__)


def build_expert_b_cross_review_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "CrossReview",
                    '{"reviewer":"expert_b","target":"expert_a",'
                    '"review_opinions":[{"category":"🟡","location":"第X段",'
                    '"target_wrote":"A的原文","problem":"对学习者的影响描述",'
                    '"suggestion":"具体改写方案","basis":"画像依据"}],'
                    '"positive_confirmation":"正面确认","overall_assessment":"总体评价"}',
                )
                + _CROSS_REVIEW_PROMPT,
            ),
            (
                "user",
                "专家 A 的教学草稿：\n{expert_a_draft}\n\n"
                "学习者画像：{learner_profile}\n\n"
                "请逐条审查专家 A 的草稿，输出 CrossReview 格式的审查意见。",
            ),
        ]
    )

    def cross_review_b_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=0.5,
            agent="cross_review_b",
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
            "cross_review_b": review.model_dump(),
            "events": [completed_event("cross_review_b", "cross-reviewed expert A draft")],
        }

    return cross_review_b_node
