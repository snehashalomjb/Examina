"""Admin dashboard and user-management schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.db.models.enums import AccessStatus, UserRole
from app.schemas.auth import UserOut


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
    attempts: int = 0
    completed: int = 0
    flagged_sessions: int = 0
    average_percentage: float | None = None


class RecentActivity(BaseModel):
    kind: str
    message: str
    at: datetime
    severity: str = "info"
