"""Expert A Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import ExpertDraft, FinalAnswer, StateDict, completed_event

_EXTRA_TEXT = load_prompt(__file__)


def _judge_accepted(state: StateDict) -> bool:
    decision = str(state.get("judge_report", {}).get("decision", ""))
    match decision:
        case "accept" | "accept_with_minor_revision":
            return True
        case _:
            return False


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
                + _EXTRA_TEXT,
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
        if _judge_accepted(state) and "feedback_result" in state:
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "FinalAnswer",
                            '{"title":"标题","content":"正文","sources":["依据"],'
                            '"judge_summary":"审核摘要","next_questions":["问题"]}',
                        )
                        + _EXTRA_TEXT
                        + "\n你现在执行专家 A 的最终审核职责：不得再做多专家整合，"
                        "只能基于已通过的专家草稿、judge_report 和反馈结果输出最终答案。",
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"用户问题：{state['user_input']}\n"
                            f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                            f"裁判报告：{json.dumps(state.get('judge_report', {}), ensure_ascii=False)}\n"
                            f"反馈结果：{json.dumps(state.get('feedback_result', {}), ensure_ascii=False)}\n"
                            "请以专家 A 的严谨口径做最终审核并输出 FinalAnswer。"
                        ),
                    ),
                ],
                temperature=0.3,
                agent="expert_a",
            )
            final_answer = FinalAnswer.model_validate(
                normalize_key_aliases(
                    raw,
                    {
                        "judgeSummary": "judge_summary",
                        "nextStudyQuestions": "next_questions",
                        "next_study_questions": "next_questions",
                        "follow_up_questions": "next_questions",
                    },
                )
            )
            return {
                "final_answer": final_answer.model_dump(),
                "events": [completed_event("expert_a", "final reviewed teaching answer with LLM")],
            }

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
