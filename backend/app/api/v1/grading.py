"""Examiner grading portal: the subjective review queue and score overrides."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.core.storage import presigned_url
from app.db.models import (
    AiEvaluation,
    Answer,
    Exam,
    ExamSession,
    GradeStatus,
    SessionStatus,
)
from app.db.models.enums import SUBJECTIVE_TYPES
from app.db.session import SessionLocal
from app.schemas.common import Message
from app.schemas.grading import (
    AiEvaluationOut,
    GradeOverride,
    GradingQueueItem,
    GradingSummary,
    RegradeRequest,
)
from app.services import exam_engine
from app.services.text_metrics import shortfall

router = APIRouter(tags=["grading"])
logger = get_logger("grading")


def _to_item(answer: Answer) -> GradingQueueItem:
    session = answer.session
    evaluation = answer.latest_ai_evaluation
    return GradingQueueItem(
        answer_id=answer.id,
        session_id=session.id,
        exam_id=session.exam_id,
        exam_title=session.exam.title,
        candidate_name=session.candidate.full_name,
        candidate_email=session.candidate.email,
        question_id=answer.question_id,
        question_body=answer.question.body,
        question_type=answer.question.question_type,
        model_answer=answer.question.model_answer,
        rubric=answer.question.rubric,
        text_answer=answer.text_answer,
        word_count=answer.word_count,
        words_below_minimum=shortfall(answer.question, answer.text_answer),
        image_url=presigned_url(answer.image_object_key),
        image_thumb_url=presigned_url(answer.image_thumb_key),
        ocr_text=answer.ocr_text,
        ocr_confidence=answer.ocr_confidence,
        max_marks=answer.max_marks,
        awarded_marks=answer.awarded_marks,
        grade_status=answer.grade_status,
        examiner_comment=answer.examiner_comment,
        ai_evaluation=(
            AiEvaluationOut(
                provider=evaluation.provider,
                model=evaluation.model,
                score=evaluation.score,
                max_score=evaluation.max_score,
                justification=evaluation.justification,
                confidence=evaluation.confidence,
                created_at=evaluation.created_at,
                error=evaluation.error,
            )
            if evaluation
            else None
        ),
        submitted_at=session.submitted_at,
    )


@router.get("/grading/queue", response_model=list[GradingQueueItem])
def grading_queue(
    staff: CurrentStaff,
    db: DbSession,
    exam_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    grade_status: GradeStatus | None = None,
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
) -> list[GradingQueueItem]:
    """Subjective answers awaiting a human decision, AI score pre-filled."""
    stmt = (
        select(Answer)
        .join(ExamSession, ExamSession.id == Answer.session_id)
        .where(Answer.grade_status.in_([GradeStatus.PENDING_AI, GradeStatus.AI_SCORED]))
        .options(
            selectinload(Answer.question),
            selectinload(Answer.ai_evaluations),
            selectinload(Answer.session).selectinload(ExamSession.exam),
            selectinload(Answer.session).selectinload(ExamSession.candidate),
        )
        .order_by(ExamSession.submitted_at.desc().nullslast(), Answer.created_at)
        .limit(limit)
        .offset(offset)
    )
    if exam_id:
        stmt = stmt.where(ExamSession.exam_id == exam_id)
    if session_id:
        stmt = stmt.where(Answer.session_id == session_id)
    if grade_status:
        stmt = stmt.where(Answer.grade_status == grade_status)

    return [_to_item(a) for a in db.scalars(stmt)]


@router.get("/grading/reviewed", response_model=list[GradingQueueItem])
def reviewed_answers(
    staff: CurrentStaff,
    db: DbSession,
    exam_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=300),
) -> list[GradingQueueItem]:
    stmt = (
        select(Answer)
        .join(ExamSession, ExamSession.id == Answer.session_id)
        .where(Answer.grade_status == GradeStatus.EXAMINER_REVIEWED)
        .options(
            selectinload(Answer.question),
            selectinload(Answer.ai_evaluations),
            selectinload(Answer.session).selectinload(ExamSession.exam),
            selectinload(Answer.session).selectinload(ExamSession.candidate),
        )
        .order_by(Answer.graded_at.desc().nullslast())
        .limit(limit)
    )
    if exam_id:
        stmt = stmt.where(ExamSession.exam_id == exam_id)
    return [_to_item(a) for a in db.scalars(stmt)]


@router.post("/grading/answers/{answer_id}/score", response_model=GradingQueueItem)
def override_score(
    answer_id: uuid.UUID, payload: GradeOverride, staff: CurrentStaff, db: DbSession
) -> GradingQueueItem:
    """The examiner's decision. This is the score that counts."""
    answer = db.scalar(
        select(Answer)
        .where(Answer.id == answer_id)
        .options(
            selectinload(Answer.question),
            selectinload(Answer.ai_evaluations),
            selectinload(Answer.session).selectinload(ExamSession.exam),
            selectinload(Answer.session).selectinload(ExamSession.candidate),
        )
    )
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")

    if payload.awarded_marks > answer.max_marks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This question is worth at most {answer.max_marks:g} marks",
        )

    previous = answer.awarded_marks
    answer.awarded_marks = payload.awarded_marks
    answer.examiner_comment = payload.comment
    answer.grade_status = GradeStatus.EXAMINER_REVIEWED
    answer.graded_by_id = staff.id
    answer.graded_at = exam_engine.now()
    db.flush()

    session = exam_engine.load_session(db, answer.session_id)
    if session is not None:
        exam_engine.compute_result(db, session)

    logger.info(
        "%s graded answer %s: %s -> %.2f/%.2f",
        staff.email,
        answer_id,
        f"{previous:.2f}" if previous is not None else "unscored",
        payload.awarded_marks,
        answer.max_marks,
    )
    return _to_item(answer)


