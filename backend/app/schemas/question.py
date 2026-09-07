"""Subject and question-bank schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import Difficulty, QuestionCategory, QuestionStatus, QuestionType
from app.schemas.common import ORMModel
from app.services.validators import OptionDraft, ValidationError, validate_question


class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class SubjectOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    question_count: int = 0


class OptionIn(BaseModel):
    text: str = Field(..., min_length=1)
    #: Object key from the image upload endpoint. Text stays required as the accessible
    #: label even when the option is really a picture.
    image_key: str | None = Field(default=None, max_length=512)
    is_correct: bool = False
    order_index: int = 0


class OptionOut(ORMModel):
    id: uuid.UUID
    text: str
    image_key: str | None = None
    #: Time-limited read URL, resolved from ``image_key`` when the paper is built.
    image_url: str | None = None
    order_index: int


class OptionOutWithAnswer(OptionOut):
    is_correct: bool


class QuestionBase(BaseModel):
    subject_id: uuid.UUID
    question_type: QuestionType
    #: The bank's top-level shelf, orthogonal to subject. Corporate sections select on it.
    category: QuestionCategory = QuestionCategory.ACADEMIC
    topic: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty = Difficulty.MEDIUM
    #: May be blank when ``image_key`` carries the question - a diagram question is often
    #: the figure plus a one-line prompt, and sometimes just the figure.
    body: str = Field(default="", max_length=20_000)
    model_answer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    #: Type-specific configuration - tolerance, accepted answers, coding problem, passage.
    spec: dict[str, Any] | None = None
    image_key: str | None = Field(default=None, max_length=512)
    #: Set on a child question to attach it to its passage.
    parent_question_id: uuid.UUID | None = None
    #: ge=0 rather than gt=0: the "marks must be positive" rule is per-type and lives in
    #: validate_question, which exempts a passage. A field constraint here would reject a
    #: valid passage before the domain rule ever ran.
    marks: float = Field(1.0, ge=0)
    negative_marks: float = Field(0.0, ge=0)
    tags: list[str] | None = None
    #: Written-answer length bounds. short_answer / long_answer only.
    min_words: int | None = Field(default=None, ge=0, le=100_000)
    max_words: int | None = Field(default=None, ge=1, le=100_000)


class QuestionCreate(QuestionBase):
    options: list[OptionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_domain_rules(self) -> QuestionCreate:
        try:
            # validate_question parses the spec as part of checking it, and hands back
            # the normalised form - so what gets stored is what was validated.
            self.spec = validate_question(
                question_type=self.question_type,
                body=self.body,
                marks=self.marks,
                negative_marks=self.negative_marks,
                options=[OptionDraft(o.text, o.is_correct, o.order_index) for o in self.options],
                model_answer=self.model_answer,
                min_words=self.min_words,
                max_words=self.max_words,
                spec=self.spec,
                image_key=self.image_key,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class QuestionUpdate(BaseModel):
    category: QuestionCategory | None = None
    topic: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty | None = None
    status: QuestionStatus | None = None
    body: str | None = None
    model_answer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    image_key: str | None = Field(default=None, max_length=512)
    marks: float | None = Field(default=None, ge=0)
    negative_marks: float | None = Field(default=None, ge=0)
    tags: list[str] | None = None
    min_words: int | None = Field(default=None, ge=0, le=100_000)
    max_words: int | None = Field(default=None, ge=1, le=100_000)
    is_active: bool | None = None
    options: list[OptionIn] | None = None


class QuestionOut(ORMModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    question_type: QuestionType
    category: QuestionCategory
    topic: str | None = None
    difficulty: Difficulty
    status: QuestionStatus
    body: str
    marks: float
    negative_marks: float
    min_words: int | None = None
    max_words: int | None = None
    tags: list[str] | None = None
    is_active: bool
    image_key: str | None = None
    image_url: str | None = None
    parent_question_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None
    options: list[OptionOut] = Field(default_factory=list)


class QuestionOutFull(QuestionOut):
    """Examiner view - includes the answer key.

    The spec belongs here and *only* here: for a numerical or fill-blank question it is
    the answer key, so it must never travel on the candidate's paper.
    """

    model_answer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    spec: dict[str, Any] | None = None
    options: list[OptionOutWithAnswer] = Field(default_factory=list)


class QuestionImageOut(BaseModel):
    """What the authoring UI needs after an upload: the key to save, and URLs to show."""

    image_key: str
    image_url: str | None = None
    thumbnail_url: str | None = None


class BulkQuestionCreate(BaseModel):
    questions: list[QuestionCreate] = Field(..., min_length=1, max_length=500)


class BulkQuestionResult(BaseModel):
    created: int
    failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
