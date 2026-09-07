"""Exams, their configuration, and the question pool bound to each exam."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import ExamStatus, ExamType

if TYPE_CHECKING:
    from app.db.models.enrollment import ExamEnrollment
    from app.db.models.exam_session import ExamSession
    from app.db.models.question import Question, Subject
    from app.db.models.user import User


DEFAULT_PROCTOR_CONFIG: dict[str, Any] = {
    "webcam_enabled": True,
    "gaze_tracking_enabled": True,
    "gaze_sensitivity": 0.6,  # 0..1, higher = stricter
    "max_tab_switches": 3,  # warnings before the session is auto-flagged
    "terminate_on_score": 100.0,  # suspicion score that ends the session
    "flag_on_score": 45.0,  # suspicion score that flags for review
    "snapshot_interval_seconds": 60,
    "require_fullscreen": True,
    "block_copy_paste": True,
    "weights": {
        "face_missing": 6.0,
        "multiple_faces": 15.0,
        "gaze_away": 3.0,
        "tab_switch": 10.0,
        "window_blur": 4.0,
        "fullscreen_exit": 8.0,
        "camera_blocked": 20.0,
        "paste_attempt": 12.0,
        "copy_attempt": 6.0,
        "devtools_open": 25.0,
    },
}

DEFAULT_GRADING_CONFIG: dict[str, Any] = {
    "partial_credit_multi_select": False,
    "auto_publish_results": False,
    "grader_provider": None,  # None -> fall back to the app-level setting
    "grader_model": None,
}


class Exam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exams"

    #: Which mode this exam runs in. Both modes share one engine, one bank and one
    #: session lifecycle - the type decides which configuration fields apply and which
    #: reports are offered. Defaults to ``academic`` so every pre-existing exam keeps
    #: behaving exactly as it did.
    exam_type: Mapped[ExamType] = mapped_column(
        Enum(ExamType, name="exam_type", values_callable=lambda e: [m.value for m in e]),
        default=ExamType.ACADEMIC,
        server_default=ExamType.ACADEMIC.value,
        nullable=False,
        index=True,
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    #: Shown on the pre-exam screen. Free text, authored per exam.
    instructions: Mapped[str | None] = mapped_column(Text)

    # --- academic mode ------------------------------------------------------
    course: Mapped[str | None] = mapped_column(String(150))
    department: Mapped[str | None] = mapped_column(String(150))
    semester: Mapped[str | None] = mapped_column(String(40))

    # --- corporate mode -----------------------------------------------------
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_role: Mapped[str | None] = mapped_column(String(200))

    #: Total the examiner *declares* on the exam sheet. Left null to mean "whatever the
    #: generated paper adds up to", which is how every Milestone 1 exam behaves. The
    #: ``total_marks`` property below resolves the two.
    declared_total_marks: Mapped[float | None] = mapped_column(Float)
    #: Percentage at or above which a candidate passes / qualifies. Null = no verdict.
    passing_percentage: Mapped[float | None] = mapped_column(Float)

    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # {"rules": [{"question_type": "mcq", "difficulty": "easy", "count": 10}, ...]}
    selection_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    randomize: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    negative_marking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: How many sittings one candidate may take. Defaults to 1, which is exactly the
    #: behaviour the old two-column unique constraint enforced.
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # Stable per-exam salt so the deterministic paper seed cannot be guessed from ids alone.
    paper_salt: Mapped[str] = mapped_column(String(64), nullable=False)

    proctor_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: dict(DEFAULT_PROCTOR_CONFIG)
    )
    grading_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: dict(DEFAULT_GRADING_CONFIG)
    )

    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus, name="exam_status", values_callable=lambda e: [m.value for m in e]),
        default=ExamStatus.DRAFT,
        nullable=False,
        index=True,
    )
    results_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    subject: Mapped[Subject] = relationship()
    created_by: Mapped[User | None] = relationship(
        back_populates="exams_created", foreign_keys=[created_by_id]
    )
    sections: Mapped[list[ExamSection]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
        order_by="ExamSection.order_index",
    )
    exam_questions: Mapped[list[ExamQuestion]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[ExamSession]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list[ExamEnrollment]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )

    @property
    def total_marks(self) -> float:
        """What the paper is out of.

        The examiner's declared total wins when they set one - a corporate paper is
        advertised as "out of 100" and must say so even if the pool sums differently.
        Otherwise it falls back to summing the pool, which is what every exam built
        before ``declared_total_marks`` existed does.
        """
        if self.declared_total_marks is not None:
            return self.declared_total_marks
        return sum(eq.effective_marks for eq in self.exam_questions)


class ExamSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named, ordered part of a paper that owns its own selection rules.

    This is the seam that lets one engine serve both modes. A corporate paper is a list
    of these - Aptitude, Reasoning, Verbal, Technical, Coding - each drawing its own
    questions at its own marks. An academic paper usually has none at all, in which case
    the generator synthesises a single implicit section from ``exam.selection_rules``.
    That fallback is what keeps every Milestone 1 exam running untouched: no rows here
    means exactly the old behaviour, on the same code path.

    Questions are still drawn from the one ``exam_questions`` pool. A section narrows
    *which* of them it may take; it does not own a pool of its own.
    """

    __tablename__ = "exam_sections"
    __table_args__ = (
        UniqueConstraint("exam_id", "order_index", name="uq_exam_section_order"),
        UniqueConstraint("exam_id", "name", name="uq_exam_section_name"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    #: Same shape as ``exams.selection_rules`` - {"rules": [...]} - but scoped to this
    #: section, and able to select on category and topic as well as type and difficulty.
    selection_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    #: Flat marks for every question drawn into this section, overriding the question's
    #: own value. "Technical: 25 questions x 2 marks" is one number, not 25 edits.
    marks_per_question: Mapped[float | None] = mapped_column(Float)
    #: Section-level negative marking, same idea. Null inherits the question's own value.
    negative_marks: Mapped[float | None] = mapped_column(Float)

    #: Per-section time limit. Null means the section shares the exam's single clock,
    #: which is how every paper behaves today. Reserved for sectional timing.
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    exam: Mapped[Exam] = relationship(back_populates="sections")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ExamSection {self.order_index}:{self.name!r}>"


class ExamQuestion(UUIDPrimaryKeyMixin, Base):
    """The pool an exam draws from. A candidate's paper is a subset of these."""

    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),)

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    marks_override: Mapped[float | None] = mapped_column(Float)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    exam: Mapped[Exam] = relationship(back_populates="exam_questions")
    question: Mapped[Question] = relationship()

    @property
    def effective_marks(self) -> float:
        return self.marks_override if self.marks_override is not None else self.question.marks
