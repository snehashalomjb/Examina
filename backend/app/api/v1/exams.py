"""Exam configuration, publishing, and the paper-generation preview."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.core.security import generate_salt
from app.db.models import (
    Exam,
    ExamQuestion,
    ExamSection,
    ExamSession,
    ExamStatus,
    Question,
    Subject,
    UserRole,
)
from app.schemas.common import Message
from app.schemas.exam import (
    ExamCreate,
    ExamOut,
    ExamPoolCheck,
    ExamUpdate,
    PaperPreview,
    PaperPreviewEntry,
    SectionOut,
)
from app.services.paper_generator import check_pool_satisfies_rules, generate_paper
from app.services.validators import ValidationError, normalise_selection_rules

router = APIRouter(prefix="/exams", tags=["exams"])
logger = get_logger("exams")


def _required_count(exam: Exam) -> int:
    try:
        return sum(r["count"] for r in normalise_selection_rules(exam.selection_rules))
    except ValidationError:
        return 0


def _to_out(exam: Exam) -> ExamOut:
    sections = [
        SectionOut(
            id=s.id,
            exam_id=s.exam_id,
            name=s.name,
            description=s.description,
            order_index=s.order_index,
            selection_rules=s.selection_rules,
            marks_per_question=s.marks_per_question,
            negative_marks=s.negative_marks,
            duration_minutes=s.duration_minutes,
            created_at=s.created_at,
        )
        for s in (exam.sections or [])
    ]
    return ExamOut(
        id=exam.id,
        exam_type=exam.exam_type,
        subject_id=exam.subject_id,
        title=exam.title,
        description=exam.description,
        instructions=exam.instructions,
        duration_minutes=exam.duration_minutes,
        starts_at=exam.starts_at,
        ends_at=exam.ends_at,
        status=exam.status,
        randomize=exam.randomize,
        shuffle_options=exam.shuffle_options,
        negative_marking=exam.negative_marking,
        results_published=exam.results_published,
        selection_rules=exam.selection_rules,
        proctor_config=exam.proctor_config,
        grading_config=exam.grading_config,
        created_at=exam.created_at,
        pool_size=len(exam.exam_questions),
        total_questions=_required_count(exam),
        subject_name=exam.subject.name if exam.subject else None,
        passing_percentage=exam.passing_percentage,
        declared_total_marks=exam.declared_total_marks,
        course=exam.course,
        department=exam.department,
        semester=exam.semester,
        company_name=exam.company_name,
        job_role=exam.job_role,
        sections=sections,
    )


def _load_exam(db, exam_id: uuid.UUID) -> Exam:
    exam = db.scalar(
        select(Exam)
        .where(Exam.id == exam_id)
        .options(
            selectinload(Exam.exam_questions)
            .selectinload(ExamQuestion.question)
            .selectinload(Question.options),
            selectinload(Exam.subject),
            selectinload(Exam.sections),
        )
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


def _set_pool(db, exam: Exam, question_ids: list[uuid.UUID]) -> None:
    questions = list(db.scalars(select(Question).where(Question.id.in_(question_ids))))
    found = {q.id for q in questions}
    missing = set(question_ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{len(missing)} question id(s) do not exist",
        )
    off_subject = [q for q in questions if q.subject_id != exam.subject_id]
    if off_subject:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{len(off_subject)} question(s) belong to a different subject",
        )

    exam.exam_questions.clear()
    for index, question in enumerate(questions):
        exam.exam_questions.append(ExamQuestion(question_id=question.id, order_index=index))


def _set_sections(db, exam: Exam, section_payloads: list) -> None:
    """Replace exam sections atomically during exam create/update."""
    # Clear existing sections (cascade handles the DB rows)
    exam.sections.clear()
    db.flush()  # ensure the DELETE propagates before re-adding

    for payload in section_payloads:
        rules = payload.selection_rules.model_dump(mode="json") if payload.selection_rules else {}
        exam.sections.append(
            ExamSection(
                exam_id=exam.id,
                name=payload.name,
                description=payload.description,
                order_index=payload.order_index,
                selection_rules=rules,
                marks_per_question=payload.marks_per_question,
                negative_marks=payload.negative_marks,
                duration_minutes=payload.duration_minutes,
            )
        )


@router.get("", response_model=list[ExamOut])
def list_exams(
    staff: CurrentStaff,
    db: DbSession,
    subject_id: uuid.UUID | None = None,
    exam_status: ExamStatus | None = Query(default=None, alias="status"),
    exam_type: str | None = Query(default=None),
    mine: bool = False,
    limit: int = Query(100, ge=1, le=500),
) -> list[ExamOut]:
    stmt = (
        select(Exam)
        .options(
            selectinload(Exam.exam_questions),
            selectinload(Exam.subject),
            selectinload(Exam.sections),
        )
        .order_by(Exam.created_at.desc())
        .limit(limit)
    )
    if subject_id:
        stmt = stmt.where(Exam.subject_id == subject_id)
    if exam_status:
        stmt = stmt.where(Exam.status == exam_status)
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    if mine and staff.role is UserRole.EXAMINER:
        stmt = stmt.where(Exam.created_by_id == staff.id)
    return [_to_out(e) for e in db.scalars(stmt)]


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(payload: ExamCreate, staff: CurrentStaff, db: DbSession) -> ExamOut:
    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    exam = Exam(
        exam_type=payload.exam_type,
        subject_id=payload.subject_id,
        title=payload.title.strip(),
        description=payload.description,
        instructions=payload.instructions,
        duration_minutes=payload.duration_minutes,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        selection_rules=payload.selection_rules.model_dump(mode="json"),
        randomize=payload.randomize,
        shuffle_options=payload.shuffle_options,
        negative_marking=payload.negative_marking,
        paper_salt=generate_salt(),
        proctor_config=payload.proctor_config.model_dump(mode="json"),
        grading_config=payload.grading_config.model_dump(mode="json"),
        created_by_id=staff.id,
        passing_percentage=payload.passing_percentage,
        declared_total_marks=payload.declared_total_marks,
        course=payload.course,
        department=payload.department,
        semester=payload.semester,
        company_name=payload.company_name,
        job_role=payload.job_role,
    )
    db.add(exam)
    db.flush()

    if payload.question_ids:
        _set_pool(db, exam, payload.question_ids)

    if payload.sections:
        _set_sections(db, exam, payload.sections)

    db.flush()
    db.refresh(exam)
    logger.info("%s created %s exam %r", staff.email, exam.exam_type.value, exam.title)
    return _to_out(_load_exam(db, exam.id))


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamOut:
    return _to_out(_load_exam(db, exam_id))


@router.patch("/{exam_id}", response_model=ExamOut)
def update_exam(
    exam_id: uuid.UUID, payload: ExamUpdate, staff: CurrentStaff, db: DbSession
) -> ExamOut:
    exam = _load_exam(db, exam_id)

    if exam.status is ExamStatus.PUBLISHED and db.scalar(
        select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidates have already started this exam; it can no longer be edited",
        )

    data = payload.model_dump(exclude_unset=True, exclude={"question_ids"})
    for field, value in data.items():
        if field in {"selection_rules", "proctor_config", "grading_config"} and value is not None:
            setattr(
                exam, field, value if isinstance(value, dict) else value.model_dump(mode="json")
            )
        else:
            setattr(exam, field, value)

    if exam.ends_at <= exam.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The exam window must end after it starts",
        )

    if payload.question_ids is not None:
        _set_pool(db, exam, payload.question_ids)

    db.flush()
    db.refresh(exam)
    logger.info("%s updated exam %s", staff.email, exam_id)
    return _to_out(_load_exam(db, exam_id))


@router.get("/{exam_id}/pool-check", response_model=ExamPoolCheck)
def pool_check(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamPoolCheck:
    """Can this exam's rules actually be satisfied by its pool? Drives the live UI hint."""
    exam = _load_exam(db, exam_id)
    problems = check_pool_satisfies_rules(exam)
    return ExamPoolCheck(
        can_publish=not problems,
        problems=problems,
        pool_size=len(exam.exam_questions),
        required_count=_required_count(exam),
    )


