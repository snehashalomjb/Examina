"""Proctoring evidence: one row per behavioural or vision signal."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.models.enums import ProctorEventType, ProctorSeverity

if TYPE_CHECKING:
    from app.db.models.exam_session import ExamSession


class ProctorEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "proctor_events"
    __table_args__ = (Index("ix_proctor_events_timeline", "session_id", "occurred_at"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[ProctorEventType] = mapped_column(
        Enum(
            ProctorEventType,
            name="proctor_event_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    severity: Mapped[ProctorSeverity] = mapped_column(
        Enum(
            ProctorSeverity,
            name="proctor_severity",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ProctorSeverity.INFO,
        nullable=False,
    )
    # Client clock, echoed for ordering inside a batch; server_received_at is authoritative.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column()
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # e.g. {"face_count": 2, "yaw": -34.2, "confidence": 0.91}
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    snapshot_object_key: Mapped[str | None] = mapped_column(String(512))

    session: Mapped[ExamSession] = relationship(back_populates="proctor_events")
