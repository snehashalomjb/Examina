"""Exam configuration schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import Difficulty, ExamStatus, ExamType, QuestionCategory, QuestionType
from app.schemas.common import ORMModel


class SelectionRule(BaseModel):
    question_type: QuestionType
    difficulty: Difficulty | None = None
    count: int = Field(..., gt=0, le=200)
    #: Optional category filter – corporate section rules filter on category, not subject.
    category: QuestionCategory | None = None
    topic: str | None = None


class SelectionRules(BaseModel):
    rules: list[SelectionRule] = Field(..., min_length=1)


class ProctorConfig(BaseModel):
    webcam_enabled: bool = True
    gaze_tracking_enabled: bool = True
    gaze_sensitivity: float = Field(0.6, ge=0.0, le=1.0)
    max_tab_switches: int = Field(3, ge=0, le=50)
    flag_on_score: float = Field(45.0, ge=0)
    terminate_on_score: float = Field(100.0, gt=0)
    snapshot_interval_seconds: int = Field(60, ge=10, le=600)
    require_fullscreen: bool = True
    block_copy_paste: bool = True
    weights: dict[str, float] | None = None

    @model_validator(mode="after")
    def terminate_above_flag(self) -> ProctorConfig:
        if self.terminate_on_score <= self.flag_on_score:
            raise ValueError("terminate_on_score must be greater than flag_on_score")
        return self


class GradingConfig(BaseModel):
    partial_credit_multi_select: bool = False
    auto_publish_results: bool = False
    grader_provider: str | None = None
    grader_model: str | None = None


# ------------------------------------------------------------------ sections


class SectionCreate(BaseModel):
    """Configuration for one named section of a multi-section exam."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    order_index: int = Field(0, ge=0)
    selection_rules: SelectionRules
    marks_per_question: float | None = Field(default=None, gt=0)
    negative_marks: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, gt=0, le=600)


class SectionOut(ORMModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    name: str
    description: str | None = None
    order_index: int
    selection_rules: dict[str, Any]
    marks_per_question: float | None = None
    negative_marks: float | None = None
    duration_minutes: int | None = None
    created_at: datetime


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)
    selection_rules: SelectionRules | None = None
    marks_per_question: float | None = Field(default=None, gt=0)
    negative_marks: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, gt=0, le=600)


# ------------------------------------------------------------------ exams


class ExamCreate(BaseModel):
    #: Which mode this exam runs in. Defaults to academic so existing API callers are unchanged.
    exam_type: ExamType = ExamType.ACADEMIC

    subject_id: uuid.UUID
    title: str = Field(..., min_length=3, max_length=200)
    description: str | None = None
    instructions: str | None = None
    duration_minutes: int = Field(..., gt=0, le=600)
    starts_at: datetime
    ends_at: datetime
    selection_rules: SelectionRules
    randomize: bool = True
    shuffle_options: bool = True
    negative_marking: bool = False
    proctor_config: ProctorConfig = Field(default_factory=ProctorConfig)
    grading_config: GradingConfig = Field(default_factory=GradingConfig)
    question_ids: list[uuid.UUID] = Field(default_factory=list)

    # --- passing threshold (both modes) ---
    passing_percentage: float | None = Field(default=None, ge=0, le=100)
    declared_total_marks: float | None = Field(default=None, gt=0)

    # --- academic mode ---
    course: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    semester: str | None = Field(default=None, max_length=40)

    # --- corporate mode ---
    company_name: str | None = Field(default=None, max_length=200)
    job_role: str | None = Field(default=None, max_length=200)

    #: Sections to create atomically with the exam. Empty = single implicit section
    #: (which is how every Milestone 1 exam still works).
    sections: list[SectionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def window_is_sane(self) -> ExamCreate:
        if self.ends_at <= self.starts_at:
            raise ValueError("The exam window must end after it starts")
        window_minutes = (self.ends_at - self.starts_at).total_seconds() / 60
        if self.duration_minutes > window_minutes:
            raise ValueError(
                f"Duration ({self.duration_minutes} min) exceeds the exam window "
                f"({int(window_minutes)} min)"
            )
        return self


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    instructions: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=600)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    selection_rules: SelectionRules | None = None
    randomize: bool | None = None
    shuffle_options: bool | None = None
    negative_marking: bool | None = None
    proctor_config: ProctorConfig | None = None
    grading_config: GradingConfig | None = None
    question_ids: list[uuid.UUID] | None = None

    passing_percentage: float | None = Field(default=None, ge=0, le=100)
    declared_total_marks: float | None = Field(default=None, gt=0)
    course: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    semester: str | None = Field(default=None, max_length=40)
    company_name: str | None = Field(default=None, max_length=200)
    job_role: str | None = Field(default=None, max_length=200)


class ExamOut(ORMModel):
    id: uuid.UUID
    exam_type: ExamType = ExamType.ACADEMIC
    subject_id: uuid.UUID
    title: str
    description: str | None = None
    instructions: str | None = None
    duration_minutes: int
    starts_at: datetime
    ends_at: datetime
    status: ExamStatus
    randomize: bool
    shuffle_options: bool
    negative_marking: bool
    results_published: bool
    selection_rules: dict[str, Any]
    proctor_config: dict[str, Any]
    grading_config: dict[str, Any]
    created_at: datetime
    pool_size: int = 0
    total_questions: int = 0
    subject_name: str | None = None

    # Mode-specific
    passing_percentage: float | None = None
    declared_total_marks: float | None = None
    # Academic
    course: str | None = None
    department: str | None = None
    semester: str | None = None
    # Corporate
    company_name: str | None = None
    job_role: str | None = None

    # Sections (populated inline for detail views)
    sections: list[SectionOut] = Field(default_factory=list)


class ExamPoolCheck(BaseModel):
    can_publish: bool
    problems: list[str] = Field(default_factory=list)
    pool_size: int
    required_count: int


class PaperPreviewEntry(BaseModel):
    question_id: uuid.UUID
    body: str
    question_type: QuestionType
    difficulty: Difficulty
    marks: float
    option_order: list[uuid.UUID] = Field(default_factory=list)


class PaperPreview(BaseModel):
    seed: str
    candidate_id: uuid.UUID
    total_marks: float
    entries: list[PaperPreviewEntry]
