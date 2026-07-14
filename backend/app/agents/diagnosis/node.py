"""Diagnosis Agent node."""

from __future__ import annotations

import json
from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.memory import load_profile_memories, save_learner_memories, save_profile_snapshot
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import FeedbackResult, LearnerProfile, StateDict, completed_event

_DIAGNOSIS_PROMPT = load_prompt(__file__, "diagnosis_system.md")
_FEEDBACK_PHASE_PROMPT = load_prompt(__file__, "feedback_system.md")


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
            temperature=agent_temperature("learner_state", 0.5),
            agent="learner_state",
        )
        profile = LearnerProfile.model_validate(raw)
        save_profile_snapshot(runtime, state, profile.model_dump())
        return {
            "learner_profile": profile.model_dump(),
            "events": [completed_event("learner_state", "generated learner profile with LLM")],
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
        memories = load_profile_memories(runtime, limit=1)
        current_profile = dict(memories[0] if memories else state.get("learner_profile", {}))
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=current_profile,
                judge_report=state.get("judge_report", {}),
            ),
            temperature=agent_temperature("learner_state", 0.5),
            agent="learner_state",
        )
        feedback = FeedbackResult.model_validate(raw)
        feedback_dict = feedback.model_dump()
        updated_profile = current_profile
        updated_profile["profile_update_hint"] = feedback.profile_update_hint
        memory_state = dict(state)
        memory_state["learner_profile"] = updated_profile
        save_learner_memories(runtime, cast(StateDict, memory_state), feedback_dict)
        input_payload = state.get("input_payload", {})
        responses = input_payload.get("exercise_responses", [])
        grading_report = [
            {
                "question_id": response.get("question_id"),
                "observed_correct": response.get("observed_correct"),
                "result": (
                    "correct" if response.get("observed_correct") is True else
                    "incorrect" if response.get("observed_correct") is False else "ungraded"
                ),
            }
            for response in responses
            if isinstance(response, dict)
        ]
        return {
            "feedback_result": feedback_dict,
            "learner_profile_update": updated_profile,
            "grading_report": grading_report,
            "workflow_status": "completed",
            "events": [
                completed_event(
                    "learner_state",
                    "diagnosis agent created feedback suggestion with LLM",
                )
            ],
        }

    return feedback_phase_node


def build_learner_state_node(llm_client: LLMClient) -> Node:
    diagnosis = build_diagnosis_node(llm_client)
    feedback = build_diagnosis_feedback_node(llm_client)

    def learner_state_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        if state.get("learner_state_phase") == "feedback":
            return feedback(state, runtime)
        updates = diagnosis(state, runtime)
        if state.get("intent") == "diagnose":
            updates["workflow_status"] = "completed"
        return updates

    return learner_state_node
