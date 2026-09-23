"""Admin dashboard and user-management schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.enums import AccessStatus, LoginAccessStatus, UserRole
from app.schemas.auth import PASSWORD_MIN, UserOut


class UserAdminOut(UserOut):
    exam_count: int = 0
    session_count: int = 0
    access_changed_at: datetime | None = None
    access_changed_by_email: EmailStr | None = None


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=150)
    role: UserRole
    access_status: AccessStatus = AccessStatus.APPROVED


class AdminSetPasswordRequest(BaseModel):
    """An administrator setting someone else's password directly.

    Distinct from ``ChangePasswordRequest``: there is no current password to prove,
    because the acting user is an admin, not the account owner.
    """

    new_password: str = Field(..., min_length=PASSWORD_MIN, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class AdminStats(BaseModel):
    total_users: int
    candidates: int
    examiners: int
    admins: int
    pending_approvals: int
    subjects: int
    questions: int
    exams: int
    published_exams: int
    #: Published and inside its start/end window right now - see
    #: ``app.services.exam_status``. Distinct from ``live_sessions`` below, which counts
    #: candidate sittings, not exams.
    live_exams: int
    #: Published, but its window has already ended.
    completed_exams: int
    live_sessions: int
    flagged_sessions: int
    pending_grading: int


class ExaminerStats(BaseModel):
    my_questions: int
    my_exams: int
    published_exams: int
    live_sessions: int
    flagged_sessions: int
    pending_grading: int
    subjects: int
    active_assessments: int
    completed_assessments: int
    published_results_count: int
    total_candidates: int


class CandidateStats(BaseModel):
    available_exams: int
    completed_exams: int
    published_results: int
    average_percentage: float | None = None
    best_percentage: float | None = None


class CandidateAdminRow(BaseModel):
    """The candidate list that admins and examiners both see."""

    id: uuid.UUID
    full_name: str
    email: EmailStr
    access_status: AccessStatus
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    #: Permission to *use* the platform, separate from whether the account exists.
    #: An exam may only be assigned to a candidate who can actually sign in and sit it.
    login_access: LoginAccessStatus | None = None
    attempts: int = 0
    completed: int = 0
    flagged_sessions: int = 0
    average_percentage: float | None = None


class RecentActivity(BaseModel):
    kind: str
    message: str
    at: datetime
    severity: str = "info"


class ComponentHealth(BaseModel):
    #: "checked" - a real probe ran this request. "configured" - not independently
    #: measurable from here, so this only reports whether the feature is wired up at
    #: all, and is labelled differently in the UI so it is never confused with a live
    #: health check.
    basis: str
    status: str
    detail: str | None = None


class SystemHealth(BaseModel):
    api: ComponentHealth
    database: ComponentHealth
    storage: ComponentHealth
    websocket: ComponentHealth
    ai_proctoring: ComponentHealth
    authentication: ComponentHealth
