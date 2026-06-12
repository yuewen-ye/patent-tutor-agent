"""Workflow finalization node."""

from __future__ import annotations

from typing import Any

from backend.app.schemas.state import FinalAnswer, StateDict, completed_event


def finalize_node(state: StateDict) -> dict[str, Any]:
    expert_a = state.get("expert_a_draft", {})
    expert_b = state.get("expert_b_draft", {})
    judge_report = state.get("judge_report", {})
    feedback_result = state.get("feedback_result", {})
    final = FinalAnswer(
        title="个性化知识产权学习建议",
        content="\n\n".join(
            part
            for part in [
                str(expert_a.get("teaching_content", "")),
                str(expert_b.get("teaching_content", "")),
            ]
            if part
        ),
        sources=[chunk["citation"] for chunk in state.get("retrieval_context", [])],
        judge_summary=str(judge_report.get("rationale", "")) or None,
        next_questions=feedback_result.get("questionnaire"),
    )
    return {
        "final_answer": final.model_dump(),
        "events": [completed_event("finalize", "assembled final teaching answer")],
    }
