"""Live exam sessions and the answers recorded inside them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
from app.db.models.enums import GradeStatus, SessionStatus

if TYPE_CHECKING:
    from app.db.models.exam import Exam
    from app.db.models.grading import AiEvaluation, Result
    from app.db.models.proctor import ProctorEvent
    from app.db.models.question import Question
    from app.db.models.user import User


class ExamSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One candidate's attempt at one exam.

    The unique (exam_id, candidate_id) constraint is what enforces a single attempt.
    ``question_order`` is persisted at start so a server restart mid-exam cannot reshuffle
    the paper under the candidate.
    """

    __tablename__ = "exam_sessions"
    __table_args__ = (
        # Was (exam_id, candidate_id). Widened to include the attempt so a retake is a
        # new row rather than a constraint violation; with max_attempts defaulting to 1
        # the effective behaviour for every existing exam is unchanged.
        UniqueConstraint(
            "exam_id", "candidate_id", "attempt_number", name="uq_exam_session_attempt"
        ),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: 1 for a first sitting, 2 for the first retake, and so on. Feeds the paper seed
    #: from attempt 2 onward, so a retake is a genuinely different paper rather than the
    #: same one again - see ``app.services.paper_generator.compute_seed``.
    attempt_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )

    paper_seed: Mapped[str] = mapped_column(String(64), nullable=False)
    # [{"question_id": "...", "option_order": ["...", "..."]}, ...]
    question_order: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", values_callable=lambda e: [m.value for m in e]),
        default=SessionStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )

    suspicion_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tab_switch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_flagged: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    termination_reason: Mapped[str | None] = mapped_column(Text)

    exam: Mapped[Exam] = relationship(back_populates="sessions")
    candidate: Mapped[User] = relationship(
        back_populates="exam_sessions", foreign_keys=[candidate_id]
    )
    answers: Mapped[list[Answer]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    proctor_events: Mapped[list[ProctorEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    result: Mapped[Result | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )

    @property
    def is_open(self) -> bool:
        return self.status is SessionStatus.IN_PROGRESS


class Answer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("session_id", "question_id", name="uq_answer_per_question"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    #: Which section of the paper this answer belongs to, for section-wise scoring.
    #: Null on every answer written before sections existed, and on any single-section
    #: paper. SET NULL rather than CASCADE: deleting a section must never delete a
    #: candidate's submitted work.
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exam_sections.id", ondelete="SET NULL"), index=True
    )

    # Objective answers: list of chosen option ids (stringified UUIDs).
    selected_option_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    # Subjective answers: free text, or an object key for a handwritten scan.
    text_answer: Mapped[str | None] = mapped_column(Text)
    image_object_key: Mapped[str | None] = mapped_column(String(512))
    # Server-generated so the examiner queue can render a grid of scans without pulling
    # a dozen multi-megabyte originals through presigned URLs.
    image_thumb_key: Mapped[str | None] = mapped_column(String(512))
    # OCR pre-pass over a handwritten scan. Advisory only - the examiner reads the image.
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    # Recorded at save time so grading and analytics never re-tokenise the text.
    word_count: Mapped[int | None] = mapped_column(Integer)

    awarded_marks: Mapped[float | None] = mapped_column(Float)
    max_marks: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    grade_status: Mapped[GradeStatus] = mapped_column(
        Enum(GradeStatus, name="grade_status", values_callable=lambda e: [m.value for m in e]),
        default=GradeStatus.UNANSWERED,
        nullable=False,
        index=True,
    )
    examiner_comment: Mapped[str | None] = mapped_column(Text)
    graded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Candidate has flagged this answer for final review before submitting.
    #: Never affects scoring - purely a UX aid that persists across refreshes.
    is_review_flagged: Mapped[bool] = mapped_column(default=False, nullable=False)

    session: Mapped[ExamSession] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()
    graded_by: Mapped[User | None] = relationship(foreign_keys=[graded_by_id])
    ai_evaluations: Mapped[list[AiEvaluation]] = relationship(
        back_populates="answer",
        cascade="all, delete-orphan",
        order_by="AiEvaluation.created_at.desc()",
    )

    @property
    def latest_ai_evaluation(self) -> AiEvaluation | None:
        return self.ai_evaluations[0] if self.ai_evaluations else None

    @property
    def is_answered(self) -> bool:
        return bool(self.selected_option_ids or self.text_answer or self.image_object_key)
