"""Workflow finalization node — merges expert drafts into a unified teaching answer."""

from __future__ import annotations

from typing import Any

from backend.app.agents.common import Node, LLMMessage, load_prompt, normalize_key_aliases
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import FinalAnswer, StateDict, completed_event

_FINALIZE_SYSTEM = load_prompt(__file__)


def build_finalize_node(llm_client: LLMClient) -> Node:
    def finalize_node(state: StateDict) -> dict[str, Any]:
        synthesis = state.get("joint_synthesis_output", {})
        judge_report = state.get("judge_report", {})
        feedback_result = state.get("feedback_result", {})

        import json as _json

        messages = [
            LLMMessage(role="system", content=_FINALIZE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"联合合成稿：\n{_json.dumps(synthesis, ensure_ascii=False, indent=2)}\n\n"
                    f"裁判报告：\n{_json.dumps(judge_report, ensure_ascii=False, indent=2)}\n\n"
                    f"反馈分析：\n{_json.dumps(feedback_result, ensure_ascii=False, indent=2)}\n\n"
                    "请格式化为最终答案。"
                ),
            ),
        ]

        raw = llm_client.generate_json(messages=messages, temperature=0.3, agent="finalize")
        # Normalize known LLM key variants before validation
        normalized = normalize_key_aliases(
            raw,
            {
                "nextStudyQuestions": "next_questions",
                "next_study_questions": "next_questions",
                "questions": "next_questions",
                "follow_up_questions": "next_questions",
                "judgeSummary": "judge_summary",
            },
        )
        validated = FinalAnswer.model_validate(normalized)

        return {
            "final_answer": validated.model_dump(),
            "events": [completed_event("finalize", "formatted final teaching answer from joint synthesis")],
        }

    return finalize_node
