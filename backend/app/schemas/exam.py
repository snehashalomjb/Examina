"""Exam configuration schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.db.models.enums import (
    SUPPORTED_LOCALES,
    Difficulty,
    ExamStatus,
    ExamType,
    QuestionCategory,
    QuestionType,
)
from app.schemas.common import ORMModel
from app.services.exam_status import effective_status as compute_effective_status


def _validate_languages(value: list[str]) -> list[str]:
    unknown = [code for code in value if code not in SUPPORTED_LOCALES]
    if unknown:
        raise ValueError(f"Unsupported language code(s): {', '.join(unknown)}")
    # "en" always leads and is never absent - the universal fallback for anything not
    # yet translated. De-duplicated, order-preserving otherwise.
    ordered = [code for code in value if code != "en"]
    return ["en", *dict.fromkeys(ordered)]


class SelectionRule(BaseModel):
    question_type: QuestionType
    difficulty: Difficulty | None = None
    count: int = Field(..., gt=0, le=200)
    #: Optional category filter – corporate section rules filter on category, not subject.
    category: QuestionCategory | None = None
    topic: str | None = None
    #: Optional subject narrowing, e.g. "Python MCQ 10" vs "SQL MCQ 10" in the same exam.
    subject_id: uuid.UUID | None = None
    #: Match-any tag narrowing.
    tags: list[str] | None = None


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
    require_microphone: bool = True
    require_single_display: bool = True
    min_bandwidth_mbps: float = Field(2.0, ge=0)
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
    #: Independent of ``randomize``, and off unless the examiner asks for it.
    shuffle_options: bool = False
    negative_marking: bool = False
    proctor_config: ProctorConfig = Field(default_factory=ProctorConfig)
    grading_config: GradingConfig = Field(default_factory=GradingConfig)
    question_ids: list[uuid.UUID] = Field(default_factory=list)

    # --- passing threshold (both modes) ---
    passing_percentage: float | None = Field(default=None, ge=0, le=100)
    declared_total_marks: float | None = Field(default=None, gt=0)
    #: How many sittings one candidate may take.
    max_attempts: int = Field(default=1, ge=1, le=10)
    #: A descriptive top-level tag shown to candidates. Null means "mixed" and never
    #: constrains which per-rule difficulties the pool can draw from.
    difficulty: Difficulty | None = None

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
    #: Per-locale text, e.g. {"te": {"title": "...", "instructions": "..."}}. ``en`` is
    #: always upserted from the fields above regardless of whether it's repeated here.
    translations: dict[str, dict[str, str]] | None = None
    #: Which languages the candidate's language selector offers for this exam, e.g.
    #: ["en", "hi", "ta"]. "en" is always included even if omitted here.
    enabled_languages: list[str] = Field(default_factory=lambda: ["en"])

    @field_validator("enabled_languages")
    @classmethod
    def _check_languages(cls, value: list[str]) -> list[str]:
        return _validate_languages(value)

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
    #: The complete section list. Omitted leaves the exam's sections alone; sent, it
    #: replaces them - matched by position, so a section keeps its id and its pinned
    #: questions across the wizard's autosaves.
    sections: list[SectionCreate] | None = None

    passing_percentage: float | None = Field(default=None, ge=0, le=100)
    declared_total_marks: float | None = Field(default=None, gt=0)
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    difficulty: Difficulty | None = None
    course: str | None = Field(default=None, max_length=150)
    department: str | None = Field(default=None, max_length=150)
    semester: str | None = Field(default=None, max_length=40)
    company_name: str | None = Field(default=None, max_length=200)
    job_role: str | None = Field(default=None, max_length=200)
    translations: dict[str, dict[str, str]] | None = None
    enabled_languages: list[str] | None = None

    @field_validator("enabled_languages")
    @classmethod
    def _check_languages(cls, value: list[str] | None) -> list[str] | None:
        return _validate_languages(value) if value is not None else None


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
    max_attempts: int = 1
    difficulty: Difficulty | None = None
    # Academic
    course: str | None = None
    department: str | None = None
    semester: str | None = None
    # Corporate
    company_name: str | None = None
    job_role: str | None = None

    # Sections (populated inline for detail views)
    sections: list[SectionOut] = Field(default_factory=list)
    #: Language codes the candidate's selector offers for this exam. Always leads with
    #: "en". Read from ``Exam.languages`` (derived from ``enabled_languages``).
    languages: list[str] = Field(default_factory=lambda: ["en"])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_status(self) -> str:
        """"draft" / "scheduled" / "live" / "completed" / "archived" - see
        ``app.services.exam_status``. Read-only, derived from ``status`` plus the
        window, so the admin/examiner exam tables can show what is actually happening
        without a second status column to keep in sync."""
        return compute_effective_status(
            status=self.status, starts_at=self.starts_at, ends_at=self.ends_at
        )


class ExamPoolCheck(BaseModel):
    can_publish: bool
    problems: list[str] = Field(default_factory=list)
    pool_size: int
    required_count: int


class PreviewOption(BaseModel):
    """An option as the candidate will see it.

    Note what is absent: ``is_correct``. This is the examiner previewing the candidate's
    view, and the candidate's view has never carried the key - so neither does this,
    even though the caller is staff and could have been trusted with it. A preview that
    quietly showed more than the real paper would be worth nothing as a check.
    """

    id: uuid.UUID
    text: str
    image_url: str | None = None


class PaperPreviewEntry(BaseModel):
    question_id: uuid.UUID
    body: str
    question_type: QuestionType
    difficulty: Difficulty
    marks: float
    negative_marks: float = 0.0
    topic: str | None = None
    #: Diagram the question is *about*, if any - distinct from an image-upload answer.
    image_url: str | None = None
    #: Which section this entry sits under, or None for an exam with no sections.
    section_id: uuid.UUID | None = None
    option_order: list[uuid.UUID] = Field(default_factory=list)
    #: The options in the order this candidate would see them.
    options: list[PreviewOption] = Field(default_factory=list)


class PreviewSection(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    order_index: int


class PaperPreview(BaseModel):
    seed: str
    candidate_id: uuid.UUID
    total_marks: float
    entries: list[PaperPreviewEntry]

    # --- exam-level context, enough to render a full preview page without a
    # second round trip for exam metadata. ---
    exam_id: uuid.UUID
    title: str
    subject_name: str
    exam_type: str
    category_label: str
    duration_minutes: int
    negative_marking: bool
    instructions: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    sections: list[PreviewSection] = Field(default_factory=list)
    total_questions: int = 0


# ------------------------------------------------------- the exam question pool
#
# "Pool" and "paper" are deliberately different words throughout. The pool is every
# question an exam may draw from; the paper is the subset one candidate actually sits.
# Conflating them is how examiners end up thinking a 50-question pool means a
# 50-question exam.


class PoolEntry(BaseModel):
    """One question sitting in an exam's pool, with its position and effective marks."""

    question_id: uuid.UUID
    order_index: int
    #: Which subject this question belongs to. Always set; only worth showing in the
    #: pool UI once a pool holds more than one, which is the whole point of carrying
    #: it on every row rather than assuming the exam's own subject.
    subject_id: uuid.UUID
    subject_name: str
    #: The section this question was chosen for, or null if it is free for any of them.
    section_id: uuid.UUID | None = None
    #: Per-exam marks override. Null means "use the question's own marks".
    marks_override: float | None = None
    effective_marks: float
    body: str
    question_type: QuestionType
    difficulty: Difficulty
    category: QuestionCategory
    topic: str | None = None
    source: str
    #: True when the question lives only in this exam and not in the reusable bank.
    exam_only: bool = False
    created_by_name: str | None = None
    option_count: int = 0
    has_answer_key: bool = False


