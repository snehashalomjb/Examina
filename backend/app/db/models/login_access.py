"""Login approval — permission to use the platform, distinct from account state.

A candidate's account is created **active** and stays active. What is gated is the *login*:
on their first sign-in attempt with valid credentials, a request is raised here and the
candidate is held on a pending screen until an administrator — or an examiner authorised
over them — decides.

Once approved, it stays approved: later logins reuse the same row and never queue again
unless someone explicitly revokes it (which moves the row back to ``REJECTED`` with a note).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import LoginAccessStatus

if TYPE_CHECKING:
    from app.db.models.user import User


class LoginAccessRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "login_access_requests"

    # One standing request per candidate: approval is a durable state, not an event log.
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[LoginAccessStatus] = mapped_column(
        Enum(
            LoginAccessStatus,
            name="login_access_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=LoginAccessStatus.PENDING,
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    review_note: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[User] = relationship(
        back_populates="login_access_request", foreign_keys=[candidate_id]
    )
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])

    @property
    def is_approved(self) -> bool:
        return self.status is LoginAccessStatus.APPROVED

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LoginAccessRequest {self.candidate_id} {self.status.value}>"
