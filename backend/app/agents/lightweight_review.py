"""Lightweight review agent node — quick peer review of changed paragraphs only."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import LightweightReview, StateDict, completed_event

_LIGHTWEIGHT_REVIEW_SYSTEM = """你是轻量互审器。Judge 审核联合合成稿后打回修改，你只审查变更段落 + 前后各一段，判断变更是否解决了 Judge 提出的问题。

审查规则：
1. 只关注变更段落——不重新审查全文
2. 对照 Judge 的 revision_requests 逐条检查：该修正的问题是否已修正？
3. 每条修正标注 verdict：acceptable（修改到位）/ needs_more_work（仍未解决）
4. 不能引入新的问题——如果变更段落引入了新的法律错误，必须标注

verdict 取值：
- "acceptable"：所有变更都是可接受的修改，可以重新提交给 Judge
- "needs_more_work"：仍有未解决的问题，需要进一步修改

注意：
- 只审变更段落 + 前后各一段（共 3 段）
- 不审与变更无关的内容
- 不要过于严格——轻量互审是快速检查，不是完整审查"""


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
                "联合合成稿（修改前）：\n{joint_synthesis}\n\n"
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
