"""Expert A revision node — responds to Expert B's cross-review."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import RevisionRecord, StateDict, completed_event

_REVISE_PROMPT = """你是专家 A（保守严谨型·审查员视角）——修订模式。

你的任务：收到专家 B 对你的教学草稿的审查意见后，逐条回应。

修订原则：
1. 逐条回应：同意的 → 修改原文段落；不同意的 → 给出理由；不确定的 → 标注"需裁判裁决"（status="needs_arbitration"）
2. 修改段落标注变更标记：[经B审查修正] 或 [经B审查：此处坚持原表述]
3. 不引入大段新内容：修订只做局部修正
4. B 指出法律偏差时 → 感谢指正，修正
5. B 指出表达太抽象 → 考虑是否增加一句话概括或表格
6. B 指出引用错误 → 核实后修正
7. B 指出遗漏实务要点 → 判断是否必须覆盖；是则补充，超出则说明理由

status 取值：
- "accepted"：同意审查意见，已修改
- "rejected"：不同意，坚持原表述（需给出理由）
- "needs_arbitration"：不确定，需裁判裁决"""


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
                "检索上下文：{retrieval_context}\n\n"
                "请逐条回应 B 的审查意见，输出 RevisionRecord 格式。",
            ),
        ]
    )

    def expert_a_revise_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                cross_review_b=state.get("cross_review_b", {}),
                retrieval_context=state.get("retrieval_context", []),
            ),
            temperature=0.4,
            agent="expert_a_revise",
        )
        record = RevisionRecord.model_validate(
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
        return {
            "revision_record_a": record.model_dump(),
            "events": [completed_event("expert_a", "revised draft based on expert B review")],
        }

    return expert_a_revise_node
