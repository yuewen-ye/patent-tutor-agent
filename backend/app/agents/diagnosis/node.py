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
    """Return every valid KC node id from the static knowledge graph."""
    try:
        nodes = load_knowledge_dag().get("nodes", [])
    except Exception:
        return []
    return [n["node_id"] for n in nodes if isinstance(n, dict) and n.get("node_id")]


def _kc_node_name_aliases() -> dict[str, str]:
    try:
        nodes = load_knowledge_dag().get("nodes", [])
    except Exception:
        return {}
    return {
        str(node["node_name"]): str(node["node_id"])
        for node in nodes
        if isinstance(node, dict) and node.get("node_id") and node.get("node_name")
    }


def _complete_knowledge_snapshot(
    payload: object,
    *,
    base_knowledge: object = None,
) -> object:
    """Fill omitted KC states deterministically while preserving observed model estimates."""

    if not isinstance(payload, dict):
        return payload
    five_dimensions = payload.get("five_dimensions")
    if not isinstance(five_dimensions, dict):
        return payload

    node_ids = _kc_node_ids()
    valid_ids = set(node_ids)
    name_aliases = _kc_node_name_aliases()
    default_state = {
        "pl": 0.15,
        "ci_low": 0.02,
        "ci_high": 0.40,
        "observations": 0,
        "low_confidence": True,
    }
    completed = {node_id: dict(default_state) for node_id in node_ids}
    for source in (base_knowledge, five_dimensions.get("knowledge")):
        if not isinstance(source, dict):
            continue
        for raw_node_id, state in source.items():
            node_id = str(raw_node_id)
            normalized_id = node_id if node_id in valid_ids else name_aliases.get(node_id)
            if normalized_id is not None and isinstance(state, dict):
                completed[normalized_id] = state
    five_dimensions["knowledge"] = completed
    return payload


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
    return _complete_knowledge_snapshot(normalized)


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
                "新学员问卷题目、选项和回答：{questionnaire_context}\n"
                "历史学习者画像：{historical_profiles}\n"
                "知识图合法 KC 节点 id（knowledge 只输出有问卷或历史证据的节点；"
                "其余节点由后端按 P(L₀)=0.15 的冷启动先验补齐）：\n"
                "{kc_node_ids}\n\n"
                "请综合问卷与历史数据诊断学习者画像。须含完整 five_dimensions，"
                "但 knowledge 不要重复输出没有观测证据的节点。",
            ),
        ]
    )

    def diagnosis_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        memories = load_profile_memories(runtime)
        historical_profiles = json.dumps(memories, ensure_ascii=False) if memories else "无"
        input_payload = state.get("input_payload", {})
        questionnaire_context = input_payload.get("questionnaire_context") or input_payload.get(
            "questionnaire_responses", []
        )
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                questionnaire_context=json.dumps(questionnaire_context, ensure_ascii=False),
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
                "知识图合法 KC 节点 id（knowledge 只输出本轮有证据发生变化的节点；"
                "其余节点由后端沿用既有 P(L)）：\n"
                "{kc_node_ids}\n\n"
                "请作为 feedback 阶段生成本轮反馈闭环建议。须含 five_dimensions 的五个维度，"
                "knowledge 不要重复输出未变化节点。",
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
        base_knowledge = (
            current_profile.get("five_dimensions", {}).get("knowledge", {})
            if isinstance(current_profile.get("five_dimensions"), dict)
            else {}
        )
        feedback = FeedbackResult.model_validate(
            _complete_knowledge_snapshot(raw, base_knowledge=base_knowledge)
        )
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
