from __future__ import annotations

import logging
from copy import deepcopy
import json
from typing import Any, Literal, cast

from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.agents.common import (
    Node,
    generate_validated_json,
    load_prompt,
    messages_from_prompt,
    normalize_key_aliases,
    schema_note,
)
from backend.app.core.llm import LLMClient
from backend.app.learner_memory.memory import (
    load_mastery_snapshot,
    load_profile_memories,
    save_learner_memories,
    save_profile_snapshot,
)
from backend.app.learner_memory.bkt.model import profile_confidence_from_mastery
from backend.app.curriculum.learning_path import load_knowledge_dag
from backend.app.curriculum.learning_progress import deterministic_next_action
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import (
    BKTUpdate,
    DiagnosisAgentResult,
    FeedbackAgentResult,
    FeedbackResult,
    FiveDimensions,
    KnowledgeNodeState,
    LearnerProfile,
    LearningProgressDecision,
    NonKnowledgeDimensions,
    StateDict,
    completed_event,
)

_DIAGNOSIS_PROMPT = load_prompt(__file__, "diagnosis_system.md")
_FEEDBACK_PHASE_PROMPT = load_prompt(__file__, "feedback_system.md")
_LOGGER = logging.getLogger(__name__)

_NO_ERROR_PATTERN_ALIASES = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "no_error",
    "no-error",
    "no error",
    "not_applicable",
    "not applicable",
    "无",
    "无错误",
    "没有错误",
    "不适用",
}

_AFFECT_STATE_ALIASES = {
    "focused": "focused",
    "focus": "focused",
    "attentive": "focused",
    "calm": "focused",
    "concentrated": "focused",
    "专注": "focused",
    "平静": "focused",
    "confused": "confused",
    "puzzled": "confused",
    "uncertain": "confused",
    "unsure": "confused",
    "迷惑": "confused",
    "困惑": "confused",
    "anxious": "anxious",
    "nervous": "anxious",
    "worried": "anxious",
    "stressed": "anxious",
    "焦虑": "anxious",
    "紧张": "anxious",
    "担忧": "anxious",
    "interested": "interested",
    "curious": "interested",
    "engaged": "interested",
    "motivated": "interested",
    "enthusiastic": "interested",
    "好奇": "interested",
    "感兴趣": "interested",
    "积极": "interested",
}


def _kc_node_ids() -> list[str]:
    """Return every valid KC node id from the static knowledge graph."""
    try:
        nodes = load_knowledge_dag().get("nodes", [])
    except Exception:
        return []
    return [n["node_id"] for n in nodes if isinstance(n, dict) and n.get("node_id")]


def _knowledge_node_names() -> dict[str, str]:
    try:
        nodes = load_knowledge_dag().get("nodes", [])
    except Exception:
        return {}
    return {
        str(node["node_id"]): str(node.get("node_name") or node["node_id"])
        for node in nodes
        if isinstance(node, dict) and node.get("node_id")
    }


def _authoritative_knowledge(primary: object) -> dict[str, dict[str, Any]]:
    """Build a complete BKT snapshot without accepting any LLM-generated values."""

    default_state = {
        "pl": 0.15,
        "ci_low": 0.02,
        "ci_high": 0.40,
        "observations": 0,
        "low_confidence": True,
        "inferred": False,
    }
    completed = {node_id: dict(default_state) for node_id in _kc_node_ids()}
    for source in (primary,):
        if not isinstance(source, dict):
            continue
        for node_id, state in source.items():
            normalized_id = str(node_id)
            if normalized_id not in completed or not isinstance(state, dict):
                continue
            completed[normalized_id] = KnowledgeNodeState.model_validate(state).model_dump()
    return completed


def _derive_knowledge_level(
    knowledge: dict[str, dict[str, Any]],
) -> Literal["beginner", "intermediate", "advanced"]:
    evidence = [
        state
        for state in knowledge.values()
        if int(state.get("observations", 0)) > 0 or bool(state.get("inferred"))
    ]
    if not evidence:
        return "beginner"
    weighted_total = sum(
        float(state["pl"]) * max(1, int(state.get("observations", 0)))
        for state in evidence
    )
    total_weight = sum(max(1, int(state.get("observations", 0))) for state in evidence)
    mean_mastery = weighted_total / total_weight
    if mean_mastery < 0.40:
        return "beginner"
    if mean_mastery < 0.75:
        return "intermediate"
    return "advanced"


