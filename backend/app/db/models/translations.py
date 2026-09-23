"""Per-locale sibling rows for translatable content.

Each table here mirrors one existing content table 1:1 in shape (same parent id,
one row per locale) rather than adding language columns to the content tables
themselves. That keeps every existing id, column and relationship untouched -
grading, exports and anything else that reads the base ``body``/``text``/``title``
columns keeps working exactly as before; these tables are pure additions.

Reading translated text goes through ``app.services.i18n.translated_field``, which
falls back locale -> ``en`` -> the base column, so a candidate never sees blank
content just because a translator hasn't reached a row yet.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import SUPPORTED_LOCALES

_LOCALE_CHECK = "locale IN (" + ", ".join(f"'{loc}'" for loc in SUPPORTED_LOCALES) + ")"


class QuestionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_translations"
    __table_args__ = (
        UniqueConstraint("question_id", "locale", name="uq_question_translations_locale"),
        CheckConstraint(_LOCALE_CHECK, name="locale_supported"),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    body: Mapped[str | None] = mapped_column(Text)
    model_answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)

    question: Mapped["Question"] = relationship(back_populates="translations")  # noqa: F821


class OptionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "option_translations"
    __table_args__ = (
        UniqueConstraint("option_id", "locale", name="uq_option_translations_locale"),
        CheckConstraint(_LOCALE_CHECK, name="locale_supported"),
    )

    option_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("question_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    text: Mapped[str | None] = mapped_column(Text)

    option: Mapped["QuestionOption"] = relationship(back_populates="translations")  # noqa: F821


class ExamTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_translations"
    __table_args__ = (
        UniqueConstraint("exam_id", "locale", name="uq_exam_translations_locale"),
        CheckConstraint(_LOCALE_CHECK, name="locale_supported"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    course: Mapped[str | None] = mapped_column(String(150))
    department: Mapped[str | None] = mapped_column(String(150))
    semester: Mapped[str | None] = mapped_column(String(40))
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_role: Mapped[str | None] = mapped_column(String(200))

    exam: Mapped["Exam"] = relationship(back_populates="translations")  # noqa: F821


class SubjectTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subject_translations"
    __table_args__ = (
        UniqueConstraint("subject_id", "locale", name="uq_subject_translations_locale"),
        CheckConstraint(_LOCALE_CHECK, name="locale_supported"),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)

    subject: Mapped["Subject"] = relationship(back_populates="translations")  # noqa: F821


class ExamSectionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exam_section_translations"
    __table_args__ = (
        UniqueConstraint("exam_section_id", "locale", name="uq_exam_section_translations_locale"),
        CheckConstraint(_LOCALE_CHECK, name="locale_supported"),
    )

    exam_section_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)

    section: Mapped["ExamSection"] = relationship(back_populates="translations")  # noqa: F821
