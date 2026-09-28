"""Exam-level result report summaries for the Examiner/Admin reports dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ExamReportSummary(BaseModel):
    """One exam's row on the Reports dashboard - counts only, no per-candidate detail."""

    exam_id: uuid.UUID
    exam_title: str
    subject_name: str | None = None
    exam_date: datetime
    total_candidates: int
    completed: int
    pending_review: int
    approved: int
    flagged: int
    rejected: int
    average_marks: float | None = None
    highest_marks: float | None = None
    lowest_marks: float | None = None