def _derive_weak_points(knowledge: dict[str, dict[str, Any]]) -> list[str]:
    names = _knowledge_node_names()
    return [
        names.get(node_id, node_id)
        for node_id, state in knowledge.items()
        if int(state.get("observations", 0)) > 0 and float(state["pl"]) < 0.40
    ]


def _parse_stringified_json(value: object) -> object:
    """Recursively parse stringified JSON objects inside dicts/lists.

    LLM sometimes returns nested objects as JSON strings, e.g.:
      {"perception": '{"chosen": "sensing", "strength": 0.62}'}
    """
    if isinstance(value, str):
        stripped = value.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (dict, list)):
                    return _parse_stringified_json(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        return value
    if isinstance(value, dict):
        return {k: _parse_stringified_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_parse_stringified_json(v) for v in value]
    return value


_STYLE_AXES = ("perception", "input", "processing", "understanding")


def _coerce_style_axis(value: object) -> dict[str, object]:
    """Convert LLM output to a StyleAxis-compatible dict.

    Handles: dict, JSON string, or plain string like 'sensing'.
    """
    if isinstance(value, dict):
        return _parse_stringified_json(value)  # type: ignore[return-value]
    if isinstance(value, str):
        parsed = _parse_stringified_json(value)
        if isinstance(parsed, dict) and "chosen" in parsed:
            return parsed
        return {"chosen": value.strip(), "strength": 0.5}
    return {"chosen": str(value), "strength": 0.5}


def _coerce_signals(value: object) -> list[str]:
    """Ensure affect.signals is a list of strings."""
    if isinstance(value, list):
        return [str(s) for s in value]
    if isinstance(value, str):
        return [value]
    return []


def _dimensions_without_knowledge(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    dimensions = _parse_stringified_json(dict(raw))
    dimensions.pop("knowledge", None)
    dimensions.pop("progress", None)

    # Fix style axes: LLM may return plain strings instead of {chosen, strength} dicts
    style = dimensions.get("style")
    if isinstance(style, dict):
        normalized_style = dict(style)
        for axis in _STYLE_AXES:
            if axis in normalized_style:
                normalized_style[axis] = _coerce_style_axis(normalized_style[axis])
        dimensions["style"] = normalized_style

    # Fix affect: LLM may return signals as a string instead of a list
    affect = dimensions.get("affect")
    if isinstance(affect, dict):
        normalized_affect = dict(affect)
        primary_state = normalized_affect.get("primary_state")
        if isinstance(primary_state, str):
            alias_key = primary_state.strip().casefold().replace("-", "_").replace(" ", "_")
            normalized_affect["primary_state"] = _AFFECT_STATE_ALIASES.get(
                alias_key,
                primary_state,
            )
        signals = normalized_affect.get("signals")
        if signals is not None and not isinstance(signals, list):
            normalized_affect["signals"] = _coerce_signals(signals)
        dimensions["affect"] = normalized_affect

    return dimensions


def _normalize_diagnosis_agent_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "learningStyle": "learning_style",
            "errorPattern": "error_pattern",
            "fiveDimensions": "five_dimensions",
            "learnerDimensions": "learner_dimensions",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    dimensions = normalized.get("learner_dimensions", normalized.get("five_dimensions"))
    return {
        "learning_style": normalized.get("learning_style") or "未识别",
        "error_pattern": normalized.get("error_pattern"),
        "confidence": normalized.get("confidence"),
        "learner_dimensions": _dimensions_without_knowledge(dimensions),
    }


def _normalize_error_pattern(value: object) -> object:
    if isinstance(value, str) and value.strip().casefold() in _NO_ERROR_PATTERN_ALIASES:
        return None
    return value


def _normalize_feedback_agent_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "teachingEvaluation": "teaching_evaluation",
            "nextAction": "next_action",
            "profileUpdateHint": "profile_update_hint",
            "fiveDimensions": "five_dimensions",
            "learnerDimensions": "learner_dimensions",
            "errorPattern": "error_pattern",
            "bktUpdate": "bkt_update",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    bkt_update = normalize_key_aliases(
        normalized.get("bkt_update"),
        {"errorPattern": "error_pattern"},
    )
    error_pattern = normalized.get("error_pattern")
    if error_pattern is None and isinstance(bkt_update, dict):
        error_pattern = bkt_update.get("error_pattern")
    dimensions = normalized.get("learner_dimensions", normalized.get("five_dimensions"))
    return {
        "questionnaire": normalized.get("questionnaire"),
        "teaching_evaluation": normalized.get("teaching_evaluation"),
        "next_action": normalized.get("next_action"),
        "profile_update_hint": normalized.get("profile_update_hint"),
        "error_pattern": _normalize_error_pattern(error_pattern),
        "confidence": normalized.get("confidence"),
        "learner_dimensions": _dimensions_without_knowledge(dimensions),
    }


def _build_five_dimensions(
    agent_dimensions: object,
    knowledge: dict[str, dict[str, Any]],
    *,
    base_dimensions: object = None,
    progress_override: object = None,
) -> FiveDimensions:
    agent_values: dict[str, Any] = (
        agent_dimensions.model_dump()
        if isinstance(agent_dimensions, NonKnowledgeDimensions)
        else dict(agent_dimensions)
        if isinstance(agent_dimensions, dict)
        else {}
    )
    dimensions: dict[str, Any] = {
        "cognition": {
            "remember": 0.0,
            "understand": 0.0,
            "apply": 0.0,
            "analyze": 0.0,
            "evaluate": 0.0,
            "create": 0.0,
            "method": "insufficient_evidence",
        },
        "style": {
            "perception": {"chosen": "unknown", "strength": 0.0},
            "input": {"chosen": "unknown", "strength": 0.0},
            "processing": {"chosen": "unknown", "strength": 0.0},
            "understanding": {"chosen": "unknown", "strength": 0.0},
        },
        "progress": {
            "completed_nodes": [],
            "current_node": None,
            "pending_nodes": [],
            "avg_time_per_node_min": None,
            "overall_completion_ratio": 0.0,
        },
        "affect": {
            "primary_state": "focused",
            "confidence": 0.0,
            "signals": ["insufficient_evidence"],
        },
    }
    if isinstance(base_dimensions, dict):
        for key in {"cognition", "style", "progress", "affect"}:
            if key in base_dimensions:
                dimensions[key] = base_dimensions[key]
    for key in {"cognition", "style", "affect"}:
        if key in agent_values:
            dimensions[key] = agent_values[key]
    if isinstance(progress_override, dict):
        dimensions["progress"] = progress_override
    return FiveDimensions.model_validate({"knowledge": knowledge, **dimensions})


def build_diagnosis_phase_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "DiagnosisAgentResult",
                    '{"learning_style":"sensing/sequential","error_pattern":"concept_confusion",'
                    '"confidence":0.5,"learner_dimensions":{'
                    '"cognition":{"remember":0.8,"understand":0.6,"apply":0.3,"analyze":0.2,"evaluate":0.1,"create":0.05},'
                    '"style":{"perception":{"chosen":"sensing","strength":0.7},"input":{"chosen":"visual","strength":0.6},"processing":{"chosen":"active","strength":0.55},"understanding":{"chosen":"sequential","strength":0.65}},'
                    '"affect":{"primary_state":"confused","confidence":0.5,"signals":["同节点停留超均值2倍"]}}}',
                )
                + _DIAGNOSIS_PROMPT,
            ),
            (
                "user",
                "当前学习需求：{user_input}\n"
                "新学员问卷题目、选项和回答：{questionnaire_context}\n"
                "CAT/BKT 确定性知识快照（knowledge 权威来源，不得改写）："
                "{diagnostic_snapshot}\n"
                "CAT 答题日志（用于解释认知、进度和情感信号）：{diagnostic_answer_log}\n"
                "历史学习者画像：{historical_profiles}\n"
                "请综合问卷、答题行为和历史数据诊断非知识维度。"
                "禁止输出 knowledge、P(L)、掌握度、knowledge_level 或 weak_points；"
                "这些字段全部由后端根据 CAT/BKT 结果计算。",
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
        diagnostic_snapshot = input_payload.get("diagnostic_snapshot") or {}
        agent_result = generate_validated_json(
            llm_client,
            messages=messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                questionnaire_context=json.dumps(questionnaire_context, ensure_ascii=False),
                diagnostic_snapshot=json.dumps(diagnostic_snapshot, ensure_ascii=False),
                diagnostic_answer_log=json.dumps(
                    diagnostic_snapshot.get("answer_log", [])
                    if isinstance(diagnostic_snapshot, dict)
                    else [],
                    ensure_ascii=False,
                ),
                historical_profiles=historical_profiles,
            ),
            temperature=agent_temperature("diagnosis_feedback", 0.5),
            agent="diagnosis_feedback",
            output_model=DiagnosisAgentResult,
            normalize=_normalize_diagnosis_agent_payload,
            schema_name="DiagnosisAgentResult",
        )
        previous_profile = dict(memories[0]) if memories else {}
        diagnostic_knowledge = (
            diagnostic_snapshot.get("knowledge", {})
            if isinstance(diagnostic_snapshot, dict)
            else {}
        )
        persisted_mastery = load_mastery_snapshot(runtime)
        knowledge = _authoritative_knowledge(
            diagnostic_knowledge if diagnostic_knowledge else persisted_mastery
        )
        education_background = (
            diagnostic_snapshot.get("education_background")
            if isinstance(diagnostic_snapshot, dict)
            else None
        ) or input_payload.get("education_background") or previous_profile.get(
            "education_background"
        ) or "未提供"
        weak_points = _derive_weak_points(knowledge)
        # 显式告警：有作答观测却算不出薄弱点，说明掌握度快照被推高（例如问卷播种
        # 写入虚高 pl），弱项推导已静默失效——不再无提示地退化成"无重点"教学。
        observed_nodes = [
            node_id
            for node_id, state in knowledge.items()
            if isinstance(state, dict) and int(state.get("observations", 0)) > 0
        ]
        if not weak_points and observed_nodes:
            _LOGGER.warning(
                "diagnosis_feedback: weak_points 为空但存在 %d 个有作答观测的节点 "
                "(pl 可能被播种虚高): %s",
                len(observed_nodes),
                observed_nodes[:10],
            )
        profile = LearnerProfile(
            education_background=str(education_background),
            knowledge_level=_derive_knowledge_level(knowledge),
            learning_style=agent_result.learning_style,
            weak_points=weak_points,
            learning_goal=state["user_input"],
            error_pattern=agent_result.error_pattern,
            confidence=profile_confidence_from_mastery(knowledge),
            five_dimensions=_build_five_dimensions(
                agent_result.learner_dimensions,
                knowledge,
                base_dimensions=previous_profile.get("five_dimensions"),
            ),
        )
        save_profile_snapshot(runtime, state, profile.model_dump())
        return {
            "learner_profile": profile.model_dump(),
            "events": [
                completed_event(
                    "diagnosis_feedback",
                    "assembled learner profile from backend BKT and LLM non-knowledge dimensions",
                )
            ],
        }

    return diagnosis_node


