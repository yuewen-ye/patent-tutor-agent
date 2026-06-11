"""Mock Agent nodes for the first LangGraph workflow MVP."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.schemas.state import (
    ExpertDraft,
    FeedbackResult,
    FinalAnswer,
    JudgeReport,
    LearnerProfile,
    LearningPathItem,
    RetrievalChunk,
    StateDict,
    completed_event,
)

DIAGNOSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是学情诊断 Agent，输出稳定的五维学习者画像 JSON。"),
        ("human", "学习目标：{user_input}"),
    ]
)

EXPERT_A_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是保守严谨的专利法专家 A，优先保证法条准确。"),
        ("human", "结合检索上下文解释：{user_input}"),
    ]
)

EXPERT_B_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是生动灵活的教学专家 B，使用案例和类比帮助理解。"),
        ("human", "结合学习者画像解释：{user_input}"),
    ]
)


def diagnosis_node(state: StateDict) -> dict[str, Any]:
    DIAGNOSIS_PROMPT.format_messages(user_input=state["user_input"])
    profile = LearnerProfile(
        education_background="patent_exam_candidate",
        knowledge_level="beginner",
        learning_style="case_first_then_rule",
        weak_points=["法条概念辨析", "案例适用"],
        learning_goal=state["user_input"],
    )
    return {
        "learner_profile": profile.model_dump(),
        "events": [completed_event("diagnosis", "generated learner profile")],
    }


def planner_node(state: StateDict) -> dict[str, Any]:
    path = [
        LearningPathItem(
            node_id="patentability-basic",
            node_name="专利授权条件基础",
            duration_min=20,
            strategy="先建立新颖性、创造性、实用性的边界",
        ),
        LearningPathItem(
            node_id="novelty-vs-inventiveness",
            node_name="新颖性与创造性对比",
            duration_min=25,
            strategy="用同一案例分别判断两个条件",
            prerequisites=["patentability-basic"],
        ),
    ]
    return {
        "learning_path": [item.model_dump() for item in path],
        "events": [completed_event("planner", "planned two-step learning path")],
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
    EXPERT_A_PROMPT.format_messages(user_input=state["user_input"])
    draft = ExpertDraft(
        expert="expert_a",
        style="conservative_precise",
        knowledge_points=["新颖性看是否属于现有技术", "创造性看是否具有突出的实质性特点和显著进步"],
        legal_basis=["专利法第二十二条"],
        teaching_content="先按法条定义拆解，再用现有技术对比判断新颖性和创造性。",
        risks=["不能把新颖性和创造性的判断标准混用"],
    )
    return {
        "expert_a_draft": draft.model_dump(),
        "events": [completed_event("expert_a", "generated conservative legal draft")],
    }


def expert_b_node(state: StateDict) -> dict[str, Any]:
    EXPERT_B_PROMPT.format_messages(user_input=state["user_input"])
    draft = ExpertDraft(
        expert="expert_b",
        style="vivid_teaching",
        knowledge_points=["新颖性像确认答案是不是已经公开", "创造性像判断改进是否足够不容易想到"],
        legal_basis=["专利法第二十二条"],
        teaching_content="用考试题的排除法讲解：先排掉已公开方案，再判断改进是否显著。",
        risks=["类比必须回到法条，不替代法律判断"],
    )
    return {
        "expert_b_draft": draft.model_dump(),
        "events": [completed_event("expert_b", "generated vivid teaching draft")],
    }


def judge_node(state: StateDict) -> dict[str, Any]:
    report = JudgeReport(
        decision="accept_with_minor_revision",
        accuracy_score=5,
        adaptation_score=4,
        disputes=["B 的类比表达需要明确回扣专利法第二十二条"],
        rationale="A 的法条边界准确，B 的教学表达有助理解；最终答案应合并两者并保留法条依据。",
    )
    return {
        "judge_report": report.model_dump(),
        "events": [completed_event("judge", "reviewed both expert drafts")],
    }


def feedback_node(state: StateDict) -> dict[str, Any]:
    feedback = FeedbackResult(
        questionnaire=["你能否用一句话区分新颖性和创造性？", "你是否需要更多案例练习？"],
        next_action="安排 3 道新颖性/创造性对比题，观察薄弱点是否仍集中在概念辨析。",
        profile_update_hint="若连续答错创造性判断题，提高创造性技能点的复习权重。",
    )
    return {
        "feedback_result": feedback.model_dump(),
        "events": [completed_event("feedback", "created feedback loop suggestion")],
    }


def finalize_node(state: StateDict) -> dict[str, Any]:
    final = FinalAnswer(
        title="新颖性与创造性的入门区分",
        content=(
            "新颖性主要判断方案是否已经被现有技术公开；创造性进一步判断该方案"
            "相对于现有技术是否具有突出的实质性特点和显著进步。学习时先查法条，"
            "再用案例分别套用两个判断标准。"
        ),
        sources=[chunk["citation"] for chunk in state.get("retrieval_context", [])],
    )
    return {
        "final_answer": final.model_dump(),
        "events": [completed_event("finalize", "assembled final teaching answer")],
    }
