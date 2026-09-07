"""Registration, login, refresh, and the forgot/reset password flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentCandidateAccount, CurrentUser, DbSession
from app.core.logging_config import get_logger
from app.core.security import (
    TOKEN_TYPE_PASSWORD_RESET,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.models import AccessStatus, LoginAccessStatus, User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UpdateProfileRequest,
    UserOut,
)
from app.schemas.common import Message
from app.schemas.login_access import LoginAccessOut
from app.services import login_access

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth")


def _issue_tokens(user: User, login_status: LoginAccessStatus | None = None) -> TokenPair:
    """Issue the token pair.

    A candidate awaiting approval still receives a token: they need one to see their own
    pending screen and to sign out. It buys them nothing else - every protected candidate
    route sits behind the login-approval gate in ``deps.require_login_approval``.
    """
    return TokenPair(
        access_token=create_access_token(
            user_id=user.id, role=user.role.value, access_status=user.access_status.value
        ),
        refresh_token=create_refresh_token(user_id=user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
        login_access=login_status,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> TokenPair:
    """Self-service registration.

    **Candidates**: registration is open and needs no approval. The account is created
    active and they can use the login page immediately. What is gated is the *login* -
    the first time they sign in, a login-approval request is raised for a reviewer.

    **Examiners**: the account itself stays pending until an administrator approves it,
    because an examiner can author papers and grade. Approval is administrator-only; no
    examiner can approve anyone, including another examiner.
    """
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    is_candidate = payload.role is UserRole.CANDIDATE
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        # The candidate's *account* is active from the moment it is created. Approval
        # belongs to the login flow, not to registration.
        access_status=AccessStatus.APPROVED if is_candidate else AccessStatus.PENDING,
        access_changed_at=datetime.now(UTC) if is_candidate else None,
    )
    user.set_name(payload.first_name, payload.last_name)
    db.add(user)
    db.flush()

    logger.info(
        "Registered %s as %s (account %s)",
        user.email,
        user.role.value,
        user.access_status.value,
    )
    # No login request yet - it is raised when they first sign in.
    return _issue_tokens(user, LoginAccessStatus.PENDING if is_candidate else None)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    # Same error and roughly the same work whether the email exists or not.
    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("Failed login for %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated"
        )

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    user.last_login_at = datetime.now(UTC)

    # The approval gate lives here, at first sign-in - not at registration. An approved
    # candidate reuses their standing request and never queues again.
    login_status: LoginAccessStatus | None = None
    if user.role is UserRole.CANDIDATE:
        login_status = login_access.ensure_request(db, user).status

    db.flush()
    logger.info(
        "Login: %s (%s/%s%s)",
        user.email,
        user.role.value,
        user.access_status.value,
        f", login={login_status.value}" if login_status else "",
    )
    return _issue_tokens(user, login_status)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    claims = decode_token(payload.refresh_token)
    if not claims or claims.get("typ") != TOKEN_TYPE_REFRESH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed refresh token"
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer active"
        )
    # Re-read the status rather than trusting the old token: a revocation must take
    # effect on the next refresh, not at the next full sign-in.
    return _issue_tokens(user, login_access.status_for(db, user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> UserOut:
    """A user editing their own name.

    It reads the id from the JWT, so it can only ever touch the caller's own record.
    """
    user.set_name(payload.first_name, payload.last_name)
    db.flush()
    logger.info("Profile updated for %s", user.email)
    return UserOut.model_validate(user)


@router.get("/login-access", response_model=LoginAccessOut)
def my_login_access(user: CurrentCandidateAccount, db: DbSession) -> LoginAccessOut:
    """A candidate's own login-approval status.

    Deliberately behind the *account* gate rather than the login-approval gate: someone
    who is still pending has to be able to see that they are pending. It reads the
    authenticated user's own id from the JWT, so it cannot be pointed at anyone else.
    """
    request = login_access.ensure_request(db, user)
    return LoginAccessOut(
        status=request.status,
        requested_at=request.requested_at,
        reviewed_at=request.reviewed_at,
        review_note=request.review_note,
    )


@router.post("/forgot-password", response_model=Message)
def forgot_password(payload: ForgotPasswordRequest, db: DbSession) -> Message:
    """Start a password reset.

    Always answers the same way so the endpoint cannot be used to enumerate accounts.
    This deployment has no mail transport: the reset link is written to the log, and in a
    development environment it is also returned in the response so the flow is usable.
    """
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    generic = "If an account exists for that email, a reset link has been issued."

    if user is None or not user.is_active:
        logger.info("Password reset requested for unknown/inactive email %s", payload.email)
        return Message(detail=generic)

    token = create_password_reset_token(user_id=user.id)
    logger.info("Password reset token issued for %s: %s", user.email, token)

    if settings.ENVIRONMENT == "development":
        return Message(detail=f"{generic} [dev] reset_token={token}")
    return Message(detail=generic)


@router.post("/reset-password", response_model=Message)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> Message:
    claims = decode_token(payload.token)
    if not claims or claims.get("typ") != TOKEN_TYPE_PASSWORD_RESET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
        )
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed reset token"
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account unavailable")

    user.password_hash = hash_password(payload.new_password)
    db.flush()
    logger.info("Password reset completed for %s", user.email)
    return Message(detail="Your password has been updated. You can now sign in.")
