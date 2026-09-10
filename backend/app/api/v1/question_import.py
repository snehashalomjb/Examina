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
from app.db.models import Exam, ExamQuestion, Question, QuestionOption, QuestionSource, Subject
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

    try:
        rows = parse_questions(filename=file.filename or "upload", data=data)
    except ImportError_ as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # Duplicate detection against the bank the questions would land in. Restricted to
    # one subject because the same wording across two subjects is usually coincidence.
    if subject_id is not None:
        existing = {
            fingerprint(body): body
            for body in db.scalars(
                select(Question.body).where(
                    Question.subject_id == subject_id, Question.origin_exam_id.is_(None)
                )
            )
        }
        for row in rows:
            if row.duplicate_of is None and fingerprint(row.body) in existing:
                row.duplicate_of = "the question bank"

    out_rows = [
        ImportedRow(
            row_number=row.row_number,
            body=row.body,
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
    if exam is not None and exam.subject_id != payload.subject_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The import's subject must match the exam's subject",
        )

    created: list[Question] = []
    errors: list[dict] = []

    for row in payload.rows:
        try:
            question = _build_question(row, payload.subject_id, staff, exam)
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
                ExamQuestion(
                    exam_id=exam.id, question_id=question.id, order_index=start + offset
                )
            )
        db.flush()

    logger.info(
        "%s imported %d question(s), %d refused", staff.email, len(created), len(errors)
    )
    return ImportResult(
        created=len(created),
        failed=len(errors),
        errors=errors,
        question_ids=[q.id for q in created],
    )
