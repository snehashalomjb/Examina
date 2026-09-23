"""Where an exam is in its lifecycle, derived from its own timestamps.

Not a fourth or fifth value bolted onto ``ExamStatus`` - that column stays exactly
draft/published/closed, which is what authoring and publishing actually operate on. A
richer label ("scheduled", "live", "completed") is a read-only view over the same three
facts everyone already has (``status``, ``starts_at``, ``ends_at``), computed fresh each
time rather than stored, so it can never drift out of sync with the timestamps it
describes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.models.enums import ExamStatus

#: "draft" | "scheduled" | "live" | "completed" | "archived"
EffectiveStatus = str


def effective_status(
    *, status: ExamStatus, starts_at: datetime, ends_at: datetime, now: datetime | None = None
) -> EffectiveStatus:
    now = now or datetime.now(UTC)
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)

    if status is ExamStatus.DRAFT:
        return "draft"
    if status is ExamStatus.CLOSED:
        return "archived"
    # published
    if now < starts_at:
        return "scheduled"
    if now > ends_at:
        return "completed"
    return "live"
