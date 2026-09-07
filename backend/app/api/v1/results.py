"""Results: the candidate's view of their own score, and the staff roll-up."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentCandidate, CurrentStaff, CurrentUser, DbSession
from app.core.storage import presigned_url
from app.services.pdf_generator import generate_result_pdf
from app.db.models import (
    Answer,
    Exam,
    ExamSession,
    ExamStatus,
    GradeStatus,
    Question,
    QuestionType,
    Result,
    SessionStatus,
    Subject,
    User,
    UserRole,
)
from app.db.models.enums import OBJECTIVE_TYPES
from app.schemas.admin import ExaminerStats
from app.schemas.exam_session import QuestionResult, ResultDetail, ResultOut

router = APIRouter(tags=["results"])


def _answer_text(answer: Answer, question: Question) -> str | None:
    if question.question_type in OBJECTIVE_TYPES:
        selected = set(answer.selected_option_ids or [])
        if not selected:
            return None
        chosen = [o.text for o in question.options if str(o.id) in selected]
        return ", ".join(chosen) if chosen else None
    if question.question_type is QuestionType.IMAGE_UPLOAD:
        return presigned_url(answer.image_object_key)
    return answer.text_answer


def _correct_text(question: Question) -> str | None:
    if question.question_type in OBJECTIVE_TYPES:
        return ", ".join(o.text for o in question.options if o.is_correct) or None
    return question.model_answer


@router.get("/my/results", response_model=list[ResultOut])
def my_results(candidate: CurrentCandidate, db: DbSession) -> list[ResultOut]:
    results = db.scalars(
        select(Result)
        .join(ExamSession, ExamSession.id == Result.session_id)
        .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
        .order_by(Result.published_at.desc().nullslast())
    )
    return [ResultOut.model_validate(r) for r in results]


@router.get("/results/{result_id}", response_model=ResultDetail)
def result_detail(result_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ResultDetail:
    """Question-level feedback.

    A candidate sees this only for their own published result; staff see any result at any
    time, published or not.
    """
    result = db.scalar(
        select(Result)
        .where(Result.id == result_id)
        .options(
            selectinload(Result.session)
            .selectinload(ExamSession.answers)
            .selectinload(Answer.question)
            .selectinload(Question.options),
            selectinload(Result.session).selectinload(ExamSession.exam).selectinload(Exam.subject),
            selectinload(Result.session).selectinload(ExamSession.candidate),
            selectinload(Result.session)
            .selectinload(ExamSession.answers)
            .selectinload(Answer.ai_evaluations),
        )
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")

    session = result.session
    exam = session.exam
    is_staff = user.role in {UserRole.EXAMINER, UserRole.ADMIN}

    if not is_staff:
        if session.candidate_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="This result is not yours"
            )
        if not result.published:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your result has not been published yet",
            )

    order = {
        uuid.UUID(entry["question_id"]): index for index, entry in enumerate(session.question_order)
    }

    # Build section lookup: question_id -> (section_id, section_name)
    from app.db.models.exam import ExamSection as ExamSectionModel
    raw_sections = list(
        db.scalars(
            select(ExamSectionModel)
            .where(ExamSectionModel.exam_id == exam.id)
            .order_by(ExamSectionModel.order_index)
        )
    )
    section_by_id: dict[uuid.UUID, ExamSectionModel] = {s.id: s for s in raw_sections}
    # question_order entries may carry section_id written at paper-generation time
    qid_to_section_id: dict[uuid.UUID, uuid.UUID] = {}
    for entry in session.question_order:
        if entry.get("section_id"):
            qid_to_section_id[uuid.UUID(entry["question_id"])] = uuid.UUID(entry["section_id"])

    answers = sorted(session.answers, key=lambda a: order.get(a.question_id, 999))

    # Per-section accumulators
    section_acc: dict[uuid.UUID, dict] = {
        s.id: {
            "name": s.name,
            "total_marks": 0.0,
            "obtained_marks": 0.0,
            "correct": 0,
            "incorrect": 0,
            "unanswered": 0,
        }
        for s in raw_sections
    }

    questions: list[QuestionResult] = []
    for answer in answers:
        question = answer.question
        evaluation = answer.latest_ai_evaluation
        is_correct = None
        if answer.awarded_marks is not None and answer.is_answered:
            is_correct = answer.awarded_marks >= answer.max_marks

        sec_id = qid_to_section_id.get(answer.question_id)
        sec_name = section_by_id[sec_id].name if sec_id and sec_id in section_by_id else None

        # Accumulate section stats
        if sec_id and sec_id in section_acc:
            acc = section_acc[sec_id]
            acc["total_marks"] += answer.max_marks
            if answer.awarded_marks is not None:
                acc["obtained_marks"] += answer.awarded_marks
            if not answer.is_answered:
                acc["unanswered"] += 1
            elif is_correct:
                acc["correct"] += 1
            else:
                acc["incorrect"] += 1

        questions.append(
            QuestionResult(
                question_id=question.id,
                body=question.body,
                question_type=question.question_type,
                marks=answer.max_marks,
                awarded_marks=answer.awarded_marks,
                grade_status=answer.grade_status,
                is_correct=is_correct,
                your_answer=_answer_text(answer, question),
                correct_answer=_correct_text(question),
                examiner_comment=answer.examiner_comment,
                section_name=sec_name,
                # Candidates see the justification only once a human has signed the score
                # off; before that it is a provisional machine opinion.
                ai_justification=(
                    evaluation.justification
                    if evaluation
                    and (is_staff or answer.grade_status is GradeStatus.EXAMINER_REVIEWED)
                    else None
                ),
            )
        )

    from app.schemas.exam_session import SectionScore
    section_scores: list[SectionScore] = []
    for s in raw_sections:
        acc = section_acc[s.id]
        total = acc["total_marks"] or 1.0
        section_scores.append(
            SectionScore(
                section_id=s.id,
                section_name=acc["name"],
                total_marks=acc["total_marks"],
                obtained_marks=acc["obtained_marks"],
                percentage=round(acc["obtained_marks"] / total * 100, 1),
                correct=acc["correct"],
                incorrect=acc["incorrect"],
                unanswered=acc["unanswered"],
            )
        )

    # Percentile: how many published results for this exam scored strictly below this candidate
    # Only meaningful when the cohort is large enough.
    MIN_COHORT = 10
    cohort_results = list(
        db.scalars(
            select(Result)
            .join(ExamSession, ExamSession.id == Result.session_id)
            .where(ExamSession.exam_id == exam.id, Result.published.is_(True))
        )
    )
    cohort_size = len(cohort_results)
    percentile: float | None = None
    if cohort_size >= MIN_COHORT:
        below = sum(1 for r in cohort_results if r.percentage < result.percentage)
        percentile = round(below / cohort_size * 100, 1)

    # Time taken
    time_taken_seconds: int | None = None
    if session.submitted_at and session.started_at:
        diff = session.submitted_at - session.started_at
        time_taken_seconds = int(diff.total_seconds())

    return ResultDetail(
        result=ResultOut.model_validate(result),
        exam_title=exam.title,
        subject_name=exam.subject.name,
        candidate_name=session.candidate.full_name,
        submitted_at=session.submitted_at,
        questions=questions,
        section_scores=section_scores,
        exam_type=exam.exam_type.value,
        passing_percentage=exam.passing_percentage,
        percentile=percentile,
        cohort_size=cohort_size,
        time_taken_seconds=time_taken_seconds,
    )



@router.get("/exams/{exam_id}/results", response_model=list[dict])
def exam_results(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    limit: int = Query(300, ge=1, le=1000),
) -> list[dict]:
    """Every attempt at one exam - the examiner's marks sheet."""
    sessions = db.scalars(
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id)
        .options(
            selectinload(ExamSession.candidate),
            selectinload(ExamSession.result),
        )
        .order_by(ExamSession.created_at.desc())
        .limit(limit)
    )
    rows = []
    for session in sessions:
        result = session.result
        rows.append(
            {
                "session_id": str(session.id),
                "result_id": str(result.id) if result else None,
                "candidate_name": session.candidate.full_name,
                "candidate_email": session.candidate.email,
                "status": session.status.value,
                "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
                "obtained_marks": result.obtained_marks if result else None,
                "total_marks": result.total_marks if result else None,
                "percentage": result.percentage if result else None,
                "pending_review": result.pending_review_count if result else 0,
                "published": result.published if result else False,
                "suspicion_score": session.suspicion_score,
                "is_flagged": session.is_flagged,
            }
        )
    return rows


