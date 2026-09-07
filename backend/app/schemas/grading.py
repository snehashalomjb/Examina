"""Examiner grading queue schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import GradeStatus, QuestionType


class AiEvaluationOut(BaseModel):
    provider: str
    model: str | None = None
    score: float
    max_score: float
    justification: str
    confidence: float
    created_at: datetime
    error: str | None = None


class GradingQueueItem(BaseModel):
    answer_id: uuid.UUID
    session_id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    candidate_name: str
    candidate_email: str
    question_id: uuid.UUID
    question_body: str
    question_type: QuestionType
    model_answer: str | None = None
    rubric: dict | None = None
    text_answer: str | None = None
    word_count: int | None = None
    #: Words this answer is below the question's minimum, if the examiner set one. The
    #: platform never penalises for it - it is shown so the examiner can.
    words_below_minimum: int = 0
    image_url: str | None = None
    image_thumb_url: str | None = None
    #: Tesseract's read of a handwritten scan. Advisory - the examiner reads the image.
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    max_marks: float
    awarded_marks: float | None = None
    grade_status: GradeStatus
    examiner_comment: str | None = None
    ai_evaluation: AiEvaluationOut | None = None
    submitted_at: datetime | None = None


class GradeOverride(BaseModel):
    awarded_marks: float = Field(..., ge=0)
    comment: str | None = Field(default=None, max_length=4000)


class RegradeRequest(BaseModel):
    answer_ids: list[uuid.UUID] | None = None
    session_id: uuid.UUID | None = None


class GradingSummary(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    total_sessions: int
    submitted_sessions: int
    pending_review: int
    reviewed: int
    results_published: bool
