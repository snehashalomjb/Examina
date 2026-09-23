"""Importing questions from a file: upload, parse, validate, preview, then import.

Two endpoints and a template download, matching the workflow in that order. The split
is the point - parsing does not write, so the examiner sees every problem before a
single question exists. An importer that goes straight from upload to database is how
a bank fills up with half-formed questions nobody notices until an exam is live.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.db.models import (
    Exam,
    ExamQuestion,
    ExamType,
    Question,
    QuestionOption,
    QuestionSource,
    Subject,
)
from app.db.models.enums import UserRole
from app.schemas.question_import import (
    ImportCommit,
    ImportedRow,
    ImportParseOut,
    ImportResult,
    ImportRowIn,
)
from app.services.question_import import (
    ImportError_,
    fingerprint,
    parse_questions,
    template_csv,
    xlsx_active_sheet_name,
    xlsx_sheet_names,
)
from app.services.validators import OptionDraft, ValidationError, validate_question

router = APIRouter(tags=["question-import"])
logger = get_logger("question_import")

#: A question bank spreadsheet is text. Anything this size is a mistake or an attack.
MAX_IMPORT_BYTES = 10 * 1024 * 1024


def _resolve_exam(db, staff, exam_id: uuid.UUID | None) -> Exam | None:
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


@router.get("/questions/import/template")
def import_template(staff: CurrentStaff) -> Response:
    """A filled-in CSV showing every column the parser understands."""
    return Response(
        content=template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="examina-question-template.csv"'},
    )


@router.post("/questions/import/parse", response_model=ImportParseOut)
async def parse_import(
    staff: CurrentStaff,
    db: DbSession,
    file: UploadFile = File(...),
    subject_id: uuid.UUID | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
) -> ImportParseOut:
    """Read a file and report what is in it, without writing anything.

    Rows come back in file order with their problems attached, so the preview can show
    "row 7: MCQ has no correct answer" against the row it belongs to.
    """
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That file is empty."
        )
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"That file is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB.",
        )

    filename = file.filename or "upload"
    sheet_names = (
        xlsx_sheet_names(data) if filename.lower().rsplit(".", 1)[-1] in ("xlsx", "xlsm") else []
    )

    try:
        rows = parse_questions(filename=filename, data=data, sheet_name=sheet_name)
    except ImportError_ as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # A row may name its own subject - "Aptitude + Java + Python in one file" is the
    # whole point of the column. Every subject in the database is loaded once and
    # matched by code or name, case-insensitively; a row whose text matches none of
    # them is a validation error on that row, not a silent fallback to the default.
    subjects_by_key = {
        key: subj
        for subj in db.scalars(select(Subject))
        for key in (subj.code.strip().casefold(), subj.name.strip().casefold())
    }
    default_subject = db.get(Subject, subject_id) if subject_id else None

    for row in rows:
        text = row.subject_text.strip()
        if not text:
            if default_subject is not None:
                row.subject_id = default_subject.id
                row.subject_name = default_subject.name
            continue
        match = subjects_by_key.get(text.casefold())
        if match is None:
            row.problems.append(f"Unknown subject '{text}'.")
            continue
        row.subject_id = match.id
        row.subject_name = match.name

    # Duplicate detection against the bank the questions would land in, per row's own
    # subject - the same wording in two different subjects is usually coincidence, but
    # the same wording twice in the same subject almost never is.
    subject_ids = {row.subject_id for row in rows if row.subject_id is not None}
    existing_by_subject: dict[uuid.UUID, set[str]] = {}
    for sid in subject_ids:
        existing_by_subject[sid] = {
            fingerprint(body)
            for body in db.scalars(
                select(Question.body).where(
                    Question.subject_id == sid, Question.origin_exam_id.is_(None)
                )
            )
        }
    for row in rows:
        sid = row.subject_id
        if row.duplicate_of is None and sid is not None:
            if fingerprint(row.body) in existing_by_subject.get(sid, set()):
                row.duplicate_of = "the question bank"

    out_rows = [
        ImportedRow(
            row_number=row.row_number,
            body=row.body,
            subject_id=row.subject_id,
            subject_name=row.subject_name,
            question_type=row.question_type,
            difficulty=row.difficulty,
            category=row.category,
            topic=row.topic,
            marks=row.marks,
            negative_marks=row.negative_marks,
            model_answer=row.model_answer,
            explanation=row.explanation,
            tags=row.tags,
            min_words=row.min_words,
            max_words=row.max_words,
            spec=row.spec,
            options=[{"text": o.text, "is_correct": o.is_correct} for o in row.options],
            problems=row.problems,
            duplicate_of=row.duplicate_of,
        )
        for row in rows
    ]

    logger.info(
        "%s parsed %s: %d row(s), %d with problems",
        staff.email,
        file.filename,
        len(out_rows),
        sum(1 for r in out_rows if r.problems),
    )
    return ImportParseOut(
        filename=file.filename or "upload",
        total=len(out_rows),
        valid=sum(1 for r in out_rows if not r.problems),
        invalid=sum(1 for r in out_rows if r.problems),
        duplicates=sum(1 for r in out_rows if r.duplicate_of),
        rows=out_rows,
        sheet_names=sheet_names,
        # The sheet actually read: the one the examiner picked, or - the first time,
        # before they have picked anything - whichever tab was active when the
        # workbook was saved. Echoing back the request's own (possibly null) value
        # here would tell the picker nothing about what it is looking at.
        sheet_name=(sheet_name or xlsx_active_sheet_name(data)) if sheet_names else None,
    )


def _build_question(row: ImportRowIn, subject_id: uuid.UUID, staff, exam: Exam | None) -> Question:
    """Re-validate a row the client may have edited, then turn it into a question."""
    spec = validate_question(
        question_type=row.question_type,
        body=row.body,
        marks=row.marks,
        negative_marks=row.negative_marks,
        options=[OptionDraft(o.text, o.is_correct, i) for i, o in enumerate(row.options)],
        model_answer=row.model_answer,
        min_words=row.min_words,
        max_words=row.max_words,
        spec=row.spec,
        image_key=None,
    )
    question = Question(
        subject_id=subject_id,
        question_type=row.question_type,
        category=row.category,
        topic=row.topic,
        difficulty=row.difficulty,
        body=row.body.strip(),
        model_answer=row.model_answer,
        explanation=row.explanation,
        spec=spec,
        marks=row.marks,
        negative_marks=row.negative_marks,
        tags=row.tags or None,
        min_words=row.min_words,
        max_words=row.max_words,
        source=QuestionSource.IMPORTED,
        origin_exam_id=(exam.id if exam is not None and not row.save_to_bank else None),
        created_by_id=staff.id,
    )
    for index, option in enumerate(row.options):
        question.options.append(
            QuestionOption(text=option.text, is_correct=option.is_correct, order_index=index)
        )
    return question


@router.post("/questions/import", response_model=ImportResult)
def commit_import(payload: ImportCommit, staff: CurrentStaff, db: DbSession) -> ImportResult:
    """Import the rows the examiner approved, after any corrections they made.

    The client sends rows back rather than a file handle: the examiner has been fixing
    them in the preview, and what they see is what should be imported. Every row is
    validated again here - the browser's copy of the rules is a convenience, never the
    authority.
    """
    if db.get(Subject, payload.subject_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    exam = _resolve_exam(db, staff, payload.exam_id)
    # An academic paper is one subject, so a row that disagrees with the exam's
    # subject is refused, same as every other way into that pool. A corporate
    # assessment is legitimately built from several skill domains in one sitting -
    # "Technical Assessment" drawing Java, Python, SQL, DBMS and Aptitude - so a row
    # is free to name its own subject there, and does not have to match the exam's.
    mixed_subjects_allowed = exam is not None and exam.exam_type is ExamType.CORPORATE
    if exam is not None and not mixed_subjects_allowed and exam.subject_id != payload.subject_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The import's subject must match the exam's subject",
        )

    row_subject_ids = {row.subject_id for row in payload.rows if row.subject_id is not None}
    if row_subject_ids:
        known = {s.id for s in db.scalars(select(Subject).where(Subject.id.in_(row_subject_ids)))}
        missing = row_subject_ids - known
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{len(missing)} row(s) name a subject that no longer exists",
            )
        if exam is not None and not mixed_subjects_allowed:
            off_subject = row_subject_ids - {payload.subject_id}
            if off_subject:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "This exam accepts one subject; some rows named a different "
                        "one. Only a corporate assessment can mix subjects."
                    ),
                )

    created: list[Question] = []
    errors: list[dict] = []

    for row in payload.rows:
        try:
            question = _build_question(row, row.subject_id or payload.subject_id, staff, exam)
        except ValidationError as exc:
            errors.append({"row_number": row.row_number, "error": str(exc)})
            continue
        db.add(question)
        created.append(question)

    db.flush()

    if exam is not None and created:
        next_index = db.scalar(
            select(ExamQuestion.order_index)
            .where(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.order_index.desc())
            .limit(1)
        )
        start = (next_index + 1) if next_index is not None else 0
        for offset, question in enumerate(created):
            db.add(
                ExamQuestion(exam_id=exam.id, question_id=question.id, order_index=start + offset)
            )
        db.flush()

    logger.info("%s imported %d question(s), %d refused", staff.email, len(created), len(errors))
    return ImportResult(
        created=len(created),
        failed=len(errors),
        errors=errors,
        question_ids=[q.id for q in created],
    )
