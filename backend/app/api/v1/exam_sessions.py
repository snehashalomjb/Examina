"""Candidate-facing exam engine: start, rehydrate, autosave, heartbeat, submit."""

from __future__ import annotations

import uuid
from datetime import UTC

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import ActiveExamSession, CurrentCandidate, DbSession
from app.core.logging_config import get_logger
from app.core.security import create_exam_session_token
from app.core.storage import build_key, presigned_url, put_object
from app.db.models import (
    Answer,
    Exam,
    ExamQuestion,
    ExamSection,
    ExamSession,
    ExamStatus,
    Question,
    QuestionType,
    Result,
    SessionStatus,
)
from app.db.session import SessionLocal
from app.schemas.exam_session import (
    AnswerSave,
    AnswerSaved,
    CandidateExamCard,
    ExamSessionOut,
    HeartbeatOut,
    PaperQuestion,
    SessionSection,
    SubmitOut,
)
from app.schemas.question import OptionOut
from app.services import answer_media, exam_engine, login_access
from app.services.question_spec import candidate_spec
from app.services.text_metrics import WordCountError
from app.services.validators import ValidationError

router = APIRouter(tags=["exam-session"])
logger = get_logger("exam")

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ------------------------------------------------------------------ helpers
def _build_paper(db, session: ExamSession, *, include_token: bool) -> ExamSessionOut:
    """Render the candidate's frozen paper, merged with whatever they have saved."""
    question_ids = [uuid.UUID(e["question_id"]) for e in session.question_order]
    questions = {
        q.id: q
        for q in db.scalars(
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(selectinload(Question.options))
        )
    }
    answers = {a.question_id: a for a in session.answers}

    # Build a section lookup keyed by question_id (from the frozen question_order entries).
    # question_order entries may carry a section_id field written at paper-generation time.
    section_qids: dict[uuid.UUID, uuid.UUID] = {}
    for entry in session.question_order:
        if entry.get("section_id"):
            section_qids[uuid.UUID(entry["question_id"])] = uuid.UUID(entry["section_id"])

    # Load sections ordered by order_index so the tabs appear in the right order.
    raw_sections = list(
        db.scalars(
            select(ExamSection)
            .where(ExamSection.exam_id == session.exam_id)
            .order_by(ExamSection.order_index)
        )
    )

    paper: list[PaperQuestion] = []
    for entry in session.question_order:
        qid = uuid.UUID(entry["question_id"])
        question = questions.get(qid)
        if question is None:  # pragma: no cover - only if a question was hard-deleted
            continue

        by_id = {o.id: o for o in question.options}
        ordered = [
            by_id[uuid.UUID(oid)]
            for oid in entry.get("option_order", [])
            if uuid.UUID(oid) in by_id
        ]
        answer = answers.get(qid)
        sec_id = section_qids.get(qid)

        paper.append(
            PaperQuestion(
                question_id=qid,
                question_type=question.question_type,
                difficulty=question.difficulty,
                body=question.body,
                marks=entry.get("marks", question.marks),
                negative_marks=question.negative_marks,
                category=question.category,
                topic=question.topic,
                min_words=question.min_words,
                max_words=question.max_words,
                image_url=presigned_url(question.image_key),
                # Allowlisted projection - a numerical question's spec is its answer key
                # and projects to nothing at all.
                spec=candidate_spec(question.question_type, question.spec),
                parent_question_id=question.parent_question_id,
                section_id=sec_id,
                # No is_correct field here - the answer key never reaches the browser.
                options=[OptionOut.model_validate(o) for o in ordered],
                saved_option_ids=[uuid.UUID(o) for o in (answer.selected_option_ids or [])]
                if answer
                else [],
                saved_text=answer.text_answer if answer else None,
                saved_image_url=presigned_url(answer.image_object_key) if answer else None,
                saved_word_count=answer.word_count if answer else None,
                is_review_flagged=answer.is_review_flagged if answer else False,
            )
        )

    token = None
    if include_token and session.status is SessionStatus.IN_PROGRESS:
        token = create_exam_session_token(
            session_id=session.id,
            exam_id=session.exam_id,
            candidate_id=session.candidate_id,
            expires_at=session.expires_at.replace(tzinfo=session.expires_at.tzinfo or UTC),
        )

    # Build ordered section objects with their question id lists.
    built_sections: list[SessionSection] = []
    if raw_sections:
        sec_question_lists: dict[uuid.UUID, list[uuid.UUID]] = {s.id: [] for s in raw_sections}
        for pq in paper:
            if pq.section_id and pq.section_id in sec_question_lists:
                sec_question_lists[pq.section_id].append(pq.question_id)
        for s in raw_sections:
            built_sections.append(
                SessionSection(
                    id=s.id,
                    name=s.name,
                    order_index=s.order_index,
                    question_ids=sec_question_lists[s.id],
                )
            )

    return ExamSessionOut(
        session_id=session.id,
        exam_id=session.exam_id,
        exam_title=session.exam.title,
        status=session.status,
        started_at=session.started_at,
        expires_at=session.expires_at,
        server_time=exam_engine.now(),
        seconds_remaining=exam_engine.seconds_remaining(session),
        total_marks=sum(p.marks for p in paper),
        questions=paper,
        proctor_config=session.exam.proctor_config,
        exam_token=token,
        sections=built_sections,
    )


