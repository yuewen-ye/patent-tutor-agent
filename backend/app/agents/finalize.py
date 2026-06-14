"""Workflow finalization node — merges expert drafts into a unified teaching answer."""

from __future__ import annotations

from typing import Any

from backend.app.agents.common import Node, LLMMessage, LLMRole
from backend.app.core.llm import LLMClient
from backend.app.schemas.state import FinalAnswer, StateDict, completed_event

_FINALIZE_SYSTEM = """你是专利教学内容的最终整合专家。你的任务是将两位专家的教学草稿合并为一份统一的最终答案。

整合规则：
1. 两位专家的共识知识点作为核心内容，各自独有的知识点作为补充
2. 法条引用取并集，去重
3. 如有 IRAC 分析，保留更完整的那份
4. 对于裁判指出的 dispute 要修正——优先采纳评分更高的专家的说法
5. 内容要连贯，不能是两篇草稿的简单拼接
6. 标题要概括本次教学内容

你必须只输出 JSON，不要输出 Markdown。字段名必须使用 snake_case。
示例：{"title": "专利新颖性判断标准", "content": "整合后的教学内容...", "sources": ["法条来源"]}"""


def build_finalize_node(llm_client: LLMClient) -> Node:
    def finalize_node(state: StateDict) -> dict[str, Any]:
        expert_a = state.get("expert_a_draft", {})
        expert_b = state.get("expert_b_draft", {})
        judge_report = state.get("judge_report", {})
        feedback_result = state.get("feedback_result", {})

        import json as _json

        messages = [
            LLMMessage(role="system", content=_FINALIZE_SYSTEM),
            LLMMessage(
                role="user",
                content=(
                    f"专家 A 草稿（风格：{expert_a.get('style', '')}）：\n"
                    f"{_json.dumps(expert_a, ensure_ascii=False, indent=2)}\n\n"
                    f"专家 B 草稿（风格：{expert_b.get('style', '')}）：\n"
                    f"{_json.dumps(expert_b, ensure_ascii=False, indent=2)}\n\n"
                    f"裁判报告：\n{_json.dumps(judge_report, ensure_ascii=False, indent=2)}\n\n"
                    "请整合为最终答案。"
                ),
            ),
        ]

        raw = llm_client.generate_json(messages=messages, temperature=0.3, agent="finalize")
        validated = FinalAnswer.model_validate(raw)

        return {
            "final_answer": validated.model_dump(),
            "events": [completed_event("finalize", "merged and assembled final teaching answer")],
        }

    return finalize_node
