"""Proctoring event intake and review schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.db.models.enums import IntegrityVerdict, ProctorEventType, ProctorSeverity


class ProctorEventIn(BaseModel):
    event_type: ProctorEventType
    occurred_at: datetime
    severity: ProctorSeverity | None = None
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    metadata: dict | None = None


class ProctorBatchIn(BaseModel):
    """One flush of the client-side event buffer (~10 s worth)."""

    events: list[ProctorEventIn] = Field(..., max_length=200)


class ProctorBatchOut(BaseModel):
    accepted: int
    suspicion_score: float
    tab_switch_count: int
    is_flagged: bool
    terminated: bool
    warnings: list[str] = Field(default_factory=list)


class SnapshotOut(BaseModel):
    snapshot_key: str
    event_id: uuid.UUID | None = None


class ProctorEventOut(BaseModel):
    id: uuid.UUID
    event_type: ProctorEventType
    severity: ProctorSeverity
    occurred_at: datetime
    server_received_at: datetime
    duration_ms: int | None = None
    weight: float
    metadata: dict | None = None
    snapshot_url: str | None = None


class ProctorReview(BaseModel):
    session_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    exam_title: str
    status: str
    started_at: datetime
    submitted_at: datetime | None
    suspicion_score: float
    tab_switch_count: int
    is_flagged: bool
    termination_reason: str | None = None
    #: The examiner's ruling on how the sitting was conducted. Separate from the score.
    integrity_verdict: IntegrityVerdict = IntegrityVerdict.PENDING
    integrity_note: str | None = None
    integrity_reviewed_by: str | None = None
    integrity_reviewed_at: datetime | None = None
    #: True when this sitting is flagged and still unreviewed - the queue an examiner
    #: has to clear before results for the exam can go out.
    needs_integrity_review: bool = False
    breakdown: dict[str, float] = Field(default_factory=dict)
    events: list[ProctorEventOut] = Field(default_factory=list)


class IntegrityDecision(BaseModel):
    """An examiner's ruling on a sitting.

    ``note`` is required for a malpractice verdict: a ruling that costs a candidate
    their result must carry a reason someone can review afterwards.
    """

    verdict: IntegrityVerdict
    note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _malpractice_needs_a_reason(self) -> IntegrityDecision:
        if self.verdict is IntegrityVerdict.MALPRACTICE and not (self.note or "").strip():
            raise ValueError("A malpractice verdict needs a note explaining the decision")
        if self.verdict is IntegrityVerdict.PENDING:
            raise ValueError("Cannot rule a sitting back to pending")
        return self
