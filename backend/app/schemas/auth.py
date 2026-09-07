"""Auth request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.enums import AccessStatus, LoginAccessStatus, UserRole
from app.schemas.common import ORMModel

PASSWORD_MIN = 8


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    # Self-registration is limited to candidate/examiner. Admins are created by an admin.
    role: UserRole = UserRole.CANDIDATE

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name.strip(), self.last_name.strip()) if part)

    @field_validator("role")
    @classmethod
    def no_self_serve_admin(cls, value: UserRole) -> UserRole:
        if value is UserRole.ADMIN:
            raise ValueError("Administrator accounts cannot be self-registered")
        return value

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UpdateProfileRequest(BaseModel):
    """What a user may change about their own record: their name, and nothing else.

    Email is the login identity and role/access are decisions an administrator makes,
    so neither is editable here.
    """

    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=PASSWORD_MIN, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    access_status: AccessStatus
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    access_note: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    # Candidates only. ``None`` for examiners and admins, who are not login-gated.
    login_access: LoginAccessStatus | None = None


class AccessDecision(BaseModel):
    access_status: AccessStatus
    note: str | None = Field(default=None, max_length=500)
