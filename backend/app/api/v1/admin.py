"""Admin surface: user management, the examiner access gate, and platform stats."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import CurrentAdmin, CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.db.models import (
    AccessStatus,
    AiEvaluation,
    Answer,
    Exam,
    ExamSession,
    ExamStatus,
    GradeStatus,
    LoginAccessRequest,
    LoginAccessStatus,
    Question,
    Result,
    SessionStatus,
    Subject,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminStats,
    AdminUserCreate,
    CandidateAdminRow,
    RecentActivity,
    UserAdminOut,
)
from app.schemas.auth import AccessDecision, UserOut
from app.schemas.common import Message

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("admin")


def _to_admin_out(user: User, exam_count: int = 0, session_count: int = 0) -> UserAdminOut:
    data = UserOut.model_validate(user).model_dump()
    return UserAdminOut(
        **data,
        exam_count=exam_count,
        session_count=session_count,
        access_changed_at=user.access_changed_at,
        access_changed_by_email=(user.access_changed_by.email if user.access_changed_by else None),
    )


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    admin: CurrentAdmin,
    db: DbSession,
    role: UserRole | None = None,
    access_status: AccessStatus | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[UserAdminOut]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if access_status is not None:
        stmt = stmt.where(User.access_status == access_status)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(pattern) | func.lower(User.full_name).like(pattern)
        )

    users = list(db.scalars(stmt))

    exam_counts = dict(
        db.execute(
            select(Exam.created_by_id, func.count(Exam.id)).group_by(Exam.created_by_id)
        ).all()
    )
    session_counts = dict(
        db.execute(
            select(ExamSession.candidate_id, func.count(ExamSession.id)).group_by(
                ExamSession.candidate_id
            )
        ).all()
    )

    return [_to_admin_out(u, exam_counts.get(u.id, 0), session_counts.get(u.id, 0)) for u in users]


@router.get("/users/pending", response_model=list[UserAdminOut])
def list_pending(admin: CurrentAdmin, db: DbSession) -> list[UserAdminOut]:
    """Everyone waiting on an access decision - the admin dashboard's action queue.

    Both examiners and candidates land here on registration; only an administrator can
    clear them.
    """
    users = db.scalars(
        select(User)
        .where(User.access_status == AccessStatus.PENDING, User.role != UserRole.ADMIN)
        .order_by(User.created_at.asc())
    )
    return [_to_admin_out(u) for u in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: AdminUserCreate, admin: CurrentAdmin, db: DbSession) -> UserOut:
    """Create any user, including another admin. The only route to an admin account."""
    if db.scalar(select(User).where(User.email == payload.email.lower())) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )
    first, _, last = payload.full_name.strip().partition(" ")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role,
        access_status=payload.access_status,
        access_changed_at=datetime.now(UTC),
        access_changed_by_id=admin.id,
    )
    user.set_name(first, last)

    # A candidate created by an administrator is already vouched for, so give them
    # login access straight away rather than making them queue at first sign-in.
    if user.role is UserRole.CANDIDATE and payload.access_status is AccessStatus.APPROVED:
        db.add(user)
        db.flush()
        db.add(
            LoginAccessRequest(
                candidate_id=user.id,
                status=LoginAccessStatus.APPROVED,
                requested_at=datetime.now(UTC),
                reviewed_at=datetime.now(UTC),
                reviewed_by_id=admin.id,
                review_note="Created directly by an administrator",
            )
        )
    else:
        db.add(user)
    db.flush()
    logger.info("Admin %s created %s (%s)", admin.email, user.email, user.role.value)
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}/access", response_model=UserAdminOut)
def set_access(
    user_id: uuid.UUID, payload: AccessDecision, admin: CurrentAdmin, db: DbSession
) -> UserAdminOut:
    """Grant, revoke, or reset a user's access.

    Administrator-only, by design: an examiner can never approve anyone, including
    another examiner. Until an account is ``approved`` here it is inert - an examiner
    gets 403 from every question-bank, exam, grading and proctoring route, and a
    candidate gets 403 from every exam route.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own access status",
        )
    if user.role is UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator access cannot be gated",
        )

    previous = user.access_status
    user.access_status = payload.access_status
    user.access_note = payload.note
    user.access_changed_at = datetime.now(UTC)
    user.access_changed_by_id = admin.id
    db.flush()
    db.refresh(user)

    logger.info(
        "Admin %s changed access for %s: %s -> %s (%s)",
        admin.email,
        user.email,
        previous.value,
        user.access_status.value,
        payload.note or "no note",
    )
    return _to_admin_out(user)


@router.patch("/users/{user_id}/active", response_model=UserAdminOut)
def set_active(
    user_id: uuid.UUID, is_active: bool, admin: CurrentAdmin, db: DbSession
) -> UserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself"
        )
    user.is_active = is_active
    db.flush()
    db.refresh(user)
    logger.info("Admin %s set active=%s for %s", admin.email, is_active, user.email)
    return _to_admin_out(user)


@router.delete("/users/{user_id}", response_model=Message)
def delete_user(user_id: uuid.UUID, admin: CurrentAdmin, db: DbSession) -> Message:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete yourself"
        )
    email = user.email
    db.delete(user)
    db.flush()
    logger.warning("Admin %s deleted user %s", admin.email, email)
    return Message(detail=f"Deleted {email}")