def _guard_live(db, session: ExamSession) -> None:
    """Reject any write to a session that is closed or has run out of time."""
    if session.status is not SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This exam session is {session.status.value.replace('_', ' ')}",
        )
    if exam_engine.expire_if_due(db, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your time has expired and the exam was submitted automatically",
        )


def _grade_in_background(session_id: uuid.UUID) -> None:
    """Run the grader on its own DB session - the request's session is already closed."""
    db = SessionLocal()
    try:
        exam_engine.grade_pending_answers(db, session_id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error("Background grading failed for session %s: %s", session_id, exc)
    finally:
        db.close()


# ------------------------------------------------------------- candidate view
@router.get("/my/exams", response_model=list[CandidateExamCard])
def my_exams(candidate: CurrentCandidate, db: DbSession) -> list[CandidateExamCard]:
    """Everything this candidate can sit, is sitting, or has sat.

    Scoped to their enrolments: an approved login is permission to use the platform, not
    permission to sit every paper on it.
    """
    enrolled_ids = login_access.enrolled_exam_ids(db, candidate.id)
    if not enrolled_ids:
        return []

    exams = list(
        db.scalars(
            select(Exam)
            .where(
                Exam.id.in_(enrolled_ids),
                Exam.status.in_([ExamStatus.PUBLISHED, ExamStatus.CLOSED]),
            )
            .options(
                selectinload(Exam.subject),
                selectinload(Exam.exam_questions).selectinload(ExamQuestion.question),
                selectinload(Exam.sections),
            )
            .order_by(Exam.starts_at.desc())
        )
    )
    sessions = {
        s.exam_id: s
        for s in db.scalars(
            select(ExamSession)
            .where(ExamSession.candidate_id == candidate.id)
            .options(selectinload(ExamSession.result))
        )
    }

    now = exam_engine.now()
    cards: list[CandidateExamCard] = []
    for exam in exams:
        session = sessions.get(exam.id)
        starts = exam.starts_at if exam.starts_at.tzinfo else exam.starts_at.replace(tzinfo=UTC)
        ends = exam.ends_at if exam.ends_at.tzinfo else exam.ends_at.replace(tzinfo=UTC)

        can_start = False
        reason: str | None = None
        if session is not None:
            reason = (
                "Attempt in progress"
                if session.status is SessionStatus.IN_PROGRESS
                else "Already attempted"
            )
            can_start = session.status is SessionStatus.IN_PROGRESS
        elif exam.status is not ExamStatus.PUBLISHED:
            reason = "This exam is closed"
        elif now < starts:
            reason = f"Opens {starts.strftime('%d %b %Y, %H:%M UTC')}"
        elif now > ends:
            reason = "The exam window has closed"
        else:
            can_start = True

        total_questions = 0
        try:
            from app.services.validators import normalise_selection_rules

            total_questions = sum(
                r["count"] for r in normalise_selection_rules(exam.selection_rules)
            )
        except ValidationError:
            total_questions = len(exam.exam_questions)

        has_coding = any(
            eq.question and eq.question.question_type == QuestionType.CODING
            for eq in exam.exam_questions
        )

        cards.append(
            CandidateExamCard(
                exam_id=exam.id,
                title=exam.title,
                subject_name=exam.subject.name,
                duration_minutes=exam.duration_minutes,
                starts_at=exam.starts_at,
                ends_at=exam.ends_at,
                total_questions=total_questions,
                session_status=session.status if session else None,
                session_id=session.id if session else None,
                result_id=session.result.id if session and session.result else None,
                result_published=bool(session and session.result and session.result.published),
                can_start=can_start,
                reason=reason,
                exam_type=exam.exam_type,
                course=exam.course,
                department=exam.department,
                semester=exam.semester,
                company_name=exam.company_name,
                job_role=exam.job_role,
                sections_count=len(exam.sections or []),
                has_coding=has_coding,
            )
        )
    return cards


# ------------------------------------------------------------- session lifecycle
@router.post("/exams/{exam_id}/start", response_model=ExamSessionOut)
def start_exam(exam_id: uuid.UUID, candidate: CurrentCandidate, db: DbSession) -> ExamSessionOut:
    exam = exam_engine.load_exam_with_pool(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Enrolment is checked server-side on every start: knowing an exam id is not access.
    if not login_access.is_enrolled(db, exam_id=exam_id, candidate_id=candidate.id):
        logger.warning(
            "Candidate %s tried to start exam %s without an enrolment", candidate.id, exam_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this examination",
        )

    if exam.status is not ExamStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This exam is not open for attempts"
        )

    now = exam_engine.now()
    starts = exam.starts_at if exam.starts_at.tzinfo else exam.starts_at.replace(tzinfo=UTC)
    ends = exam.ends_at if exam.ends_at.tzinfo else exam.ends_at.replace(tzinfo=UTC)
    if now < starts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This exam has not opened yet"
        )
    if now > ends:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The exam window has closed"
        )

    existing = db.scalar(
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id, ExamSession.candidate_id == candidate.id)
        .options(
            selectinload(ExamSession.answers).selectinload(Answer.question),
            selectinload(ExamSession.exam),
        )
    )
    if existing is not None:
        # Resume rather than refuse: a refresh or a crash must not cost the attempt.
        if existing.status is SessionStatus.IN_PROGRESS:
            exam_engine.expire_if_due(db, existing)
            return _build_paper(db, existing, include_token=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already attempted this exam",
        )

    try:
        session = exam_engine.start_session(db, exam=exam, candidate_id=candidate.id)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.refresh(session)
    return _build_paper(db, session, include_token=True)


