"""Expert B Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import ExpertDraft, StateDict, completed_event


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
                + "你是生动灵活的教学专家 B，但必须回扣法条依据。",
            ),
            (
                "user",
                "问题：{user_input}\n学习者画像：{learner_profile}\n请生成专家 B 草稿。",
            ),
        ]
    )

    def expert_b_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=0.7,
            agent="expert_b",
        )
        draft = ExpertDraft.model_validate(raw)
        return {
            "expert_b_draft": draft.model_dump(),
            "events": [completed_event("expert_b", "generated expert B draft with LLM")],
        }

    return expert_b_node
