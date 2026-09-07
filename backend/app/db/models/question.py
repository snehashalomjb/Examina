"""Subjects, question bank and options."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import (
    Difficulty,
    QuestionCategory,
    QuestionStatus,
    QuestionType,
)

if TYPE_CHECKING:
    from app.db.models.user import User


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    questions: Mapped[list[Question]] = relationship(back_populates="subject")


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("ix_questions_pool_lookup", "subject_id", "question_type", "difficulty"),
        # The bank browser filters on these three together far more often than singly.
        Index("ix_questions_bank_filter", "category", "topic", "status"),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    #: The bank's top-level shelf, orthogonal to ``subject_id``. Corporate section rules
    #: select on this; academic exams mostly select on subject. Defaults to ``academic``
    #: so every question authored before the two modes existed keeps its meaning.
    category: Mapped[QuestionCategory] = mapped_column(
        Enum(
            QuestionCategory,
            name="question_category",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=QuestionCategory.ACADEMIC,
        # Mirrors the migration: the column was added to a populated table, so it needs a
        # server default to be NOT NULL. Declaring it here keeps `alembic check` clean.
        server_default=QuestionCategory.ACADEMIC.value,
        nullable=False,
    )
    #: Free-text within a subject - "OOP", "Profit and Loss", "Blood Relations". Kept as
    #: a string rather than a table: the topic lists in the spec are long, per-subject and
    #: change with the syllabus, and a lookup table would make authoring a two-step form.
    topic: Mapped[str | None] = mapped_column(String(120))

    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, name="difficulty", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Difficulty.MEDIUM,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Reference answer for subjective types; also shown to the examiner while grading.
    model_answer: Mapped[str | None] = mapped_column(Text)
    # Free-form rubric handed to the grader, e.g. {"criteria": [{"name":..,"weight":..}]}
    rubric: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    #: Shown after the result is published, never during the exam.
    explanation: Mapped[str | None] = mapped_column(Text)
    #: Object key for a diagram or figure the question is *about*. Distinct from an
    #: ``image_upload`` answer, which is what the candidate submits.
    image_key: Mapped[str | None] = mapped_column(String(512))
    #: Type-specific configuration - numerical tolerance, fill-blank accepted answers and
    #: case sensitivity, coding language and sample cases, passage metadata. One JSONB
    #: column rather than a dozen sparse ones: the shape differs per type and only the
    #: validator for that type ever reads it. See ``app.services.question_spec``.
    spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Word bounds for written answers. Enforced server-side on every autosave, and shown
    # as a live counter in the runner so a candidate is never surprised at submit time.
    min_words: Mapped[int | None] = mapped_column(Integer)
    max_words: Mapped[int | None] = mapped_column(Integer)
    marks: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    negative_marks: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    #: Authoring lifecycle. Only ``published`` questions may enter an exam pool. Defaults
    #: to ``published`` so the whole existing bank stays usable - a ``draft`` default would
    #: silently empty every exam built before this column existed.
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(
            QuestionStatus,
            name="question_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=QuestionStatus.PUBLISHED,
        server_default=QuestionStatus.PUBLISHED.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    #: A passage/case-study question owns child questions; the children carry the marks
    #: and the passage carries none. Self-referential so one table still holds the bank.
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    subject: Mapped[Subject] = relationship(back_populates="questions")
    created_by: Mapped[User | None] = relationship()
    parent: Mapped[Question | None] = relationship(
        back_populates="children", remote_side="Question.id"
    )
    children: Mapped[list[Question]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Question.created_at",
    )
    options: Mapped[list[QuestionOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.order_index",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Question {self.question_type.value} {self.body[:40]!r}>"


class QuestionOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: An option may be a picture rather than a phrase - common in reasoning and
    #: diagram questions. Text stays required as the accessible label.
    image_key: Mapped[str | None] = mapped_column(String(512))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    question: Mapped[Question] = relationship(back_populates="options")
