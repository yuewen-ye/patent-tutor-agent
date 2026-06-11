"""LLM-backed Agent nodes for the first real-model workflow MVP."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.core.llm import LLMClient, LLMMessage, LLMProviderError
from backend.app.schemas.state import (
    ExpertDraft,
    FeedbackResult,
    JudgeReport,
    LearnerProfile,
    LearningPathItem,
    RetrievalChunk,
    StateDict,
    completed_event,
)

Node = Callable[[StateDict], dict[str, Any]]


def _messages(prompt: ChatPromptTemplate, **values: object) -> list[LLMMessage]:
    return [
        LLMMessage(role=message.type, content=str(message.content))  # type: ignore[arg-type]
        for message in prompt.format_messages(**values)
    ]


def _schema_note(schema_name: str, example: str) -> str:
    return (
        f"你必须只输出 json，不要输出 Markdown。输出必须符合 {schema_name}。"
        f"示例 json：{example.replace(chr(123), chr(123) * 2).replace(chr(125), chr(125) * 2)}"
    )


def build_agent_nodes(llm_client: LLMClient) -> dict[str, Node]:
    diagnosis_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "LearnerProfile",
                    '{"education_background":"patent_exam_candidate","knowledge_level":"beginner",'
                    '"learning_style":"case_first_then_rule","weak_points":["概念辨析"],'
                    '"learning_goal":"学习目标"}',
                ),
            ),
            ("user", "请诊断该学习需求对应的学习者画像：{user_input}"),
        ]
    )
    planner_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "list[LearningPathItem]",
                    '[{"node_id":"patentability-basic","node_name":"专利授权条件基础",'
                    '"duration_min":20,"strategy":"先学概念","prerequisites":[]}]',
                ),
            ),
            (
                "user",
                "用户问题：{user_input}\n学习者画像：{learner_profile}\n请规划学习路径。",
            ),
        ]
    )
    expert_a_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "ExpertDraft",
                    '{"expert":"expert_a","style":"conservative_precise",'
                    '"knowledge_points":["要点"],"legal_basis":["依据"],'
                    '"teaching_content":"正文","risks":[]}',
                )
                + "你是保守严谨的专利法专家 A，优先保证法条准确。",
            ),
            (
                "user",
                "问题：{user_input}\n检索上下文：{retrieval_context}\n请生成专家 A 草稿。",
            ),
        ]
    )
    expert_b_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "ExpertDraft",
                    '{"expert":"expert_b","style":"vivid_teaching",'
                    '"knowledge_points":["要点"],"legal_basis":["依据"],'
                    '"teaching_content":"正文","risks":[]}',
                )
                + "你是生动灵活的教学专家 B，但必须回扣法条依据。",
            ),
            (
                "user",
                "问题：{user_input}\n学习者画像：{learner_profile}\n请生成专家 B 草稿。",
            ),
        ]
    )
    judge_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "JudgeReport",
                    '{"decision":"accept_with_minor_revision","accuracy_score":5,'
                    '"adaptation_score":4,"disputes":[],"rationale":"理由"}',
                )
                + "你是审核裁判 Agent，只评估，不生成教学正文。",
            ),
            (
                "user",
                "专家 A：{expert_a_draft}\n专家 B：{expert_b_draft}\n请审核并裁决。",
            ),
        ]
    )
    feedback_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                _schema_note(
                    "FeedbackResult",
                    '{"questionnaire":["问题"],"next_action":"下一步",'
                    '"profile_update_hint":"画像更新建议"}',
                ),
            ),
            (
                "user",
                "最终教学主题：{user_input}\n裁判报告：{judge_report}\n请生成反馈闭环建议。",
            ),
        ]
    )

    def diagnosis_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(diagnosis_prompt, user_input=state["user_input"]),
            temperature=0.5,
            agent="diagnosis",
        )
        profile = LearnerProfile.model_validate(raw)
        return {
            "learner_profile": profile.model_dump(),
            "events": [completed_event("diagnosis", "generated learner profile with LLM")],
        }

    def planner_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(
                planner_prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=0.5,
            agent="planner",
        )
        if not isinstance(raw, list):
            raise LLMProviderError("Planner Agent must return a JSON array.")
        path = [LearningPathItem.model_validate(item) for item in raw]
        return {
            "learning_path": [item.model_dump() for item in path],
            "events": [completed_event("planner", "planned learning path with LLM")],
        }

    def retrieve_context_node(state: StateDict) -> dict[str, Any]:
        chunks = [
            RetrievalChunk(
                chunk_id="patent-law-22",
                source="专利法",
                citation="第二十二条",
                text="授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。",
            )
        ]
        return {
            "retrieval_context": [chunk.model_dump() for chunk in chunks],
            "events": [completed_event("retrieve_context", "attached mock patent law context")],
        }

    def expert_a_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(
                expert_a_prompt,
                user_input=state["user_input"],
                retrieval_context=state.get("retrieval_context", []),
            ),
            temperature=0.4,
            agent="expert_a",
        )
        draft = ExpertDraft.model_validate(raw)
        return {
            "expert_a_draft": draft.model_dump(),
            "events": [completed_event("expert_a", "generated expert A draft with LLM")],
        }

    def expert_b_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(
                expert_b_prompt,
                user_input=state["user_input"],
                learner_profile=state.get("learner_profile", {}),
            ),
            temperature=0.7,
            agent="expert_b",
        )
        draft = ExpertDraft.model_validate(raw)
        return {
            "expert_b_draft": draft.model_dump(),
            "events": [completed_event("expert_b", "generated expert B draft with LLM")],
        }

    def judge_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(
                judge_prompt,
                expert_a_draft=state.get("expert_a_draft", {}),
                expert_b_draft=state.get("expert_b_draft", {}),
            ),
            temperature=0.0,
            agent="judge",
        )
        report = JudgeReport.model_validate(raw)
        return {
            "judge_report": report.model_dump(),
            "events": [completed_event("judge", "reviewed expert drafts with LLM")],
        }

    def feedback_node(state: StateDict) -> dict[str, Any]:
        raw = llm_client.generate_json(
            _messages(
                feedback_prompt,
                user_input=state["user_input"],
                judge_report=state.get("judge_report", {}),
            ),
            temperature=0.5,
            agent="feedback",
        )
        feedback = FeedbackResult.model_validate(raw)
        return {
            "feedback_result": feedback.model_dump(),
            "events": [completed_event("feedback", "created feedback suggestion with LLM")],
        }

    return {
        "diagnosis": diagnosis_node,
        "planner": planner_node,
        "retrieve_context": retrieve_context_node,
        "expert_a": expert_a_node,
        "expert_b": expert_b_node,
        "judge": judge_node,
        "feedback": feedback_node,
    }


def finalize_node(state: StateDict) -> dict[str, Any]:
    from backend.app.schemas.state import FinalAnswer

    expert_a = state.get("expert_a_draft", {})
    expert_b = state.get("expert_b_draft", {})
    final = FinalAnswer(
        title="个性化知识产权学习建议",
        content="\n\n".join(
            part
            for part in [
                str(expert_a.get("teaching_content", "")),
                str(expert_b.get("teaching_content", "")),
            ]
            if part
        ),
        sources=[chunk["citation"] for chunk in state.get("retrieval_context", [])],
    )
    return {
        "final_answer": final.model_dump(),
        "events": [completed_event("finalize", "assembled final teaching answer")],
    }
