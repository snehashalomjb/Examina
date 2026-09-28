"""Subjects and the question bank.

Every route here sits behind ``CurrentStaff`` - an approved examiner or an admin. An
examiner whose access is still pending gets a 403 with an explanatory message, which is
exactly the "admin grants access before the examiner can set the question bank" rule.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status
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
    ExamType,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionSource,
    QuestionStatus,
    QuestionType,
    Subject,
    UserRole,
)
from app.db.models.enums import DEFAULT_LOCALE, SUPPORTED_LOCALES
from app.db.models.translations import SubjectTranslation
from app.schemas.common import Message
from app.schemas.question import (
    BulkQuestionCreate,
    BulkQuestionResult,
    DuplicateCheckOut,
    DuplicateCheckRequest,
    DuplicateMatch,
    OptionIn,
    QuestionCreate,
    QuestionDuplicate,
    QuestionImageOut,
    QuestionOutFull,
    QuestionUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.services.i18n import resolve_locale, translated_field, upsert_translations
from app.services.language_purity import check_language_purity
from app.services.question_import import fingerprint
from app.services.validators import OptionDraft, ValidationError, validate_question

router = APIRouter(tags=["question-bank"])
logger = get_logger("questions")


def _get_locale(staff: CurrentStaff, lang: str | None, accept_language: str | None) -> str:
    return resolve_locale(
        query_lang=lang, user_locale=staff.preferred_locale, accept_language=accept_language
    )


def _to_full(question: Question) -> QuestionOutFull:
    """Serialise a question with its image URLs resolved.

    Object keys are what the database stores; a browser needs a time-limited URL, and
    presigning is a per-request concern rather than a model one. The question bank is
    English-only: the base columns *are* the text, and no locale-resolved variant of a
    question exists any more.
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
def _subject_out(subject: Subject, question_count: int, locale: str) -> SubjectOut:
    """Return a subject with its display label resolved for ``locale``.

    The id and code stay untouched - they are what every question, exam and section
    references - while only the human-facing name/description follow the language
    dropdown. The canonical English values travel alongside it so the subject manager
    never mistakes a translated label for the source name.
    """
    return SubjectOut(
        id=subject.id,
        code=subject.code,
        name=translated_field(subject.name, subject.translations, locale, "name") or subject.name,
        description=(
            translated_field(subject.description, subject.translations, locale, "description")
            or subject.description
        ),
        question_count=question_count,
        base_name=subject.name,
        base_description=subject.description,
    )


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(
    staff: CurrentStaff,
    db: DbSession,
    lang: str | None = None,
    #: Content-language scope, distinct from ``lang`` (display-label locale). Omitted,
    #: every subject is returned exactly as before. Given, restricts the list to subjects
    #: that have at least one *published* question in that language - the Primary Subject
    #: dropdown on Create Exam must show only subjects with real content in the exam's
    #: declared language.
    #:
    #: A subject is not globally "English" or "Kannada": the same subject code can carry
    #: questions in several languages (e.g. a shared ``CS203`` with both English and
    #: Hindi rows), and it must appear whenever *either* of those languages is selected -
    #: availability is scoped to ``subject_id`` + ``questions.language``, not to the
    #: subject as a whole. So this filter is symmetric across every language including
    #: English: it never additionally excludes a subject for also having rows in some
    #: other language. Keeping this separate from ``lang`` also matters on its own: a
    #: Hindi-UI examiner must keep seeing English subjects, so display locale must never
    #: double as a content filter.
    language: str | None = None,
    accept_language: str | None = Header(default=None),
) -> list[SubjectOut]:
    """List the shared taxonomy in the requested display language.

    ``?lang=`` deliberately wins over the signed-in user's preference, because the bank
    and composer expose an explicit language dropdown and that choice must not be
    overridden by a preference stored on another device.
    """
    locale = _get_locale(staff, lang, accept_language)
    counts = dict(
        db.execute(
            select(Question.subject_id, func.count(Question.id))
            .where(Question.is_active)
            .group_by(Question.subject_id)
        ).all()
    )
    stmt = select(Subject).options(selectinload(Subject.translations))
    if language:
        stmt = stmt.where(
            Subject.id.in_(select(Question.subject_id).where(Question.language == language))
        )
    subjects = db.scalars(stmt).all()
    localized = [_subject_out(subject, counts.get(subject.id, 0), locale) for subject in subjects]
    return sorted(localized, key=lambda item: (item.name.casefold(), item.code))


