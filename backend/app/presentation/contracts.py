"""Typed contracts shared by presentation providers and workflow state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PresentationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PresentationSlide(PresentationContract):
    id: str
    order: int = Field(ge=1)
    type: str
    title: str
    content: dict[str, object] = Field(default_factory=dict)
    narration: str
    source_block_id: str | None = None


class PresentationCoursePackage(PresentationContract):
    title: str | None = None
    teaching_content: str | None = None
    legal_basis: list[object] = Field(default_factory=list)
    block_plan: dict[str, object] | None = None
    assessment: dict[str, object] | None = None


class PresentationSource(PresentationContract):
    course_package: PresentationCoursePackage
    slides: list[PresentationSlide] = Field(min_length=1)


PresentationTheme = Literal[
    "patent_exam_classic",
    "legal_case_analysis",
    "technical_blueprint",
    "minimal_academic",
    "practice_workshop",
    "patent_blue",
    "professional_green",
    "warm_orange",
]
PresentationLayout = Literal[
    "title", "content", "two_column", "process", "comparison", "summary",
    "cover_minimal", "cover_split", "content_rule_card", "content_bullet_grid",
    "irac_flow", "legal_citation_focus", "case_analysis_split", "comparison_matrix",
    "timeline_process", "exam_checklist", "summary_roadmap",
]
PresentationTemplate = Literal[
    "cover_minimal", "cover_split", "content_rule_card", "content_bullet_grid",
    "irac_flow", "legal_citation_focus", "case_analysis_split", "comparison_matrix",
    "timeline_process", "exam_checklist", "summary_roadmap",
]


class PresentationVisualSlide(PresentationContract):
    id: str
    order: int = Field(ge=1)
    layout: PresentationLayout
    template_id: PresentationTemplate | None = None
    title: str
    subtitle: str | None = None
    body: str | None = None
    bullets: list[str] = Field(default_factory=list, max_length=6)
    steps: list[str] = Field(default_factory=list, max_length=6)
    left_title: str | None = None
    left_items: list[str] = Field(default_factory=list, max_length=6)
    right_title: str | None = None
    right_items: list[str] = Field(default_factory=list, max_length=6)
    legal_reference: str | None = None
    legal_summary: str | None = None
    issue: str | None = None
    rule: str | None = None
    application: str | None = None
    conclusion: str | None = None
    warning: str | None = None
    speaker_notes: str


class PresentationDesign(PresentationContract):
    title: str
    theme: PresentationTheme = "patent_exam_classic"
    slides: list[PresentationVisualSlide] = Field(min_length=1)


class PresentationArtifact(PresentationContract):
    artifact_id: str
    path: str
    title: str
    mime_type: Literal[
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ]
    sha256: str
    size_bytes: int = Field(ge=1)
    created_at: str


class PresentationResult(PresentationContract):
    status: Literal["generated", "skipped", "degraded"]
    provider: str
    source_slide_count: int = Field(ge=0)
    speaker_notes_status: Literal["written", "unsupported", "unknown"]
    artifact: PresentationArtifact | None = None
    error_summary: str | None = None
