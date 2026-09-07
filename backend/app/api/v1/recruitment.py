"""Corporate recruitment: candidate ranking and examiner shortlisting.

Nothing here scores or ranks automatically. Ranking is derived from results at query time;
shortlisting is an explicit examiner action. The platform assists, it does not decide.
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
    Answer,
    CandidateShortlist,
    Exam,
    ExamSection,
    ExamSession,
    ExamType,
    Result,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas.recruitment import RankingRow, SectionScore, ShortlistBulkCreate, ShortlistOut

router = APIRouter(tags=["recruitment"])
logger = get_logger("recruitment")


def _require_corporate(exam: Exam) -> None:
    if exam.exam_type is not ExamType.CORPORATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available for corporate exams",
        )


# --------------------------------------------------------------- ranking


@router.get("/exams/{exam_id}/ranking", response_model=list[RankingRow])
def exam_ranking(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    limit: int = Query(500, ge=1, le=2000),
) -> list[RankingRow]:
    """Full candidate ranking for a corporate exam, with section-wise breakdown."""
    exam = db.scalar(
        select(Exam)
        .where(Exam.id == exam_id)
        .options(selectinload(Exam.sections))
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    _require_corporate(exam)

    # Load completed sessions + results
    sessions = list(
        db.scalars(
            select(ExamSession)
            .where(
                ExamSession.exam_id == exam_id,
                ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.AUTO_SUBMITTED]),
            )
            .options(
                selectinload(ExamSession.candidate),
                selectinload(ExamSession.result),
                selectinload(ExamSession.answers).selectinload(Answer.question),
            )
            .limit(limit)
        )
    )

    # Shortlist decisions keyed by candidate_id
    shortlists = {
        sl.candidate_id: sl.status
        for sl in db.scalars(
            select(CandidateShortlist).where(CandidateShortlist.exam_id == exam_id)
        )
    }

    # Section names for breakdown
    sections = sorted(exam.sections, key=lambda s: s.order_index)
    section_by_id = {s.id: s for s in sections}

    rows: list[RankingRow] = []
    for session in sessions:
        result = session.result
        if result is None:
            continue

        correct = result.correct_count
        answered = correct + result.incorrect_count
        accuracy = round(correct / answered * 100, 2) if answered else 0.0

        # Section breakdown from answers
        section_scores: list[SectionScore] = []
        if sections:
            sec_data: dict[uuid.UUID, dict] = {
                s.id: {"name": s.name, "obtained": 0.0, "total": 0.0, "c": 0, "i": 0, "u": 0}
                for s in sections
            }
            for ans in session.answers:
                sid = ans.section_id
                if sid and sid in sec_data:
                    awarded = ans.awarded_marks or 0.0
                    maximum = ans.max_marks or 0.0
                    sec_data[sid]["obtained"] += awarded
                    sec_data[sid]["total"] += maximum
                    if ans.awarded_marks is not None:
                        if ans.awarded_marks >= ans.max_marks:
                            sec_data[sid]["c"] += 1
                        elif ans.awarded_marks > 0:
                            sec_data[sid]["i"] += 1
                        else:
                            sec_data[sid]["i"] += 1
                    else:
                        sec_data[sid]["u"] += 1

            for sec in sections:
                d = sec_data[sec.id]
                pct = round(d["obtained"] / d["total"] * 100, 2) if d["total"] else 0.0
                section_scores.append(
                    SectionScore(
                        section_name=d["name"],
                        obtained_marks=round(d["obtained"], 2),
                        total_marks=round(d["total"], 2),
                        percentage=pct,
                        correct=d["c"],
                        incorrect=d["i"],
                        unanswered=d["u"],
                    )
                )

        # Time taken
        time_taken = None
        if session.submitted_at and session.started_at:
            time_taken = int((session.submitted_at - session.started_at).total_seconds())

        rows.append(
            RankingRow(
                candidate_id=session.candidate_id,
                full_name=session.candidate.full_name,
                email=session.candidate.email,
                overall_percentage=result.percentage,
                obtained_marks=result.obtained_marks,
                total_marks=result.total_marks,
                correct_count=result.correct_count,
                incorrect_count=result.incorrect_count,
                unanswered_count=result.unanswered_count,
                accuracy=accuracy,
                time_taken_seconds=time_taken,
                rank=0,  # filled after sort
                section_scores=section_scores,
                shortlist_status=shortlists.get(session.candidate_id),
                suspicion_score=session.suspicion_score,
                is_flagged=session.is_flagged,
                result_id=result.id,
                session_id=session.id,
            )
        )

    # Sort by percentage desc, then accuracy desc, then time asc
    rows.sort(
        key=lambda r: (-r.overall_percentage, -r.accuracy, r.time_taken_seconds or 99999)
    )
    for i, row in enumerate(rows, start=1):
        row.rank = i

    return rows


# ----------------------------------------------------------- shortlisting


@router.get("/exams/{exam_id}/shortlists", response_model=list[ShortlistOut])
def list_shortlists(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
) -> list[ShortlistOut]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    _require_corporate(exam)

    rows = db.scalars(
        select(CandidateShortlist).where(CandidateShortlist.exam_id == exam_id)
    )
    return [ShortlistOut.model_validate(r) for r in rows]


@router.post("/exams/{exam_id}/shortlist", response_model=list[ShortlistOut])
def upsert_shortlists(
    exam_id: uuid.UUID,
    payload: ShortlistBulkCreate,
    staff: CurrentStaff,
    db: DbSession,
) -> list[ShortlistOut]:
    """Set / update shortlist decisions for one or many candidates.

    Each decision is an upsert: if a row already exists for that candidate it is updated,
    otherwise it is created. The examiner's identity and timestamp are always recorded.
    """
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    _require_corporate(exam)

    now = datetime.now(UTC)
    results: list[CandidateShortlist] = []

    for decision in payload.decisions:
        existing = db.scalar(
            select(CandidateShortlist).where(
                CandidateShortlist.exam_id == exam_id,
                CandidateShortlist.candidate_id == decision.candidate_id,
            )
        )
        if existing:
            existing.status = decision.status
            existing.note = decision.note
            existing.decided_by_id = staff.id
            existing.decided_at = now
            results.append(existing)
        else:
            sl = CandidateShortlist(
                exam_id=exam_id,
                candidate_id=decision.candidate_id,
                status=decision.status,
                note=decision.note,
                decided_by_id=staff.id,
                decided_at=now,
            )
            db.add(sl)
            results.append(sl)

    db.flush()
    for r in results:
        db.refresh(r)

    logger.info(
        "%s set shortlist decisions for %d candidate(s) on exam %s",
        staff.email,
        len(results),
        exam_id,
    )
    return [ShortlistOut.model_validate(r) for r in results]