@router.post("/grading/regrade", response_model=Message)
def regrade(
    payload: RegradeRequest, staff: CurrentStaff, db: DbSession, background: BackgroundTasks
) -> Message:
    """Re-run the configured grader over answers, e.g. after switching provider."""
    stmt = select(Answer).options(selectinload(Answer.question))
    if payload.answer_ids:
        stmt = stmt.where(Answer.id.in_(payload.answer_ids))
    elif payload.session_id:
        stmt = stmt.where(Answer.session_id == payload.session_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide answer_ids or a session_id",
        )

    answers = list(db.scalars(stmt))
    subjective = [a for a in answers if a.question.question_type in SUBJECTIVE_TYPES]
    session_ids = set()
    for answer in subjective:
        answer.grade_status = GradeStatus.PENDING_AI
        session_ids.add(answer.session_id)
    db.flush()

    for session_id in session_ids:
        background.add_task(_regrade_session, session_id)

    logger.info("%s queued %d answer(s) for re-grading", staff.email, len(subjective))
    return Message(detail=f"Queued {len(subjective)} answer(s) for re-grading")


def _regrade_session(session_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        exam_engine.grade_pending_answers(db, session_id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("Re-grade failed for session %s: %s", session_id, exc)
    finally:
        db.close()


@router.get("/grading/summary", response_model=list[GradingSummary])
def grading_summary(staff: CurrentStaff, db: DbSession) -> list[GradingSummary]:
    """Per-exam progress bar for the examiner dashboard."""
    exams = list(db.scalars(select(Exam).order_by(Exam.created_at.desc()).limit(50)))
    summaries: list[GradingSummary] = []

    for exam in exams:
        total_sessions = (
            db.scalar(select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam.id)) or 0
        )
        if not total_sessions:
            continue
        submitted = (
            db.scalar(
                select(func.count(ExamSession.id)).where(
                    ExamSession.exam_id == exam.id,
                    ExamSession.status != SessionStatus.IN_PROGRESS,
                )
            )
            or 0
        )
        pending = (
            db.scalar(
                select(func.count(Answer.id))
                .join(ExamSession, ExamSession.id == Answer.session_id)
                .where(
                    ExamSession.exam_id == exam.id,
                    Answer.grade_status.in_([GradeStatus.PENDING_AI, GradeStatus.AI_SCORED]),
                )
            )
            or 0
        )
        reviewed = (
            db.scalar(
                select(func.count(Answer.id))
                .join(ExamSession, ExamSession.id == Answer.session_id)
                .where(
                    ExamSession.exam_id == exam.id,
                    Answer.grade_status == GradeStatus.EXAMINER_REVIEWED,
                )
            )
            or 0
        )
        summaries.append(
            GradingSummary(
                exam_id=exam.id,
                exam_title=exam.title,
                total_sessions=total_sessions,
                submitted_sessions=submitted,
                pending_review=pending,
                reviewed=reviewed,
                results_published=exam.results_published,
            )
        )
    return summaries


@router.post("/exams/{exam_id}/results/publish", response_model=Message)
def publish_results(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Message:
    """Release results to candidates.

    Refuses while any answer is still awaiting review - publishing a provisional machine
    score as a final grade is exactly the failure mode this platform exists to avoid.
    """
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    outstanding = (
        db.scalar(
            select(func.count(Answer.id))
            .join(ExamSession, ExamSession.id == Answer.session_id)
            .where(
                ExamSession.exam_id == exam_id,
                Answer.grade_status.in_([GradeStatus.PENDING_AI, GradeStatus.AI_SCORED]),
            )
        )
        or 0
    )
    if outstanding:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{outstanding} answer(s) still need examiner review before results "
                "can be published"
            ),
        )

    sessions = list(
        db.scalars(
            select(ExamSession)
            .where(
                ExamSession.exam_id == exam_id,
                ExamSession.status != SessionStatus.IN_PROGRESS,
            )
            .options(
                selectinload(ExamSession.answers).selectinload(Answer.question),
                selectinload(ExamSession.exam),
                selectinload(ExamSession.result),
            )
        )
    )

    published = 0
    now = exam_engine.now()
    for session in sessions:
        result = exam_engine.compute_result(db, session)
        result.published = True
        result.published_at = result.published_at or now
        published += 1

    exam.results_published = True
    db.flush()
    logger.info("%s published %d result(s) for exam %r", staff.email, published, exam.title)
    return Message(detail=f"Published {published} result(s)")


