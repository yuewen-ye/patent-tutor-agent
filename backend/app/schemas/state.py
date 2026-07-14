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


class LearnerProfile(ContractModel):
    education_background: str
    knowledge_level: Literal["beginner", "intermediate", "advanced"]
    learning_style: str
    weak_points: list[str]
    learning_goal: str
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    markdown_artifact: MarkdownArtifact | None = None


class LearningPathItem(ContractModel):
    node_id: str = Field(pattern="^[a-z0-9][a-z0-9-]*$")
    node_name: str
    duration_min: int = Field(ge=1)
    strategy: str
    prerequisites: list[str] = Field(default_factory=list)
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


class ExpertDraft(ContractModel):
    expert: Literal["expert_a", "expert_b"]
    style: Literal["conservative_precise", "vivid_teaching", "case_based", "exam_oriented"]
    knowledge_points: list[str] = Field(min_length=1)
    legal_basis: list[str] = Field(min_length=1)
    teaching_content: str
    risks: list[str] = Field(default_factory=list)
    draft_stage: Literal["debate", "integration"] | None = None
    irac: IRAC | None = None
    interactive_questions: list[str] | None = None
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


class FeedbackResult(ContractModel):
    questionnaire: list[str] = Field(min_length=1)
    next_action: str
    profile_update_hint: str
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


class CrossReview(ContractModel):
    reviewer: Literal["expert_a", "expert_b"]
    target: Literal["expert_a", "expert_b"]
    review_opinions: list[ReviewOpinion] = Field(min_length=1, max_length=7)
    positive_confirmation: str | None = None
    overall_assessment: str


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
