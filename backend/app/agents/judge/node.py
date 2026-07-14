"""Judge Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agent_runtime_config import agent_temperature
from backend.app.agents.common import Node, load_prompt, messages_from_prompt, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import JudgeReport, StateDict, completed_event

_DECISION_NORMALIZATION = {
    "accept": "accept",
    "accept_with_minor_revision": "accept_with_minor_revision",
    "minor_revision": "accept_with_minor_revision",
    "accept_with_major_revision": "revise",
    "major_revision": "revise",
    "revise": "revise",
    "reject": "revise",
}

_VALID_TARGETS = {"expert_a", "expert_b", "both"}

_EXTRA_TEXT = load_prompt(__file__)


def _normalize_target(raw_target: object) -> str:
    """将 LLM 可能输出的中文描述规范化为 expert_a / expert_b / both."""
    text = str(raw_target).strip() if raw_target else ""
    if text in _VALID_TARGETS:
        return text
    has_a = any(kw in text for kw in ("expert_a", "expert a", "专家A", "专家 A", "保守", "严谨"))
    has_b = any(kw in text for kw in ("expert_b", "expert b", "专家B", "专家 B", "生动", "灵活"))
    if has_a and not has_b:
        return "expert_a"
    if has_b and not has_a:
        return "expert_b"
    return "both"


def _normalize_judge_report(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    decision = str(normalized.get("decision", "")).strip().lower()
    if decision in _DECISION_NORMALIZATION:
        normalized["decision"] = _DECISION_NORMALIZATION[decision]
    # 规范化 revision_requests 中每个 target 字段
    raw_requests = normalized.get("revision_requests")
    if isinstance(raw_requests, list):
        normalized_requests: list[dict[str, object]] = []
        for req in raw_requests:
            if isinstance(req, dict):
                nr = dict(req)
                nr["target"] = _normalize_target(nr.get("target"))
                normalized_requests.append(nr)
        normalized["revision_requests"] = normalized_requests
    if normalized.get("decision") == "revise" and not normalized.get("revision_requests"):
        disputes = normalized.get("disputes")
        issue = "需要修订专家草稿"
        if isinstance(disputes, list) and disputes:
            issue = str(disputes[0])
        rationale = str(normalized.get("rationale") or issue)
        normalized["revision_requests"] = [
            {
                "target": "both",
                "issue": issue,
                "required_change": rationale,
                "basis": None,
            }
        ]
    return normalized


def build_judge_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "JudgeReport",
                    '{"decision":"accept_with_minor_revision","accuracy_score":5,'
                    '"adaptation_score":4,"completeness_score":4,"disputes":[],"rationale":"理由"}',
                )
                + _EXTRA_TEXT,
            ),
            (
                "user",
                "教学阶段：{teach_phase}\n"
                "专家 A 整合稿：{expert_a_draft}\n"
                "用户问题：{user_input}\n"
                "检索上下文：{retrieval_context}\n"
                "学习者画像：{learner_profile}\n"
                "学习路径：{learning_path}\n"
                "请只审核专家 A 的整合教学稿。通过后它就是 teach 路由的最终教学内容。"
                "judge 只判断是否通过并说明理由，不生成教学正文，不承担整合过程输出。",
            ),
        ]
    )

    def judge_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                teach_phase=state.get("teach_phase", "debate"),
                user_input=state["user_input"],
                retrieval_context=state.get("retrieval_context", []),
                learner_profile=state.get("learner_profile", {}),
                learning_path=state.get("learning_path", []),
            ),
            temperature=agent_temperature("judge", 0.0),
            agent="judge",
        )
        report = JudgeReport.model_validate(_normalize_judge_report(raw))
        return {
            "judge_report": report.model_dump(),
            "diagnosis_feedback_phase": "feedback",
            "events": [completed_event("judge", "reviewed expert A integration draft with LLM")],
        }

    return judge_node