@router.get("/examiner/stats", response_model=ExaminerStats)
def examiner_stats(staff: CurrentStaff, db: DbSession) -> ExaminerStats:
    """Numbers for the examiner dashboard."""
    mine = staff.id if staff.role is UserRole.EXAMINER else None

    question_stmt = select(func.count(Question.id)).where(Question.is_active)
    exam_stmt = select(func.count(Exam.id))
    if mine:
        question_stmt = question_stmt.where(Question.created_by_id == mine)
        exam_stmt = exam_stmt.where(Exam.created_by_id == mine)

    return ExaminerStats(
        my_questions=db.scalar(question_stmt) or 0,
        my_exams=db.scalar(exam_stmt) or 0,
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
        subjects=db.scalar(select(func.count(Subject.id))) or 0,
    )


@router.get("/candidates/{candidate_id}/attempts", response_model=list[dict])
def candidate_attempts(candidate_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> list[dict]:
    """One candidate's history - the drill-down from the candidate roster."""
    candidate = db.get(User, candidate_id)
    if candidate is None or candidate.role is not UserRole.CANDIDATE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    sessions = db.scalars(
        select(ExamSession)
        .where(ExamSession.candidate_id == candidate_id)
        .options(selectinload(ExamSession.exam), selectinload(ExamSession.result))
        .order_by(ExamSession.created_at.desc())
    )
    return [
        {
            "session_id": str(s.id),
            "exam_id": str(s.exam_id),
            "exam_title": s.exam.title,
            "status": s.status.value,
            "started_at": s.started_at.isoformat(),
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            "percentage": s.result.percentage if s.result else None,
            "published": s.result.published if s.result else False,
            "result_id": str(s.result.id) if s.result else None,
            "suspicion_score": s.suspicion_score,
            "is_flagged": s.is_flagged,
        }
        for s in sessions
    ]


@router.get("/results/{result_id}/pdf")
def result_pdf(result_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Generates and downloads the certified PDF scorecard for a result."""
    detail = result_detail(result_id=result_id, user=user, db=db)
    session = db.scalar(
        select(ExamSession)
        .where(ExamSession.id == detail.result.session_id)
        .options(selectinload(ExamSession.candidate))
    )
    email = session.candidate.email if session and session.candidate else None

    pdf_bytes = generate_result_pdf(detail, candidate_email=email)
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in detail.exam_title)[:30]
    filename = f"scorecard_{safe_title}_{detail.result.id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )

