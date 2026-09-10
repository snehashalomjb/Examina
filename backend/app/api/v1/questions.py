"""Subjects and the question bank.

Every route here sits behind ``CurrentStaff`` - an approved examiner or an admin. An
examiner whose access is still pending gets a 403 with an explanatory message, which is
exactly the "admin grants access before the examiner can set the question bank" rule.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentStaff, DbSession
from app.core.images import ImageError, make_thumbnail
from app.core.logging_config import get_logger
from app.core.storage import build_key, presigned_url, put_object
from app.db.models import (
    Difficulty,
    Exam,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionSource,
    QuestionStatus,
    QuestionType,
    Subject,
    UserRole,
)
from app.schemas.common import Message
from app.schemas.question import (
    BulkQuestionCreate,
    BulkQuestionResult,
    OptionIn,
    QuestionCreate,
    QuestionDuplicate,
    QuestionImageOut,
    QuestionOutFull,
    QuestionUpdate,
    SubjectCreate,
    SubjectOut,
)
from app.services.validators import OptionDraft, ValidationError, validate_question

router = APIRouter(tags=["question-bank"])
logger = get_logger("questions")


def _to_full(question: Question) -> QuestionOutFull:
    """Serialise a question with its image URLs resolved.

    Object keys are what the database stores; a browser needs a time-limited URL, and
    presigning is a per-request concern rather than a model one.
    """
    out = QuestionOutFull.model_validate(question)
    out.image_url = presigned_url(question.image_key)
    out.created_by_name = question.created_by.full_name if question.created_by else None
    out.subject_code = question.subject.code if question.subject else None
    out.exam_only = question.origin_exam_id is not None
    by_id = {o.id: o for o in question.options}
    for option in out.options:
        source = by_id.get(option.id)
        if source is not None:
            option.image_url = presigned_url(source.image_key)
    return out


# ------------------------------------------------------------------ subjects
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(staff: CurrentStaff, db: DbSession) -> list[SubjectOut]:
    counts = dict(
        db.execute(
            select(Question.subject_id, func.count(Question.id))
            .where(Question.is_active)
            .group_by(Question.subject_id)
        ).all()
    )
    subjects = db.scalars(select(Subject).order_by(Subject.name))
    return [
        SubjectOut(
            id=s.id,
            code=s.code,
            name=s.name,
            description=s.description,
            question_count=counts.get(s.id, 0),
        )
        for s in subjects
    ]


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, staff: CurrentStaff, db: DbSession) -> SubjectOut:
    if db.scalar(select(Subject).where(Subject.code == payload.code.upper())) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That subject code already exists"
        )
    subject = Subject(
        code=payload.code.upper(), name=payload.name.strip(), description=payload.description
    )
    db.add(subject)
    db.flush()
    logger.info("%s created subject %s", staff.email, subject.code)
    return SubjectOut(
        id=subject.id,
        code=subject.code,
        name=subject.name,
        description=subject.description,
        question_count=0,
    )


# ----------------------------------------------------------------- questions
def _apply_options(question: Question, options: list[OptionIn]) -> None:
    question.options.clear()
    for index, option in enumerate(options):
        question.options.append(
            QuestionOption(
                text=option.text.strip(),
                image_key=option.image_key,
                is_correct=option.is_correct,
                order_index=option.order_index or index,
            )
        )


# --------------------------------------------------------------- bank images
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_QUESTION_IMAGE_BYTES = 8 * 1024 * 1024


@router.post("/questions/images", response_model=QuestionImageOut)
def upload_question_image(
    staff: CurrentStaff,
    file: UploadFile = File(...),
) -> QuestionImageOut:
    """Store a figure for a question, an option, or an explanation.

    Returns an object key to put on whichever field it belongs to, so one endpoint serves
    all of them and an image can be uploaded before the question it belongs to exists.
    Reuses the same object storage as answer scans and webcam snapshots - large binaries
    stay out of Postgres, and the database holds only the key.

    Nothing links the key to a question here. An orphaned upload costs a few kilobytes;
    blocking an examiner mid-authoring because the question is not saved yet costs more.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a JPEG, PNG, WebP or GIF image",
        )

    data = file.file.read()
    if len(data) > MAX_QUESTION_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be under {MAX_QUESTION_IMAGE_BYTES // (1024 * 1024)} MB",
        )

    # Decode before storing: this both rejects a file that only claims to be an image
    # and gives the authoring UI a thumbnail to preview without pulling the original.
    try:
        thumbnail = make_thumbnail(data)
    except ImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    extension = (file.filename or "figure.png").rsplit(".", 1)[-1][:8] or "png"
    key = build_key(prefix="questions", session_id=staff.id, extension=extension)
    put_object(key=key, data=data, content_type=file.content_type)

    thumb_key = f"{key.rsplit('.', 1)[0]}-thumb.jpg"
    put_object(key=thumb_key, data=thumbnail, content_type="image/jpeg")

    logger.info("%s uploaded a question image (%d bytes)", staff.email, len(data))
    return QuestionImageOut(
        image_key=key,
        image_url=presigned_url(key),
        thumbnail_url=presigned_url(thumb_key),
    )


