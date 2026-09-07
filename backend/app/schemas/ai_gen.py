"""AI question generation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.enums import Difficulty, DraftStatus, QuestionCategory, QuestionType
from app.schemas.common import ORMModel


class AiGenerateRequest(BaseModel):
    """Parameters an examiner sends to request AI-generated questions."""

    subject_id: uuid.UUID | None = None
    category: QuestionCategory = QuestionCategory.TECHNICAL
    topic: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty = Difficulty.MEDIUM
    question_type: QuestionType = QuestionType.MCQ
    count: int = Field(5, ge=1, le=20)
    #: Extra instructions injected into the generation prompt (e.g. "focus on OOP concepts")
    extra_instructions: str | None = Field(default=None, max_length=500)


class AiDraftOut(ORMModel):
    id: uuid.UUID
    subject_id: uuid.UUID | None = None
    category: QuestionCategory
    topic: str | None = None
    difficulty: Difficulty
    question_type: QuestionType
    payload: dict[str, Any]
    original_payload: dict[str, Any] | None = None
    provider: str
    model: str | None = None
    error: str | None = None
    status: DraftStatus
    requested_by_id: uuid.UUID | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    published_question_id: uuid.UUID | None = None
    created_at: datetime


class AiPdfImportOut(BaseModel):
    """What came back from a PDF import: the drafts, plus what was read to make them.

    The counts are reported so an examiner can tell a fully-read document from one where
    only a few pages carried a text layer, before they trust the drafts.
    """

    filename: str
    pages: int
    #: Pages with no text layer at all - a scanned insert in an otherwise digital PDF.
    empty_pages: int
    characters: int
    #: True when the document was longer than the extractor's prompt budget.
    truncated: bool
    #: False when the drafts came from the offline stub and are NOT drawn from the PDF.
    source_grounded: bool
    drafts: list[AiDraftOut]


class AiDraftApprove(BaseModel):
    """Examiner may edit the payload before approving."""

    payload: dict[str, Any]


class AiDraftReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
