"""Persistent notifications shown in the dashboard bell."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.exam_session import ExamSession
    from app.db.models.user import User


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One recipient's copy of one event.

    A submission fans out to several recipients (the owning examiner, every admin), so
    each gets its own row rather than a single shared one - a row is exactly one bell
    entry for one person, and "mark as read" only ever touches the reader's own row.

    The unique constraint on (recipient_id, session_id, type) is the duplicate guard: a
    retried request or a re-entrant background task can call the notify function twice
    for the same submission, but the second insert is rejected at the database rather
    than relying on the caller to remember it already ran.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "recipient_id", "session_id", "type", name="uq_notification_recipient_session_type"
        ),
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Short machine tag, e.g. "exam_submission". Lets the bell/UI branch on kind without
    #: parsing the title, and keeps the duplicate-guard scoped to one kind of event.
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)

    #: What "View Submission" resolves to. Nullable because a future notification type
    #: might not need one, but every current type sets it.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exam_sessions.id", ondelete="CASCADE"), index=True
    )
    result_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("results.id", ondelete="CASCADE")
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    session: Mapped[ExamSession | None] = relationship(foreign_keys=[session_id])
