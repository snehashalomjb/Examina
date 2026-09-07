"""Proctoring event intake and review schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import ProctorEventType, ProctorSeverity


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
    breakdown: dict[str, float] = Field(default_factory=dict)
    events: list[ProctorEventOut] = Field(default_factory=list)
