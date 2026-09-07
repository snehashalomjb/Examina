"""The grader seam.

Nothing in the platform depends on a language model being configured. Everything talks to
``Grader``; the active implementation is chosen at runtime from settings.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.db.models import Answer, Question


class GradeResult(BaseModel):
    """A single first-pass evaluation of one subjective answer."""

    score: float = Field(..., description="Marks awarded, between 0 and max_score")
    max_score: float = Field(..., description="Marks the question is worth")
    justification: str = Field(..., description="Why this score - shown to the examiner")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="How sure the grader is, 0..1"
    )

    def clamped(self) -> GradeResult:
        """Never let a grader award more than the question is worth, or less than zero."""
        return self.model_copy(update={"score": max(0.0, min(self.score, self.max_score))})


@runtime_checkable
class Grader(Protocol):
    """Implemented by every grading backend."""

    name: str
    model: str | None

    def grade(self, *, question: Question, answer: Answer, max_marks: float) -> GradeResult: ...