@router.get("/questions", response_model=list[QuestionOutFull])
def list_questions(
    staff: CurrentStaff,
    db: DbSession,
    subject_id: uuid.UUID | None = None,
    question_type: QuestionType | None = None,
    category: QuestionCategory | None = None,
    topic: str | None = None,
    difficulty: Difficulty | None = None,
    question_status: QuestionStatus | None = Query(default=None, alias="status"),
    marks: float | None = None,
    search: str | None = None,
    source: QuestionSource | None = None,
    #: Only questions this examiner wrote. Cheaper for the client than knowing its own id.
    mine: bool = False,
    created_by: uuid.UUID | None = None,
    #: Questions private to one exam. Without it, exam-only questions stay out of the
    #: bank browser entirely, which is the whole point of marking them private.
    exam_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    include_children: bool = False,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[QuestionOutFull]:
    """Browse the bank. Every filter in the spec, all optional, all combinable."""
    stmt = (
        select(Question)
        .options(
            selectinload(Question.options),
            selectinload(Question.created_by),
            selectinload(Question.subject),
        )
        .order_by(Question.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if not include_inactive:
        stmt = stmt.where(Question.is_active)
    if not include_children:
        # A passage's children are shown nested under it, not loose in the list, or the
        # browser fills with fragments that make no sense on their own.
        stmt = stmt.where(Question.parent_question_id.is_(None))
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if question_type:
        stmt = stmt.where(Question.question_type == question_type)
    if category:
        stmt = stmt.where(Question.category == category)
    if topic:
        stmt = stmt.where(func.lower(Question.topic) == topic.lower())
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if question_status:
        stmt = stmt.where(Question.status == question_status)
    if marks is not None:
        stmt = stmt.where(Question.marks == marks)
    if source:
        stmt = stmt.where(Question.source == source)
    if mine:
        stmt = stmt.where(Question.created_by_id == staff.id)
    if created_by:
        stmt = stmt.where(Question.created_by_id == created_by)
    # A question authored for one exam only is not bank material. It is visible when
    # that exam is named, and nowhere else.
    stmt = stmt.where(
        Question.origin_exam_id == exam_id
        if exam_id
        else Question.origin_exam_id.is_(None)
    )
    if search:
        needle = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Question.body).like(needle),
                func.lower(Question.topic).like(needle),
            )
        )

    return [_to_full(q) for q in db.scalars(stmt)]


@router.get("/questions/topics", response_model=list[str])
def list_topics(
    staff: CurrentStaff,
    db: DbSession,
    subject_id: uuid.UUID | None = None,
    category: QuestionCategory | None = None,
) -> list[str]:
    """Distinct topics already in use, for the filter and authoring dropdowns.

    Topics are free text by design - the syllabus lists are long and change - so the
    dropdown is built from what examiners have actually used rather than a fixed table.
    """
    stmt = select(Question.topic).where(Question.topic.is_not(None)).distinct()
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if category:
        stmt = stmt.where(Question.category == category)
    return sorted(t for t in db.scalars(stmt) if t and t.strip())


