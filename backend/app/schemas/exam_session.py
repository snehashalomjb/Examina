"""Live exam session, answer autosave, and result schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import (
    Difficulty,
    ExamType,
    GradeStatus,
    QuestionCategory,
    QuestionType,
    SessionStatus,
)
from app.schemas.common import ORMModel
from app.schemas.question import OptionOut


class SessionSection(BaseModel):
    """A section as seen from the candidate's paper — no answer-key data."""

    id: uuid.UUID
    name: str
    order_index: int
    question_ids: list[uuid.UUID] = Field(default_factory=list)


class PaperQuestion(BaseModel):
    """What the candidate sees - never carries the answer key."""

    question_id: uuid.UUID
    question_type: QuestionType
    difficulty: Difficulty
    body: str
    marks: float
    negative_marks: float
    category: QuestionCategory
    topic: str | None = None
    #: Word bounds for written answers - the runner shows a live counter against these.
    min_words: int | None = None
    max_words: int | None = None
    #: A figure the question is about. Presigned, so it expires with the sitting.
    image_url: str | None = None
    #: The candidate-safe projection of ``questions.spec`` - a coding problem statement,
    #: a passage's text. Never the answer key: see ``question_spec.candidate_spec``.
    spec: dict | None = None
    #: Set on a child question so the runner can group it under its passage.
    parent_question_id: uuid.UUID | None = None
    #: Section this question belongs to, null for single-section papers.
    section_id: uuid.UUID | None = None
    options: list[OptionOut] = Field(default_factory=list)
    saved_option_ids: list[uuid.UUID] = Field(default_factory=list)
    saved_text: str | None = None
    saved_image_url: str | None = None
    saved_word_count: int | None = None
    #: Candidate flagged for final review. Persisted in DB, survives refreshes.
    is_review_flagged: bool = False


class ExamSessionOut(BaseModel):
    session_id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    status: SessionStatus
    started_at: datetime
    expires_at: datetime
    server_time: datetime
    seconds_remaining: int
    total_marks: float
    questions: list[PaperQuestion]
    proctor_config: dict
    exam_token: str | None = None
    #: Ordered sections for the section-navigation tabs. Empty on single-section papers.
    sections: list[SessionSection] = Field(default_factory=list)


class AnswerSave(BaseModel):
    selected_option_ids: list[uuid.UUID] | None = None
    text_answer: str | None = Field(default=None, max_length=50_000)

    @model_validator(mode="after")
    def at_least_one_field(self) -> AnswerSave:
        if self.selected_option_ids is None and self.text_answer is None:
            raise ValueError("Provide selected_option_ids or text_answer")
        return self


class AnswerSaved(BaseModel):
    question_id: uuid.UUID
    saved_at: datetime
    seconds_remaining: int
    #: Server-side count for text answers, so the runner's counter can be corrected from
    #: the authority rather than drifting on its own tokenisation.
    word_count: int | None = None


class HeartbeatOut(BaseModel):
    server_time: datetime
    seconds_remaining: int
    status: SessionStatus
    suspicion_score: float
    warnings: list[str] = Field(default_factory=list)
    exam_token: str | None = None


class SubmitOut(BaseModel):
    session_id: uuid.UUID
    status: SessionStatus
    submitted_at: datetime
    auto_scored: int
    pending_review: int
    message: str


class QuestionResult(BaseModel):
    question_id: uuid.UUID
    body: str
    question_type: QuestionType
    marks: float
    awarded_marks: float | None
    grade_status: GradeStatus
    is_correct: bool | None = None
    your_answer: str | None = None
    correct_answer: str | None = None
    examiner_comment: str | None = None
    ai_justification: str | None = None
    section_name: str | None = None


class SectionScore(BaseModel):
    section_id: uuid.UUID
    section_name: str
    total_marks: float
    obtained_marks: float
    percentage: float
    correct: int
    incorrect: int
    unanswered: int


class ResultOut(ORMModel):
    id: uuid.UUID
    session_id: uuid.UUID
    total_marks: float
    obtained_marks: float
    percentage: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    pending_review_count: int
    published: bool
    published_at: datetime | None = None


class ResultDetail(BaseModel):
    result: ResultOut
    exam_title: str
    subject_name: str
    candidate_name: str
    submitted_at: datetime | None
    questions: list[QuestionResult]
    #: Ordered section score breakdown. Empty for single-section papers.
    section_scores: list[SectionScore] = Field(default_factory=list)
    #: "academic" | "corporate" - drives PASS/FAIL vs QUALIFIED display.
    exam_type: str = "academic"
    passing_percentage: float | None = None
    #: How many candidates from the same cohort scored below this candidate, as a %.
    #: None when the cohort is too small to be meaningful (< 10 published results).
    percentile: float | None = None
    cohort_size: int = 0
    time_taken_seconds: int | None = None


class CandidateExamCard(BaseModel):
    """A row in the candidate's "my exams" list."""

    exam_id: uuid.UUID
    title: str
    subject_name: str
    duration_minutes: int
    starts_at: datetime
    ends_at: datetime
    total_questions: int
    session_status: SessionStatus | None = None
    session_id: uuid.UUID | None = None
    result_id: uuid.UUID | None = None
    result_published: bool = False
    can_start: bool = False
    reason: str | None = None
    exam_type: ExamType = ExamType.ACADEMIC
    course: str | None = None
    department: str | None = None
    semester: str | None = None
    company_name: str | None = None
    job_role: str | None = None
    sections_count: int = 0
    has_coding: bool = False
