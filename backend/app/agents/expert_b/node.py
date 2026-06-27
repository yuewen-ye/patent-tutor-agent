"""Expert B Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import ExpertDraft, StateDict, completed_event

_EXTRA_TEXT = load_prompt(__file__)


def build_expert_b_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "ExpertDraft",
                    '{"expert":"expert_b","style":"vivid_teaching",'
                    '"knowledge_points":["要点"],"legal_basis":["依据"],'
                    '"teaching_content":"正文","risks":[]}',
                )
                + _EXTRA_TEXT,
            ),
            (
                "user",
                "问题：{user_input}\n"
                "学习者画像：{learner_profile}\n"
                "当前辩论轮次：{debate_round}\n"
                "辩论上下文：{revision_context}\n"
                "请生成专家 B 草稿。",
            ),
        ]
    )

    def expert_b_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
                debate_round=state.get("debate_round", 1),
                revision_context=state.get("expert_a_draft", {}),
            ),
            temperature=0.7,
            agent="expert_b",
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
        draft_dict = draft.model_dump()
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_b_draft": draft_dict,
            "events": [completed_event("expert_b", "generated expert B draft with LLM")],
        }

    return expert_b_node