@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    staff: CurrentStaff,
    db: DbSession,
    lang: str | None = None,
    accept_language: str | None = Header(default=None),
) -> SubjectOut:
    if db.scalar(select(Subject).where(Subject.code == payload.code.upper())) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That subject code already exists"
        )
    subject = Subject(
        code=payload.code.upper(), name=payload.name.strip(), description=payload.description
    )
    db.add(subject)
    db.flush()
    upsert_translations(
        db,
        model_cls=SubjectTranslation,
        parent_fk="subject_id",
        parent_id=subject.id,
        kind="subject",
        base_values={"name": subject.name, "description": subject.description},
        translations_payload=payload.translations,
    )
    db.flush()
    db.expire(subject, ["translations"])
    logger.info("%s created subject %s", staff.email, subject.code)
    return _subject_out(subject, 0, _get_locale(staff, lang, accept_language))


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: uuid.UUID,
    payload: SubjectUpdate,
    staff: CurrentStaff,
    db: DbSession,
    lang: str | None = None,
    accept_language: str | None = Header(default=None),
) -> SubjectOut:
    """Rename, redescribe or translate a subject.

    The code is permanent - exams and questions already reference it, and it is what an
    examiner types to find a subject again. Translations are sibling rows keyed by the
    subject id, so changing a language never forks the taxonomy or breaks references.
    """
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    if payload.name is not None:
        subject.name = payload.name.strip()
    if payload.description is not None:
        subject.description = payload.description
    db.flush()
    upsert_translations(
        db,
        model_cls=SubjectTranslation,
        parent_fk="subject_id",
        parent_id=subject.id,
        kind="subject",
        base_values={"name": subject.name, "description": subject.description},
        translations_payload=payload.translations,
    )
    db.flush()
    db.expire(subject, ["translations"])
    count = (
        db.scalar(
            select(func.count(Question.id)).where(
                Question.subject_id == subject.id, Question.is_active
            )
        )
        or 0
    )
    logger.info("%s updated subject %s", staff.email, subject.code)
    return _subject_out(subject, count, _get_locale(staff, lang, accept_language))


@router.get("/subjects/type-counts", response_model=dict[str, dict[str, int]])
def subject_type_counts(staff: CurrentStaff, db: DbSession) -> dict[str, dict[str, int]]:
    """Question count per (subject, question_type) - what the bank's landing view shows
    under each subject before an examiner drills into one: ``Python -> MCQ: 200, ...``."""
    rows = db.execute(
        select(Question.subject_id, Question.question_type, func.count(Question.id))
        .where(Question.is_active)
        .group_by(Question.subject_id, Question.question_type)
    ).all()
    out: dict[str, dict[str, int]] = {}
    for subject_id, qtype, count in rows:
        out.setdefault(str(subject_id), {})[qtype.value] = count
    return out


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
    #: Match-any: a question carrying any one of the given tags is included.
    tags: list[str] | None = Query(default=None),
    #: Only questions this examiner wrote. Cheaper for the client than knowing its own id.
    mine: bool = False,
    created_by: uuid.UUID | None = None,
    #: Questions private to one exam. Without it, exam-only questions stay out of the
    #: bank browser entirely, which is the whole point of marking them private.
    exam_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    include_children: bool = False,
    language: str | None = Query(default=None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[QuestionOutFull]:
    """Browse the bank. Every filter in the spec, all optional, all combinable.

    Defaults to English (``language`` omitted) so every existing caller keeps getting
    exactly what it always has. Passing ``language`` scopes the browse to that content
    language instead - a Kannada exam's pool builder sees only Kannada questions, never
    a mix with English or Hindi material for the same subject.
    """
    if language is not None and language not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language"
        )
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
    stmt = stmt.where(Question.language == (language or DEFAULT_LOCALE))
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
    if tags:
        stmt = stmt.where(or_(*[Question.tags.contains([t]) for t in tags]))
    if mine:
        stmt = stmt.where(Question.created_by_id == staff.id)
    if created_by:
        stmt = stmt.where(Question.created_by_id == created_by)
    # A question authored for one exam only is not bank material. It is visible when
    # that exam is named, and nowhere else.
    stmt = stmt.where(
        Question.origin_exam_id == exam_id if exam_id else Question.origin_exam_id.is_(None)
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
    language: str | None = None,
) -> list[str]:
    """Distinct topics already in use, for the filter and authoring dropdowns.

    Topics are free text by design - the syllabus lists are long and change - so the
    dropdown is built from what examiners have actually used rather than a fixed table.
    Defaults to English, same as ``list_questions``; pass ``language`` to see another
    content language's topics instead.
    """
    stmt = (
        select(Question.topic)
        .where(Question.topic.is_not(None), Question.language == (language or DEFAULT_LOCALE))
        .distinct()
    )
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if category:
        stmt = stmt.where(Question.category == category)
    return sorted(t for t in db.scalars(stmt) if t and t.strip())


