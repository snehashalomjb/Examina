"""AI question generation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import Difficulty, DraftStatus, QuestionCategory, QuestionType
from app.schemas.common import ORMModel


class AiGenerateRequest(BaseModel):
    """Parameters an examiner sends to request AI-generated questions."""

    subject_id: uuid.UUID | None = None
    category: QuestionCategory = QuestionCategory.TECHNICAL
    topic: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty = Difficulty.MEDIUM
    question_type: QuestionType = QuestionType.MCQ
    #: Ask for a mix. The count is split across these; ``question_type`` is the
    #: single-type shorthand and stays supported so existing callers are unchanged.
    question_types: list[QuestionType] | None = Field(default=None, max_length=6)
    count: int = Field(5, ge=1, le=20)
    #: What one generated question should be worth. Applied to every draft in the batch.
    marks_per_question: float | None = Field(default=None, gt=0, le=100)
    #: Syllabus text or learning objectives the questions must be drawn from. Folded
    #: into the prompt as source material rather than as loose instructions.
    syllabus: str | None = Field(default=None, max_length=20_000)
    #: The language to write in. Free text so regional languages are not gate-kept by
    #: an enum somebody has to remember to extend.
    language: str | None = Field(default=None, max_length=40)
    #: Extra instructions injected into the generation prompt (e.g. "focus on OOP concepts")
    extra_instructions: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def types_are_a_set(self) -> AiGenerateRequest:
        if self.question_types:
            # Order is preserved so the split across types is predictable, but a type
            # named twice would silently double its share.
            self.question_types = list(dict.fromkeys(self.question_types))
        return self

    def type_plan(self) -> list[tuple[QuestionType, int]]:
        """How many questions of each type to ask for.

        The remainder goes to the earlier types rather than being dropped, so asking
        for 10 questions across 3 types yields 4+3+3 and never 9.
        """
        types = self.question_types or [self.question_type]
        base, extra = divmod(self.count, len(types))
        return [
            (question_type, base + (1 if index < extra else 0))
            for index, question_type in enumerate(types)
            if base or index < extra
        ]


class AiRegenerateRequest(BaseModel):
    """Ask for another attempt at one draft the examiner did not like.

    The original stays in place, rejected with the note the examiner gave, so the
    history of what the model produced is not quietly rewritten.
    """

    #: What was wrong with the first attempt. Also becomes the rejection reason.
    feedback: str | None = Field(default=None, max_length=500)
    difficulty: Difficulty | None = None


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
    #: Approve straight into an exam's pool, which is what the wizard does.
    exam_id: uuid.UUID | None = None
    #: False keeps the approved question private to ``exam_id``.
    save_to_bank: bool = True


class AiDraftReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
