"""Recruitment-specific schemas: corporate ranking and shortlisting."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.enums import ShortlistStatus
from app.schemas.common import ORMModel


class ShortlistCreate(BaseModel):
    candidate_id: uuid.UUID
    status: ShortlistStatus
    note: str | None = None


class ShortlistOut(ORMModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    candidate_id: uuid.UUID
    status: ShortlistStatus
    note: str | None = None
    decided_by_id: uuid.UUID | None = None
    decided_at: datetime
    created_at: datetime


class SectionScore(BaseModel):
    section_name: str
    obtained_marks: float
    total_marks: float
    percentage: float
    correct: int
    incorrect: int
    unanswered: int


class RankingRow(BaseModel):
    """One candidate's row in the corporate ranking table."""

    candidate_id: uuid.UUID
    full_name: str
    email: str
    overall_percentage: float
    obtained_marks: float
    total_marks: float
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    accuracy: float  # correct / (correct + incorrect), 0 if none answered
    time_taken_seconds: int | None = None
    rank: int
    # Section-wise breakdown (empty for academic exams)
    section_scores: list[SectionScore] = Field(default_factory=list)
    shortlist_status: ShortlistStatus | None = None
    suspicion_score: float = 0.0
    is_flagged: bool = False
    result_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None


class ShortlistBulkCreate(BaseModel):
    """Examiner sets/updates shortlist status for one or many candidates at once."""

    decisions: list[ShortlistCreate] = Field(..., min_length=1)
