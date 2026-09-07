"""Corporate recruitment: reusable exam templates and shortlisting decisions.

Nothing here scores or ranks anybody. Ranking is derived from ``results`` at query time,
and a shortlist row exists only because a named examiner made a decision and clicked. The
platform assists a hiring process; it does not run one.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import ExamType, ShortlistStatus

if TYPE_CHECKING:
    from app.db.models.exam import Exam
    from app.db.models.user import User


class ExamTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A starting point for an exam, not a constraint on one.

    A template is copied into an exam's sections at creation time and then forgotten -
    editing a template never reaches back into an exam already built from it, and every
    field stays editable before publishing.
    """

    __tablename__ = "exam_templates"
    __table_args__ = (UniqueConstraint("name", name="uq_exam_template_name"),)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    exam_type: Mapped[ExamType] = mapped_column(
        Enum(ExamType, name="exam_type", values_callable=lambda e: [m.value for m in e]),
        default=ExamType.CORPORATE,
        server_default=ExamType.CORPORATE.value,
        nullable=False,
    )
    #: The role this template is shaped for - "Software Developer", "Data Analyst".
    job_role: Mapped[str | None] = mapped_column(String(200))

    #: The sections to create, in order. Same shape as the ``exam_sections`` payload:
    #: [{"name", "order_index", "selection_rules", "marks_per_question", ...}]
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    duration_minutes: Mapped[int | None] = mapped_column()

    #: Shipped with the platform. Built-ins are seeded, never edited in place, and cannot
    #: be deleted by an examiner - so the four documented templates always exist.
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by: Mapped[User | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ExamTemplate {self.name!r}>"


class CandidateShortlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One examiner's recruitment decision about one candidate on one exam.

    A row here is always the record of a human choice. Nothing in the platform writes it
    automatically, and no score threshold creates one: the ranking table sorts candidates
    and the examiner decides. ``decided_by_id`` is SET NULL so a departing examiner does
    not erase the decisions they made.
    """

    __tablename__ = "candidate_shortlists"
    __table_args__ = (
        UniqueConstraint("exam_id", "candidate_id", name="uq_shortlist_per_candidate"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ShortlistStatus] = mapped_column(
        Enum(
            ShortlistStatus,
            name="shortlist_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text)

    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    exam: Mapped[Exam] = relationship()
    candidate: Mapped[User] = relationship(foreign_keys=[candidate_id])
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CandidateShortlist {self.status.value} candidate={self.candidate_id}>"
