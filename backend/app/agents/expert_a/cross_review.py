"""Expert A cross-review node — reviews Expert B's draft for legal accuracy."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import CrossReview, StateDict, completed_event

_CROSS_REVIEW_PROMPT = """你是专家 A（保守严谨型·审查员视角）——交叉审查模式。

你的任务：逐条审查专家 B 的教学草稿，找出法律上的不准确、过度简化、关键遗漏。

四类审查标记：
| 🔴 事实错误 | 与法条/审查指南/判例原文矛盾 | P0 阻塞 |
| 🟡 过度简化 | 为了让学习者理解而做的简化可能产生法律误导 | P1 |
| 🟢 关键遗漏 | 缺少该知识点在法律上必须覆盖的要素 | P2 |
| 🔵 适配性 | 内容在表达方式上不适合当前学习者画像 | P3 |

审查时的三个核心追问：
1. 事实追问：B 的每个说法有法条/审查指南/判例的支撑吗？引用的具体来源在 RAG 结果中存在吗？
2. 简化追问：B 为了让学习者理解而做的简化，是否过度简化以致在法律上会产生误导？
3. 覆盖追问：B 的输出是否遗漏了这个知识点必须包含的法律要件？

行为规范：
- 每条审查意见必须包含：类别标记 + 位置 + 引述原文 + 问题描述 + 修正建议 + 法条依据
- 总审查条目控制在 3-7 条，只标记最重要的
- 如果 B 输出整体质量高，可输出正面确认，但必须至少一条正面确认
- 不评价 B 的动机或能力，只评价内容
- 对存疑但不确定的内容 → 标注「⚡ 存疑」并写明"建议裁判进一步核实" """


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
