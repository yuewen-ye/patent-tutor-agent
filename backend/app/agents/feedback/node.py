"""Feedback Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.memory import save_learner_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import FeedbackResult, StateDict, completed_event


def build_feedback_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "FeedbackResult",
                    '{"questionnaire":["问题"],"next_action":"下一步",'
                    '"profile_update_hint":"画像更新建议"}',
                ),
            ),
            (
                "user",
                "最终教学主题：{user_input}\n裁判报告：{judge_report}\n请生成反馈闭环建议。",
            ),
        ]
    )

    def feedback_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                judge_report=state.get("judge_report", {}),
            ),
            temperature=0.5,
            agent="feedback",
        )
        feedback = FeedbackResult.model_validate(raw)
        feedback_dict = feedback.model_dump()
        save_learner_memories(runtime, state, feedback_dict)
        return {
            "feedback_result": feedback_dict,
            "events": [completed_event("feedback", "created feedback suggestion with LLM")],
        }

    return feedback_node
