"""AI question generation and draft review workflow.

Generate → Examiner Review → Edit / Approve / Reject → Question Bank

AI-generated questions are never automatically published. A human must approve every one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.db.models import (
    AiQuestionDraft,
    DraftStatus,
    Exam,
    ExamQuestion,
    ExamType,
    Question,
    QuestionOption,
    QuestionSource,
    Subject,
    UserRole,
)
from app.db.models.enums import Difficulty, QuestionCategory, QuestionType
from app.schemas.ai_gen import (
    AiDraftApprove,
    AiDraftOut,
    AiDraftReject,
    AiGenerateRequest,
    AiPdfImportOut,
    AiRegenerateRequest,
)
from app.services.ai_generator import generate_questions
from app.services.pdf_extract import PdfError, extract_pdf_text
from app.services.validators import OptionDraft, ValidationError, validate_question

router = APIRouter(tags=["ai-questions"])
logger = get_logger("ai_questions")


def _draft_out(draft: AiQuestionDraft) -> AiDraftOut:
    return AiDraftOut.model_validate(draft)


def _compose_instructions(payload: AiGenerateRequest) -> str | None:
    """Fold the language choice into the free-text instructions.

    Kept out of the generator's signature: "write in Tamil" is an instruction like any
    other, and threading a language parameter through every provider would buy nothing.
    """
    parts = [payload.extra_instructions] if payload.extra_instructions else []
    if payload.language:
        parts.append(f"Write every question and option in {payload.language}.")
    return " ".join(parts) or None


# ----------------------------------------------------------------- generate


@router.post(
    "/questions/ai-generate",
    response_model=list[AiDraftOut],
    status_code=status.HTTP_201_CREATED,
)
def ai_generate(payload: AiGenerateRequest, staff: CurrentStaff, db: DbSession) -> list[AiDraftOut]:
    """Generate a batch of question drafts. None are published until an examiner approves.

    Each draft may succeed or fail independently - a partial batch is still useful and is
    stored so the examiner can see which prompts produced errors.
    """
    subject: Subject | None = None
    if payload.subject_id:
        subject = db.get(Subject, payload.subject_id)
        if subject is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    saved: list[AiQuestionDraft] = []
    for question_type, share in payload.type_plan():
        raw_drafts = generate_questions(
            category=payload.category,
            topic=payload.topic,
            difficulty=payload.difficulty,
            question_type=question_type,
            count=share,
            extra_instructions=_compose_instructions(payload),
            source_text=payload.syllabus,
            subject_name=subject.name if subject else None,
        )
        for item in raw_drafts:
            body = dict(item.get("payload", {}))
            if payload.marks_per_question is not None:
                body["marks"] = payload.marks_per_question
            draft = AiQuestionDraft(
                subject_id=payload.subject_id,
                category=payload.category,
                topic=payload.topic,
                difficulty=payload.difficulty,
                question_type=question_type,
                payload=body,
                original_payload=body,
                provider=item.get("provider", "stub"),
                model=item.get("model"),
                error=item.get("error"),
                status=DraftStatus.PENDING,
                requested_by_id=staff.id,
            )
            db.add(draft)
            saved.append(draft)

    db.flush()
    for d in saved:
        db.refresh(d)

    logger.info(
        "%s generated %d AI question draft(s) (category=%s topic=%s)",
        staff.email,
        len(saved),
        payload.category.value,
        payload.topic or "-",
    )
    return [_draft_out(d) for d in saved]


# --------------------------------------------------------------- pdf import
#: Well above a long syllabus, well below anything that would strain the parser.
MAX_PDF_BYTES = 20 * 1024 * 1024
ALLOWED_PDF_TYPES = {"application/pdf", "application/x-pdf"}


@router.post(
    "/questions/ai-generate/from-pdf",
    response_model=AiPdfImportOut,
    status_code=status.HTTP_201_CREATED,
)
def ai_generate_from_pdf(
    staff: CurrentStaff,
    db: DbSession,
    file: UploadFile = File(...),
    subject_id: uuid.UUID | None = Form(default=None),
    category: QuestionCategory = Form(default=QuestionCategory.TECHNICAL),
    topic: str | None = Form(default=None, max_length=120),
    difficulty: Difficulty = Form(default=Difficulty.MEDIUM),
    question_type: QuestionType = Form(default=QuestionType.MCQ),
    count: int = Form(default=5, ge=1, le=20),
    extra_instructions: str | None = Form(default=None, max_length=500),
) -> AiPdfImportOut:
    """Turn an uploaded PDF into question drafts.

    Same destination as ``/questions/ai-generate`` - the review queue - so a PDF import
    is reviewed, edited and approved through exactly the one path that already guards the
    bank. The PDF itself is not stored: only the text it yielded reaches the generator,
    and only the drafts are kept.
    """
    if file.content_type not in ALLOWED_PDF_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF file",
        )
    subject: Subject | None = None
    if subject_id is not None:
        subject = db.get(Subject, subject_id)
        if subject is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    data = file.file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF must be under {MAX_PDF_BYTES // (1024 * 1024)} MB",
        )

    try:
        extracted = extract_pdf_text(data)
    except PdfError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    raw_drafts = generate_questions(
        category=category,
        topic=(topic or None),
        difficulty=difficulty,
        question_type=question_type,
        count=count,
        extra_instructions=extra_instructions,
        source_text=extracted.text,
        subject_name=subject.name if subject else None,
    )

    filename = (file.filename or "upload.pdf")[:200]
    saved: list[AiQuestionDraft] = []
    for item in raw_drafts:
        payload = dict(item.get("payload", {}))
        # The provenance travels with the draft, so the review queue can show where a
        # question came from long after this request is gone.
        payload["source_pdf"] = filename
        draft = AiQuestionDraft(
            subject_id=subject_id,
            category=category,
            topic=(topic or None),
            difficulty=difficulty,
            question_type=question_type,
            payload=payload,
            original_payload=payload,
            provider=item.get("provider", "stub"),
            model=item.get("model"),
            error=item.get("error"),
            status=DraftStatus.PENDING,
            requested_by_id=staff.id,
        )
        db.add(draft)
        saved.append(draft)

    db.flush()
    for d in saved:
        db.refresh(d)

    grounded = all(d.payload.get("source_grounded") for d in saved) if saved else False

    logger.info(
        "%s imported %s (%d pages, %d chars) -> %d draft(s), grounded=%s",
        staff.email,
        filename,
        extracted.pages,
        extracted.characters,
        len(saved),
        grounded,
    )
    return AiPdfImportOut(
        filename=filename,
        pages=extracted.pages,
        empty_pages=extracted.empty_pages,
        characters=extracted.characters,
        truncated=extracted.truncated,
        source_grounded=grounded,
        drafts=[_draft_out(d) for d in saved],
    )


# ------------------------------------------------------------------- drafts


@router.get("/questions/ai-drafts", response_model=list[AiDraftOut])
def list_drafts(
    staff: CurrentStaff,
    db: DbSession,
    draft_status: DraftStatus | None = Query(default=None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    mine: bool = False,
) -> list[AiDraftOut]:
    stmt = select(AiQuestionDraft).order_by(AiQuestionDraft.created_at.desc()).limit(limit)
    if draft_status:
        stmt = stmt.where(AiQuestionDraft.status == draft_status)
    if mine:
        stmt = stmt.where(AiQuestionDraft.requested_by_id == staff.id)
    return [_draft_out(d) for d in db.scalars(stmt)]


@router.get("/questions/ai-drafts/{draft_id}", response_model=AiDraftOut)
def get_draft(draft_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> AiDraftOut:
    draft = db.get(AiQuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return _draft_out(draft)


# ------------------------------------------------------------------ approve


@router.put("/questions/ai-drafts/{draft_id}/approve", response_model=AiDraftOut)
def approve_draft(
    draft_id: uuid.UUID,
    payload: AiDraftApprove,
    staff: CurrentStaff,
    db: DbSession,
) -> AiDraftOut:
    """Approve a draft (with optional edits) and promote it to the live question bank.

    The examiner may edit the payload before approval - the edited version is what gets
    saved as a Question; the original_payload stays intact as the audit trail.
    The draft status is set to APPROVED and linked to the created Question.
    """
    draft = db.get(AiQuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.status is not DraftStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft is already {draft.status.value}",
        )

    exam = _resolve_exam(db, staff, payload.exam_id)
    if (
        exam is not None
        and exam.exam_type is not ExamType.CORPORATE
        and draft.subject_id not in (None, exam.subject_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This draft was generated for a different subject",
        )

    p = payload.payload
    try:
        options_raw = p.get("options", [])
        option_drafts = [
            OptionDraft(o.get("text", ""), o.get("is_correct", False), i)
            for i, o in enumerate(options_raw)
        ]
        spec = validate_question(
            question_type=draft.question_type,
            body=p.get("body", ""),
            marks=p.get("marks", 1.0),
            negative_marks=p.get("negative_marks", 0.0),
            options=option_drafts,
            model_answer=p.get("model_answer"),
            min_words=p.get("min_words"),
            max_words=p.get("max_words"),
            spec=p.get("spec"),
            image_key=p.get("image_key"),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    question = Question(
        subject_id=draft.subject_id,
        question_type=draft.question_type,
        category=draft.category,
        topic=draft.topic,
        difficulty=draft.difficulty,
        body=p.get("body", "").strip(),
        model_answer=p.get("model_answer"),
        explanation=p.get("explanation"),
        spec=spec,
        image_key=p.get("image_key"),
        marks=p.get("marks", 1.0),
        negative_marks=p.get("negative_marks", 0.0),
        tags=p.get("tags"),
        # The examiner approved it, but a model wrote it. Recording that is what lets
        # the bank browser show an "AI generated" shelf honestly a year from now.
        source=QuestionSource.AI_GENERATED,
        origin_exam_id=(exam.id if exam is not None and not payload.save_to_bank else None),
        created_by_id=staff.id,
    )
    for i, opt in enumerate(options_raw):
        question.options.append(
            QuestionOption(
                text=opt.get("text", ""),
                is_correct=opt.get("is_correct", False),
                order_index=i,
            )
        )

    if exam is not None and question.subject_id is None:
        # A draft generated without a subject still has to belong to one to enter a
        # pool; the exam's own subject is the only defensible answer.
        question.subject_id = exam.subject_id

    db.add(question)
    db.flush()

    if exam is not None:
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
        db.flush()

    draft.payload = payload.payload
    draft.status = DraftStatus.APPROVED
    draft.reviewed_by_id = staff.id
    draft.reviewed_at = datetime.now(UTC)
    draft.published_question_id = question.id
    db.flush()
    db.refresh(draft)

    logger.info("%s approved AI draft %s → question %s", staff.email, draft_id, question.id)
    return _draft_out(draft)


def _resolve_exam(db, staff, exam_id: uuid.UUID | None) -> Exam | None:
    """The exam an approved draft is being added to, if any."""
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


@router.post(
    "/questions/ai-drafts/{draft_id}/regenerate",
    response_model=AiDraftOut,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_draft(
    draft_id: uuid.UUID,
    payload: AiRegenerateRequest,
    staff: CurrentStaff,
    db: DbSession,
) -> AiDraftOut:
    """Ask for another attempt at one draft, on the same subject, topic and type.

    The first attempt is rejected rather than overwritten. An examiner who regenerates
    four times should be able to see all four attempts and what they said was wrong
    with each - that record is the difference between reviewing a model and trusting it.
    """
    draft = db.get(AiQuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.status is DraftStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This draft is already a question. Edit the question instead.",
        )

    subject = db.get(Subject, draft.subject_id) if draft.subject_id else None
    instructions = payload.feedback or "Write a different question on the same material."
    generated = generate_questions(
        category=draft.category,
        topic=draft.topic,
        difficulty=payload.difficulty or draft.difficulty,
        question_type=draft.question_type,
        count=1,
        extra_instructions=instructions,
        subject_name=subject.name if subject else None,
    )
    item = generated[0] if generated else {"payload": {}, "provider": "stub"}

    replacement = AiQuestionDraft(
        subject_id=draft.subject_id,
        category=draft.category,
        topic=draft.topic,
        difficulty=payload.difficulty or draft.difficulty,
        question_type=draft.question_type,
        payload=item.get("payload", {}),
        original_payload=item.get("payload", {}),
        provider=item.get("provider", "stub"),
        model=item.get("model"),
        error=item.get("error"),
        status=DraftStatus.PENDING,
        requested_by_id=staff.id,
    )
    db.add(replacement)

    if draft.status is DraftStatus.PENDING:
        draft.status = DraftStatus.REJECTED
        draft.reject_reason = payload.feedback or "Regenerated"
        draft.reviewed_by_id = staff.id
        draft.reviewed_at = datetime.now(UTC)

    db.flush()
    db.refresh(replacement)
    logger.info("%s regenerated AI draft %s", staff.email, draft_id)
    return _draft_out(replacement)


# ------------------------------------------------------------------- reject


@router.put("/questions/ai-drafts/{draft_id}/reject", response_model=AiDraftOut)
def reject_draft(
    draft_id: uuid.UUID,
    payload: AiDraftReject,
    staff: CurrentStaff,
    db: DbSession,
) -> AiDraftOut:
    draft = db.get(AiQuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.status is not DraftStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft is already {draft.status.value}",
        )

    draft.status = DraftStatus.REJECTED
    draft.reject_reason = payload.reason
    draft.reviewed_by_id = staff.id
    draft.reviewed_at = datetime.now(UTC)
    db.flush()
    db.refresh(draft)

    logger.info("%s rejected AI draft %s: %s", staff.email, draft_id, payload.reason)
    return _draft_out(draft)
