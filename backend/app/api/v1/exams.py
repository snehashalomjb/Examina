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
    ExamPoolOut,
    ExamUpdate,
    PaperPreview,
    PaperPreviewEntry,
    PoolAdd,
    PoolEntry,
    PoolMarks,
    PoolReorder,
    PoolStats,
    PreviewOption,
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
        max_attempts=exam.max_attempts,
        difficulty=exam.difficulty,
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
            selectinload(Exam.exam_questions)
            .selectinload(ExamQuestion.question)
            .selectinload(Question.created_by),
            selectinload(Exam.subject),
            selectinload(Exam.sections),
        )
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


def _resolve_pool_questions(db, exam: Exam, question_ids: list[uuid.UUID]) -> list[Question]:
    """Load the given questions in the caller's order, refusing anything unusable.

    Order matters: ``order_index`` is assigned from the position in this list, and a
    ``SELECT ... WHERE id IN (...)`` returns rows in whatever order the planner likes.
    Reading the pool back out of the query result - which is what this used to do -
    silently discarded the ordering the examiner had just arranged.
    """
    by_id = {
        q.id: q
        for q in db.scalars(
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(selectinload(Question.options))
        )
    }
    missing = [qid for qid in question_ids if qid not in by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{len(missing)} question id(s) do not exist",
        )

    ordered = [by_id[qid] for qid in question_ids]

    off_subject = [q for q in ordered if q.subject_id != exam.subject_id]
    if off_subject:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{len(off_subject)} question(s) belong to a different subject",
        )
    # A question authored for a *different* exam is not shared material. Letting one
    # into a second paper would surprise the examiner who wrote it as a one-off.
    borrowed = [q for q in ordered if q.origin_exam_id is not None and q.origin_exam_id != exam.id]
    if borrowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{len(borrowed)} question(s) belong privately to another exam",
        )
    return ordered


def _set_pool(
    db,
    exam: Exam,
    question_ids: list[uuid.UUID],
    marks_overrides: dict[uuid.UUID, float] | None = None,
) -> None:
    """Replace the pool with exactly these questions, in exactly this order."""
    ordered = _resolve_pool_questions(db, exam, question_ids)
    overrides = marks_overrides or {}

    seen: set[uuid.UUID] = set()
    exam.exam_questions.clear()
    db.flush()  # the DELETEs must land before re-inserting, or the unique index trips
    for index, question in enumerate(ordered):
        if question.id in seen:  # a duplicated id is a client slip, not a second slot
            continue
        seen.add(question.id)
        exam.exam_questions.append(
            ExamQuestion(
                question_id=question.id,
                order_index=index,
                marks_override=overrides.get(question.id),
            )
        )


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
        max_attempts=payload.max_attempts,
        difficulty=payload.difficulty,
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


# --------------------------------------------------------------- pool management
#
# The pool is edited incrementally from the wizard - questions arrive one at a time
# from four different sources - so replacing the whole list on every change (which is
# what PATCH /exams/{id} does) would make the UI fight itself. These endpoints add,
# remove and reorder in place instead.


def _pool_entry(eq: ExamQuestion) -> PoolEntry:
    question = eq.question
    return PoolEntry(
        question_id=question.id,
        order_index=eq.order_index,
        marks_override=eq.marks_override,
        effective_marks=eq.effective_marks,
        body=question.body,
        question_type=question.question_type,
        difficulty=question.difficulty,
        category=question.category,
        topic=question.topic,
        source=question.source.value,
        exam_only=question.origin_exam_id is not None,
        created_by_name=question.created_by.full_name if question.created_by else None,
        option_count=len(question.options),
        has_answer_key=any(o.is_correct for o in question.options)
        or question.model_answer is not None
        or question.spec is not None,
    )


def _pool_out(exam: Exam) -> ExamPoolOut:
    entries = sorted(
        (_pool_entry(eq) for eq in exam.exam_questions), key=lambda e: e.order_index
    )
    by_type: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    for entry in entries:
        by_type[entry.question_type.value] = by_type.get(entry.question_type.value, 0) + 1
        by_difficulty[entry.difficulty.value] = by_difficulty.get(entry.difficulty.value, 0) + 1

    problems = check_pool_satisfies_rules(exam)
    return ExamPoolOut(
        exam_id=exam.id,
        entries=entries,
        stats=PoolStats(
            total_questions=len(entries),
            total_marks=round(sum(e.effective_marks for e in entries), 2),
            by_type=by_type,
            by_difficulty=by_difficulty,
        ),
        required_count=_required_count(exam),
        can_publish=not problems,
        problems=problems,
    )


