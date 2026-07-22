"""Shared state and structured output contracts for the Agent workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field

AgentNode = Literal[
    "diagnosis_feedback",
    "planner",
    "expert_a",
    "expert_b",
    "judge",
    "route",
    "retrieve_context",
    "chat_answer",
]
ErrorPattern = Literal[
    "unknown",
    "no_prior_knowledge",
    "concept_confusion",
    "application_gap",
    "careless",
    "overconfidence",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentEvent(ContractModel):
    node: AgentNode
    status: Literal["started", "completed", "failed", "retrying"]
    message: str
    timestamp: str | None = None
    error_code: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class MarkdownArtifact(ContractModel):
    artifact_id: str
    kind: Literal[
        "learner_profile_report",
        "learning_path_plan",
        "retrieval_context",
        "expert_draft",
        "judge_report",
        "feedback_report",
        "route_decision",
        "chat_answer",
        "cross_review",
        "expert_revision",
        "course_package",
        "dual_axis_snapshot",
        "questionnaire",
        "questionnaire_submission",
        "exercise_submission",
        "grading_report",
    ]
    path: str
    created_by: Literal[
        "diagnosis_feedback",
        "planner",
        "retrieve_context",
        "expert_a",
        "expert_b",
        "judge",
        "route",
        "chat_answer",
        "learner",
    ]
    title: str
    mime_type: Literal["text/markdown"] = "text/markdown"
    sha256: str | None = None
    created_at: str | None = None


AffectState = Literal["focused", "confused", "anxious", "interested"]


class KnowledgeNodeState(ContractModel):
    """单个知识节点上的学习者 BKT 状态（图节点状态值，非图结构定义）。"""

    pl: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)
    observations: int = Field(default=0, ge=0)
    low_confidence: bool = False


class CognitionProfile(ContractModel):
    """布鲁姆六层认知能力分布（0~1）。"""

    remember: float = Field(ge=0.0, le=1.0)
    understand: float = Field(ge=0.0, le=1.0)
    apply: float = Field(ge=0.0, le=1.0)
    analyze: float = Field(ge=0.0, le=1.0)
    evaluate: float = Field(ge=0.0, le=1.0)
    create: float = Field(ge=0.0, le=1.0)
    method: str | None = None


class StyleAxis(ContractModel):
    """Felder-Silverman 单轴：chosen 取向 + strength 强度。"""

    chosen: str
    strength: float = Field(ge=0.0, le=1.0)


class StyleProfile(ContractModel):
    """Felder-Silverman 四轴学习风格。"""

    perception: StyleAxis
    input: StyleAxis
    processing: StyleAxis
    understanding: StyleAxis


class ProgressProfile(ContractModel):
    """进度状态。"""

    completed_nodes: list[str] = Field(default_factory=list)
    current_node: str | None = None
    pending_nodes: list[str] = Field(default_factory=list)
    avg_time_per_node_min: float | None = Field(default=None, ge=0)
    overall_completion_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class AffectProfile(ContractModel):
    """情感倾向。"""

    primary_state: AffectState
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)


class FiveDimensions(ContractModel):
    """学习者五维画像快照（学习者在已有知识图上的状态，非图结构本身）。

    顶层 5 个维度键均须齐全（完整快照）；knowledge 为逐知识节点 dict
    （key=节点 id，value=KnowledgeNodeState）。
    """

    knowledge: dict[str, KnowledgeNodeState]
    cognition: CognitionProfile
    style: StyleProfile
    progress: ProgressProfile
    affect: AffectProfile


class LearnerProfile(ContractModel):
    education_background: str
    knowledge_level: Literal["beginner", "intermediate", "advanced"]
    learning_style: str
    weak_points: list[str]
    learning_goal: str
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    five_dimensions: FiveDimensions | None = None
    markdown_artifact: MarkdownArtifact | None = None


class LearningPathItem(ContractModel):
    node_id: str = Field(pattern="^[a-z0-9][a-z0-9-]*$")
    node_name: str
    duration_min: int = Field(ge=1)
    strategy: str
    prerequisites: list[str] = Field(default_factory=list)
    difficulty_cap: str | None = None
    target_ability: str | None = None
    assessment: str | None = None
    markdown_artifact: MarkdownArtifact | None = None


class RetrievalMetadata(ContractModel):
    doc_type: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    law_article: str | None = None
    retrieval_method: Literal["bm25", "vector", "hybrid", "manual"] | None = None


class RetrievalChunk(ContractModel):
    chunk_id: str
    source: str
    citation: str
    text: str
    score: float | None = Field(default=None, ge=0)
    rerank_score: float | None = Field(default=None, ge=0)
    metadata: RetrievalMetadata | None = None


class IRAC(ContractModel):
    issue: str | None = None
    rule: str | None = None
    application: str | None = None
    conclusion: str | None = None


class KnowledgePoint(ContractModel):
    node_id: str
    kc_name: str


class BlockPlan(ContractModel):
    block_id: str
    block_type: Literal[
        "legal_anchor",
        "knowledge_synthesis",
        "assessment",
        "anchor_scenario",
        "global_framework",
        "worked_example",
        "decision_flow",
        "verbal_explanation",
        "predict_activate",
        "reflect_prompt",
        "mnemonic",
        "common_pitfall",
        "summary_card",
    ]
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    # 十个自适应模块均为共享模块，A/B 均可主张；chosen_by 仅记录融合后的实际归属，非预设默认归属
    chosen_by: Literal["[A]", "[B]", "[A+B融合]"] | None = None
    trigger: str | None = None
    rationale: str | None = None
    adapts_to: list[str] = Field(default_factory=list)
    source: str | None = None


class BlockPlanPackage(ContractModel):
    """整合稿的板块方案复合包（spec v3：node + blocks[] + 顺序/预算/共识标记）。"""

    node: str | None = None
    learner_id: str | None = None
    blocks: list[BlockPlan] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    debate_resolved: bool = False


class InteractiveQuestion(ContractModel):
    qid: str
    category: str
    difficulty: str
    source_tag: str | None = None
    kc_node_id: str | None = None
    question: str
    answer: str | None = None
    options: list[str] | None = None


class AssessmentItem(ContractModel):
    qid: str
    category: str
    difficulty: str
    question: str
    answer: str | None = None
    kc: str | None = None
    source: str | None = None
    evidence: str | None = None


class KnowledgeSynthesis(ContractModel):
    node: str | None = None
    coverage: list[dict[str, Any]] = Field(default_factory=list)
    confusable_pairs: list[dict[str, Any]] | None = None


class Assessment(ContractModel):
    items: list[AssessmentItem] = Field(default_factory=list)


class LegalBasisItem(ContractModel):
    """法条溯源条目（spec v3：article + source 双字段，供幻觉率审计）。"""

    article: str
    source: str | None = None


class RiskItem(ContractModel):
    """风险点条目（spec v3：risk 描述 + 关联节点）。"""

    risk: str
    related_node_id: str | None = None


class ExpertDraft(ContractModel):
    expert: Literal["expert_a", "expert_b", "A+B融合"]
    style: Literal["conservative", "accessible", "fused"]
    knowledge_points: list[KnowledgePoint] = Field(min_length=1)
    legal_basis: list[LegalBasisItem] = Field(min_length=1)
    teaching_content: str
    risks: list[RiskItem] = Field(default_factory=list)
    draft_stage: Literal["debate", "integration"] | None = None
    irac: IRAC | None = None
    interactive_questions: list[InteractiveQuestion] | None = None
    block_plan: BlockPlanPackage | None = None
    knowledge_synthesis: KnowledgeSynthesis | None = None
    assessment: Assessment | None = None
    exercises: list[dict[str, Any]] | None = None
    markdown_artifact: MarkdownArtifact | None = None


class RevisionRequest(ContractModel):
    target: Literal["expert_a", "expert_b", "both"]
    issue: str
    required_change: str
    basis: str | None = None


class ToulminCheck(ContractModel):
    claim: str | None = None
    data: str | None = None
    warrant: str | None = None
    backing: str | None = None
    qualifier: str | None = None
    rebuttal: str | None = None


class AttackRelation(ContractModel):
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    reason: str


class DebateReport(ContractModel):
    round: int | None = Field(default=None, ge=1, le=3)
    toulmin_checks: list[ToulminCheck] | None = None
    attack_relations: list[AttackRelation] | None = None


class JudgeReport(ContractModel):
    decision: Literal["accept", "accept_with_minor_revision", "revise"]
    accuracy_score: int = Field(ge=1, le=5)
    adaptation_score: int = Field(ge=1, le=5)
    completeness_score: int = Field(default=3, ge=1, le=5)
    adaptation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    disputes: list[str]
    rationale: str
    revision_requests: list[RevisionRequest] | None = None
    debate: DebateReport | None = None
    markdown_artifact: MarkdownArtifact | None = None


class BKTUpdate(ContractModel):
    skill_id: str | None = None
    observed_correct: bool | None = None
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class TeachingEvaluation(ContractModel):
    """教学评价反馈（spec v3：面向教学本身的评价，回写 five_dimensions.affect）。"""

    questions: list[str] = Field(min_length=1)
    evaluation_signals: list[str] | None = None
    feeds: str | None = None


class FeedbackResult(ContractModel):
    questionnaire: list[str] = Field(min_length=1)
    teaching_evaluation: TeachingEvaluation | None = None
    next_action: str
    profile_update_hint: str
    five_dimensions: FiveDimensions
    bkt_update: BKTUpdate | None = None
    markdown_artifact: MarkdownArtifact | None = None


class IntentResult(ContractModel):
    intent: Literal["teach", "chat", "diagnose"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ChatAnswer(ContractModel):
    content: str
    sources: list[str] = Field(default_factory=list)
    title: str | None = None
    markdown_artifact: MarkdownArtifact | None = None


class WorkflowError(ContractModel):
    session_id: str
    node: str
    error_code: Literal[
        "llm_timeout",
        "llm_bad_json",
        "schema_validation_failed",
        "rag_unavailable",
        "provider_rate_limited",
        "unknown",
    ]
    message: str
    recoverable: bool
    retry_after_sec: int | None = Field(default=None, ge=0)


class ReviewOpinion(ContractModel):
    category: Literal["🔴", "🟡", "🟢", "🔵", "🌉"]
    location: str
    target_wrote: str
    problem: str
    suggestion: str
    basis: str | None = None
    legal_basis: list[str] | None = None


class CrossReview(ContractModel):
    reviewer: Literal["expert_a", "expert_b"]
    target: Literal["expert_a", "expert_b"]
    review_opinions: list[ReviewOpinion] = Field(min_length=1, max_length=7)
    positive_confirmation: str | None = None
    overall_assessment: str
    legal_basis: list[str] | None = None


class RevisionItem(ContractModel):
    review_id: int
    review_category: str
    review_summary: str
    response: str
    status: Literal["accepted", "rejected", "needs_arbitration"]


class RevisionRecord(ContractModel):
    agent: Literal["expert_a", "expert_b"]
    revisions: list[RevisionItem]
    unresolved_disputes: list[dict[str, Any]] | None = None
    modified_paragraphs: list[str] | None = None
    modification_tags: list[str] | None = None


class JointSection(ContractModel):
    heading: str
    content: str
    source: Literal["A", "B", "A+B融合", "B-过渡"]
    note: str | None = None


class JointSynthesis(ContractModel):
    node_id: str | None = None
    title: str
    sections: list[JointSection]
    transition_notes: list[dict[str, Any]] | None = None
    unresolved_in_synthesis: list[dict[str, Any]] | None = None


class LightweightReview(ContractModel):
    reviewed_changes: list[dict[str, Any]]
    verdict: Literal["acceptable", "needs_more_work"]
    unresolved: list[str] | None = None


class StateDict(TypedDict):
    session_id: str
    user_input: str
    events: Annotated[list[dict[str, Any]], operator.add]
    artifacts: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    learner_profile: NotRequired[dict[str, Any]]
    learner_profile_update: NotRequired[dict[str, Any]]
    grading_report: NotRequired[list[dict[str, Any]]]
    learning_path: NotRequired[list[dict[str, Any]]]
    retrieval_context: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    expert_a_draft: NotRequired[dict[str, Any]]
    expert_b_draft: NotRequired[dict[str, Any]]
    judge_report: NotRequired[dict[str, Any]]
    feedback_result: NotRequired[dict[str, Any]]
    intent: NotRequired[str]  # "teach" | "chat" | "diagnose"
    teach_phase: NotRequired[Literal["debate", "integration"]]
    chat_answer: NotRequired[dict[str, Any]]
    workflow_mode: NotRequired[Literal["auto", "teach", "chat", "diagnose", "feedback"]]
    input_payload: NotRequired[dict[str, Any]]
    parent_session_id: NotRequired[str | None]
    diagnosis_feedback_phase: NotRequired[Literal["diagnosis", "feedback"]]
    expert_phase: NotRequired[Literal["draft", "cross_review", "revision", "integration"]]
    dual_axis_snapshot: NotRequired[dict[str, Any]]
    path_decision: NotRequired[dict[str, Any]]
    expert_a_cross_review: NotRequired[dict[str, Any]]
    expert_b_cross_review: NotRequired[dict[str, Any]]
    expert_a_revision: NotRequired[dict[str, Any]]
    expert_b_revision: NotRequired[dict[str, Any]]
    course_package: NotRequired[dict[str, Any]]
    workflow_status: NotRequired[Literal["running", "completed", "failed", "canceled"]]


def agent_output_json_schemas() -> dict[str, dict[str, Any]]:
    expert_schema = ExpertDraft.model_json_schema(mode="validation")
    return {
        "diagnosis_feedback_diagnosis": LearnerProfile.model_json_schema(mode="validation"),
        "expert_a": expert_schema,
        "expert_b": expert_schema,
        "judge": JudgeReport.model_json_schema(mode="validation"),
        "diagnosis_feedback_feedback": FeedbackResult.model_json_schema(mode="validation"),
        "route": IntentResult.model_json_schema(mode="validation"),
        "chat_answer": ChatAnswer.model_json_schema(mode="validation"),
    }


def completed_event(node: AgentNode, message: str) -> dict[str, Any]:
    return AgentEvent(node=node, status="completed", message=message).model_dump()
