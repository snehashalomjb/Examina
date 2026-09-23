"""Subject and question-bank schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models.enums import (
    Difficulty,
    QuestionCategory,
    QuestionSource,
    QuestionStatus,
    QuestionType,
)
from app.schemas.common import ORMModel
from app.services.validators import OptionDraft, ValidationError, validate_question


class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150)
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
    #: Per-locale text, e.g. {"te": {"text": "..."}}. ``en`` is always upserted from the
    #: ``text`` field above regardless of whether it's repeated here.
    translations: dict[str, dict[str, str]] | None = None


class OptionOut(ORMModel):
    id: uuid.UUID
    text: str
    image_key: str | None = None
    #: Time-limited read URL, resolved from ``image_key`` when the paper is built.
    image_url: str | None = None
    order_index: int


class OptionOutWithAnswer(OptionOut):
    is_correct: bool
    #: Per-locale text already on file, keyed by locale (``en`` included), for the
    #: examiner's translation editor to load into its fields. Empty until a translation
    #: has been written or generated.
    translations: dict[str, str] = Field(default_factory=dict)

    @field_validator("translations", mode="before")
    @classmethod
    def _from_rows(cls, value: Any) -> dict[str, str]:
        # `model_validate(option, from_attributes=True)` finds `OptionTranslation` rows
        # on the ORM object's own `.translations` relationship (same field name) before
        # `_to_full` gets a chance to set the resolved dict - convert them here instead
        # of forbidding the natural name.
        if isinstance(value, dict):
            return value
        return {row.locale: (row.text or "") for row in value}


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
    #: Per-locale question text, e.g. {"te": {"body": "...", "explanation": "..."}}.
    #: ``en`` is always upserted from ``body``/``model_answer``/``explanation`` above.
    translations: dict[str, dict[str, str]] | None = None

    #: Where this question came from. The client may declare it, but the AI and import
    #: paths set it server-side - a caller cannot dress an AI draft up as hand-authored.
    source: QuestionSource = QuestionSource.MANUAL
    #: Set when the question is being authored from inside an exam wizard. The question
    #: is added to that exam's pool as soon as it is saved.
    exam_id: uuid.UUID | None = None
    #: "Save to My Question Bank". False keeps the question private to ``exam_id``, which
    #: is the only case where it means anything - a question with no exam has nowhere
    #: else to live, so it is shelved regardless.
    save_to_bank: bool = True

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


class QuestionDuplicate(BaseModel):
    """Copy a question. Everything is optional - an unmodified copy is a valid ask."""

    #: Where the copy lands. Null shelves it in the bank like the original.
    exam_id: uuid.UUID | None = None
    save_to_bank: bool = True


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
    translations: dict[str, dict[str, str]] | None = None


class QuestionOut(ORMModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    #: Denormalised for the bank browser, which shows the subject on every card.
    subject_code: str | None = None
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
    source: QuestionSource = QuestionSource.MANUAL
    created_by_id: uuid.UUID | None = None
    #: Who wrote it, for the "Created by" line and the edit-permission check.
    created_by_name: str | None = None
    #: True when the question is private to one exam rather than shelved in the bank.
    exam_only: bool = False
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
    #: Per-locale {body, model_answer, explanation} already on file, keyed by locale
    #: (``en`` included), for the examiner's translation editor to load. Empty until a
    #: translation has been written or generated.
    translations: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("translations", mode="before")
    @classmethod
    def _from_rows(cls, value: Any) -> dict[str, dict[str, str]]:
        if isinstance(value, dict):
            return value
        return {
            row.locale: {
                "body": row.body or "",
                "model_answer": row.model_answer or "",
                "explanation": row.explanation or "",
            }
            for row in value
        }


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


class DuplicateCheckRequest(BaseModel):
    subject_id: uuid.UUID
    body: str = Field(..., min_length=1)
    #: The question being edited, so it never flags itself as its own duplicate.
    exclude_question_id: uuid.UUID | None = None


class DuplicateMatch(BaseModel):
    id: uuid.UUID
    body: str


class DuplicateCheckOut(BaseModel):
    matches: list[DuplicateMatch] = Field(default_factory=list)


class GenerateTranslationsRequest(BaseModel):
    #: Locales to (re)generate. Defaults to every supported locale except English, which
    #: is the source and is never generated.
    locales: list[str] | None = None
    #: Regenerate a locale even if it already has a saved translation. Off by default -
    #: a generate click should never silently blow away an examiner's hand edits.
    overwrite_existing: bool = False


class GenerateTranslationsOut(BaseModel):
    #: {locale: {body, explanation}} - a *preview* only, nothing is saved here. The
    #: examiner reviews/edits these in the form, then PATCHes the question with
    #: ``translations`` to actually persist them.
    translations: dict[str, dict[str, str]] = Field(default_factory=dict)
    #: {option_id: {locale: text}}.
    options: dict[uuid.UUID, dict[str, str]] = Field(default_factory=dict)
    #: "stub" | "openai" - which provider actually produced this, so the UI can warn
    #: when no real translation model is configured.
    provider: str
    #: Locales that already had a saved translation and were skipped because
    #: ``overwrite_existing`` was false.
    skipped_existing: list[str] = Field(default_factory=list)