def _resolve_owning_exam(db, staff, exam_id: uuid.UUID | None) -> Exam | None:
    """Load the exam a question is being authored into, refusing what is not editable."""
    if exam_id is None:
        return None
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if staff.role is not UserRole.ADMIN and exam.created_by_id != staff.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add questions to an exam you created",
        )
    return exam


def _append_to_pool(db, exam: Exam, question: Question) -> None:
    """Put a freshly authored question at the end of its exam's pool."""
    next_index = db.scalar(
        select(func.coalesce(func.max(ExamQuestion.order_index), -1)).where(
            ExamQuestion.exam_id == exam.id
        )
    )
    db.add(
        ExamQuestion(
            exam_id=exam.id, question_id=question.id, order_index=(next_index or -1) + 1
        )
    )


def _may_edit(staff, question: Question) -> bool:
    """An examiner owns what they wrote. An admin may edit anything.

    Questions with no recorded author (seeded before authorship was tracked) stay
    editable by any staff member - locking them would strand the existing bank.
    """
    if staff.role is UserRole.ADMIN:
        return True
    return question.created_by_id in (None, staff.id)


def _require_edit(staff, question: Question) -> None:
    if not _may_edit(staff, question):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This question belongs to another examiner. Duplicate it to make your own copy.",
        )


@router.post("/questions", response_model=QuestionOutFull, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, staff: CurrentStaff, db: DbSession) -> QuestionOutFull:
    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    exam = _resolve_owning_exam(db, staff, payload.exam_id)
    if exam is not None and payload.subject_id != exam.subject_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question's subject must match the exam's subject",
        )

    question = Question(
        subject_id=payload.subject_id,
        question_type=payload.question_type,
        category=payload.category,
        topic=(payload.topic or None),
        difficulty=payload.difficulty,
        body=payload.body.strip(),
        model_answer=payload.model_answer,
        explanation=payload.explanation,
        rubric=payload.rubric,
        spec=payload.spec,
        image_key=payload.image_key,
        parent_question_id=payload.parent_question_id,
        marks=payload.marks,
        negative_marks=payload.negative_marks,
        min_words=payload.min_words,
        max_words=payload.max_words,
        tags=payload.tags,
        source=payload.source,
        # Private to the exam only when the examiner both named an exam and declined
        # the bank. No exam means nowhere else to live, so it is shelved.
        origin_exam_id=(exam.id if exam is not None and not payload.save_to_bank else None),
        created_by_id=staff.id,
    )
    _apply_options(question, payload.options)
    db.add(question)
    db.flush()

    if exam is not None:
        _append_to_pool(db, exam, question)
        db.flush()

    db.refresh(question)
    logger.info(
        "%s added a %s question (%s)",
        staff.email,
        question.question_type.value,
        "exam-only" if question.origin_exam_id else "bank",
    )
    return _to_full(question)


@router.post("/questions/bulk", response_model=BulkQuestionResult)
def bulk_create(
    payload: BulkQuestionCreate, staff: CurrentStaff, db: DbSession
) -> BulkQuestionResult:
    """Import many questions at once. Valid rows are kept; invalid rows are reported."""
    created = 0
    errors: list[dict] = []

    for index, item in enumerate(payload.questions):
        if db.get(Subject, item.subject_id) is None:
            errors.append({"index": index, "error": "Subject not found"})
            continue
        question = Question(
            subject_id=item.subject_id,
            question_type=item.question_type,
            category=item.category,
            topic=(item.topic or None),
            difficulty=item.difficulty,
            body=item.body.strip(),
            model_answer=item.model_answer,
            explanation=item.explanation,
            rubric=item.rubric,
            spec=item.spec,
            image_key=item.image_key,
            parent_question_id=item.parent_question_id,
            marks=item.marks,
            negative_marks=item.negative_marks,
            min_words=item.min_words,
            max_words=item.max_words,
            tags=item.tags,
            created_by_id=staff.id,
        )
        _apply_options(question, item.options)
        db.add(question)
        created += 1

    db.flush()
    logger.info("%s bulk-imported %d questions (%d failed)", staff.email, created, len(errors))
    return BulkQuestionResult(created=created, failed=len(errors), errors=errors)


