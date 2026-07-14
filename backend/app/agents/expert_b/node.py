"""Expert B Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import (
    Node,
    load_prompt,
    messages_from_prompt,
    normalize_expert_draft_payload,
    schema_note,
)
from backend.app.agents.rag_tools import collect_expert_retrieval_context
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import CrossReview, ExpertDraft, StateDict, completed_event

_DRAFT_SYSTEM_PROMPT = load_prompt(__file__, "draft_system.md")
_CROSS_REVIEW_SYSTEM_PROMPT = load_prompt(__file__, "cross_review_system.md")
_REVISION_SYSTEM_PROMPT = load_prompt(__file__, "revision_system.md")


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
                + _DRAFT_SYSTEM_PROMPT,
            ),
            (
                "user",
                "问题：{user_input}\n"
                "学习者画像：{learner_profile}\n"
                "检索上下文：{retrieval_context}\n"
                "辩论上下文：{revision_context}\n"
                "请生成专家 B 草稿。",
            ),
        ]
    )

    def expert_b_node(state: StateDict) -> dict[str, Any]:
        phase = state.get("expert_phase", "draft")
        if phase == "cross_review":
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "CrossReview",
                            '{"reviewer":"expert_b","target":"expert_a",'
                            '"review_opinions":[{"category":"🟡","location":"正文",'
                            '"target_wrote":"原文","problem":"问题","suggestion":"建议"}],'
                            '"overall_assessment":"总体评价"}',
                        )
                        + _CROSS_REVIEW_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=str(state.get("expert_a_draft", {})),
                    ),
                ],
                temperature=agent_temperature("expert_b", 0.3),
                agent="expert_b",
            )
            review = CrossReview.model_validate(raw)
            return {
                "expert_b_cross_review": review.model_dump(),
                "expert_phase": "revision",
                "events": [completed_event("expert_b", "reviewed expert A draft")],
            }
        if phase == "revision":
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "ExpertDraft",
                            '{"expert":"expert_b","style":"vivid_teaching",'
                            '"knowledge_points":["要点"],"legal_basis":["依据"],'
                            '"teaching_content":"修订正文","risks":[]}',
                        )
                        + _REVISION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"原草稿：{state.get('expert_b_draft', {})}\n"
                            f"专家A互评：{state.get('expert_a_cross_review', {})}"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_b", 0.4),
                agent="expert_b",
            )
            draft = ExpertDraft.model_validate(normalize_expert_draft_payload(raw))
            revised = draft.model_dump()
            revised["draft_stage"] = "debate"
            return {
                "expert_b_draft": revised,
                "expert_b_revision": revised,
                "expert_phase": "integration",
                "teach_phase": "integration",
                "events": [completed_event("expert_b", "revised expert B draft")],
            }
        prompt_messages = messages_from_prompt(
            prompt,
            user_input=state["user_input"],
            learner_profile=state.get("learner_profile", {}),
            retrieval_context=state.get("retrieval_context", []),
            revision_context=state.get("expert_a_draft", {}),
        )
        retrieved_context = collect_expert_retrieval_context(
            llm_client,
            messages=prompt_messages,
            temperature=agent_temperature("expert_b", 0.3, "tool_temperature"),
            agent="expert_b",
        )
        retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
                retrieval_context=retrieval_context,
                revision_context=state.get("expert_a_draft", {}),
            ),
            temperature=agent_temperature("expert_b", 0.7),
            agent="expert_b",
        )
        draft = ExpertDraft.model_validate(normalize_expert_draft_payload(raw))
        draft_dict = draft.model_dump()
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_b_draft": draft_dict,
            "expert_phase": "cross_review",
            **({"retrieval_context": retrieved_context} if retrieved_context else {}),
            "events": [completed_event("expert_b", "generated expert B draft with LLM")],
        }

    return expert_b_node
