"""Exam section management: create, reorder, update and delete sections."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentStaff, DbSession
from app.core.logging_config import get_logger
from app.db.models import Exam, ExamSection, ExamSession, ExamStatus
from app.schemas.common import Message
from app.schemas.exam import SectionCreate, SectionOut, SectionUpdate

router = APIRouter(prefix="/exams", tags=["exam-sections"])
logger = get_logger("sections")


def _load_exam(db, exam_id: uuid.UUID) -> Exam:
    exam = db.scalar(
        select(Exam)
        .where(Exam.id == exam_id)
        .options(selectinload(Exam.sections))
    )
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


def _section_out(section: ExamSection) -> SectionOut:
    return SectionOut(
        id=section.id,
        exam_id=section.exam_id,
        name=section.name,
        description=section.description,
        order_index=section.order_index,
        selection_rules=section.selection_rules,
        marks_per_question=section.marks_per_question,
        negative_marks=section.negative_marks,
        duration_minutes=section.duration_minutes,
        created_at=section.created_at,
    )


@router.get("/{exam_id}/sections", response_model=list[SectionOut])
def list_sections(exam_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> list[SectionOut]:
    exam = _load_exam(db, exam_id)
    return [_section_out(s) for s in sorted(exam.sections, key=lambda s: s.order_index)]


@router.post(
    "/{exam_id}/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED
)
def add_section(
    exam_id: uuid.UUID, payload: SectionCreate, staff: CurrentStaff, db: DbSession
) -> SectionOut:
    exam = _load_exam(db, exam_id)
    if exam.status is ExamStatus.PUBLISHED and db.scalar(
        select(ExamSession).where(ExamSession.exam_id == exam_id).limit(1)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidates have already started this exam",
        )

    section = ExamSection(
        exam_id=exam_id,
        name=payload.name,
        description=payload.description,
        order_index=payload.order_index,
        selection_rules=payload.selection_rules.model_dump(mode="json"),
        marks_per_question=payload.marks_per_question,
        negative_marks=payload.negative_marks,
        duration_minutes=payload.duration_minutes,
    )
    db.add(section)
    db.flush()
    db.refresh(section)
    logger.info("%s added section %r to exam %s", staff.email, section.name, exam_id)
    return _section_out(section)


@router.patch("/{exam_id}/sections/{section_id}", response_model=SectionOut)
def update_section(
    exam_id: uuid.UUID,
    section_id: uuid.UUID,
    payload: SectionUpdate,
    staff: CurrentStaff,
    db: DbSession,
) -> SectionOut:
    section = db.scalar(
        select(ExamSection).where(
            ExamSection.id == section_id, ExamSection.exam_id == exam_id
        )
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field == "selection_rules" and value is not None:
            section.selection_rules = (
                value if isinstance(value, dict) else value.model_dump(mode="json")
            )
        else:
            setattr(section, field, value)

    db.flush()
    db.refresh(section)
    logger.info("%s updated section %s on exam %s", staff.email, section_id, exam_id)
    return _section_out(section)


@router.delete("/{exam_id}/sections/{section_id}", response_model=Message)
def delete_section(
    exam_id: uuid.UUID,
    section_id: uuid.UUID,
    staff: CurrentStaff,
    db: DbSession,
) -> Message:
    section = db.scalar(
        select(ExamSection).where(
            ExamSection.id == section_id, ExamSection.exam_id == exam_id
        )
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    name = section.name
    db.delete(section)
    db.flush()
    logger.info("%s deleted section %r from exam %s", staff.email, name, exam_id)
    return Message(detail=f"Deleted section {name!r}")
