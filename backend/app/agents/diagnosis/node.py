"""Diagnosis Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.agents.common import Node, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.memory import load_profile_memories
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import LearnerProfile, StateDict, completed_event


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
                ),
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
