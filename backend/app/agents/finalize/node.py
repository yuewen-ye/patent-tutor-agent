"""Workflow finalization node — merges expert drafts into a unified teaching answer."""

from __future__ import annotations

from typing import Any

from backend.app.agents.common import Node, LLMMessage, normalize_key_aliases
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import FinalAnswer, StateDict, completed_event

_FINALIZE_SYSTEM = """你是专利教学内容的最终格式化专家。你的任务是将专家联合合成稿格式化为最终答案。

联合合成稿已由两位专家协作完成，包含来源标注（[A]/[B]/[A+B融合]），你主要负责：
1. 检查并确认标题、内容、来源是否完整
2. 如有裁判指出的问题但尚未在联合合成稿中修正的，在最终答案中修正
3. 保留完整的来源引用列表
4. 添加下一步学习问题建议

你必须只输出 JSON，不要输出 Markdown。字段名必须使用 snake_case。
示例：{"title": "专利新颖性判断标准", "content": "格式化后的教学内容...", "sources": ["法条来源"]}"""


def build_finalize_node(llm_client: LLMClient) -> Node:
    def finalize_node(state: StateDict) -> dict[str, Any]:
        synthesis = state.get("joint_synthesis_output", {})
        judge_report = state.get("judge_report", {})
        feedback_result = state.get("feedback_result", {})

        import json as _json

        messages = [
            LLMMessage(role="system", content=_FINALIZE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"联合合成稿：\n{_json.dumps(synthesis, ensure_ascii=False, indent=2)}\n\n"
                    f"裁判报告：\n{_json.dumps(judge_report, ensure_ascii=False, indent=2)}\n\n"
                    f"反馈分析：\n{_json.dumps(feedback_result, ensure_ascii=False, indent=2)}\n\n"
                    "请格式化为最终答案。"
                ),
            ),
        ]

        raw = llm_client.generate_json(messages=messages, temperature=0.3, agent="finalize")
        # Normalize known LLM key variants before validation
        normalized = normalize_key_aliases(
            raw,
            {
                "nextStudyQuestions": "next_questions",
                "next_study_questions": "next_questions",
                "judgeSummary": "judge_summary",
            },
        )
        validated = FinalAnswer.model_validate(normalized)

        return {
            "final_answer": validated.model_dump(),
            "events": [completed_event("finalize", "formatted final teaching answer from joint synthesis")],
        }

    return finalize_node