@router.get("/sessions/{session_id}", response_model=ExamSessionOut)
def get_session(
    session_id: uuid.UUID, candidate: CurrentCandidate, db: DbSession
) -> ExamSessionOut:
    """Rehydrate after a refresh or a crash. Deliberately does not need the exam token."""
    session = exam_engine.load_session(db, session_id)
    if session is None or session.candidate_id != candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    exam_engine.expire_if_due(db, session)
    return _build_paper(db, session, include_token=True)


@router.put("/sessions/{session_id}/answers/{question_id}", response_model=AnswerSaved)
def save_answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: AnswerSave,
    session: ActiveExamSession,
    db: DbSession,
) -> AnswerSaved:
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    _guard_live(db, session)

    try:
        answer = exam_engine.save_answer(
            db,
            session=session,
            question_id=question_id,
            selected_option_ids=payload.selected_option_ids,
            text_answer=payload.text_answer,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WordCountError as exc:
        # The runner counts words with the same rule and blocks typing past the limit, so
        # reaching here means a client that bypassed it. Reject rather than truncate.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return AnswerSaved(
        question_id=question_id,
        saved_at=answer.answered_at,
        seconds_remaining=exam_engine.seconds_remaining(session),
        word_count=answer.word_count,
    )


@router.post("/sessions/{session_id}/answers/{question_id}/image", response_model=AnswerSaved)
def upload_answer_image(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    session: ActiveExamSession,
    db: DbSession,
    background: BackgroundTasks,
    file: UploadFile = File(...),
) -> AnswerSaved:
    """Upload a photo/scan of a handwritten answer."""
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    _guard_live(db, session)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG or WebP image",
        )
    data = file.file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be under {MAX_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    question = db.get(Question, question_id)
    if question is None or question.question_type is not QuestionType.IMAGE_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question does not accept an image answer",
        )

    extension = (file.filename or "answer.jpg").rsplit(".", 1)[-1][:8] or "jpg"
    key = build_key(prefix="answers", session_id=session.id, extension=extension)
    put_object(key=key, data=data, content_type=file.content_type)

    # The original is stored first and is what gets graded; the thumbnail is only there so
    # the examiner queue can render a wall of scripts cheaply.
    thumb_key = answer_media.build_thumbnail(session_id=session.id, data=data)

    try:
        answer = exam_engine.save_answer(
            db,
            session=session,
            question_id=question_id,
            image_object_key=key,
            image_thumb_key=thumb_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # OCR runs after the response: it takes seconds on a page of handwriting and the
    # candidate is mid-exam. The examiner queue only needs it by the time the exam closes.
    if settings.OCR_ENABLED:
        background.add_task(answer_media.run_ocr, answer.id, data)

    logger.info("Session %s uploaded an answer image for question %s", session.id, question_id)
    return AnswerSaved(
        question_id=question_id,
        saved_at=answer.answered_at,
        seconds_remaining=exam_engine.seconds_remaining(session),
    )


@router.post("/sessions/{session_id}/heartbeat", response_model=HeartbeatOut)
def heartbeat(session_id: uuid.UUID, session: ActiveExamSession, db: DbSession) -> HeartbeatOut:
    """Authoritative clock + a fresh exam token. The client corrects its timer from this."""
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )

    expired = exam_engine.expire_if_due(db, session)
    session.last_heartbeat_at = exam_engine.now()
    db.flush()

    warnings: list[str] = []
    if expired:
        warnings.append("Your time expired and the exam was submitted automatically.")
    elif session.is_flagged:
        warnings.append("Your session has been flagged for review by the proctoring system.")

    token = None
    if session.status is SessionStatus.IN_PROGRESS:
        token = create_exam_session_token(
            session_id=session.id,
            exam_id=session.exam_id,
            candidate_id=session.candidate_id,
            expires_at=session.expires_at.replace(tzinfo=session.expires_at.tzinfo or UTC),
        )

    return HeartbeatOut(
        server_time=exam_engine.now(),
        seconds_remaining=exam_engine.seconds_remaining(session),
        status=session.status,
        suspicion_score=session.suspicion_score,
        warnings=warnings,
        exam_token=token,
    )


