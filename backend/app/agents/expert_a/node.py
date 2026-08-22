"""Expert A Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import (
    Node,
    _slim_draft_for_review,
    constrain_expert_draft_to_current_lesson,
    extract_planning_directive,
    extract_teaching_context,
    generate_validated_json_stream,
    load_prompt,
    messages_from_prompt,
    normalize_cross_review_payload,
    normalize_expert_draft_payload,
)
from backend.app.agents.rag_tools import (
    cap_retrieval_context,
    collect_expert_retrieval_context,
)
from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.block_content_spec import (
    format_block_content_directive,
    validate_block_payloads,
)
from backend.app.curriculum.learning_path import (
    compute_default_block_plan,
    format_default_block_plan_directive,
    reconcile_block_plan,
)
from backend.app.schemas.state import CrossReview, ExpertDraft, StateDict, completed_event

_DEBATE_SYSTEM_PROMPT = load_prompt(__file__, "debate_system.md")
_INTEGRATION_SYSTEM_PROMPT = load_prompt(__file__, "integration_system.md")
_CROSS_REVIEW_SYSTEM_PROMPT = load_prompt(__file__, "cross_review_system.md")
_REVISION_SYSTEM_PROMPT = load_prompt(__file__, "revision_system.md")


def _should_integrate(state: StateDict) -> bool:
    return state.get("teach_phase") == "integration"


def build_expert_a_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _DEBATE_SYSTEM_PROMPT,
            ),
            (
                "user",
                (
                    "问题：{user_input}\n"
                    "学习者画像：{learner_profile}\n"
                    "路径规划指令（来自 planner）：{planning_directive}\n"
                    "本节单节点教学上下文：{teaching_context}\n"
                    "检索上下文：{retrieval_context}\n"
                    "辩论上下文：{revision_context}\n"
                    "【教学模块选择硬约束（须严格遵循，据此产出 block_plan）】{block_plan_directive}\n"
                    "【各模块 payload 内容要素约束（须填实，禁空心 payload）】{block_content_directive}\n"
                    "请生成专家 A 草稿。"
                ),
            ),
        ]
    )

    def expert_a_node(state: StateDict) -> dict[str, Any]:
        phase = state.get("expert_phase", "draft")
        if phase == "cross_review":
            teaching_context = extract_teaching_context(state)
            review = generate_validated_json_stream(
                llm_client,
                messages=[
                    LLMMessage(
                        role="system",
                        content=_CROSS_REVIEW_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"学习者画像：{json.dumps(state.get('learner_profile', {}), ensure_ascii=False)}\n"
                            f"受限教学上下文（窗口权威）：{json.dumps(teaching_context, ensure_ascii=False)}\n"
                            "请仅依据该窗口审查专家B草稿，发现超出窗口的教学节点时提出修改意见。\n"
                            f"专家B草稿：{json.dumps(_slim_draft_for_review(state.get('expert_b_draft', {})), ensure_ascii=False)}"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.2),
                agent="expert_a",
                output_model=CrossReview,
                normalize=normalize_cross_review_payload,
                schema_name="ExpertACrossReview",
            )
            return {
                "expert_a_cross_review": review.model_dump(),
                "events": [completed_event("expert_a", "reviewed expert B draft")],
            }
        if phase == "revision":
            teaching_context = extract_teaching_context(state)
            draft = generate_validated_json_stream(
                llm_client,
                messages=[
                    LLMMessage(
                        role="system",
                        content=_REVISION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            "受限教学上下文（窗口权威，禁止扩展到其他路线节点）："
                            f"{json.dumps(teaching_context, ensure_ascii=False)}\n"
                            f"原草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            f"专家B互评：{json.dumps(state.get('expert_b_cross_review', {}), ensure_ascii=False)}"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.3),
                agent="expert_a",
                output_model=ExpertDraft,
                normalize=normalize_expert_draft_payload,
                schema_name="ExpertARevision",
            )
            revised = constrain_expert_draft_to_current_lesson(draft.model_dump(), state)
            revised["draft_stage"] = "debate"
            return {
                "expert_a_draft": revised,
                "expert_a_revision": revised,
                "events": [completed_event("expert_a", "revised expert A draft")],
            }
        if _should_integrate(state):
            judge_report_state = state.get("judge_report", {}) or {}
            _judge_decision = (judge_report_state.get("decision") or "").strip().lower()
            _rev_round = state.get("revision_round", 0) or 0
            # 跨轮累积：汇总 judge_report_history 中所有历史必须修改项 + 当前轮，
            # 优先按 request_id 去重，缺失 request_id 时回退到 (target, issue, required_change)。
            # 只保留 status 为 open / new / regressed 的项；fixed 项不再要求修改。
            _history = state.get("judge_report_history") or []
            _accumulated: list[dict[str, Any]] = []
            _seen_ids: set[str] = set()
            _seen_keys: set[tuple[object, object, object]] = set()
            for _rep in (*_history, judge_report_state):
                if not isinstance(_rep, dict):
                    continue
                for _r in (_rep.get("revision_requests") or []):
                    if not isinstance(_r, dict):
                        continue
                    _status = _r.get("status")
                    if _status == "fixed":
                        continue
                    _rid = _r.get("request_id")
                    if isinstance(_rid, str) and _rid:
                        if _rid in _seen_ids:
                            continue
                        _seen_ids.add(_rid)
                        _accumulated.append(_r)
                        continue
                    _key = (_r.get("target"), _r.get("issue"), _r.get("required_change"))
                    if _key in _seen_keys:
                        continue
                    _seen_keys.add(_key)
                    _accumulated.append(_r)
            revision_requests = _accumulated
            _revision_directive = ""
            if _judge_decision == "revise" and revision_requests:
                _revision_directive = (
                    f"\n这是第 {_rev_round} 次修订。上一轮整合稿已在专家A草稿中，"
                    "请以它为基准，**针对下方全部累积必须修改项逐条定点修改对应内容点**；"
                    "不动文档整体结构与 block 布局，结构化模块归 block，"
                    "teaching_content 保持连贯叙事；"
                    "禁止把模块名切片塞进 teaching_content、禁止重排结构；"
                    "保留其余部分不变，禁止重新生成全文。\n"
                )

            # C：锁定 planner 权威当前节点（不让 LLM 自由跳节点）
            teaching_context = extract_teaching_context(state)
            current_node_id = str(teaching_context.get("current_node_id") or "")

            # A/B：按 spec 规则确定性算出应含板块集合，渲染为整合硬约束
            profile = state.get("learner_profile", {}) or {}
            default_block_plan: dict[str, Any] | None = None
            block_plan_directive = ""
            block_content_directive = ""
            if current_node_id and profile:
                try:
                    default_block_plan = compute_default_block_plan(
                        profile=profile,
                        current_node_id=current_node_id,
                        weak_points=profile.get("weak_points"),
                    )
                    block_plan_directive = format_default_block_plan_directive(
                        default_block_plan
                    )
                    block_content_directive = format_block_content_directive(
                        default_block_plan.get("required_blocks", [])
                    )
                except (KeyError, TypeError, ValueError):
                    default_block_plan = None
                    block_plan_directive = ""
                    block_content_directive = ""
            tool_messages = [
                LLMMessage(
                    role="system",
                    content=_INTEGRATION_SYSTEM_PROMPT,
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"用户问题：{state['user_input']}\n"
                        f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                        f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                        "请判断整合前是否需要补充检索。"
                    ),
                ),
            ]
            retrieved_context = collect_expert_retrieval_context(
                llm_client,
                messages=tool_messages,
                temperature=agent_temperature("expert_a", 0.2, "tool_temperature"),
                agent="expert_a",
            )
            retrieval_context = cap_retrieval_context(
                list(state.get("retrieval_context", []) or []) + retrieved_context
            )
            draft = generate_validated_json_stream(
                llm_client,
                messages=[
                    LLMMessage(
                        role="system",
                        content=_INTEGRATION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"用户问题：{state['user_input']}\n"
                            f"【教学当前节点（planner 权威，硬约束）】：{current_node_id or '（未提供）'}\n"
                            f"路径规划指令（来自 planner）：{extract_planning_directive(state)}\n"
                            f"本节单节点教学上下文：{json.dumps(extract_teaching_context(state), ensure_ascii=False)}\n"
                            + (f"\n{block_plan_directive}\n\n" if block_plan_directive else "")
                            + f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            + f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                            + f"裁判报告：{json.dumps(state.get('judge_report', {}), ensure_ascii=False)}\n"
                            + f"裁判打回意见（revision_requests，你必须逐条回应每条 required_change 并在整合稿中实际修正对应内容）：{json.dumps(revision_requests, ensure_ascii=False)}\n"
                            + (_revision_directive if _revision_directive else "")
                            + f"检索上下文：{json.dumps(retrieval_context, ensure_ascii=False)}\n"
                            + (f"\n{block_content_directive}\n\n" if block_content_directive else "")
                            + f"教学正文必须围绕当前节点【{current_node_id or '（见路径）'}】展开，block_plan.node 必须等于该节点。\n"
                            "每个选中模块的 payload **必须按上『内容要素约束』填实**（结构化字段+最低深度），"
                            "禁止空心 payload（仅一句标题/字符串）。教学正文各段也要展开到位："
                            "worked_example 段须含完整例题（事实→规则→分步推理→结论），common_pitfall 段须写出"
                            "『误解原话 + 正解推理 + 区分判据』。\n"
                            "请整合两位专家的有效观点，并**逐条回应**上方 revision_requests 的修改要求，"
                            "输出可由 judge 二审直接审核的 ExpertDraft。"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.3, "integration_temperature"),
                agent="expert_a",
                output_model=ExpertDraft,
                normalize=normalize_expert_draft_payload,
                schema_name="ExpertAIntegration",
            )
            draft_dict = constrain_expert_draft_to_current_lesson(draft.model_dump(), state)
            draft_dict["draft_stage"] = "integration"

            # B/C：用确定性 default 校正 LLM 的 block_plan（补漏块/删规则外块/
            # 覆盖 trigger 消灭张冠李戴/对齐 node 到 planner 权威节点）
            if default_block_plan is not None:
                draft_dict["block_plan"] = reconcile_block_plan(
                    llm_plan=draft_dict.get("block_plan"),
                    default_plan=default_block_plan,
                    current_node_id=current_node_id,
                )
                # 内容要素完整性校验（非阻断，仅日志观察；真正确由提示词约束）
                _bp = draft_dict.get("block_plan") or {}
                _pw = validate_block_payloads(_bp.get("blocks") or [])
                if _pw:
                    print(
                        f"[expert_a] block_plan payload 不完整（{current_node_id}）："
                        + "；".join(_pw)
                    )
            return {
                "expert_a_draft": draft_dict,
                "course_package": draft_dict,
                "teach_phase": "integration",
                **({"retrieval_context": retrieved_context} if retrieved_context else {}),
                "events": [completed_event("expert_a", "integrated expert debate result with LLM")],
            }

        # 双专家初稿也按确定性块大纲写作（与 integration 一致的硬约束）
        _cur = str(extract_teaching_context(state).get("current_node_id") or "")
        _profile = state.get("learner_profile", {}) or {}
        _bp_dir = ""
        _bc_dir = ""
        if _cur and _profile:
            try:
                _default = compute_default_block_plan(
                    profile=_profile,
                    current_node_id=_cur,
                    weak_points=_profile.get("weak_points"),
                )
                _bp_dir = format_default_block_plan_directive(_default)
                _bc_dir = format_block_content_directive(_default.get("required_blocks", []))
            except (KeyError, TypeError, ValueError):
                _bp_dir = ""
                _bc_dir = ""

        prompt_messages = messages_from_prompt(
            prompt,
            user_input=state["user_input"],
            learner_profile=state.get("learner_profile", {}),
            planning_directive=extract_planning_directive(state),
            teaching_context=extract_teaching_context(state),
            retrieval_context=state.get("retrieval_context", []),
            revision_context=state.get("expert_b_draft", {}),
            block_plan_directive=_bp_dir,
            block_content_directive=_bc_dir,
        )
        retrieved_context = collect_expert_retrieval_context(
            llm_client,
            messages=prompt_messages,
            temperature=agent_temperature("expert_a", 0.2, "tool_temperature"),
            agent="expert_a",
        )
        retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
        draft = generate_validated_json_stream(
            llm_client,
            messages=messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
                planning_directive=extract_planning_directive(state),
                teaching_context=extract_teaching_context(state),
                retrieval_context=retrieval_context,
                revision_context=state.get("expert_b_draft", {}),
                block_plan_directive=_bp_dir,
                block_content_directive=_bc_dir,
            ),
            temperature=agent_temperature("expert_a", 0.4),
            agent="expert_a",
            output_model=ExpertDraft,
            normalize=normalize_expert_draft_payload,
            schema_name="ExpertADraft",
        )
        draft_dict = constrain_expert_draft_to_current_lesson(draft.model_dump(), state)
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_a_draft": draft_dict,
            **({"retrieval_context": retrieved_context} if retrieved_context else {}),
            "events": [completed_event("expert_a", "generated expert A draft with LLM")],
        }

    return expert_a_node
