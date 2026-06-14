"""Shared state and structured output contracts for the Agent workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

AgentNode = Literal[
    "diagnosis",
    "planner",
    "retrieve_context",
    "expert_a",
    "expert_b",
    "judge",
    "feedback",
    "finalize",
    "route",
    "tool_agent",
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
    status: Literal["started", "completed", "failed", "retrying", "debate_round"]
    message: str
    round: int | None = Field(default=None, ge=1, le=3)
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
        "final_answer",
        "route_decision",
        "chat_answer",
    ]
    path: str
    created_by: Literal[
        "diagnosis", "planner", "retrieve_context", "expert_a", "expert_b", "judge", "feedback", "finalize",
        "route", "tool_agent", "chat_answer",
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
    irac: IRAC | None = None
    interactive_questions: list[str] | None = None
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


class FinalAnswer(ContractModel):
    title: str
    content: str
    sources: list[str]
    judge_summary: str | None = None
    next_questions: list[str] | None = None
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


class StateDict(TypedDict):
    session_id: str
    user_input: str
    events: Annotated[list[dict[str, Any]], operator.add]
    artifacts: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    learner_profile: NotRequired[dict[str, Any]]
    learning_path: NotRequired[list[dict[str, Any]]]
    retrieval_context: NotRequired[list[dict[str, Any]]]
    expert_a_draft: NotRequired[dict[str, Any]]
    expert_b_draft: NotRequired[dict[str, Any]]
    judge_report: NotRequired[dict[str, Any]]
    feedback_result: NotRequired[dict[str, Any]]
    final_answer: NotRequired[dict[str, Any]]
    debate_round: NotRequired[int]
    max_debate_rounds: NotRequired[int]
    revision_history: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    intent: NotRequired[str]  # "teach" | "chat" | "diagnose"
    chat_answer: NotRequired[dict[str, Any]]


def _inline_array_item_schema(schema: dict[str, Any]) -> dict[str, Any]:
    item = schema.get("items", {})
    ref = item.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        schema = dict(schema)
        schema["items"] = schema.get("$defs", {})[name]
    return schema


def agent_output_json_schemas() -> dict[str, dict[str, Any]]:
    planner_schema = _inline_array_item_schema(
        TypeAdapter(list[LearningPathItem]).json_schema(mode="validation")
    )
    expert_schema = ExpertDraft.model_json_schema(mode="validation")
    return {
        "diagnosis": LearnerProfile.model_json_schema(mode="validation"),
        "planner": planner_schema,
        "expert_a": expert_schema,
        "expert_b": expert_schema,
        "judge": JudgeReport.model_json_schema(mode="validation"),
        "feedback": FeedbackResult.model_json_schema(mode="validation"),
        "finalize": FinalAnswer.model_json_schema(mode="validation"),
        "route": IntentResult.model_json_schema(mode="validation"),
        "chat_answer": ChatAnswer.model_json_schema(mode="validation"),
    }


def completed_event(node: AgentNode, message: str) -> dict[str, Any]:
    return AgentEvent(node=node, status="completed", message=message).model_dump()
