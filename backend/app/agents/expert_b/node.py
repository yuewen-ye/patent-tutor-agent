"""Expert B Agent node."""

from __future__ import annotations

import json

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.core.agent_runtime_config import agent_temperature
from backend.app.agents.common import (
    Node,
    constrain_expert_draft_to_current_lesson,
    extract_planning_directive,
    extract_teaching_context,
    generate_validated_json,
    load_prompt,
    messages_from_prompt,
    normalize_cross_review_payload,
    normalize_expert_draft_payload,
    _slim_draft_for_review,
)
from backend.app.agents.rag_tools import collect_expert_retrieval_context
from backend.app.core.llm import LLMClient, LLMMessage
from backend.app.schemas.state import CrossReview, ExpertDraft, StateDict, completed_event
from backend.app.curriculum.learning_path import (
    compute_default_block_plan,
    format_default_block_plan_directive,
)
from backend.app.curriculum.block_content_spec import format_block_content_directive

_DRAFT_SYSTEM_PROMPT = load_prompt(__file__, "draft_system.md")
_CROSS_REVIEW_SYSTEM_PROMPT = load_prompt(__file__, "cross_review_system.md")
_REVISION_SYSTEM_PROMPT = load_prompt(__file__, "revision_system.md")


def build_expert_b_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _DRAFT_SYSTEM_PROMPT,
            ),
            (
                "user",
                "问题：{user_input}\n"
                "学习者画像：{learner_profile}\n"
                "路径规划指令（来自 planner）：{planning_directive}\n"
                "本节单节点教学上下文：{teaching_context}\n"
                "检索上下文：{retrieval_context}\n"
                "辩论上下文：{revision_context}\n"
                "【教学模块选择硬约束（须严格遵循，据此产出 block_plan）】{block_plan_directive}\n"
                "【各模块 payload 内容要素约束（须填实，禁空心 payload）】{block_content_directive}\n"
                "请生成专家 B 草稿。",
            ),
        ]
    )

    def expert_b_node(state: StateDict) -> dict[str, Any]:
        phase = state.get("expert_phase", "draft")
        if phase == "cross_review":
            review = generate_validated_json(
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
                    f"专家A草稿：{json.dumps(_slim_draft_for_review(state.get('expert_a_draft', {})), ensure_ascii=False)}"
                ),
                    ),
                ],
                temperature=agent_temperature("expert_b", 0.3),
                agent="expert_b",
                output_model=CrossReview,
                normalize=normalize_cross_review_payload,
                schema_name="ExpertBCrossReview",
            )
            return {
                "expert_b_cross_review": review.model_dump(),
                "events": [completed_event("expert_b", "reviewed expert A draft")],
            }
        if phase == "revision":
            draft = generate_validated_json(
                llm_client,
                messages=[
                    LLMMessage(
                        role="system",
                        content=_REVISION_SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            f"原草稿：{json.dumps(state.get('expert_b_draft', {}), ensure_ascii=False)}\n"
                            f"专家A互评：{json.dumps(state.get('expert_a_cross_review', {}), ensure_ascii=False)}"
                        ),
                    ),
                ],
                temperature=agent_temperature("expert_b", 0.4),
                agent="expert_b",
                output_model=ExpertDraft,
                normalize=normalize_expert_draft_payload,
                schema_name="ExpertBRevision",
            )
            revised = constrain_expert_draft_to_current_lesson(draft.model_dump(), state)
            revised["draft_stage"] = "debate"
            return {
                "expert_b_draft": revised,
                "expert_b_revision": revised,
                "events": [completed_event("expert_b", "revised expert B draft")],
            }

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
            learner_profile=state.get("learner_profile", {}),
            planning_directive=extract_planning_directive(state),
            teaching_context=extract_teaching_context(state),
            retrieval_context=state.get("retrieval_context", []),
            revision_context=state.get("expert_a_draft", {}),
            block_plan_directive=_bp_dir,
            block_content_directive=_bc_dir,
        )
        retrieved_context = collect_expert_retrieval_context(
            llm_client,
            messages=prompt_messages,
            temperature=agent_temperature("expert_b", 0.3, "tool_temperature"),
            agent="expert_b",
        )
        retrieval_context = list(state.get("retrieval_context", []) or []) + retrieved_context
        draft = generate_validated_json(
            llm_client,
            messages=messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
                planning_directive=extract_planning_directive(state),
                teaching_context=extract_teaching_context(state),
                retrieval_context=retrieval_context,
                revision_context=state.get("expert_a_draft", {}),
                block_plan_directive=_bp_dir,
                block_content_directive=_bc_dir,
            ),
            temperature=agent_temperature("expert_b", 0.7),
            agent="expert_b",
            output_model=ExpertDraft,
            normalize=normalize_expert_draft_payload,
            schema_name="ExpertBDraft",
        )
        draft_dict = constrain_expert_draft_to_current_lesson(draft.model_dump(), state)
        draft_dict["draft_stage"] = "debate"
        return {
            "expert_b_draft": draft_dict,
            **({"retrieval_context": retrieved_context} if retrieved_context else {}),
            "events": [completed_event("expert_b", "generated expert B draft with LLM")],
        }

    return expert_b_node
