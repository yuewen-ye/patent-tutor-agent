"""Joint synthesis agent node — merges Expert A and B revised drafts into one output."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import Node, messages_from_prompt, normalize_key_aliases, schema_note
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import JointSynthesis, StateDict, completed_event

_JOINT_SYNTHESIS_SYSTEM = """你是专家联合合成器。你的任务是将专家 A（保守严谨型，法条优先）和专家 B（生动灵活型，面向案例）的修订稿协作整合为一份统一的最终输出。

合成规则：
1. 以 A 的法条框架为骨架（法条、要件、判断流程、边界例外、常见错误），B 的内容嵌入对应位置
2. 每段必须标注来源：A / B / A+B融合 / B-过渡
3. 不创造任何一方修订稿中没有的新内容——你只做选择和拼接
4. B 主导阅读体验——内容的顺序、节奏、难度曲线由 B 的风格主导
5. 准确性与可读性冲突时，准确性优先——保留 A 的精确表述，B 在前面加通俗概括

source 标注含义：
- "A"：完全来自专家 A 的修订稿
- "B"：完全来自专家 B 的修订稿
- "A+B融合"：框架来自 A，通俗解释来自 B
- "B-过渡"：B 提供的段落间过渡文字

注意：
- 如果有 judge_report.decision=revise，说明这是修订轮次，需要按 revision_requests 在现有合成稿基础上局部修正，而非重新合成
- 如果有 lightweight_review_result，必须确认轻量互审指出的问题已经处理
- 关注 unresolved_disputes 中的问题，标注解决方案"""


def build_joint_synthesis_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                schema_note(
                    "JointSynthesis",
                    '{"node_id":"patent_22_2","title":"新颖性判断标准",'
                    '"sections":[{"heading":"法条依据","content":"...","source":"A","note":null},'
                    '{"heading":"通俗解释","content":"...","source":"B","note":null},'
                    '{"heading":"判断标准详解","content":"...","source":"A+B融合",'
                    '"note":"框架来自A，通俗解释来自B"}],'
                    '"transition_notes":[],"unresolved_in_synthesis":[]}',
                )
                + _JOINT_SYNTHESIS_SYSTEM,
            ),
            (
                "user",
                "用户问题：{user_input}\n\n"
                "专家 A 修订稿：\n{expert_a_draft}\n\n"
                "专家 A 修订记录：\n{revision_record_a}\n\n"
                "专家 B 修订稿：\n{expert_b_draft}\n\n"
                "专家 B 修订记录：\n{revision_record_b}\n\n"
                "学习者画像：{learner_profile}\n\n"
                "现有联合合成稿（如有）：{existing_synthesis}\n"
                "Judge 打回意见（如有）：{judge_report}\n"
                "轻量互审结果（如有）：{lightweight_review}\n\n"
                "请整合为联合合成稿。",
            ),
        ]
    )

    def joint_synthesis_node(state: StateDict) -> dict[str, Any]:
        existing = state.get("joint_synthesis_output")
        lightweight = state.get("lightweight_review_result")

        raw = llm_client.generate_json(
            messages_from_prompt(
                prompt,
                user_input=state["user_input"],
                expert_a_draft=state.get("expert_a_draft", {}),
                expert_b_draft=state.get("expert_b_draft", {}),
                revision_record_a=state.get("revision_record_a", {}),
                revision_record_b=state.get("revision_record_b", {}),
                learner_profile=state.get("learner_profile", {}),
                existing_synthesis=existing if existing else {},
                judge_report=state.get("judge_report", {}),
                lightweight_review=lightweight if lightweight else {},
            ),
            temperature=0.3,
            agent="joint_synthesis",
        )
        # Normalize key aliases and LLM output format quirks
        normalized = normalize_key_aliases(
            raw,
            {
                "nodeId": "node_id",
                "transitionNotes": "transition_notes",
                "unresolvedInSynthesis": "unresolved_in_synthesis",
            },
        )
        # Defensive: normalize LLM output format quirks
        _SOURCE_ALIASES = {
            "A+B": "A+B融合", "AB": "A+B融合", "a+b": "A+B融合",
            "B过渡": "B-过渡", "B-过渡": "B-过渡", "B_TRANSITION": "B-过渡",
        }
        if isinstance(normalized, dict):
            # Coerce string transition_notes into dict format
            tn = normalized.get("transition_notes")
            if isinstance(tn, list):
                normalized["transition_notes"] = [
                    {"text": item} if isinstance(item, str) else item
                    for item in tn
                ]
            # Normalize section source values
            sections = normalized.get("sections")
            if isinstance(sections, list):
                for sec in sections:
                    if isinstance(sec, dict):
                        src = sec.get("source")
                        if isinstance(src, str) and src in _SOURCE_ALIASES:
                            sec["source"] = _SOURCE_ALIASES[src]
        synthesis = JointSynthesis.model_validate(normalized)
        return {
            "joint_synthesis_output": synthesis.model_dump(),
            "events": [
                completed_event("joint_synthesis", "produced joint expert synthesis")
            ],
        }

    return joint_synthesis_node
