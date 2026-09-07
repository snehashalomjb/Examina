"""Derivatives for an uploaded handwritten answer: thumbnail and OCR pre-pass.

Both run *after* the candidate's upload has been acknowledged. Neither is allowed to cost
a candidate their answer: a thumbnail is a convenience for the examiner queue and OCR is
advisory text beside an image a human is going to read anyway, so a failure in either is
logged and stored, never raised at the candidate.
"""

from __future__ import annotations

import uuid

from app.core.images import ImageError, make_thumbnail
from app.core.logging_config import get_logger
from app.core.storage import build_key, get_object_bytes, put_object
from app.db.models import Answer
from app.db.session import SessionLocal
from app.services import ocr

logger = get_logger("answer_media")


def build_thumbnail(*, session_id: uuid.UUID, data: bytes) -> str | None:
    """Generate and store a thumbnail. Returns its object key, or None if it could not be
    made - the original is already stored, so a missing thumbnail costs only convenience.
    """
    try:
        thumb = make_thumbnail(data)
    except ImageError as exc:
        logger.warning("Could not thumbnail an answer image: %s", exc)
        return None

    key = build_key(prefix="answers/thumbs", session_id=session_id, extension="jpg")
    try:
        return put_object(key=key, data=thumb, content_type="image/jpeg")
    except Exception as exc:  # noqa: BLE001 - storage hiccup, not the candidate's problem
        logger.warning("Could not store thumbnail %s: %s", key, exc)
        return None


def run_ocr(answer_id: uuid.UUID, data: bytes | None = None) -> None:
    """Background task: OCR one answer image and write the text back to the row.

    Opens its own session - the request that scheduled it has long since committed and
    closed. ``data`` is passed through from the upload so the common path never round-
    trips to object storage; a re-run without it fetches the stored original.
    """
    db = SessionLocal()
    try:
        answer = db.get(Answer, answer_id)
        if answer is None or not answer.image_object_key:
            return

        payload = data if data is not None else get_object_bytes(answer.image_object_key)
        if payload is None:
            logger.warning("OCR skipped for answer %s: image unreadable", answer_id)
            return

        try:
            result = ocr.extract_text(payload)
        except (RuntimeError, ImageError) as exc:
            # A missing Tesseract binary is a deployment problem to fix, not a reason to
            # fail a script. Record the miss so the examiner sees why the panel is empty.
            logger.error("OCR failed for answer %s: %s", answer_id, exc)
            answer.ocr_text = None
            answer.ocr_confidence = None
            db.commit()
            return

        answer.ocr_text = result.text or None
        answer.ocr_confidence = result.confidence
        db.commit()
        logger.info(
            "OCR read %d chars from answer %s at confidence %.2f",
            len(result.text),
            answer_id,
            result.confidence,
        )
    except Exception:  # noqa: BLE001 - a background task must never escape
        db.rollback()
        logger.exception("OCR task crashed for answer %s", answer_id)
    finally:
        db.close()