@router.post("/sessions/{session_id}/submit", response_model=SubmitOut)
def submit(
    session_id: uuid.UUID,
    session: ActiveExamSession,
    db: DbSession,
    background: BackgroundTasks,
) -> SubmitOut:
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    if session.status is not SessionStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This session has already been closed"
        )

    auto_scored, pending = exam_engine.finalize_session(db, session)

    if pending:
        background.add_task(_grade_in_background, session.id)

    message = f"Submitted. {auto_scored} question(s) scored automatically" + (
        f"; {pending} awaiting examiner review." if pending else "."
    )
    return SubmitOut(
        session_id=session.id,
        status=session.status,
        submitted_at=session.submitted_at,
        auto_scored=auto_scored,
        pending_review=pending,
        message=message,
    )


# --------------------------------------------------------- review flag + clear


@router.put("/sessions/{session_id}/questions/{question_id}/review-flag")
def toggle_review_flag(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    session: ActiveExamSession,
    db: DbSession,
) -> dict:
    """Toggle the candidate's mark-for-review on a single question.

    A flagged answer is still scored normally - the flag is a UX bookmark only.
    """
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    _guard_live(db, session)

    answer = db.scalar(
        select(Answer).where(
            Answer.session_id == session_id, Answer.question_id == question_id
        )
    )
    if answer is None:
        # No saved answer yet - create a stub so the flag persists.
        answer = Answer(
            session_id=session_id,
            question_id=question_id,
            is_review_flagged=True,
            max_marks=1.0,  # placeholder; overwritten on first real save
        )
        db.add(answer)
    else:
        answer.is_review_flagged = not answer.is_review_flagged
    db.flush()
    return {"question_id": question_id, "is_review_flagged": answer.is_review_flagged}


