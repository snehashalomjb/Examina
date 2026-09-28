"""Exam-level result reports: per-exam summaries and the approved-candidate mark list.

Read-only over data that already exists (exams, sessions, results, proctoring, integrity
rulings). "Approved" here is exactly what ``grading.py`` already means by a published
result - see ``exam_engine.needs_integrity_review`` and ``Result.published``. Nothing here
recomputes a mark or a rank; per-candidate rows are the same ones ``recruitment.exam_ranking``
already produces.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.v1.recruitment import exam_ranking
from app.core.deps import CurrentStaff, DbSession
from app.db.models import (
    Exam,
    ExamEnrollment,
    ExamSession,
    IntegrityVerdict,
    Result,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas.recruitment import RankingRow
from app.schemas.reports import ExamReportSummary
from app.services import exam_engine
from app.services.pdf_generator import generate_exam_mark_list_pdf

router = APIRouter(tags=["reports"])

_SORT_PATTERN = "^(name|candidate_id|marks|percentage|submitted_at|status)$"

_SORT_KEYS = {
    "name": lambda r: r.full_name.lower(),
    "candidate_id": lambda r: str(r.candidate_id),
    "marks": lambda r: r.obtained_marks,
    "percentage": lambda r: r.overall_percentage,
    "submitted_at": lambda r: r.time_taken_seconds or 0,
    "status": lambda r: (not r.published, r.is_flagged, r.integrity_verdict),
}


def _sorted_rows(rows: list[RankingRow], sort_by: str | None, order: str) -> list[RankingRow]:
    if not sort_by or sort_by not in _SORT_KEYS:
        return rows
    return sorted(rows, key=_SORT_KEYS[sort_by], reverse=(order == "desc"))


def _load_owned_exam(exam_id: uuid.UUID, staff: User, db: DbSession) -> Exam:
    exam = db.scalar(
        select(Exam).where(Exam.id == exam_id).options(selectinload(Exam.subject))
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    exam_engine.assert_exam_owned(exam, staff)
    return exam


@router.get("/reports/exams", response_model=list[ExamReportSummary])
def exam_report_list(staff: CurrentStaff, db: DbSession) -> list[ExamReportSummary]:
    """One row per exam with sessions: candidate counts, review state, marks range."""
    mine = staff.id if staff.role is UserRole.EXAMINER else None

    exam_stmt = select(Exam).options(selectinload(Exam.subject)).order_by(Exam.starts_at.desc())
    if mine:
        exam_stmt = exam_stmt.where(Exam.created_by_id == mine)
    exams = list(db.scalars(exam_stmt))

    summaries: list[ExamReportSummary] = []
    for exam in exams:
        total_candidates = (
            db.scalar(
                select(func.count(ExamEnrollment.id)).where(ExamEnrollment.exam_id == exam.id)
            )
            or 0
        )
        sessions = list(
            db.scalars(select(ExamSession).where(ExamSession.exam_id == exam.id))
        )
        if not sessions and not total_candidates:
            continue

        completed = [s for s in sessions if s.status != SessionStatus.IN_PROGRESS]
        flagged = sum(1 for s in sessions if s.is_flagged)
        rejected = sum(1 for s in sessions if s.integrity_verdict is IntegrityVerdict.MALPRACTICE)

        results = list(
            db.scalars(
                select(Result)
                .join(ExamSession, ExamSession.id == Result.session_id)
                .where(ExamSession.exam_id == exam.id)
            )
        )
        approved_marks = [r.obtained_marks for r in results if r.published]
        approved = len(approved_marks)
        pending_review = len(completed) - approved - rejected
        pending_review = max(pending_review, 0)

        summaries.append(
            ExamReportSummary(
                exam_id=exam.id,
                exam_title=exam.title,
                subject_name=exam.subject.name if exam.subject else None,
                exam_date=exam.starts_at,
                total_candidates=total_candidates,
                completed=len(completed),
                pending_review=pending_review,
                approved=approved,
                flagged=flagged,
                rejected=rejected,
                average_marks=(
                    round(sum(approved_marks) / len(approved_marks), 1) if approved_marks else None
                ),
                highest_marks=max(approved_marks) if approved_marks else None,
                lowest_marks=min(approved_marks) if approved_marks else None,
            )
        )
    return summaries


@router.get("/reports/exams/{exam_id}/candidates", response_model=list[RankingRow])
def exam_report_candidates(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    sort_by: str | None = Query(None, pattern=_SORT_PATTERN),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> list[RankingRow]:
    """Every candidate's row for one exam, with approval state, orderable for the mark list."""
    _load_owned_exam(exam_id, staff, db)
    rows = exam_ranking(exam_id=exam_id, staff=staff, db=db, limit=500)
    return _sorted_rows(rows, sort_by, order)


@router.get("/reports/exams/{exam_id}/pdf")
def exam_report_pdf(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    sort_by: str | None = Query(None, pattern=_SORT_PATTERN),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> Response:
    """The full exam mark list PDF - approved (published) candidates only."""
    exam = _load_owned_exam(exam_id, staff, db)
    rows = exam_ranking(exam_id=exam_id, staff=staff, db=db, limit=500)
    approved_rows = [r for r in rows if r.published]
    approved_rows = _sorted_rows(approved_rows, sort_by, order)

    pdf_bytes = generate_exam_mark_list_pdf(
        exam_title=exam.title,
        subject_name=exam.subject.name if exam.subject else None,
        exam_date=exam.starts_at,
        generated_by=staff.full_name,
        rows=approved_rows,
        passing_percentage=exam.passing_percentage,
    )
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in exam.title)[:40]
    filename = f"marklist_{safe_title}_{exam.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