def _guard_editable(db, exam: Exam) -> None:
    """A pool may not change once anyone has sat the paper it produced."""
    if exam.status is ExamStatus.PUBLISHED and db.scalar(
        select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidates have already started this exam; its questions can no longer change",
        )


@router.get("/{exam_id}/pool", response_model=ExamPoolOut)
def get_pool(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ExamPoolOut:
    """The exam's question pool, its distribution, and whether it can be published."""
    return _pool_out(_load_exam(db, exam_id))


@router.post("/{exam_id}/questions", response_model=ExamPoolOut)
def add_to_pool(
    exam_id: uuid.UUID, payload: PoolAdd, staff: CurrentStaff, db: DbSession
) -> ExamPoolOut:
    """Append questions to the pool. Ids already present are ignored, not duplicated."""
    exam = _load_exam(db, exam_id)
    _guard_editable(db, exam)

    present = {eq.question_id for eq in exam.exam_questions}
    fresh = [qid for qid in payload.question_ids if qid not in present]
    _resolve_pool_questions(db, exam, fresh)  # validates subject and ownership

    next_index = max((eq.order_index for eq in exam.exam_questions), default=-1) + 1
    for offset, question_id in enumerate(fresh):
        exam.exam_questions.append(
            ExamQuestion(question_id=question_id, order_index=next_index + offset)
        )

    db.flush()
    logger.info("%s added %d question(s) to exam %s", staff.email, len(fresh), exam_id)
    return _pool_out(_load_exam(db, exam_id))


@router.delete("/{exam_id}/questions/{question_id}", response_model=ExamPoolOut)
def remove_from_pool(
    exam_id: uuid.UUID, question_id: uuid.UUID, staff: CurrentStaff, db: DbSession
) -> ExamPoolOut:
    exam = _load_exam(db, exam_id)
    _guard_editable(db, exam)

    entry = next((eq for eq in exam.exam_questions if eq.question_id == question_id), None)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That question is not in this pool"
        )
    exam.exam_questions.remove(entry)
    db.flush()

    # Close the gap left behind, so order_index stays a dense 0..n-1 sequence.
    for index, eq in enumerate(sorted(exam.exam_questions, key=lambda e: e.order_index)):
        eq.order_index = index
    db.flush()
    return _pool_out(_load_exam(db, exam_id))


@router.put("/{exam_id}/questions/order", response_model=ExamPoolOut)
def reorder_pool(
    exam_id: uuid.UUID, payload: PoolReorder, staff: CurrentStaff, db: DbSession
) -> ExamPoolOut:
    """Set the pool's order. The payload must be a permutation of the current pool.

    Refusing a partial list rather than quietly appending the remainder: a client that
    sends nine of ten ids has lost one, and guessing where the tenth belongs would hide
    the bug behind a plausible-looking result.
    """
    exam = _load_exam(db, exam_id)
    _guard_editable(db, exam)

    current = {eq.question_id for eq in exam.exam_questions}
    given = list(dict.fromkeys(payload.question_ids))
    if set(given) != current or len(given) != len(current):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"The order must list every question in the pool exactly once "
                f"({len(current)} expected, {len(given)} distinct given)"
            ),
        )

    position = {question_id: index for index, question_id in enumerate(given)}
    for eq in exam.exam_questions:
        eq.order_index = position[eq.question_id]
    db.flush()
    logger.info("%s reordered the pool of exam %s", staff.email, exam_id)
    return _pool_out(_load_exam(db, exam_id))


@router.patch("/{exam_id}/questions/{question_id}/marks", response_model=ExamPoolOut)
def override_pool_marks(
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: PoolMarks,
    staff: CurrentStaff,
    db: DbSession,
) -> ExamPoolOut:
    """Re-weight a question for this exam without touching the bank copy."""
    exam = _load_exam(db, exam_id)
    _guard_editable(db, exam)

    entry = next((eq for eq in exam.exam_questions if eq.question_id == question_id), None)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That question is not in this pool"
        )
    entry.marks_override = payload.marks_override
    db.flush()
    return _pool_out(_load_exam(db, exam_id))


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

    def _options(entry) -> list[PreviewOption]:
        """The question's options in this candidate's shuffled order, key omitted."""
        question = by_id[entry.question_id]
        options = {option.id: option for option in question.options}
        ordered = [options[oid] for oid in entry.option_order if oid in options]
        # A question whose options were not shuffled still has options to show.
        if not ordered:
            ordered = sorted(question.options, key=lambda o: o.order_index)
        return [PreviewOption(id=option.id, text=option.text) for option in ordered]

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
                negative_marks=by_id[e.question_id].negative_marks,
                topic=by_id[e.question_id].topic,
                option_order=e.option_order,
                options=_options(e),
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