@router.delete("/sessions/{session_id}/answers/{question_id}")
def clear_answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    session: ActiveExamSession,
    db: DbSession,
) -> dict:
    """Clear a candidate's saved answer for one question.

    Wipes selected options, text, and image fields. Does not remove the row so
    the review-flag (if set) is not accidentally cleared as a side-effect.
    """
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    _guard_live(db, session)

    answer = db.scalar(
        select(Answer).where(
            Answer.session_id == session_id, Answer.question_id == question_id
        )
    )
    if answer is not None:
        answer.selected_option_ids = None
        answer.text_answer = None
        answer.image_object_key = None
        answer.image_thumb_key = None
        answer.ocr_text = None
        answer.ocr_confidence = None
        answer.word_count = None
        answer.answered_at = None
        from app.db.models.enums import GradeStatus
        answer.grade_status = GradeStatus.UNANSWERED
        db.flush()
    return {"question_id": question_id, "cleared": True}


@router.get("/my/stats/summary")
def my_summary(candidate: CurrentCandidate, db: DbSession) -> dict:
    """Small aggregate for the candidate dashboard header."""
    completed = db.scalar(
        select(func.count(ExamSession.id)).where(
            ExamSession.candidate_id == candidate.id,
            ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.AUTO_SUBMITTED]),
        )
    )
    published = db.scalar(
        select(func.count(Result.id))
        .join(ExamSession, ExamSession.id == Result.session_id)
        .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
    )
    average = db.scalar(
        select(func.avg(Result.percentage))
        .join(ExamSession, ExamSession.id == Result.session_id)
        .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
    )
    best = db.scalar(
        select(func.max(Result.percentage))
        .join(ExamSession, ExamSession.id == Result.session_id)
        .where(ExamSession.candidate_id == candidate.id, Result.published.is_(True))
    )
    enrolled_ids = login_access.enrolled_exam_ids(db, candidate.id)
    available = (
        db.scalar(
            select(func.count(Exam.id))
            .where(Exam.id.in_(enrolled_ids), Exam.status == ExamStatus.PUBLISHED)
            .where(
                ~Exam.id.in_(
                    select(ExamSession.exam_id).where(ExamSession.candidate_id == candidate.id)
                )
            )
        )
        if enrolled_ids
        else 0
    )
    return {
        "available_exams": available or 0,
        "completed_exams": completed or 0,
        "published_results": published or 0,
        "average_percentage": round(float(average), 2) if average is not None else None,
        "best_percentage": round(float(best), 2) if best is not None else None,
    }
