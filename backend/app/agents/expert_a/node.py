"""Expert A Agent node."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.agents.common import (
    Node,
    extract_planning_directive,
    load_prompt,
    messages_from_prompt,
    normalize_cross_review_payload,
    normalize_expert_draft_payload,
    schema_note,
)
from backend.app.agents.rag_tools import collect_expert_retrieval_context
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.curriculum.learning_path import (
    compute_default_block_plan,
    format_default_block_plan_directive,
    reconcile_block_plan,
)
from backend.app.curriculum.block_content_spec import (
    format_block_content_directive,
    validate_block_payloads,
)
from backend.app.schemas.state import CrossReview, ExpertDraft, StateDict, completed_event

_DEBATE_SYSTEM_PROMPT = load_prompt(__file__, "debate_system.md")
_INTEGRATION_SYSTEM_PROMPT = load_prompt(__file__, "integration_system.md")
_CROSS_REVIEW_SYSTEM_PROMPT = load_prompt(__file__, "cross_review_system.md")
_REVISION_SYSTEM_PROMPT = load_prompt(__file__, "revision_system.md")


def _should_integrate(state: StateDict) -> bool:
    return state.get("teach_phase") == "integration"


def _normalize_expert_draft(raw: object) -> ExpertDraft:
    return ExpertDraft.model_validate(normalize_expert_draft_payload(raw))


def build_expert_a_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "ExpertDraft",
                    '{"expert":"expert_a","style":"conservative",'
                    '"knowledge_points":[{"node_id":"kp-01","kc_name":"要点"}],"legal_basis":[{"article":"《专利法》第22条"}],"irac":{"issue":"","rule":"","application":"","conclusion":""},"block_plan":{"node":"kp-01","blocks":[{"block_id":"b1","block_type":"legal_anchor","title":"法条锚定","payload":{},"chosen_by":"[A]"}],"order":["b1"],"budget":{},"debate_resolved":true},"knowledge_synthesis":{"coverage":[],"confusable_pairs":[]},"assessment":{"items":[{"qid":"q1","category":"understand","difficulty":"L1","question":"","answer":"","kc":"","source":"","evidence":""}]},"interactive_questions":[{"qid":"q1","category":"understand","difficulty":"L1","source_tag":"backward_review","kc_node_id":"kp-01","question":"","answer":""}],'
                    '"teaching_content":"正文","risks":[]}',
                )
                + _DEBATE_SYSTEM_PROMPT,
            ),
            (
                "user",
                "问题：{user_input}\n"
                "路径规划指令（来自 planner）：{planning_directive}\n"
                "学习路径（含各节点 difficulty_cap）：{learning_path}\n"
                "检索上下文：{retrieval_context}\n"
                "辩论上下文：{revision_context}\n"
                "【教学模块选择硬约束（须严格遵循，据此产出 block_plan）】{block_plan_directive}\n"
                "【各模块 payload 内容要素约束（须填实，禁空心 payload）】{block_content_directive}\n"
                "请生成专家 A 草稿。",
            ),
        ]
    )

    def expert_a_node(state: StateDict) -> dict[str, Any]:
        phase = state.get("expert_phase", "draft")
        if phase == "cross_review":
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "CrossReview",
                            '{"reviewer":"expert_a","target":"expert_b",'
                            '"review_opinions":[{"category":"🟡","location":"正文",'
                            '"target_wrote":"原文","problem":"问题","suggestion":"建议",'
                            '"legal_basis":["《专利法》第22条"]}],'
                            '"overall_assessment":"总体评价"}',
                        )
                        + _CROSS_REVIEW_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=json.dumps(state.get("expert_b_draft", {}), ensure_ascii=False),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.2),
                agent="expert_a",
            )
            review = CrossReview.model_validate(normalize_cross_review_payload(raw))
            return {
                "expert_a_cross_review": review.model_dump(),
                "events": [completed_event("expert_a", "reviewed expert B draft")],
            }
        if phase == "revision":
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "ExpertDraft",
                            '{"expert":"expert_a","style":"conservative",'
                            '"knowledge_points":[{"node_id":"kp-01","kc_name":"要点"}],"legal_basis":[{"article":"《专利法》第22条"}],"irac":{"issue":"","rule":"","application":"","conclusion":""},"block_plan":{"node":"kp-01","blocks":[{"block_id":"b1","block_type":"legal_anchor","title":"法条锚定","payload":{},"chosen_by":"[A]"}],"order":["b1"],"budget":{},"debate_resolved":true},"knowledge_synthesis":{"coverage":[],"confusable_pairs":[]},"assessment":{"items":[{"qid":"q1","category":"understand","difficulty":"L1","question":"","answer":"","kc":"","source":"","evidence":""}]},"interactive_questions":[{"qid":"q1","category":"understand","difficulty":"L1","source_tag":"backward_review","kc_node_id":"kp-01","question":"","answer":""}],'
                            '"teaching_content":"修订正文","risks":[]}',
                        )
                        + _REVISION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"原草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            f"专家B互评：{json.dumps(state.get('expert_b_cross_review', {}), ensure_ascii=False)}"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_a", 0.3),
                agent="expert_a",
            )
            draft = _normalize_expert_draft(raw)
            revised = draft.model_dump()
            revised["draft_stage"] = "debate"
            return {
                "expert_a_draft": revised,
                "expert_a_revision": revised,
                "events": [completed_event("expert_a", "revised expert A draft")],
            }
        if _should_integrate(state):
            judge_report_state = state.get("judge_report", {}) or {}
            revision_requests = judge_report_state.get("revision_requests") or []

            # C：锁定 planner 权威当前节点（不让 LLM 自由跳节点）
            path_decision = state.get("path_decision", {}) or {}
            current_node_id = str(path_decision.get("current_node_id") or "")
            if not current_node_id:
                lp = state.get("learning_path", []) or []
                if lp and isinstance(lp[0], dict):
                    current_node_id = str(lp[0].get("node_id") or "")

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
                    # 内容要素硬约束：每个选中块的 payload 必须按骨架填实
                    block_content_directive = format_block_content_directive(
                        default_block_plan.get("required_blocks", [])
                    )
                except Exception:  # 编排约束失败不阻断整合，降级为无硬约束
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
            retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
            raw = llm_client.generate_json(
                messages=[
                    LLMMessage(
                        role="system",
                        content=schema_note(
                            "ExpertDraft",
                            '{"expert":"expert_a","style":"conservative",'
                            '"knowledge_points":[{"node_id":"kp-01","kc_name":"要点"}],"legal_basis":[{"article":"《专利法》第22条"}],"irac":{"issue":"","rule":"","application":"","conclusion":""},"block_plan":{"node":"kp-01","blocks":[{"block_id":"b1","block_type":"legal_anchor","title":"法条锚定","payload":{},"chosen_by":"[A]"}],"order":["b1"],"budget":{},"debate_resolved":true},"knowledge_synthesis":{"coverage":[],"confusable_pairs":[]},"assessment":{"items":[{"qid":"q1","category":"understand","difficulty":"L1","question":"","answer":"","kc":"","source":"","evidence":""}]},"interactive_questions":[{"qid":"q1","category":"understand","difficulty":"L1","source_tag":"backward_review","kc_node_id":"kp-01","question":"","answer":""}],'
                            '"teaching_content":"整合后的教学正文","risks":[]}',
                        )
                        + _INTEGRATION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"用户问题：{state['user_input']}\n"
                            f"【教学当前节点（planner 权威，硬约束）】：{current_node_id or '（未提供）'}\n"
                            f"路径规划指令（来自 planner）：{extract_planning_directive(state)}\n"
                            f"学习路径（含各节点 difficulty_cap）：{json.dumps(state.get('learning_path', []), ensure_ascii=False)}\n"
                            + (f"\n{block_plan_directive}\n\n" if block_plan_directive else "")
                            + f"专家A草稿：{json.dumps(state.get('expert_a_draft', {}), ensure_ascii=False)}\n"
                            f"专家B草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                            f"裁判报告：{json.dumps(state.get('judge_report', {}), ensure_ascii=False)}\n"
                            f"裁判打回意见（revision_requests，你必须逐条回应每条 required_change 并在整合稿中实际修正对应内容）：{json.dumps(revision_requests, ensure_ascii=False)}\n"
                            f"检索上下文：{json.dumps(retrieval_context, ensure_ascii=False)}\n"
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
            )
            draft = _normalize_expert_draft(raw)
            draft_dict = draft.model_dump()
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
        path_decision = state.get("path_decision", {}) or {}
        _cur = str(path_decision.get("current_node_id") or "")
        if not _cur:
            _lp = state.get("learning_path", []) or []
            if _lp and isinstance(_lp[0], dict):
                _cur = str(_lp[0].get("node_id") or "")
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
            except Exception:
                _bp_dir = ""
                _bc_dir = ""

        prompt_messages = messages_from_prompt(
            prompt,
            user_input=state["user_input"],
            planning_directive=extract_planning_directive(state),
            learning_path=state.get("learning_path", []),
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
        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                planning_directive=extract_planning_directive(state),
                learning_path=state.get("learning_path", []),
                retrieval_context=retrieval_context,
                revision_context=state.get("expert_b_draft", {}),
                block_plan_directive=_bp_dir,
                block_content_directive=_bc_dir,
            ),
            temperature=agent_temperature("expert_a", 0.4),
            agent="expert_a",
        )
        draft = _normalize_expert_draft(raw)
        draft_dict = draft.model_dump()
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_a_draft": draft_dict,
            **({"retrieval_context": retrieved_context} if retrieved_context else {}),
            "events": [completed_event("expert_a", "generated expert A draft with LLM")],
        }

    return expert_a_node