@router.get("/stats", response_model=AdminStats)
def stats(admin: CurrentAdmin, db: DbSession) -> AdminStats:
    role_counts = dict(db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all())
    return AdminStats(
        total_users=db.scalar(select(func.count(User.id))) or 0,
        candidates=role_counts.get(UserRole.CANDIDATE, 0),
        examiners=role_counts.get(UserRole.EXAMINER, 0),
        admins=role_counts.get(UserRole.ADMIN, 0),
        pending_approvals=db.scalar(
            select(func.count(User.id)).where(
                User.access_status == AccessStatus.PENDING, User.role != UserRole.ADMIN
            )
        )
        or 0,
        subjects=db.scalar(select(func.count(Subject.id))) or 0,
        questions=db.scalar(select(func.count(Question.id)).where(Question.is_active)) or 0,
        exams=db.scalar(select(func.count(Exam.id))) or 0,
        published_exams=db.scalar(
            select(func.count(Exam.id)).where(Exam.status == ExamStatus.PUBLISHED)
        )
        or 0,
        live_sessions=db.scalar(
            select(func.count(ExamSession.id)).where(
                ExamSession.status == SessionStatus.IN_PROGRESS
            )
        )
        or 0,
        flagged_sessions=db.scalar(select(func.count(ExamSession.id)).where(ExamSession.is_flagged))
        or 0,
        pending_grading=db.scalar(
            select(func.count(Answer.id)).where(
                Answer.grade_status.in_([GradeStatus.PENDING_AI, GradeStatus.AI_SCORED])
            )
        )
        or 0,
    )


@router.get("/candidates", response_model=list[CandidateAdminRow])
def list_candidates(
    staff: CurrentStaff,
    db: DbSession,
    search: str | None = None,
    limit: int = Query(200, ge=1, le=500),
) -> list[CandidateAdminRow]:
    """Candidate roster.

    Deliberately available to examiners as well as admins - an examiner needs to see who
    sat their exams and how those attempts went.
    """
    stmt = (
        select(User)
        .where(User.role == UserRole.CANDIDATE)
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(User.email).like(pattern) | func.lower(User.full_name).like(pattern)
        )
    candidates = list(db.scalars(stmt))
    if not candidates:
        return []

    ids = [c.id for c in candidates]

    attempts = dict(
        db.execute(
            select(ExamSession.candidate_id, func.count(ExamSession.id))
            .where(ExamSession.candidate_id.in_(ids))
            .group_by(ExamSession.candidate_id)
        ).all()
    )
    completed = dict(
        db.execute(
            select(ExamSession.candidate_id, func.count(ExamSession.id))
            .where(
                ExamSession.candidate_id.in_(ids),
                ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.AUTO_SUBMITTED]),
            )
            .group_by(ExamSession.candidate_id)
        ).all()
    )
    flagged = dict(
        db.execute(
            select(ExamSession.candidate_id, func.count(ExamSession.id))
            .where(ExamSession.candidate_id.in_(ids), ExamSession.is_flagged)
            .group_by(ExamSession.candidate_id)
        ).all()
    )
    averages = dict(
        db.execute(
            select(ExamSession.candidate_id, func.avg(Result.percentage))
            .join(Result, Result.session_id == ExamSession.id)
            .where(ExamSession.candidate_id.in_(ids), Result.published.is_(True))
            .group_by(ExamSession.candidate_id)
        ).all()
    )

    return [
        CandidateAdminRow(
            id=c.id,
            full_name=c.full_name,
            email=c.email,
            access_status=c.access_status,
            is_active=c.is_active,
            created_at=c.created_at,
            last_login_at=c.last_login_at,
            attempts=attempts.get(c.id, 0),
            completed=completed.get(c.id, 0),
            flagged_sessions=flagged.get(c.id, 0),
            average_percentage=(
                round(float(averages[c.id]), 2) if averages.get(c.id) is not None else None
            ),
        )
        for c in candidates
    ]


@router.get("/activity", response_model=list[RecentActivity])
def recent_activity(
    staff: CurrentStaff, db: DbSession, limit: int = Query(15, ge=1, le=50)
) -> list[RecentActivity]:
    """A small, cheap activity feed for the dashboards."""
    items: list[RecentActivity] = []

    for user in db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)):
        items.append(
            RecentActivity(
                kind="user",
                message=f"{user.full_name} registered as {user.role.value}",
                at=user.created_at,
                severity="warning" if user.access_status == AccessStatus.PENDING else "info",
            )
        )

    sessions = db.scalars(select(ExamSession).order_by(ExamSession.created_at.desc()).limit(limit))
    for session in sessions:
        items.append(
            RecentActivity(
                kind="session",
                message=(
                    f"{session.candidate.full_name} - {session.exam.title} "
                    f"({session.status.value.replace('_', ' ')})"
                ),
                at=session.created_at,
                severity="critical" if session.is_flagged else "info",
            )
        )

    for ev in db.scalars(select(AiEvaluation).order_by(AiEvaluation.created_at.desc()).limit(5)):
        items.append(
            RecentActivity(
                kind="grading",
                message=f"{ev.provider} scored an answer {ev.score:g}/{ev.max_score:g}",
                at=ev.created_at,
                severity="info",
            )
        )

    items.sort(key=lambda i: i.at, reverse=True)
    return items[:limit]
