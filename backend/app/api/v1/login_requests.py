"""Candidate login requests, and the exam enrolment that scopes an examiner's authority.

Who may decide:

* **Administrators** — any candidate on the platform.
* **Examiners** — only candidates enrolled in an exam that examiner created. An examiner
  pointed at a candidate outside that scope gets a 403, not a silent success.
* **Candidates** — never. They cannot approve themselves, approve anyone else, or move
  their own status; there is no route that would let them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.db.models import (
    Exam,
    ExamEnrollment,
    ExamSession,
    LoginAccessRequest,
    LoginAccessStatus,
    User,
    UserRole,
)
from app.schemas.common import Message
from app.schemas.login_access import (
    EnrollmentCreate,
    EnrollmentRow,
    LoginRequestRow,
    ReviewDecision,
)
from app.services import login_access

router = APIRouter(tags=["login-requests"])
logger = get_logger("login-access")


def _exam_titles_for(db: DbSession, reviewer: User, candidate_id: uuid.UUID) -> list[str]:
    """Exams linking this candidate to the reviewer - the visible basis of authority."""
    stmt = (
        select(Exam.title)
        .join(ExamEnrollment, ExamEnrollment.exam_id == Exam.id)
        .where(ExamEnrollment.candidate_id == candidate_id)
    )
    if reviewer.role is UserRole.EXAMINER:
        stmt = stmt.where(Exam.created_by_id == reviewer.id)
    return list(db.scalars(stmt))


def _to_row(db: DbSession, reviewer: User, request: LoginAccessRequest) -> LoginRequestRow:
    candidate = request.candidate
    return LoginRequestRow(
        id=request.id,
        candidate_id=candidate.id,
        first_name=candidate.display_first_name,
        last_name=candidate.last_name,
        full_name=candidate.full_name,
        email=candidate.email,
        status=request.status,
        requested_at=request.requested_at,
        reviewed_at=request.reviewed_at,
        reviewed_by_name=request.reviewed_by.full_name if request.reviewed_by else None,
        review_note=request.review_note,
        enrolled_exams=_exam_titles_for(db, reviewer, candidate.id),
    )


@router.get("/login-requests", response_model=list[LoginRequestRow])
def list_login_requests(
    reviewer: CurrentStaff,
    db: DbSession,
    request_status: LoginAccessStatus | None = Query(default=None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
) -> list[LoginRequestRow]:
    """The review queue, already narrowed to what this reviewer is allowed to act on."""
    stmt = (
        select(LoginAccessRequest)
        .options(
            selectinload(LoginAccessRequest.candidate),
            selectinload(LoginAccessRequest.reviewed_by),
        )
        .order_by(LoginAccessRequest.requested_at.desc())
        .limit(limit)
    )
    if request_status is not None:
        stmt = stmt.where(LoginAccessRequest.status == request_status)

    allowed = login_access.reviewable_candidate_ids(db, reviewer)
    if allowed is not None:
        if not allowed:
            return []
        stmt = stmt.where(LoginAccessRequest.candidate_id.in_(allowed))

    return [_to_row(db, reviewer, request) for request in db.scalars(stmt)]


def _load_for_review(db: DbSession, reviewer: User, request_id: uuid.UUID) -> LoginAccessRequest:
    request = db.scalar(
        select(LoginAccessRequest)
        .where(LoginAccessRequest.id == request_id)
        .options(
            selectinload(LoginAccessRequest.candidate),
            selectinload(LoginAccessRequest.reviewed_by),
        )
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Login request not found")

    if not login_access.examiner_may_review(db, reviewer, request.candidate_id):
        logger.warning(
            "%s tried to review %s, who is outside their scope",
            reviewer.email,
            request.candidate.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This candidate is not enrolled in any of your exams, so you cannot "
                "review their login request."
            ),
        )
    return request


@router.post("/login-requests/{request_id}/approve", response_model=LoginRequestRow)
def approve_login_request(
    request_id: uuid.UUID, payload: ReviewDecision, reviewer: CurrentStaff, db: DbSession
) -> LoginRequestRow:
    request = _load_for_review(db, reviewer, request_id)
    login_access.decide(db, request=request, reviewer=reviewer, approve=True, note=payload.note)
    return _to_row(db, reviewer, request)


@router.post("/login-requests/{request_id}/reject", response_model=LoginRequestRow)
def reject_login_request(
    request_id: uuid.UUID, payload: ReviewDecision, reviewer: CurrentStaff, db: DbSession
) -> LoginRequestRow:
    """Reject, or revoke an approval that was already granted.

    Revocation is the same transition: an approved candidate moved back to ``rejected``
    loses platform access on their next request, not at some later sign-in.
    """
    request = _load_for_review(db, reviewer, request_id)
    login_access.decide(db, request=request, reviewer=reviewer, approve=False, note=payload.note)
    return _to_row(db, reviewer, request)


# ------------------------------------------------------------------- enrolment
@router.get("/exams/{exam_id}/enrollments", response_model=list[EnrollmentRow])
def list_enrollments(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> list[EnrollmentRow]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    rows = db.scalars(
        select(ExamEnrollment)
        .where(ExamEnrollment.exam_id == exam_id)
        .options(
            selectinload(ExamEnrollment.candidate).selectinload(User.login_access_request),
            selectinload(ExamEnrollment.assigned_by),
        )
        .order_by(ExamEnrollment.assigned_at.desc())
    )

    attempted = set(
        db.scalars(select(ExamSession.candidate_id).where(ExamSession.exam_id == exam_id))
    )

    return [
        EnrollmentRow(
            candidate_id=row.candidate_id,
            full_name=row.candidate.full_name,
            email=row.candidate.email,
            assigned_at=row.assigned_at,
            assigned_by_name=row.assigned_by.full_name if row.assigned_by else None,
            login_access=(
                row.candidate.login_access_request.status
                if row.candidate.login_access_request
                else LoginAccessStatus.PENDING
            ),
            has_attempted=row.candidate_id in attempted,
        )
        for row in rows
    ]


@router.post("/exams/{exam_id}/enrollments", response_model=Message)
def enroll_candidates(
    exam_id: uuid.UUID, payload: EnrollmentCreate, staff: CurrentStaff, db: DbSession
) -> Message:
    """Assign candidates to an exam. Only enrolled candidates ever see it."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    candidates = list(
        db.scalars(
            select(User).where(User.id.in_(payload.candidate_ids), User.role == UserRole.CANDIDATE)
        )
    )
    found = {c.id for c in candidates}
    missing = set(payload.candidate_ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{len(missing)} of those ids are not candidates",
        )

    already = set(
        db.scalars(select(ExamEnrollment.candidate_id).where(ExamEnrollment.exam_id == exam_id))
    )

    added = 0
    now = datetime.now(UTC)
    for candidate in candidates:
        if candidate.id in already:
            continue
        db.add(
            ExamEnrollment(
                exam_id=exam_id,
                candidate_id=candidate.id,
                assigned_by_id=staff.id,
                assigned_at=now,
            )
        )
        added += 1
    db.flush()

    logger.info("%s enrolled %d candidate(s) in %r", staff.email, added, exam.title)
    return Message(
        detail=f"Enrolled {added} candidate(s)"
        + (f"; {len(candidates) - added} were already enrolled" if added < len(candidates) else "")
    )


@router.delete("/exams/{exam_id}/enrollments/{candidate_id}", response_model=Message)
def remove_enrollment(
    exam_id: uuid.UUID, candidate_id: uuid.UUID, staff: CurrentStaff, db: DbSession
) -> Message:
    enrollment = db.scalar(
        select(ExamEnrollment).where(
            ExamEnrollment.exam_id == exam_id, ExamEnrollment.candidate_id == candidate_id
        )
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That candidate is not enrolled"
        )

    attempted = db.scalar(
        select(func.count(ExamSession.id)).where(
            ExamSession.exam_id == exam_id, ExamSession.candidate_id == candidate_id
        )
    )
    if attempted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That candidate has already sat this exam and cannot be un-enrolled",
        )

    db.delete(enrollment)
    db.flush()
    logger.info("%s removed candidate %s from exam %s", staff.email, candidate_id, exam_id)
    return Message(detail="Enrolment removed")