@router.get("/questions/tags", response_model=list[str])
def list_tags(staff: CurrentStaff, db: DbSession) -> list[str]:
    """Distinct tags already in use, for the tag picker's autocomplete.

    Tags are a plain JSONB string array on each question rather than their own table -
    fine to dedupe in Python since a question's tag list is a handful of short strings.
    """
    stmt = select(Question.tags).where(Question.tags.is_not(None))
    seen: set[str] = set()
    for tag_list in db.scalars(stmt):
        for tag in tag_list or []:
            if tag and tag.strip():
                seen.add(tag.strip())
    return sorted(seen)


@router.post("/questions/check-duplicate", response_model=DuplicateCheckOut)
def check_duplicate(
    payload: DuplicateCheckRequest, staff: CurrentStaff, db: DbSession
) -> DuplicateCheckOut:
    """Look for an existing bank question that reads the same as this one.

    Non-blocking by design: this only tells the examiner what it found, same fingerprint
    (whitespace-normalised, case-folded body) already trusted by the bulk-import duplicate
    check. Saving is never refused here - an examiner may genuinely want a near-duplicate
    (e.g. a harder variant), so this is a heads-up, not a gate.
    """
    needle = fingerprint(payload.body)
    if not needle:
        return DuplicateCheckOut()

    stmt = select(Question.id, Question.body).where(
        Question.subject_id == payload.subject_id,
        Question.origin_exam_id.is_(None),
        Question.is_active,
    )
    if payload.exclude_question_id:
        stmt = stmt.where(Question.id != payload.exclude_question_id)

    matches = [
        DuplicateMatch(id=qid, body=body)
        for qid, body in db.execute(stmt)
        if fingerprint(body) == needle
    ][:3]
    return DuplicateCheckOut(matches=matches)


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
        ExamQuestion(exam_id=exam.id, question_id=question.id, order_index=(next_index or -1) + 1)
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
    if (
        exam is not None
        and exam.exam_type is not ExamType.CORPORATE
        and payload.subject_id != exam.subject_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The question's subject must match the exam's subject",
        )
    question = Question(
        subject_id=payload.subject_id,
        language=payload.language,
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
            language=item.language,
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
def get_question(
    question_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
) -> QuestionOutFull:
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
        select(Question).where(Question.id == question_id).options(selectinload(Question.options))
    )
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    exam = _resolve_owning_exam(db, staff, payload.exam_id)
    if (
        exam is not None
        and exam.exam_type is not ExamType.CORPORATE
        and original.subject_id != exam.subject_id
    ):
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
        check_language_purity(
            language=question.language,
            fields={
                "question": question.body,
                "model answer": question.model_answer,
                "explanation": question.explanation,
                **{
                    f"option {chr(65 + i)}": o.text
                    for i, o in enumerate(question.options)
                },
            },
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