@router.post("/{exam_id}/publish", response_model=ExamOut)
def publish_exam(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamOut:
    exam = _load_exam(db, exam_id)
    problems = check_pool_satisfies_rules(exam)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "The question pool cannot satisfy this exam", "problems": problems},
        )
    exam.status = ExamStatus.PUBLISHED
    db.flush()
    logger.info("%s published exam %s (%r)", staff.email, exam_id, exam.title)
    return _to_out(_load_exam(db, exam_id))


@router.post("/{exam_id}/close", response_model=ExamOut)
def close_exam(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamOut:
    exam = _load_exam(db, exam_id)
    exam.status = ExamStatus.CLOSED
    db.flush()
    logger.info("%s closed exam %s", staff.email, exam_id)
    return _to_out(_load_exam(db, exam_id))


@router.post("/{exam_id}/preview-paper", response_model=PaperPreview)
def preview_paper(
    exam_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
    candidate_id: uuid.UUID | None = None,
) -> PaperPreview:
    """Dry-run the generator without creating a session.

    Calling this twice for the same candidate must return an identical paper - that is the
    determinism guarantee, and it is asserted in the test suite.
    """
    exam = _load_exam(db, exam_id)
    target = candidate_id or staff.id
    try:
        seed, entries = generate_paper(exam=exam, candidate_id=target)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    by_id = {eq.question_id: eq.question for eq in exam.exam_questions}
    return PaperPreview(
        seed=seed,
        candidate_id=target,
        total_marks=sum(e.marks for e in entries),
        entries=[
            PaperPreviewEntry(
                question_id=e.question_id,
                body=by_id[e.question_id].body,
                question_type=by_id[e.question_id].question_type,
                difficulty=by_id[e.question_id].difficulty,
                marks=e.marks,
                option_order=e.option_order,
            )
            for e in entries
        ],
    )


@router.delete("/{exam_id}", response_model=Message)
def delete_exam(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Message:
    exam = _load_exam(db, exam_id)
    attempts = db.scalar(select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam_id))
    if attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{attempts} candidate(s) have sat this exam; close it instead of deleting",
        )
    title = exam.title
    db.delete(exam)
    db.flush()
    logger.warning("%s deleted exam %r", staff.email, title)
    return Message(detail=f"Deleted exam {title!r}")
