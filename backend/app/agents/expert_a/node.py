"""Expert A Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.agents.rag_tools import collect_expert_retrieval_context
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import ExpertDraft, StateDict, completed_event

_DEBATE_SYSTEM_PROMPT = load_prompt(__file__, "debate_system.md")
_INTEGRATION_SYSTEM_PROMPT = load_prompt(__file__, "integration_system.md")


def _should_integrate(state: StateDict) -> bool:
    return state.get("teach_phase") == "integration"


def _normalize_expert_draft(raw: object) -> ExpertDraft:
    return ExpertDraft.model_validate(
        normalize_key_aliases(
            raw,
            {
                "knowledgePoints": "knowledge_points",
                "legalBasis": "legal_basis",
                "teachingContent": "teaching_content",
                "interactiveQuestions": "interactive_questions",
                "draftStage": "draft_stage",
            },
        )
    )


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
                + _DEBATE_SYSTEM_PROMPT,
            ),
            (
                "user",
                "问题：{user_input}\n"
                "检索上下文：{retrieval_context}\n"
                "当前辩论轮次：{debate_round}\n"
                "辩论上下文：{revision_context}\n"
                "请生成专家 A 草稿。",
            ),
        ]
    )

    def expert_a_node(state: StateDict) -> dict[str, Any]:
        if _should_integrate(state):
            tool_messages = [
                LLMMessage(
                    role="system",
                    content=_INTEGRATION_SYSTEM_PROMPT,
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"用户问题：{state['user_input']}\n"
                        f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                        f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                        "请判断整合前是否需要补充检索。"
                    ),
                ),
            ]
            retrieved_context = collect_expert_retrieval_context(
                llm_client,
                messages=tool_messages,
                temperature=agent_temperature("expert_a", 0.2, "tool_temperature"),
                agent="expert_a",
            )
            retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "ExpertDraft",
                            '{"expert":"expert_a","style":"conservative_precise",'
                            '"knowledge_points":["要点"],"legal_basis":["依据"],'
                            '"teaching_content":"整合后的教学正文","risks":[]}',
                        )
                        + _INTEGRATION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"用户问题：{state['user_input']}\n"
                            f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                            f"裁判报告：{json.dumps(state.get('judge_report', {}), ensure_ascii=False)}\n"
                            f"检索上下文：{json.dumps(retrieval_context, ensure_ascii=False)}\n"
                            "请整合两位专家的有效观点，输出可由 judge 直接审核的 ExpertDraft。"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.3, "integration_temperature"),
                agent="expert_a",
            )
            draft = _normalize_expert_draft(raw)
            draft_dict = draft.model_dump()
            draft_dict["draft_stage"] = "integration"
            return {
                "expert_a_draft": draft_dict,
                "teach_phase": "integration",
                **({"retrieval_context": retrieved_context} if retrieved_context else {}),
                "events": [completed_event("expert_a", "integrated expert debate result with LLM")],
            }

        prompt_messages = messages_from_prompt(
            prompt,
            user_input=state["user_input"],
            retrieval_context=state.get("retrieval_context", []),
            debate_round=state.get("debate_round", 1),
            revision_context=state.get("expert_b_draft", {}),
        )
        retrieved_context = collect_expert_retrieval_context(
            llm_client,
            messages=prompt_messages,
            temperature=agent_temperature("expert_a", 0.2, "tool_temperature"),
            agent="expert_a",
        )
        retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                retrieval_context=retrieval_context,
                debate_round=state.get("debate_round", 1),
                revision_context=state.get("expert_b_draft", {}),
            ),
            temperature=agent_temperature("expert_a", 0.4),
            agent="expert_a",
        )
        draft = _normalize_expert_draft(raw)
        draft_dict = draft.model_dump()
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_a_draft": draft_dict,
            **({"retrieval_context": retrieved_context} if retrieved_context else {}),
            "events": [completed_event("expert_a", "generated expert A draft with LLM")],
        }

    return expert_a_node
