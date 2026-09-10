"""Schemas for the file-import workflow.

The parse response and the commit request are near-mirrors on purpose: the examiner
edits the rows they were shown and sends them back, so the two shapes staying aligned
is what makes "fix the errors in the preview" work without a second parse.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.enums import Difficulty, QuestionCategory, QuestionType


class ImportedOption(BaseModel):
    text: str
    is_correct: bool = False


class ImportedRow(BaseModel):
    """One parsed row, with everything wrong with it attached."""

    #: 1-based including the header, so it matches the row number in Excel.
    row_number: int
    body: str = ""
    question_type: QuestionType
    difficulty: Difficulty
    category: QuestionCategory
    topic: str | None = None
    marks: float
    negative_marks: float
    model_answer: str | None = None
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list)
    min_words: int | None = None
    max_words: int | None = None
    spec: dict[str, Any] | None = None
    options: list[ImportedOption] = Field(default_factory=list)
    #: Empty means the row would pass the same validation the authoring form applies.
    problems: list[str] = Field(default_factory=list)
    #: Where an identical question already exists - an earlier row, or the bank.
    duplicate_of: str | None = None


class ImportParseOut(BaseModel):
    filename: str
    total: int
    valid: int
    invalid: int
    duplicates: int
    rows: list[ImportedRow]


class ImportRowIn(BaseModel):
    """A row the examiner has approved, possibly after correcting it."""

    row_number: int = 0
    body: str = Field(..., min_length=1)
    question_type: QuestionType
    difficulty: Difficulty = Difficulty.MEDIUM
    category: QuestionCategory = QuestionCategory.ACADEMIC
    topic: str | None = Field(default=None, max_length=120)
    marks: float = Field(1.0, ge=0)
    negative_marks: float = Field(0.0, ge=0)
    model_answer: str | None = None
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list)
    min_words: int | None = Field(default=None, ge=0)
    max_words: int | None = Field(default=None, ge=1)
    spec: dict[str, Any] | None = None
    options: list[ImportedOption] = Field(default_factory=list)
    #: Per row, because an examiner may want most of a file in the bank and a few
    #: one-off variants kept to the exam they were written for.
    save_to_bank: bool = True


class ImportCommit(BaseModel):
    subject_id: uuid.UUID
    #: When set, the imported questions also join that exam's pool.
    exam_id: uuid.UUID | None = None
    rows: list[ImportRowIn] = Field(..., min_length=1, max_length=500)


class ImportResult(BaseModel):
    created: int
    failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    #: So the wizard can show what it just added without a second round trip.
    question_ids: list[uuid.UUID] = Field(default_factory=list)
