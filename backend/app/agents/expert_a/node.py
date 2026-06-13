"""Expert A Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import ExpertDraft, StateDict, completed_event


def build_expert_a_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "ExpertDraft",
                    '{"expert":"expert_a","style":"conservative_precise",'
                    '"knowledge_points":["要点"],"legal_basis":["依据"],'
                    '"teaching_content":"正文","risks":[]}',
                )
                + "你是保守严谨的专利法专家 A，优先保证法条准确。"
                + "如果修订上下文包含 revision_requests，必须逐条回应裁判意见。",
            ),
            (
                "user",
                "问题：{user_input}\n"
                "检索上下文：{retrieval_context}\n"
                "当前辩论轮次：{debate_round}\n"
                "修订上下文：{revision_context}\n"
                "请生成专家 A 草稿。",
            ),
        ]
    )

    def expert_a_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                retrieval_context=state.get("retrieval_context", []),
                debate_round=state.get("debate_round", 1),
                revision_context=state.get("judge_report", {}),
            ),
            temperature=0.4,
            agent="expert_a",
        )
        draft = ExpertDraft.model_validate(
            normalize_key_aliases(
                raw,
                {
                    "knowledgePoints": "knowledge_points",
                    "legalBasis": "legal_basis",
                    "teachingContent": "teaching_content",
                    "interactiveQuestions": "interactive_questions",
                },
            )
        )
        return {
            "expert_a_draft": draft.model_dump(),
            "events": [completed_event("expert_a", "generated expert A draft with LLM")],
        }

    return expert_a_node
