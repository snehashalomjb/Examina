"""Login-approval schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.db.models.enums import LoginAccessStatus


class LoginAccessOut(BaseModel):
    """A candidate's own view of where their login request stands."""

    status: LoginAccessStatus
    requested_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None


class LoginRequestRow(BaseModel):
    """A row in the reviewer's queue."""

    id: uuid.UUID
    candidate_id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    email: EmailStr
    status: LoginAccessStatus
    requested_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by_name: str | None = None
    review_note: str | None = None
    # Which of the reviewer's exams this candidate is enrolled in - the basis of an
    # examiner's authority to decide.
    enrolled_exams: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class EnrollmentRow(BaseModel):
    candidate_id: uuid.UUID
    full_name: str
    email: EmailStr
    assigned_at: datetime
    assigned_by_name: str | None = None
    login_access: LoginAccessStatus | None = None
    has_attempted: bool = False


class EnrollmentCreate(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=1000)
