"""Judge Agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, schema_note
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


def _normalize_judge_report(raw: object) -> object:
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    decision = str(normalized.get("decision", "")).strip().lower()
    if decision in _DECISION_NORMALIZATION:
        normalized["decision"] = _DECISION_NORMALIZATION[decision]
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
                    '"adaptation_score":4,"disputes":[],"rationale":"理由"}',
                )
                + "你是审核裁判 Agent，只评估，不生成教学正文。"
                + "decision 只能是 accept、accept_with_minor_revision 或 revise。"
                + "如果需要大幅修订，必须输出 revise。",
            ),
            (
                "user",
                "专家 A：{expert_a_draft}\n专家 B：{expert_b_draft}\n请审核并裁决。",
            ),
        ]
    )

    def judge_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                expert_b_draft=state.get("expert_b_draft", {}),
            ),
            temperature=0.0,
            agent="judge",
        )
        report = JudgeReport.model_validate(_normalize_judge_report(raw))
        return {
            "judge_report": report.model_dump(),
            "events": [completed_event("judge", "reviewed expert drafts with LLM")],
        }

    return judge_node
