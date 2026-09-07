"""Exam enrolment — which candidates a given exam is actually assigned to.

Approved login is permission to use the platform; it is *not* permission to sit every
paper on it. A candidate sees and can start only the exams they are enrolled in, and this
table is also what defines an examiner's authority over a candidate: an examiner may
review a candidate's login request only if that candidate is enrolled in one of the
examiner's own exams.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.exam import Exam
    from app.db.models.user import User


class ExamEnrollment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exam_enrollments"
    __table_args__ = (UniqueConstraint("exam_id", "candidate_id", name="uq_exam_enrollment"),)

    exam_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    exam: Mapped[Exam] = relationship(back_populates="enrollments")
    candidate: Mapped[User] = relationship(
        back_populates="enrollments", foreign_keys=[candidate_id]
    )
    assigned_by: Mapped[User | None] = relationship(foreign_keys=[assigned_by_id])