def build_feedback_phase_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "FeedbackAgentResult",
                    '{"questionnaire":["请复述创造性三步法判断顺序"],"next_action":"插入新颖性案例强化模块",'
                    '"profile_update_hint":"已按后端计算结果更新创造性知识状态并触发重规划",'
                    '"error_pattern":"application_gap","confidence":0.7,"learner_dimensions":{'
                    '"cognition":{"remember":0.85,"understand":0.7,"apply":0.5,"analyze":0.4,"evaluate":0.3,"create":0.2},'
                    '"style":{"perception":{"chosen":"sensing","strength":0.7},"input":{"chosen":"visual","strength":0.6},"processing":{"chosen":"active","strength":0.55},"understanding":{"chosen":"sequential","strength":0.65}},'
                    '"affect":{"primary_state":"interested","confidence":0.6,"signals":["主动提问"]}}}',
                )
                + _FEEDBACK_PHASE_PROMPT,
            ),
            (
                "user",
                "当前学习需求：{user_input}\n"
                "初始学习者画像：{learner_profile}\n"
                "裁判报告：{judge_report}\n"
                "本轮练习作答与服务端判分：{exercise_responses}\n"
                "后端 BKT 状态转移：{bkt_updates}\n"
                "后端权威掌握度快照：{mastery_snapshot}\n"
                "请生成反馈建议和四个非知识维度。禁止输出 knowledge、P(L) 或掌握度；"
                "后端将直接使用上述 BKT 快照更新画像。",
            ),
        ]
    )

    def feedback_phase_node(
        state: StateDict, runtime: Runtime[WorkflowContext] | None = None
    ) -> dict[str, Any]:
        memories = load_profile_memories(runtime, limit=1)
        current_profile = deepcopy(
            dict(memories[0] if memories else state.get("learner_profile", {}))
        )
        input_payload = state.get("input_payload", {})
        responses = input_payload.get("exercise_responses", [])
        bkt_updates = input_payload.get("bkt_updates", [])
        mastery_snapshot = input_payload.get("mastery_snapshot", {})
        progress_update = input_payload.get("learning_progress_update", {})
        progress_decision = input_payload.get("learning_progress_decision", {})
        agent_result = generate_validated_json(
            llm_client,
            messages=messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=current_profile,
                judge_report=state.get("judge_report", {}),
                exercise_responses=json.dumps(responses, ensure_ascii=False),
                bkt_updates=json.dumps(bkt_updates, ensure_ascii=False),
                mastery_snapshot=json.dumps(mastery_snapshot, ensure_ascii=False),
            ),
            temperature=agent_temperature("diagnosis_feedback", 0.5),
            agent="diagnosis_feedback",
            output_model=FeedbackAgentResult,
            normalize=_normalize_feedback_agent_payload,
            schema_name="FeedbackAgentResult",
        )
        persisted_mastery = load_mastery_snapshot(runtime)
        knowledge = _authoritative_knowledge(
            mastery_snapshot if isinstance(mastery_snapshot, dict) and mastery_snapshot else persisted_mastery
        )
        five_dimensions = _build_five_dimensions(
            agent_result.learner_dimensions,
            knowledge,
            base_dimensions=current_profile.get("five_dimensions"),
            progress_override=progress_update,
        )
        first_update = (
            bkt_updates[0]
            if isinstance(bkt_updates, list) and bkt_updates and isinstance(bkt_updates[0], dict)
            else {}
        )
        bkt_update = BKTUpdate(
            skill_id=str(first_update["skill_id"]) if first_update.get("skill_id") else None,
            observed_correct=(
                bool(first_update["observed_correct"])
                if isinstance(first_update.get("observed_correct"), bool)
                else None
            ),
            error_pattern=agent_result.error_pattern,
            confidence=agent_result.confidence,
        )
        feedback = FeedbackResult(
            questionnaire=agent_result.questionnaire,
            teaching_evaluation=agent_result.teaching_evaluation,
            next_action=deterministic_next_action(
                progress_decision if isinstance(progress_decision, dict) else {}
            ),
            profile_update_hint=agent_result.profile_update_hint,
            five_dimensions=five_dimensions,
            bkt_update=bkt_update,
            learning_progress=(
                LearningProgressDecision.model_validate(progress_decision)
                if isinstance(progress_decision, dict) and progress_decision
                else None
            ),
        )
        feedback_dict = feedback.model_dump()
        updated_profile = LearnerProfile(
            education_background=str(current_profile.get("education_background") or "未提供"),
            knowledge_level=_derive_knowledge_level(knowledge),
            learning_style=str(current_profile.get("learning_style") or "未识别"),
            weak_points=_derive_weak_points(knowledge),
            learning_goal=str(current_profile.get("learning_goal") or state["user_input"]),
            error_pattern=agent_result.error_pattern,
            confidence=profile_confidence_from_mastery(knowledge),
            five_dimensions=five_dimensions,
        ).model_dump()
        updated_profile["profile_update_hint"] = feedback.profile_update_hint
        memory_state = dict(state)
        memory_state["learner_profile"] = updated_profile
        save_learner_memories(runtime, cast(StateDict, memory_state), feedback_dict)
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
                    "updated profile from backend BKT and LLM non-knowledge feedback",
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