@router.get("/questions/{question_id}", response_model=QuestionOutFull)
def get_question(question_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> QuestionOutFull:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return _to_full(question)


@router.post(
    "/questions/{question_id}/duplicate",
    response_model=QuestionOutFull,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_question(
    question_id: uuid.UUID, payload: QuestionDuplicate, staff: CurrentStaff, db: DbSession
) -> QuestionOutFull:
    """Copy a question, with its options and answer key, into the caller's name.

    Reading another examiner's question is allowed; editing it is not. Duplicating is
    the sanctioned way to build on someone else's work without altering their copy.
    """
    original = db.scalar(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.options))
    )
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    exam = _resolve_owning_exam(db, staff, payload.exam_id)
    if exam is not None and original.subject_id != exam.subject_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question's subject must match the exam's subject",
        )

    copy = Question(
        subject_id=original.subject_id,
        question_type=original.question_type,
        category=original.category,
        topic=original.topic,
        difficulty=original.difficulty,
        body=original.body,
        model_answer=original.model_answer,
        explanation=original.explanation,
        rubric=original.rubric,
        spec=original.spec,
        image_key=original.image_key,
        marks=original.marks,
        negative_marks=original.negative_marks,
        min_words=original.min_words,
        max_words=original.max_words,
        tags=original.tags,
        # The copy is the caller's own work from here on, so it carries their id and a
        # manual provenance - a hand-picked copy of an AI draft is a human decision.
        source=original.source,
        status=original.status,
        origin_exam_id=(exam.id if exam is not None and not payload.save_to_bank else None),
        created_by_id=staff.id,
    )
    for option in original.options:
        copy.options.append(
            QuestionOption(
                text=option.text,
                image_key=option.image_key,
                is_correct=option.is_correct,
                order_index=option.order_index,
            )
        )
    db.add(copy)
    db.flush()

    if exam is not None:
        _append_to_pool(db, exam, copy)
        db.flush()

    db.refresh(copy)
    logger.info("%s duplicated question %s", staff.email, question_id)
    return _to_full(copy)


@router.patch("/questions/{question_id}", response_model=QuestionOutFull)
def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, staff: CurrentStaff, db: DbSession
) -> QuestionOutFull:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    _require_edit(staff, question)

    data = payload.model_dump(exclude_unset=True, exclude={"options"})
    for field, value in data.items():
        setattr(question, field, value)

    if payload.options is not None:
        _apply_options(question, payload.options)

    # Re-check the domain rules against the merged state, not just the incoming patch.
    try:
        question.spec = validate_question(
            question_type=question.question_type,
            body=question.body,
            marks=question.marks,
            negative_marks=question.negative_marks,
            options=[OptionDraft(o.text, o.is_correct, o.order_index) for o in question.options],
            model_answer=question.model_answer,
            min_words=question.min_words,
            max_words=question.max_words,
            spec=question.spec,
            image_key=question.image_key,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    db.flush()
    db.refresh(question)
    logger.info("%s updated question %s", staff.email, question_id)
    return _to_full(question)


@router.delete("/questions/{question_id}", response_model=Message)
def delete_question(question_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> Message:
    """Soft-delete when the question is already used by an exam, hard-delete otherwise.

    A question that has been sat cannot be removed without orphaning results, so it is
    retired instead.
    """
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    _require_edit(staff, question)

    in_use = db.scalar(
        select(func.count(ExamQuestion.id)).where(ExamQuestion.question_id == question_id)
    )
    if in_use:
        question.is_active = False
        db.flush()
        logger.info("%s retired in-use question %s", staff.email, question_id)
        return Message(detail="Question is used by an exam, so it was retired instead of deleted")

    db.delete(question)
    db.flush()
    logger.info("%s deleted question %s", staff.email, question_id)
    return Message(detail="Question deleted")
