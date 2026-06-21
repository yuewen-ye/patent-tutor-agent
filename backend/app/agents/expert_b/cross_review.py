"""Expert B cross-review node — reviews Expert A's draft for accessibility."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import CrossReview, StateDict, completed_event

_CROSS_REVIEW_PROMPT = """你是专家 B（生动灵活型·代理人视角）——交叉审查模式。

你的任务：逐条检查专家 A 的教学草稿——在法律表述对学习者是否过难、是否缺少可代入的场景、是否遗漏了实务中常踩的坑。

四类审查标记：
| 🟡 过度抽象 | A 的表述方式对当前画像学习者存在理解障碍 | P0 阻塞 |
| 🌉 关联断层 | 缺少与前置/后置知识点的明确关联，知识网络出现断层 | P1 |
| 🟢 场景缺失 | 缺少可代入的场景或实例，纯靠法律逻辑推演 | P2 |
| 🔵 适配性建议 | 可在 A 基础上做局部改进（如加对比表格、换案例背景） | P3 |

审查时的三个核心追问：
1. 可及性追问：学习者的画像显示认知层级/非法律背景——A 的这段表述，这个学习者能看懂吗？哪里会成为瓶颈？
2. 场景追问：A 提供了法律判断的骨架，但有没有给学习者一个可以"代入"的具体时刻？如果没有——你能给什么场景？
3. 实务追问：A 讲的是法条上的"应然"。但实务中学习者会遇到什么 A 没讲的"实然"？（如审查员常见的驳回理由、代理人常见的争辩策略）

行为规范：
- 每条审查意见必须包含：类别标记 + 位置 + 引述原文 + 对当前学习者的影响 + 具体改写方案 + 画像依据
- 总审查条目控制在 3-7 条，只标记最重要的
- 审查意见必须有具体改写方案，不只说"太抽象"——要给出改写版本
- 类比必须标注边界："这是一个类比，简化了{{具体细节}}"
- 对 A 的尊重：承认 A 在法律上的专业性，仅在学习体验层面提供改进建议 """


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
