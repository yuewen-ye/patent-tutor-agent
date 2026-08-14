"""Typed contracts at the diagnostic question-bank boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiagnosticContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiagnosticQuestion(DiagnosticContract):
    id: str = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    p_g: float = Field(ge=0.0, le=1.0)
    p_s: float = Field(ge=0.0, le=1.0)
    question_text: str = Field(min_length=1)
    options: dict[str, str] = Field(min_length=2)
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_answer(self) -> DiagnosticQuestion:
        if self.correct_answer not in self.options:
            raise ValueError("correct_answer must reference an option")
        if len(set(self.skills)) != len(self.skills):
            raise ValueError("skills must not contain duplicates")
        return self

    def learner_view(self) -> dict[str, Any]:
        return {
            "question_id": self.id,
            "question_type": "knowledge",
            "skills": list(self.skills),
            "question_text": self.question_text,
            "options": dict(self.options),
        }


class DiagnosticAnswer(DiagnosticContract):
    question_id: str = Field(min_length=1)
    answer: str = Field(default="", description="答案文本；开放题跳过时可为空。")
    response_ms: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    skip: bool = Field(default=False, description="开放题跳过标记；仅画像阶段的开放题有效。")


class DiagnosticSessionSummary(DiagnosticContract):
    diagnostic_session_id: str
    status: Literal["running", "completed"]
    updated_at: str
    answered_questions: int = Field(default=0, ge=0)
    phase: Literal["knowledge", "profile", "completed"] = "knowledge"


class DiagnosticProgress(DiagnosticContract):
    diagnostic_session_id: str
    learner_id: str
    status: Literal["running", "completed"]
    phase: Literal["knowledge", "profile", "completed"] = "knowledge"
    answered_questions: int = Field(ge=0)
    max_questions: int = Field(ge=1)
    profile_answered_questions: int = Field(default=0, ge=0)
    profile_total_questions: int = Field(default=0, ge=0)
    termination_reason: str | None = None
    current_question: dict[str, Any] | None = None
    course_session_id: str | None = None
    knowledge_snapshot: dict[str, dict[str, Any]] | None = None
    answer_result: dict[str, Any] | None = None
    answer_log: list[dict[str, Any]] = Field(default_factory=list)
