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
