from __future__ import annotations

import json
from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.agents.common import (
    Node,
    load_prompt,
    messages_from_prompt,
    normalize_key_aliases,
    schema_note,
)
from backend.app.core.llm import LLMClient
from backend.app.learner_memory.memory import load_profile_memories, save_learner_memories, save_profile_snapshot
from backend.app.curriculum.learning_path import load_knowledge_dag
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import FeedbackResult, LearnerProfile, StateDict, completed_event

_DIAGNOSIS_PROMPT = load_prompt(__file__, "diagnosis_system.md")
_FEEDBACK_PHASE_PROMPT = load_prompt(__file__, "feedback_system.md")

_KNOWLEDGE_LEVEL_ALIASES = {
    "unknown": "beginner",
    "none": "beginner",
    "novice": "beginner",
    "basic": "beginner",
    "零基础": "beginner",
    "初级": "beginner",
    "middle": "intermediate",
    "中级": "intermediate",
    "expert": "advanced",
    "high": "advanced",
    "高级": "advanced",
}


def _kc_node_ids() -> list[str]:
    """知识图全部 KC 节点 id（供诊断 Agent 在 knowledge 维度逐一输出 P(L) 锚点）。"""
    try:
        nodes = load_knowledge_dag().get("nodes", [])
    except Exception:
        return []
    return [n["node_id"] for n in nodes if isinstance(n, dict) and n.get("node_id")]


def _normalize_learner_profile_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "educationBackground": "education_background",
            "knowledgeLevel": "knowledge_level",
            "learningStyle": "learning_style",
            "weakPoints": "weak_points",
            "learningGoal": "learning_goal",
            "errorPattern": "error_pattern",
            "fiveDimensions": "five_dimensions",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    level = str(normalized.get("knowledge_level", "")).strip().lower()
    if level in _KNOWLEDGE_LEVEL_ALIASES:
        normalized["knowledge_level"] = _KNOWLEDGE_LEVEL_ALIASES[level]
    weak_points = normalized.get("weak_points")
    if isinstance(weak_points, str):
        normalized["weak_points"] = [weak_points] if weak_points else []
    return normalized


def build_diagnosis_phase_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "LearnerProfile",
                    '{"education_background":"理工背景，有研发经验","knowledge_level":"beginner",'
                    '"learning_style":"sensing/sequential","weak_points":["创造性三步法"],'
                    '"learning_goal":"掌握新颖性与创造性判断流程","error_pattern":"concept_confusion","confidence":0.5,'
                    '"five_dimensions":{"knowledge":{"novelty":{"pl":0.22,"ci_low":0.10,"ci_high":0.40,"observations":3,"low_confidence":true}},'
                    '"cognition":{"remember":0.8,"understand":0.6,"apply":0.3,"analyze":0.2,"evaluate":0.1,"create":0.05},'
                    '"style":{"perception":{"chosen":"sensing","strength":0.7},"input":{"chosen":"visual","strength":0.6},"processing":{"chosen":"active","strength":0.55},"understanding":{"chosen":"sequential","strength":0.65}},'
                    '"progress":{"completed_nodes":["patent-law-basic"],"current_node":"novelty-basic","pending_nodes":["inventiveness"],"avg_time_per_node_min":25,"overall_completion_ratio":0.15},'
                    '"affect":{"primary_state":"confused","confidence":0.5,"signals":["同节点停留超均值2倍"]}}}',
                )
                + _DIAGNOSIS_PROMPT,
            ),
            (
                "user",
                "当前学习需求：{user_input}\n"
                "新学员问卷回答：{questionnaire_responses}\n"
                "历史学习者画像：{historical_profiles}\n"
                "知识图全部 KC 节点（你须在 knowledge 维度**逐一**输出每个节点的 P(L) 估计；"
                "未作答节点统一用 P(L₀)=0.15、置信区间 [0.02, 0.40]、observations=0、low_confidence=true）：\n"
                "{kc_node_ids}\n\n"
                "请综合问卷、历史数据与上述 KC 节点，诊断学习者画像（须含完整 five_dimensions）。",
            ),
        ]
    )

    def diagnosis_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        memories = load_profile_memories(runtime)
        historical_profiles = json.dumps(memories, ensure_ascii=False) if memories else "无"
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                questionnaire_responses=json.dumps(
                    state.get("input_payload", {}).get("questionnaire_responses", []),
                    ensure_ascii=False,
                ),
                historical_profiles=historical_profiles,
                kc_node_ids="\n".join(f"- {n}" for n in _kc_node_ids()) or "（知识图未加载）",
            ),
            temperature=agent_temperature("diagnosis_feedback", 0.5),
            agent="diagnosis_feedback",
        )
        profile = LearnerProfile.model_validate(_normalize_learner_profile_payload(raw))
        save_profile_snapshot(runtime, state, profile.model_dump())
        return {
            "learner_profile": profile.model_dump(),
            "events": [completed_event("diagnosis_feedback", "generated learner profile with LLM")],
        }

    return diagnosis_node