class PoolStats(BaseModel):
    """The distribution an examiner needs to see before publishing."""

    total_questions: int = 0
    total_marks: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_difficulty: dict[str, int] = Field(default_factory=dict)
    #: Keyed by subject name, not id - what an examiner reads is "Java: 5", never a
    #: uuid. Only interesting once a pool can hold more than one subject, but computed
    #: for every exam so a single-subject pool's own examiner sees the same number the
    #: multi-subject one does.
    by_subject: dict[str, int] = Field(default_factory=dict)


class ExamPoolOut(BaseModel):
    exam_id: uuid.UUID
    entries: list[PoolEntry] = Field(default_factory=list)
    stats: PoolStats
    #: How many questions the selection rules will put on one candidate's paper.
    required_count: int = 0
    can_publish: bool = False
    problems: list[str] = Field(default_factory=list)


class PoolAdd(BaseModel):
    """Append existing bank questions to a pool, keeping what is already there."""

    question_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    #: Pin these to one section. Null adds them to the shared pool, where any section's
    #: rules may draw them - the behaviour before sections could own questions.
    section_id: uuid.UUID | None = None


class PoolSection(BaseModel):
    """Move one pooled question into a section, or back to the shared pool."""

    #: Null returns the question to the shared pool.
    section_id: uuid.UUID | None = None


class PoolReorder(BaseModel):
    """The pool's complete new order. Must name every question currently in it."""

    question_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=1000)


class PoolMarks(BaseModel):
    """Override what one question is worth *in this exam only*."""

    #: Null clears the override, restoring the question's own marks.
    marks_override: float | None = Field(default=None, ge=0)


# ------------------------------------------------------------------- blueprint
#
# "Blueprint" is the shortcut for the pool-plus-rules dance above: instead of manually
# searching the bank and adding matches one at a time, then hand-authoring a section's
# selection rule to match, an examiner names what they want - "Python, MCQ, Medium, 10" -
# and the server does both steps in one call.


class BlueprintRow(BaseModel):
    """One line of the blueprint table, e.g. "Python  MCQ  Medium  10"."""

    #: Section title this row becomes, e.g. "Python" or "Logical Reasoning".
    title: str = Field(..., min_length=1, max_length=120)
    subject_id: uuid.UUID | None = None
    category: QuestionCategory | None = None
    question_type: QuestionType
    difficulty: Difficulty | None = None
    topic: str | None = None
    tags: list[str] | None = None
    count: int = Field(..., gt=0, le=200)


class BlueprintRequest(BaseModel):
    rows: list[BlueprintRow] = Field(..., min_length=1, max_length=50)


class BlueprintRowResult(BaseModel):
    title: str
    requested: int
    #: How many bank questions matched this row's criteria.
    matched: int
    #: How many of those were newly added to the pool (already-pooled ones are skipped).
    added: int
    section_id: uuid.UUID


class BlueprintResponse(BaseModel):
    rows: list[BlueprintRowResult]
    pool: ExamPoolOut
