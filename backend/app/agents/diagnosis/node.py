"""Diagnosis Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.agents.common import Node, load_prompt, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.memory import load_profile_memories, save_learner_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import FeedbackResult, LearnerProfile, StateDict, completed_event

_DIAGNOSIS_PROMPT = load_prompt(__file__)
_FEEDBACK_PHASE_PROMPT = load_prompt(__file__, "feedback_phase.md")


def build_diagnosis_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "LearnerProfile",
                    '{"education_background":"patent_exam_candidate","knowledge_level":"beginner",'
                    '"learning_style":"case_first_then_rule","weak_points":["概念辨析"],'
                    '"learning_goal":"学习目标"}',
                )
                + _DIAGNOSIS_PROMPT,
            ),
            ("user", "当前学习需求：{user_input}\n历史学习者画像：{historical_profiles}\n请诊断该学习需求对应的学习者画像。"),
        ]
    )

    def diagnosis_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        memories = load_profile_memories(runtime)
        historical_profiles = (
            json.dumps(memories, ensure_ascii=False) if memories else "无"
        )
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                historical_profiles=historical_profiles,
            ),
            temperature=0.5,
            agent="diagnosis",
        )
        profile = LearnerProfile.model_validate(raw)
        return {
            "learner_profile": profile.model_dump(),
            "events": [completed_event("diagnosis", "generated learner profile with LLM")],
        }

    return diagnosis_node


def build_diagnosis_feedback_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "FeedbackResult",
                    '{"questionnaire":["问题"],"next_action":"下一步",'
                    '"profile_update_hint":"画像更新建议"}',
                )
                + _FEEDBACK_PHASE_PROMPT,
            ),
            (
                "user",
                "当前学习需求：{user_input}\n"
                "初始学习者画像：{learner_profile}\n"
                "裁判报告：{judge_report}\n"
                "请作为 feedback 阶段，生成本轮反馈闭环建议。",
            ),
        ]
    )

    def feedback_phase_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
                judge_report=state.get("judge_report", {}),
            ),
            temperature=0.5,
            agent="diagnosis",
        )
        feedback = FeedbackResult.model_validate(raw)
        feedback_dict = feedback.model_dump()
        save_learner_memories(runtime, state, feedback_dict)
        return {
            "feedback_result": feedback_dict,
            "events": [
                completed_event(
                    "feedback",
                    "diagnosis agent created feedback suggestion with LLM",
                )
            ],
        }

    return feedback_phase_node
