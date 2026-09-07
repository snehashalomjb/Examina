"""Password hashing and the three flavours of JWT this platform issues.

1. ``access``        - normal API auth, 30 min.
2. ``refresh``       - rotates an access token, 7 days.
3. ``exam_session``  - short-lived, bound to (session, exam, candidate). Presented on every
   live-exam call. Because it carries ``candidate_id``, handing it to a friend does not
   work: the dependency cross-checks it against the bearer's own access token.
4. ``password_reset``- single-purpose token for the forgot-password flow.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings

_hasher = PasswordHasher()

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_EXAM_SESSION = "exam_session"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"


# --------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


def generate_salt(length: int = 32) -> str:
    return secrets.token_hex(length // 2)


# ------------------------------------------------------------------------------ tokens
def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Return the claims, or ``None`` if the token is invalid/expired/tampered."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def create_access_token(*, user_id: uuid.UUID, role: str, access_status: str) -> str:
    return _encode(
        {
            "sub": str(user_id),
            "role": role,
            "access_status": access_status,
            "typ": TOKEN_TYPE_ACCESS,
        },
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(*, user_id: uuid.UUID) -> str:
    return _encode(
        {"sub": str(user_id), "typ": TOKEN_TYPE_REFRESH},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_password_reset_token(*, user_id: uuid.UUID) -> str:
    return _encode(
        {"sub": str(user_id), "typ": TOKEN_TYPE_PASSWORD_RESET},
        timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )


def create_exam_session_token(
    *,
    session_id: uuid.UUID,
    exam_id: uuid.UUID,
    candidate_id: uuid.UUID,
    expires_at: datetime,
) -> str:
    """Short-lived exam token, never outliving the exam window itself."""
    remaining = expires_at - datetime.now(UTC)
    cap = timedelta(minutes=settings.EXAM_SESSION_TOKEN_EXPIRE_MINUTES)
    ttl = min(remaining, cap)
    if ttl.total_seconds() <= 0:
        ttl = timedelta(seconds=30)  # enough to receive the "your time is up" response
    return _encode(
        {
            "sub": str(candidate_id),
            "sid": str(session_id),
            "exam_id": str(exam_id),
            "candidate_id": str(candidate_id),
            "typ": TOKEN_TYPE_EXAM_SESSION,
        },
        ttl,
    )


@dataclass(frozen=True)
class ExamSessionClaims:
    session_id: uuid.UUID
    exam_id: uuid.UUID
    candidate_id: uuid.UUID


def decode_exam_session_token(token: str) -> ExamSessionClaims | None:
    claims = decode_token(token)
    if not claims or claims.get("typ") != TOKEN_TYPE_EXAM_SESSION:
        return None
    try:
        return ExamSessionClaims(
            session_id=uuid.UUID(claims["sid"]),
            exam_id=uuid.UUID(claims["exam_id"]),
            candidate_id=uuid.UUID(claims["candidate_id"]),
        )
    except (KeyError, ValueError):
        return None