def build_feedback_phase_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "FeedbackResult",
                    '{"questionnaire":["请复述创造性三步法判断顺序"],"next_action":"插入新颖性案例强化模块",'
                    '"profile_update_hint":"knowledge.创造性:0.12→0.35（Δ+0.23，触发重规划）",'
                    '"five_dimensions":{"knowledge":{"inventiveness":{"pl":0.35,"ci_low":0.18,"ci_high":0.52,"observations":6,"low_confidence":false}},'
                    '"cognition":{"remember":0.85,"understand":0.7,"apply":0.5,"analyze":0.4,"evaluate":0.3,"create":0.2},'
                    '"style":{"perception":{"chosen":"sensing","strength":0.7},"input":{"chosen":"visual","strength":0.6},"processing":{"chosen":"active","strength":0.55},"understanding":{"chosen":"sequential","strength":0.65}},'
                    '"progress":{"completed_nodes":["patent-law-basic","novelty-basic"],"current_node":"novelty-3step","pending_nodes":["inventiveness"],"avg_time_per_node_min":22,"overall_completion_ratio":0.4},'
                    '"affect":{"primary_state":"interested","confidence":0.6,"signals":["主动提问"]}}}',
                )
                + _FEEDBACK_PHASE_PROMPT,
            ),
            (
                "user",
                "当前学习需求：{user_input}\n"
                "初始学习者画像：{learner_profile}\n"
                "裁判报告：{judge_report}\n"
                "知识图全部 KC 节点（回传 five_dimensions 时，knowledge 维度须**逐一**覆盖以下每个节点；"
                "本轮未变化的节点沿用既有 P(L)，变化的节点更新）：\n"
                "{kc_node_ids}\n\n"
                "请作为 feedback 阶段，生成本轮反馈闭环建议（含完整 five_dimensions 快照）。",
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
                kc_node_ids="\n".join(f"- {n}" for n in _kc_node_ids()) or "（知识图未加载）",
            ),
            temperature=agent_temperature("diagnosis_feedback", 0.5),
            agent="diagnosis_feedback",
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
                    "correct"
                    if response.get("observed_correct") is True
                    else "incorrect"
                    if response.get("observed_correct") is False
                    else "ungraded"
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
                    "diagnosis_feedback",
                    "generated feedback suggestion with LLM",
                )
            ],
        }

    return feedback_phase_node


def build_diagnosis_feedback_node(llm_client: LLMClient) -> Node:
    diagnosis = build_diagnosis_phase_node(llm_client)
    feedback = build_feedback_phase_node(llm_client)

    def diagnosis_feedback_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        if state.get("diagnosis_feedback_phase") == "feedback":
            return feedback(state, runtime)
        updates = diagnosis(state, runtime)
        if state.get("intent") == "diagnose":
            updates["workflow_status"] = "completed"
        return updates

    return diagnosis_feedback_node
