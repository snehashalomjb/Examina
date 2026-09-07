"""Server-authoritative exam session lifecycle.

The client's clock is never trusted. ``expires_at`` is written when the session starts and
every subsequent call is checked against server time; a write that arrives after expiry is
refused and the session is finalised as ``auto_submitted``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging_config import get_logger
from app.db.models import (
    AiEvaluation,
    Answer,
    Exam,
    ExamQuestion,
    ExamSession,
    GradeStatus,
    Question,
    QuestionType,
    Result,
    SessionStatus,
)
from app.db.models.enums import AUTO_SCORED_TYPES, CONTAINER_TYPES
from app.services.auto_evaluator import score_answer
from app.services.grading import get_grader
from app.services.paper_generator import generate_paper
from app.services.text_metrics import check_answer_words, shortfall

logger = get_logger("exam")


def now() -> datetime:
    return datetime.now(UTC)


def seconds_remaining(session: ExamSession) -> int:
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return max(0, int((expires - now()).total_seconds()))


def load_session(db: Session, session_id: uuid.UUID) -> ExamSession | None:
    return db.scalar(
        select(ExamSession)
        .where(ExamSession.id == session_id)
        .options(
            selectinload(ExamSession.answers).selectinload(Answer.question),
            selectinload(ExamSession.exam),
            selectinload(ExamSession.candidate),
        )
    )


def load_exam_with_pool(db: Session, exam_id: uuid.UUID) -> Exam | None:
    return db.scalar(
        select(Exam)
        .where(Exam.id == exam_id)
        .options(
            selectinload(Exam.exam_questions)
            .selectinload(ExamQuestion.question)
            .selectinload(Question.options),
            selectinload(Exam.subject),
        )
    )


def start_session(db: Session, *, exam: Exam, candidate_id: uuid.UUID) -> ExamSession:
    """Create the one-and-only session for this (exam, candidate).

    The paper and its option ordering are frozen into ``question_order`` here so nothing
    can reshuffle mid-exam.
    """
    seed, entries = generate_paper(exam=exam, candidate_id=candidate_id)
    started = now()

    # The session can never outlive the exam window, even if the duration would allow it.
    exam_end = exam.ends_at if exam.ends_at.tzinfo else exam.ends_at.replace(tzinfo=UTC)
    expires = min(started + timedelta(minutes=exam.duration_minutes), exam_end)

    session = ExamSession(
        exam_id=exam.id,
        candidate_id=candidate_id,
        paper_seed=seed,
        question_order=[e.as_dict() for e in entries],
        started_at=started,
        expires_at=expires,
        last_heartbeat_at=started,
        status=SessionStatus.IN_PROGRESS,
    )
    db.add(session)
    db.flush()

    # Pre-create answer rows so autosave is a plain update and the grading queue can be
    # built from a single table without worrying about missing rows.
    for entry in entries:
        db.add(
            Answer(
                session_id=session.id,
                question_id=entry.question_id,
                max_marks=entry.marks,
                grade_status=GradeStatus.UNANSWERED,
            )
        )
    db.flush()

    logger.info(
        "Session %s started: exam=%r candidate=%s questions=%d expires=%s",
        session.id,
        exam.title,
        candidate_id,
        len(entries),
        expires.isoformat(),
    )
    return session


def expire_if_due(db: Session, session: ExamSession) -> bool:
    """Auto-submit an in-progress session whose time has run out. Returns True if it did."""
    if session.status is not SessionStatus.IN_PROGRESS:
        return False
    if seconds_remaining(session) > 0:
        return False
    finalize_session(db, session, status=SessionStatus.AUTO_SUBMITTED)
    logger.info("Session %s auto-submitted on timeout", session.id)
    return True


def save_answer(
    db: Session,
    *,
    session: ExamSession,
    question_id: uuid.UUID,
    selected_option_ids: list[uuid.UUID] | None = None,
    text_answer: str | None = None,
    image_object_key: str | None = None,
    image_thumb_key: str | None = None,
) -> Answer:
    answer = db.scalar(
        select(Answer).where(Answer.session_id == session.id, Answer.question_id == question_id)
    )
    if answer is None:
        raise LookupError("That question is not on this candidate's paper")

    if selected_option_ids is not None:
        answer.selected_option_ids = [str(o) for o in selected_option_ids]
    if text_answer is not None:
        # Raises WordCountError past the question's ceiling - checked before the write so
        # an over-long answer is refused rather than silently truncated.
        answer.word_count = check_answer_words(answer.question, text_answer)
        answer.text_answer = text_answer
    if image_object_key is not None:
        answer.image_object_key = image_object_key
    if image_thumb_key is not None:
        answer.image_thumb_key = image_thumb_key

    answer.answered_at = now()
    db.flush()
    return answer


def finalize_session(
    db: Session,
    session: ExamSession,
    *,
    status: SessionStatus = SessionStatus.SUBMITTED,
    reason: str | None = None,
) -> tuple[int, int]:
    """Close a session, auto-score the objective half, queue the subjective half.

    Returns ``(auto_scored, pending_review)``.
    """
    if session.status is not SessionStatus.IN_PROGRESS:
        # Already closed - report the existing split rather than double-scoring.
        auto = sum(1 for a in session.answers if a.grade_status is GradeStatus.AUTO_SCORED)
        pending = sum(
            1
            for a in session.answers
            if a.grade_status in {GradeStatus.PENDING_AI, GradeStatus.AI_SCORED}
        )
        return auto, pending

    exam = session.exam
    partial_credit = bool(exam.grading_config.get("partial_credit_multi_select", False))

    auto_scored = 0
    pending = 0

    for answer in session.answers:
        question = answer.question

        if question.question_type in CONTAINER_TYPES:
            # A passage carries no marks and no answer - it is the text its children are
            # asked about. Scoring it would inflate the paper's total.
            answer.awarded_marks = 0.0
            answer.grade_status = GradeStatus.UNANSWERED
            continue

        if question.question_type in AUTO_SCORED_TYPES:
            try:
                outcome = score_answer(
                    question=question,
                    selected_option_ids=answer.selected_option_ids,
                    text_answer=answer.text_answer,
                    max_marks=answer.max_marks,
                    negative_marking=exam.negative_marking,
                    partial_credit=partial_credit,
                )
            except ValueError as exc:
                # An unmarkable question (a numerical one whose spec is gone, say) must
                # not zero a candidate silently. Send it to a human instead.
                logger.error("Cannot auto-score answer %s: %s", answer.id, exc)
                answer.grade_status = GradeStatus.PENDING_AI
                pending += 1
                continue
            answer.awarded_marks = outcome.awarded
            answer.grade_status = (
                GradeStatus.AUTO_SCORED if outcome.is_answered else GradeStatus.UNANSWERED
            )
            if outcome.is_answered:
                auto_scored += 1
        else:
            if answer.is_answered:
                answer.grade_status = GradeStatus.PENDING_AI
                pending += 1
                missing = shortfall(question, answer.text_answer)
                if missing:
                    # Not a penalty - the examiner decides. It is surfaced in the queue so
                    # an under-length answer is a visible fact rather than a silent one.
                    logger.info(
                        "Answer %s is %d word(s) under the %s-word minimum",
                        answer.id,
                        missing,
                        question.min_words,
                    )
            else:
                answer.awarded_marks = 0.0
                answer.grade_status = GradeStatus.UNANSWERED

    session.status = status
    session.submitted_at = now()
    if reason:
        session.termination_reason = reason
    db.flush()

    compute_result(db, session)
    logger.info(
        "Session %s finalised as %s: %d auto-scored, %d queued for review",
        session.id,
        status.value,
        auto_scored,
        pending,
    )
    return auto_scored, pending


def grade_pending_answers(db: Session, session_id: uuid.UUID) -> int:
    """Run the configured grader over every ``pending_ai`` answer in a session.

    Called as a background task after submit. Failures are recorded on the evaluation row
    and the answer stays in the queue - a grader outage never loses a script.
    """
    session = load_session(db, session_id)
    if session is None:
        return 0

    grader = get_grader(session.exam.grading_config)
    graded = 0

    for answer in session.answers:
        if answer.grade_status is not GradeStatus.PENDING_AI:
            continue
        try:
            result = grader.grade(
                question=answer.question, answer=answer, max_marks=answer.max_marks
            )
            db.add(
                AiEvaluation(
                    answer_id=answer.id,
                    provider=grader.name,
                    model=getattr(grader, "model", None),
                    score=result.score,
                    max_score=result.max_score,
                    justification=result.justification,
                    confidence=result.confidence,
                )
            )
            # The machine score is provisional: it pre-fills the examiner's field but the
            # answer is not considered graded until a human confirms it.
            answer.awarded_marks = result.score
            answer.grade_status = GradeStatus.AI_SCORED
            graded += 1
        except Exception as exc:  # noqa: BLE001 - one bad answer must not stop the batch
            logger.error("Grading failed for answer %s: %s", answer.id, exc)
            db.add(
                AiEvaluation(
                    answer_id=answer.id,
                    provider=grader.name,
                    model=getattr(grader, "model", None),
                    score=0.0,
                    max_score=answer.max_marks,
                    justification="Automatic grading failed; full examiner review required.",
                    confidence=0.0,
                    error=str(exc)[:2000],
                )
            )

    db.flush()
    compute_result(db, session)
    logger.info("Graded %d subjective answer(s) in session %s", graded, session_id)
    return graded


def compute_result(db: Session, session: ExamSession) -> Result:
    """(Re)compute the result row. Idempotent - safe to call after every grading change."""
    total = sum(a.max_marks for a in session.answers)
    obtained = sum(a.awarded_marks or 0.0 for a in session.answers)
    obtained = max(0.0, obtained)  # negative marking cannot push a script below zero

    correct = sum(
        1
        for a in session.answers
        if a.awarded_marks is not None and a.awarded_marks >= a.max_marks and a.is_answered
    )
    unanswered = sum(1 for a in session.answers if not a.is_answered)
    pending = sum(
        1
        for a in session.answers
        if a.grade_status in {GradeStatus.PENDING_AI, GradeStatus.AI_SCORED}
    )
    incorrect = len(session.answers) - correct - unanswered - pending

    result = session.result
    if result is None:
        result = Result(session_id=session.id, total_marks=0, obtained_marks=0, percentage=0)
        db.add(result)
        session.result = result

    result.total_marks = round(total, 2)
    result.obtained_marks = round(obtained, 2)
    result.percentage = round((obtained / total * 100) if total else 0.0, 2)
    result.correct_count = correct
    result.incorrect_count = max(0, incorrect)
    result.unanswered_count = unanswered
    result.pending_review_count = pending

    if session.exam.grading_config.get("auto_publish_results") and pending == 0:
        result.published = True
        result.published_at = result.published_at or now()

    db.flush()
    return result


def sweep_expired_sessions(db: Session) -> int:
    """Close sessions abandoned without a submit (laptop closed, browser killed)."""
    stale = db.scalars(
        select(ExamSession)
        .where(
            ExamSession.status == SessionStatus.IN_PROGRESS,
            ExamSession.expires_at <= now(),
        )
        .options(
            selectinload(ExamSession.answers).selectinload(Answer.question),
            selectinload(ExamSession.exam),
        )
    )
    count = 0
    for session in stale:
        finalize_session(db, session, status=SessionStatus.AUTO_SUBMITTED)
        count += 1
    if count:
        logger.info("Sweeper auto-submitted %d expired session(s)", count)
    return count


def subjective_types() -> set[QuestionType]:
    return {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER, QuestionType.IMAGE_UPLOAD}
