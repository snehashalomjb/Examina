"""Users and the admin-controlled access gate."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import AccessStatus, UserRole

if TYPE_CHECKING:
    from app.db.models.enrollment import ExamEnrollment
    from app.db.models.exam import Exam
    from app.db.models.exam_session import ExamSession
    from app.db.models.login_access import LoginAccessRequest


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # first/last are the source of truth for greetings and sorting; full_name is kept
    # in sync so existing queries, exports and UI that read it keep working.
    first_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Admin access gate -------------------------------------------------
    # An examiner is inert until an admin approves them. Candidates are approved
    # at registration; admins are approved by definition.
    access_status: Mapped[AccessStatus] = mapped_column(
        Enum(AccessStatus, name="access_status", values_callable=lambda e: [m.value for m in e]),
        default=AccessStatus.PENDING,
        nullable=False,
        index=True,
    )
    access_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    access_note: Mapped[str | None] = mapped_column(Text)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    access_changed_by: Mapped[User | None] = relationship(
        remote_side="User.id", foreign_keys=[access_changed_by_id]
    )
    exam_sessions: Mapped[list[ExamSession]] = relationship(
        back_populates="candidate",
        foreign_keys="ExamSession.candidate_id",
        cascade="all, delete-orphan",
    )
    exams_created: Mapped[list[Exam]] = relationship(
        back_populates="created_by", foreign_keys="Exam.created_by_id"
    )
    login_access_request: Mapped[LoginAccessRequest | None] = relationship(
        back_populates="candidate",
        foreign_keys="LoginAccessRequest.candidate_id",
        cascade="all, delete-orphan",
        uselist=False,
    )
    enrollments: Mapped[list[ExamEnrollment]] = relationship(
        back_populates="candidate",
        foreign_keys="ExamEnrollment.candidate_id",
        cascade="all, delete-orphan",
    )

    @property
    def is_approved(self) -> bool:
        return self.access_status is AccessStatus.APPROVED

    @property
    def display_first_name(self) -> str:
        """First name for greetings, falling back to the first token of full_name."""
        return self.first_name or self.full_name.split(" ")[0]

    def set_name(self, first: str, last: str) -> None:
        self.first_name = first.strip()
        self.last_name = last.strip()
        self.full_name = " ".join(part for part in (self.first_name, self.last_name) if part)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email} role={self.role.value} access={self.access_status.value}>"
