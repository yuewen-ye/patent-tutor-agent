"""Judge Agent node."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from typing import Any, assert_never

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import (
    Node,
    generate_validated_json_stream,
    load_prompt,
    messages_from_prompt,
    schema_note,
)
from backend.app.agents.rag_tools import (
    cap_retrieval_context,
    collect_judge_retrieval_context,
)
from backend.app.core.agent_runtime_config import agent_runtime_settings, agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
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


def _stable_request_id(target: object, issue: object, required_change: object) -> str:
    """为 revision_request 生成稳定短 ID，用于跨轮次闭环追踪。"""
    text = "|".join(str(x or "").strip() for x in (target, issue, required_change))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _normalize_request_text(text: object) -> str:
    """用于模糊匹配的去标点、去多余空格归一化文本。"""
    s = str(text or "").strip().lower()
    s = re.sub(r"[^\u4e00-\u9fa5a-z0-9]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fuzzy_match_request(
    req: dict[str, Any], prior_requests: list[dict[str, Any]], threshold: float = 0.65
) -> str | None:
    """把当前请求按 target + 文本相似度匹配到历史 request_id，抵抗措辞改写。"""
    target = str(req.get("target") or "")
    current_text = _normalize_request_text(
        str(req.get("issue") or "") + " " + str(req.get("required_change") or "")
    )
    if not current_text:
        return None
    best_id: str | None = None
    best_ratio = 0.0
    for prior in prior_requests:
        if str(prior.get("target") or "") != target:
            continue
        prior_text = _normalize_request_text(
            str(prior.get("issue") or "") + " " + str(prior.get("required_change") or "")
        )
        if not prior_text:
            continue
        ratio = difflib.SequenceMatcher(None, current_text, prior_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = prior.get("request_id")
    if best_ratio >= threshold and isinstance(best_id, str):
        return best_id
    return None


def _reconcile_revision_requests(
    current_requests: list[dict[str, Any]], prior_requests: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """将 LLM 本轮返回的请求与历史闭环：复用 ID、标记 fixed/open/regressed/new。

    返回：
        - current_open_requests: 仍需要 expert 修改的项（open/new/regressed）
        - updated_history: 包含 fixed 项在内的完整历史快照
    """
    prior_by_id: dict[str, dict[str, Any]] = {}
    for prior_req in prior_requests:
        pid = prior_req.get("request_id")
        if isinstance(pid, str) and pid:
            prior_by_id[pid] = prior_req

    open_requests: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for req in current_requests:
        req = dict(req)
        provided_id = req.get("request_id")
        # 优先信任 LLM 提供的 ID；若缺失或无效则尝试模糊匹配历史；最后生成新 ID。
        req_id: str
        if isinstance(provided_id, str) and provided_id and provided_id in prior_by_id:
            req_id = provided_id
        else:
            matched_id = _fuzzy_match_request(req, prior_requests)
            req_id = matched_id or _stable_request_id(
                req.get("target"), req.get("issue"), req.get("required_change")
            )
        req["request_id"] = req_id

        used_ids.add(req_id)
        prior: dict[str, Any] | None = prior_by_id.get(req_id)
        current_status = req.get("status")
        valid_statuses = {"open", "fixed", "regressed", "new"}
        if current_status not in valid_statuses:
            current_status = None
        if prior is not None:
            # 历史有过的项：若 LLM 没给状态则默认仍 open
            req["status"] = current_status or "open"
        else:
            req["status"] = current_status or "new"
        open_requests.append(req)

    # 本轮未再出现的旧项视为已修复，追加到历史但不进入 current_open_requests
    updated_history = list(open_requests)
    for pid, prior in prior_by_id.items():
        if pid not in used_ids:
            fixed_req = dict(prior)
            fixed_req["status"] = "fixed"
            updated_history.append(fixed_req)

    return open_requests, updated_history


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
    # scores: 兼容 LLM 偶发的浮点/字符串形态 → int（schema 要求 int 1-5）
    for _f in ("accuracy_score", "adaptation_score", "completeness_score"):
        _v = normalized.get(_f)
        if isinstance(_v, float):
            normalized[_f] = round(_v)
        elif isinstance(_v, str):
            _s = _v.strip()
            if _s and _s.replace(".", "", 1).isdigit():
                normalized[_f] = round(float(_s))
    decision = str(normalized.get("decision", "")).strip().lower()
    if decision in _DECISION_NORMALIZATION:
        normalized["decision"] = _DECISION_NORMALIZATION[decision]
    # 规范化 revision_requests 中每个 target/request_id/status 字段
    raw_requests = normalized.get("revision_requests")
    if isinstance(raw_requests, list):
        normalized_requests: list[dict[str, object]] = []
        for req in raw_requests:
            if isinstance(req, dict):
                nr = dict(req)
                nr["target"] = _normalize_target(nr.get("target"))
                if not isinstance(nr.get("request_id"), str) or not nr.get("request_id"):
                    nr["request_id"] = _stable_request_id(
                        nr.get("target"), nr.get("issue"), nr.get("required_change")
                    )
                if nr.get("status") not in {"open", "fixed", "regressed", "new"}:
                    nr["status"] = "open"
                normalized_requests.append(nr)
        normalized["revision_requests"] = normalized_requests
    _acc = normalized.get("accuracy_score")
    _com = normalized.get("completeness_score")
    _ada = normalized.get("adaptation_score")
    _gated_decision = normalized.get("decision")
    if (
        type(_acc) is int
        and type(_com) is int
        and type(_ada) is int
        and _gated_decision in ("accept", "accept_with_minor_revision")
    ):
        _passes_accept = _acc == 5 and _com >= 4 and _ada >= 4
        _passes_minor = _acc >= 4 and _com >= 3 and _ada >= 3
        if _gated_decision == "accept" and not _passes_accept:
            normalized["decision"] = (
                "accept_with_minor_revision" if _passes_minor else "revise"
            )
        elif _gated_decision == "accept_with_minor_revision" and not _passes_minor:
            normalized["decision"] = "revise"
    if (
        normalized.get("decision") in ("accept", "accept_with_minor_revision")
        and normalized.get("revision_requests")
    ):
        normalized["decision"] = "revise"
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
                    '{"decision":"accept","accuracy_score":5,'
                    '"adaptation_score":4,"completeness_score":4,"adaptation_rate":0.8,"disputes":[],"rationale":"理由"}',
                )
                + _EXTRA_TEXT,
            ),
            (
                "user",
                (
                    "教学阶段：{teach_phase}\n"
                    "历史修订请求（含 request_id 与当前状态，用于跨轮闭环；后续轮必须复用 ID）：{prior_requests_text}\n"
                    "请只审核专家 A 的整合教学稿。通过后它就是 teach 路由的最终教学内容。"
                    "judge 只判断是否通过并说明理由，不生成教学正文，不承担整合过程输出。\n"
                    "专家 A 整合稿：{expert_a_draft}\n"
                    "用户问题：{user_input}\n"
                    "检索上下文：{retrieval_context}\n"
                    "学习者画像：{learner_profile}\n"
                    "学习路径：{learning_path}\n"
                ),
            ),
        ]
    )

    def judge_node(state: StateDict) -> dict[str, Any]:
        # 构造历史修订请求文本，要求 LLM 在后续轮复用 request_id
        prior_history = list(state.get("judge_report_history") or [])
        prior_requests: list[dict[str, Any]] = []
        for _rep in prior_history:
            if not isinstance(_rep, dict):
                continue
            for _r in (_rep.get("revision_requests") or []):
                if isinstance(_r, dict) and _r.get("request_id"):
                    prior_requests.append(_r)
        prior_requests_text = (
            "（首轮无历史）"
            if not prior_requests
            else json.dumps(prior_requests, ensure_ascii=False)
        )

        # —— RAG 预检：裁决前基于检索意图补一次检索，并入检索上下文 ——
        judge_probe_messages = [
            LLMMessage(role="system", content=_EXTRA_TEXT),
            LLMMessage(
                role="user",
                content=(
                    f"用户问题：{state['user_input']}\n"
                    f"专家 A 整合稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                    "请判断审核前是否需要补充检索以核实法条、案例或关键数据；"
                    "如需，请调用 rag_retrieve 给出检索词。"
                ),
            ),
        ]
        judge_retrieved = collect_judge_retrieval_context(
            llm_client,
            messages=judge_probe_messages,
            temperature=agent_temperature("judge", 0.2, "tool_temperature"),
            agent="judge",
            enabled=state.get("rag_tool_enabled", True),
        )
        retrieval_context = cap_retrieval_context(
            list(state.get("retrieval_context", [])) + judge_retrieved
        )

        report = generate_validated_json_stream(
            llm_client,
            messages=messages_from_prompt(
                prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                teach_phase=state.get("teach_phase", "debate"),
                user_input=state["user_input"],
                retrieval_context=retrieval_context,
                learner_profile=state.get("learner_profile", {}),
                learning_path=state.get("learning_path", []),
                prior_requests_text=prior_requests_text,
            ),
            temperature=agent_temperature("judge", 0.0),
            agent="judge",
            output_model=JudgeReport,
            normalize=_normalize_judge_report,
            schema_name="JudgeReport",
        )
        # adaptation_rate 由代码根据已校验的 adaptation_score 确定性计算，
        # 覆盖 LLM 可能算错/漏填的值，保证 rate == round(score/5.0, 2)。
        report_dict = report.model_dump()
        report_dict["adaptation_rate"] = round(report.adaptation_score / 5.0, 2)

        # —— 闭环状态机：复用 request_id、标记 fixed/open/regressed/new ——
        current_requests = list(report_dict.get("revision_requests") or [])
        open_requests, updated_history_requests = _reconcile_revision_requests(
            current_requests, prior_requests
        )
        report_dict["revision_requests"] = open_requests

        updates: dict[str, Any] = {
            "judge_report": report_dict,
            "events": [completed_event("judge", "reviewed expert A integration draft with LLM")],
        }
        # —— 历史闭环：把本轮完整状态快照 append 进 judge_report_history ——
        current_round = state.get("revision_round", 0) or 0
        snapshot = dict(report_dict)
        snapshot["revision_requests"] = updated_history_requests
        snapshot["round"] = current_round + 1
        prior_history.append(snapshot)
        updates["judge_report_history"] = prior_history
        match report_dict["decision"]:
            case "accept" | "accept_with_minor_revision":
                updates["workflow_status"] = "completed"
            case "revise":
                new_round = current_round + 1
                updates["revision_round"] = new_round
                max_revisions = agent_runtime_settings("judge").max_revisions
                cap = max_revisions if max_revisions is not None else 3
                if new_round >= cap:
                    updates["workflow_status"] = "completed"
            case unreachable:
                assert_never(unreachable)
        return updates

    return judge_node