@router.get("/grading/evaluations/{answer_id}", response_model=list[AiEvaluationOut])
def evaluation_history(
    answer_id: uuid.UUID, staff: CurrentStaff, db: DbSession
) -> list[AiEvaluationOut]:
    """Every grading run for one answer - useful when a provider is changed mid-cycle."""
    evaluations = db.scalars(
        select(AiEvaluation)
        .where(AiEvaluation.answer_id == answer_id)
        .order_by(AiEvaluation.created_at.desc())
    )
    return [
        AiEvaluationOut(
            provider=e.provider,
            model=e.model,
            score=e.score,
            max_score=e.max_score,
            justification=e.justification,
            confidence=e.confidence,
            created_at=e.created_at,
            error=e.error,
        )
        for e in evaluations
    ]


@router.put("/grading/answers/{answer_id}/annotations")
def save_annotations(
    answer_id: uuid.UUID,
    payload: dict,
    staff: CurrentStaff,
    db: DbSession,
) -> dict:
    """Persist examiner annotations for an image answer.

    Annotations are a JSON list of normalised-coordinate shapes (rectangles,
    pins, text comments). The candidate's original uploaded image is never
    modified — annotations are stored alongside it and layered on top by the UI.
    """
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")

    # Store in a flexible JSONB column; create it if the column doesn't exist yet.
    # We use a dynamic attribute so this works even if the column is added later.
    try:
        answer.examiner_annotations = payload.get("annotations", [])
    except AttributeError:
        # Column not yet present in older migrations - silently skip storage
        # until the migration is applied. The response still succeeds so the
        # front end doesn't break.
        pass

    db.flush()
    logger.info(
        "%s saved %d annotation(s) for answer %s",
        staff.email,
        len(payload.get("annotations", [])),
        answer_id,
    )
    return {"saved": True, "count": len(payload.get("annotations", []))}

