"""Lightweight review agent node — quick peer review of changed paragraphs only."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import LightweightReview, StateDict, completed_event

_LIGHTWEIGHT_REVIEW_SYSTEM = load_prompt(__file__)


def build_lightweight_review_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "LightweightReview",
                    '{"reviewed_changes":[{"change_location":"第X段",'
                    '"change_description":"修改了...","related_judge_request":"裁判要求...",'
                    '"verdict":"acceptable","reason":"修改到位"}],'
                    '"verdict":"acceptable","unresolved":[]}',
                )
                + _LIGHTWEIGHT_REVIEW_SYSTEM,
            ),
            (
                "user",
                "修订后的联合合成稿：\n{joint_synthesis}\n\n"
                "Judge 的打回意见：\n{judge_report}\n\n"
                "当前辩论轮次：{debate_round}\n\n"
                "请对变更段落进行轻量互审。",
            ),
        ]
    )

    def lightweight_review_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                joint_synthesis=state.get("joint_synthesis_output", {}),
                judge_report=state.get("judge_report", {}),
                debate_round=state.get("debate_round", 1),
            ),
            temperature=0.2,
            agent="lightweight_review",
        )
        review = LightweightReview.model_validate(
            normalize_key_aliases(
                raw,
                {
                    "reviewedChanges": "reviewed_changes",
                },
            )
        )
        return {
            "lightweight_review_result": review.model_dump(),
            "events": [
                completed_event(
                    "lightweight_review", "completed lightweight review of changes"
                )
            ],
        }

    return lightweight_review_node
