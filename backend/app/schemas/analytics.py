"""Analytics schemas for exam-level and candidate-level performance reports."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import Difficulty


class DifficultyBreakdown(BaseModel):
    difficulty: Difficulty
    total_questions: int
    correct: int
    incorrect: int
    unanswered: int
    avg_score_pct: float


class TopicPerformance(BaseModel):
    topic: str
    total_questions: int
    correct: int
    incorrect: int
    avg_score_pct: float


class SectionAnalytics(BaseModel):
    section_name: str
    total_marks: float
    avg_obtained: float
    avg_percentage: float
    pass_rate: float


class ExamAnalytics(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    exam_type: str
    total_sessions: int
    completed_sessions: int
    avg_percentage: float
    highest_percentage: float
    lowest_percentage: float
    pass_rate: float
    avg_time_seconds: int | None = None
    difficulty_breakdown: list[DifficultyBreakdown] = Field(default_factory=list)
    topic_performance: list[TopicPerformance] = Field(default_factory=list)
    section_analytics: list[SectionAnalytics] = Field(default_factory=list)
    # Distribution: list of percentage values for histogram
    score_distribution: list[float] = Field(default_factory=list)


class PerformanceAnalysis(BaseModel):
    """AI-generated narrative performance analysis for one candidate."""

    candidate_id: uuid.UUID
    candidate_name: str
    overall_percentage: float
    strong_areas: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str
    section_notes: list[str] = Field(default_factory=list)
    generated_at: datetime
