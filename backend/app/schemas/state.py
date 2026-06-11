"""Shared state and structured output models for the mock Agent workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    node: str
    status: Literal["started", "completed", "failed"]
    message: str


class LearnerProfile(BaseModel):
    education_background: str
    knowledge_level: Literal["beginner", "intermediate", "advanced"]
    learning_style: str
    weak_points: list[str]
    learning_goal: str


class LearningPathItem(BaseModel):
    node_id: str
    node_name: str
    duration_min: int = Field(gt=0)
    strategy: str
    prerequisites: list[str] = Field(default_factory=list)


class RetrievalChunk(BaseModel):
    chunk_id: str
    source: str
    citation: str
    text: str


class ExpertDraft(BaseModel):
    expert: Literal["expert_a", "expert_b"]
    style: str
    knowledge_points: list[str]
    legal_basis: list[str]
    teaching_content: str
    risks: list[str] = Field(default_factory=list)


class JudgeReport(BaseModel):
    decision: Literal["accept", "accept_with_minor_revision", "revise"]
    accuracy_score: int = Field(ge=1, le=5)
    adaptation_score: int = Field(ge=1, le=5)
    disputes: list[str]
    rationale: str


class FeedbackResult(BaseModel):
    questionnaire: list[str]
    next_action: str
    profile_update_hint: str


class FinalAnswer(BaseModel):
    title: str
    content: str
    sources: list[str]


class StateDict(TypedDict):
    session_id: str
    user_input: str
    events: Annotated[list[dict[str, Any]], operator.add]
    learner_profile: NotRequired[dict[str, Any]]
    learning_path: NotRequired[list[dict[str, Any]]]
    retrieval_context: NotRequired[list[dict[str, Any]]]
    expert_a_draft: NotRequired[dict[str, Any]]
    expert_b_draft: NotRequired[dict[str, Any]]
    judge_report: NotRequired[dict[str, Any]]
    feedback_result: NotRequired[dict[str, Any]]
    final_answer: NotRequired[dict[str, Any]]


def completed_event(node: str, message: str) -> dict[str, Any]:
    return AgentEvent(node=node, status="completed", message=message).model_dump()
