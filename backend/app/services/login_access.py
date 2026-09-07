"""Login-approval rules.

The two ideas this module keeps apart:

* **Account state** (``users.is_active`` / ``users.access_status``) — does this account
  exist and is it usable at all. A candidate's account is created active and stays active.
* **Login approval** (``login_access_requests.status``) — may this candidate actually use
  the platform. Raised on their first valid sign-in, decided by an administrator or by an
  examiner authorised over them, and durable once approved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import (
    Exam,
    ExamEnrollment,
    LoginAccessRequest,
    LoginAccessStatus,
    User,
    UserRole,
)

logger = get_logger("login-access")


def get_request(db: Session, candidate_id: uuid.UUID) -> LoginAccessRequest | None:
    return db.scalar(
        select(LoginAccessRequest).where(LoginAccessRequest.candidate_id == candidate_id)
    )


def ensure_request(db: Session, candidate: User) -> LoginAccessRequest:
    """Return the candidate's standing request, raising one on first sign-in.

    Deliberately get-or-create: an approved candidate reuses the same row on every later
    login and never re-enters the queue. Only an explicit revocation moves them back.
    """
    existing = get_request(db, candidate.id)
    if existing is not None:
        return existing

    request = LoginAccessRequest(
        candidate_id=candidate.id,
        status=LoginAccessStatus.PENDING,
        requested_at=datetime.now(UTC),
    )
    db.add(request)
    db.flush()
    logger.info(
        "Login approval requested for %s (%s) - awaiting review",
        candidate.email,
        candidate.id,
    )
    return request


def status_for(db: Session, user: User) -> LoginAccessStatus | None:
    """The login-approval status to report. ``None`` for non-candidates."""
    if user.role is not UserRole.CANDIDATE:
        return None
    request = get_request(db, user.id)
    return request.status if request else LoginAccessStatus.PENDING


def examiner_may_review(db: Session, examiner: User, candidate_id: uuid.UUID) -> bool:
    """Is this candidate inside the examiner's authority?

    Authority comes from enrolment: an examiner may decide a candidate's login request
    only when that candidate is enrolled in one of the examiner's own exams. Admins are
    unrestricted and never reach this function.
    """
    if examiner.role is UserRole.ADMIN:
        return True
    if examiner.role is not UserRole.EXAMINER:
        return False

    match = db.scalar(
        select(ExamEnrollment.id)
        .join(Exam, Exam.id == ExamEnrollment.exam_id)
        .where(
            ExamEnrollment.candidate_id == candidate_id,
            Exam.created_by_id == examiner.id,
        )
        .limit(1)
    )
    return match is not None


def reviewable_candidate_ids(db: Session, reviewer: User) -> set[uuid.UUID] | None:
    """Candidate IDs this reviewer may act on. ``None`` means 'no restriction'."""
    if reviewer.role is UserRole.ADMIN:
        return None
    rows = db.scalars(
        select(ExamEnrollment.candidate_id)
        .join(Exam, Exam.id == ExamEnrollment.exam_id)
        .where(Exam.created_by_id == reviewer.id)
    )
    return set(rows)


def decide(
    db: Session,
    *,
    request: LoginAccessRequest,
    reviewer: User,
    approve: bool,
    note: str | None = None,
) -> LoginAccessRequest:
    previous = request.status
    request.status = LoginAccessStatus.APPROVED if approve else LoginAccessStatus.REJECTED
    request.reviewed_at = datetime.now(UTC)
    request.reviewed_by_id = reviewer.id
    request.review_note = note
    db.flush()

    logger.info(
        "%s (%s) set login access for %s: %s -> %s (%s)",
        reviewer.email,
        reviewer.role.value,
        request.candidate.email,
        previous.value,
        request.status.value,
        note or "no note",
    )
    return request


def enrolled_exam_ids(db: Session, candidate_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        db.scalars(
            select(ExamEnrollment.exam_id).where(ExamEnrollment.candidate_id == candidate_id)
        )
    )


def is_enrolled(db: Session, *, exam_id: uuid.UUID, candidate_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(ExamEnrollment.id)
            .where(
                ExamEnrollment.exam_id == exam_id,
                ExamEnrollment.candidate_id == candidate_id,
            )
            .limit(1)
        )
        is not None
    )
