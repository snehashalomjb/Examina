"""Shared FastAPI dependencies: authentication, role gates, exam-session binding."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    decode_exam_session_token,
    decode_token,
)
from app.db.models import (
    AccessStatus,
    ExamSession,
    LoginAccessRequest,
    LoginAccessStatus,
    User,
    UserRole,
)
from app.db.session import get_db

logger = get_logger("auth")
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _unauthorized()

    claims = decode_token(credentials.credentials)
    if not claims or claims.get("typ") != TOKEN_TYPE_ACCESS:
        raise _unauthorized("Invalid or expired token")

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise _unauthorized("Malformed token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User no longer active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory guarding an endpoint by role.

    Note the ``= Depends(...)`` default rather than an ``Annotated`` alias: this module
    uses ``from __future__ import annotations``, so a closure-local name inside an
    annotation string cannot be resolved by FastAPI and the parameter would be mistaken
    for a query field.
    """

    allowed = set(roles)

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            logger.warning(
                "Role denied: %s (%s) tried a %s-only route",
                user.email,
                user.role.value,
                "/".join(r.value for r in allowed),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not have access to this resource",
            )
        return user

    return _dependency


def require_approved(*roles: UserRole) -> Callable[[User], User]:
    """Role gate *plus* the admin access gate.

    This is the dependency that makes "an examiner can only build the question bank once
    an admin grants access" real. Admins bypass the approval check.
    """

    role_gate = require_role(*roles)

    def _dependency(user: User = Depends(role_gate)) -> User:
        if user.role is UserRole.ADMIN:
            return user
        if user.access_status is not AccessStatus.APPROVED:
            logger.warning(
                "Access gate blocked %s (%s, status=%s)",
                user.email,
                user.role.value,
                user.access_status.value,
            )
            detail = (
                "Your account is awaiting administrator approval."
                if user.access_status is AccessStatus.PENDING
                else "Your access has been revoked by an administrator."
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return user

    return _dependency


def require_login_approval(
    user: User = Depends(require_approved(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
) -> User:
    """The candidate gate: role, account state, **and** an approved login request.

    This is the layer that makes the approval workflow real rather than cosmetic. Every
    protected candidate route depends on it, so a pending or rejected candidate cannot
    reach dashboard data, exams, questions or attempts by typing a URL or calling the API
    directly - the frontend's routing is a convenience, not the control.
    """
    request = db.scalar(
        select(LoginAccessRequest).where(LoginAccessRequest.candidate_id == user.id)
    )
    status_value = request.status if request else LoginAccessStatus.PENDING

    if status_value is LoginAccessStatus.APPROVED:
        return user

    logger.warning("Login-approval gate blocked %s (status=%s)", user.email, status_value.value)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Your login access request has been rejected. Contact an administrator."
            if status_value is LoginAccessStatus.REJECTED
            else "Your login access request is awaiting approval."
        ),
        headers={"X-Login-Access": status_value.value},
    )


# --- Common pre-built gates -------------------------------------------------
CurrentAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
CurrentExaminer = Annotated[User, Depends(require_approved(UserRole.EXAMINER))]
CurrentStaff = Annotated[User, Depends(require_approved(UserRole.EXAMINER, UserRole.ADMIN))]

#: A signed-in candidate whose login has **not** necessarily been approved. Only for the
#: pending/rejected screens and their own status endpoint - never for exam data.
CurrentCandidateAccount = Annotated[User, Depends(require_approved(UserRole.CANDIDATE))]

#: A candidate cleared to actually use the platform. The default for candidate routes.
CurrentCandidate = Annotated[User, Depends(require_login_approval)]


def get_exam_session(
    db: DbSession,
    user: CurrentCandidate,
    x_exam_token: Annotated[str | None, Header(alias="X-Exam-Token")] = None,
) -> ExamSession:
    """Resolve the live exam session from the ``X-Exam-Token`` header.

    Rejects a shared token: the claims must name the same candidate as the access token.
    """
    if not x_exam_token:
        raise _unauthorized("Missing exam session token")

    claims = decode_exam_session_token(x_exam_token)
    if claims is None:
        raise _unauthorized("Invalid or expired exam session token")

    if claims.candidate_id != user.id:
        logger.warning(
            "Exam token misuse: token for %s presented by %s", claims.candidate_id, user.id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This exam token was issued to a different candidate",
        )

    session = db.get(ExamSession, claims.session_id)
    if session is None or session.candidate_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam session not found")
    return session


ActiveExamSession = Annotated[ExamSession, Depends(get_exam_session)]


class WebSocketAuthError(Exception):
    """The socket handshake could not be authenticated. Carries a close reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def authenticate_ws(db: Session, *, access_token: str, exam_token: str) -> ExamSession:
    """Resolve a live exam session for a WebSocket handshake.

    The same two-token rule the HTTP routes enforce - an access token identifying the
    user and an exam token bound to (session, exam, candidate) - just without the request
    scaffolding, because ``Depends`` on a ``WebSocket`` cannot read an ``Authorization``
    header the browser API refuses to send.

    Tokens arrive in ``Sec-WebSocket-Protocol`` rather than the query string on purpose:
    a query string ends up in every proxy and access log, and an exam token in a log file
    is a shareable exam token.
    """
    claims = decode_token(access_token)
    if not claims or claims.get("typ") != TOKEN_TYPE_ACCESS:
        raise WebSocketAuthError("Invalid or expired token")
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise WebSocketAuthError("Malformed token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise WebSocketAuthError("User no longer active")
    if user.role is not UserRole.CANDIDATE:
        raise WebSocketAuthError("Only a candidate may stream proctoring events")

    exam_claims = decode_exam_session_token(exam_token)
    if exam_claims is None:
        raise WebSocketAuthError("Invalid or expired exam session token")
    if exam_claims.candidate_id != user.id:
        logger.warning(
            "Exam token misuse over WS: token for %s presented by %s",
            exam_claims.candidate_id,
            user.id,
        )
        raise WebSocketAuthError("This exam token was issued to a different candidate")

    session = db.get(ExamSession, exam_claims.session_id)
    if session is None or session.candidate_id != user.id:
        raise WebSocketAuthError("Exam session not found")
    return session
