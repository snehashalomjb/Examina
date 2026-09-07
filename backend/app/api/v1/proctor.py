"""Proctoring: batched event intake from the candidate, review panel for staff.

Vision inference happens in the candidate's browser (MediaPipe). This module is the
server-side half: it persists the evidence, recomputes the suspicion score from the
*stored* events rather than trusting a client-supplied score, and decides when to warn or
terminate. Snapshots are the audit trail that makes client tampering visible after the fact.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import (
    ActiveExamSession,
    CurrentStaff,
    DbSession,
    WebSocketAuthError,
    authenticate_ws,
)
from app.core.logging_config import get_logger
from app.core.storage import build_key, presigned_url, put_object
from app.db.models import (
    Answer,
    ExamSession,
    ProctorEvent,
    ProctorEventType,
    SessionStatus,
)
from app.db.session import get_db
from app.schemas.proctor import (
    ProctorBatchIn,
    ProctorBatchOut,
    ProctorEventOut,
    ProctorReview,
    SnapshotOut,
)
from app.services import exam_engine, proctor_ingest
from app.services.suspicion import event_weight, score_events, severity_for

router = APIRouter(tags=["proctoring"])
logger = get_logger("proctor")

MAX_SNAPSHOT_BYTES = 3 * 1024 * 1024


def _recompute(db, session: ExamSession) -> tuple[float, bool, bool]:
    """Thin alias kept so this module reads on its own; the logic is shared with the
    WebSocket transport in :mod:`app.services.proctor_ingest`."""
    return proctor_ingest.recompute(db, session)


@router.post("/sessions/{session_id}/proctor/events", response_model=ProctorBatchOut)
def ingest_events(
    session_id: uuid.UUID,
    payload: ProctorBatchIn,
    session: ActiveExamSession,
    db: DbSession,
) -> ProctorBatchOut:
    """Receive one flush of the client-side event buffer (~10 s of activity).

    The fallback transport. The runner prefers the WebSocket below and drops back to this
    when a socket cannot be held open - and always uses it for the unload flush, where a
    half-open socket would lose the final events.
    """
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    return proctor_ingest.ingest_batch(db, session=session, events=payload.events)


# --------------------------------------------------------------- live socket
#: Subprotocol the client must offer first. The remaining two entries it offers are the
#: access token and the exam token; the server echoes only this name back.
WS_SUBPROTOCOL = "exam-proctor.v1"

#: A single frame is one client flush. Anything larger is a client fault, not a long exam.
WS_MAX_FRAME_BYTES = 256 * 1024


@router.websocket("/ws/sessions/{session_id}/proctor")
async def proctor_socket(
    websocket: WebSocket, session_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """Live proctoring channel: the client pushes its buffer every ~10 s, we push back
    the authoritative score, warnings and any termination.

    Preferred over ``POST /proctor/events`` because the verdict reaches the candidate on
    the server's schedule rather than the client's next poll - a termination lands inside
    a heartbeat instead of up to a flush later. The POST route stays live as the fallback
    for proxies that will not carry a socket, and for the unload flush.

    Auth rides in ``Sec-WebSocket-Protocol``: ``[WS_SUBPROTOCOL, access_token, exam_token]``.
    The browser WebSocket API cannot set an ``Authorization`` header, and putting a token
    in the query string would print it into every access log.
    """
    offered = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(offered) < 3 or offered[0] != WS_SUBPROTOCOL:
        # 1008 = policy violation. Close before accepting: nothing is authenticated yet.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")
        return

    try:
        try:
            session = authenticate_ws(db, access_token=offered[1], exam_token=offered[2])
        except WebSocketAuthError as exc:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.reason)
            return

        if session.id != session_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Exam token does not match"
            )
            return

        await websocket.accept(subprotocol=WS_SUBPROTOCOL)
        logger.info("Proctor socket open for session %s", session.id)

        while True:
            raw = await websocket.receive_text()
            if len(raw) > WS_MAX_FRAME_BYTES:
                await websocket.close(
                    code=status.WS_1009_MESSAGE_TOO_BIG, reason="Event batch too large"
                )
                return

            try:
                payload = ProctorBatchIn.model_validate_json(raw)
            except PydanticValidationError as exc:
                # A malformed frame is a client bug, not grounds to drop the candidate's
                # channel - tell it and keep the socket open.
                await websocket.send_json({"error": "invalid_batch", "detail": exc.errors()[:3]})
                continue

            # Each batch is its own transaction: a crash mid-exam must not lose the
            # evidence already accepted.
            outcome = proctor_ingest.ingest_batch(db, session=session, events=payload.events)
            db.commit()
            db.refresh(session)

            await websocket.send_json(outcome.model_dump(mode="json"))
            if outcome.terminated:
                await websocket.close(
                    code=status.WS_1000_NORMAL_CLOSURE, reason="Session terminated"
                )
                return

    except WebSocketDisconnect:
        logger.info("Proctor socket closed for session %s", session_id)
    except Exception:  # noqa: BLE001 - a socket fault must not take the worker down
        db.rollback()
        logger.exception("Proctor socket failed for session %s", session_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass  # already closed


@router.post("/sessions/{session_id}/proctor/snapshot", response_model=SnapshotOut)
def upload_snapshot(
    session_id: uuid.UUID,
    session: ActiveExamSession,
    db: DbSession,
    file: UploadFile = File(...),
    event_type: ProctorEventType | None = Form(default=None),
    occurred_at: datetime | None = Form(default=None),
) -> SnapshotOut:
    """Store a webcam frame, optionally attached to a new event."""
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Exam token does not match this session"
        )
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Snapshots must be JPEG, PNG or WebP",
        )

    data = file.file.read()
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Snapshot too large"
        )

    key = build_key(prefix="snapshots", session_id=session.id, extension="jpg")
    put_object(key=key, data=data, content_type=file.content_type)

    event_id = None
    if event_type is not None:
        received = exam_engine.now()
        occurred = occurred_at or received
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=UTC)
        event = ProctorEvent(
            session_id=session.id,
            event_type=event_type,
            severity=severity_for(event_type),
            occurred_at=min(occurred, received),
            server_received_at=received,
            weight=event_weight(event_type, session.exam.proctor_config),
            snapshot_object_key=key,
        )
        db.add(event)
        db.flush()
        event_id = event.id
        _recompute(db, session)

    # A periodic snapshot with no event_type is stored as evidence only: it carries no
    # weight and must not move the suspicion score on its own.
    return SnapshotOut(snapshot_key=key, event_id=event_id)


# ------------------------------------------------------------------ staff review
@router.get("/proctoring/sessions", response_model=list[ProctorReview])
def list_monitored_sessions(
    staff: CurrentStaff,
    db: DbSession,
    exam_id: uuid.UUID | None = None,
    flagged_only: bool = False,
    limit: int = Query(100, ge=1, le=300),
) -> list[ProctorReview]:
    stmt = (
        select(ExamSession)
        .options(selectinload(ExamSession.candidate), selectinload(ExamSession.exam))
        .order_by(ExamSession.suspicion_score.desc(), ExamSession.created_at.desc())
        .limit(limit)
    )
    if exam_id:
        stmt = stmt.where(ExamSession.exam_id == exam_id)
    if flagged_only:
        stmt = stmt.where(ExamSession.is_flagged)

    return [
        ProctorReview(
            session_id=s.id,
            candidate_name=s.candidate.full_name,
            candidate_email=s.candidate.email,
            exam_title=s.exam.title,
            status=s.status.value,
            started_at=s.started_at,
            submitted_at=s.submitted_at,
            suspicion_score=s.suspicion_score,
            tab_switch_count=s.tab_switch_count,
            is_flagged=s.is_flagged,
            termination_reason=s.termination_reason,
            breakdown={},
            events=[],
        )
        for s in db.scalars(stmt)
    ]


@router.get("/proctoring/sessions/{session_id}", response_model=ProctorReview)
def review_session(session_id: uuid.UUID, staff: CurrentStaff, db: DbSession) -> ProctorReview:
    """Full timeline with presigned snapshot URLs - the examiner's review panel."""
    session = db.scalar(
        select(ExamSession)
        .where(ExamSession.id == session_id)
        .options(
            selectinload(ExamSession.candidate),
            selectinload(ExamSession.exam),
            selectinload(ExamSession.proctor_events),
            selectinload(ExamSession.answers).selectinload(Answer.question),
        )
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    outcome = score_events(session.proctor_events, session.exam.proctor_config)
    events = sorted(session.proctor_events, key=lambda e: e.occurred_at)

    return ProctorReview(
        session_id=session.id,
        candidate_name=session.candidate.full_name,
        candidate_email=session.candidate.email,
        exam_title=session.exam.title,
        status=session.status.value,
        started_at=session.started_at,
        submitted_at=session.submitted_at,
        suspicion_score=session.suspicion_score,
        tab_switch_count=session.tab_switch_count,
        is_flagged=session.is_flagged,
        termination_reason=session.termination_reason,
        breakdown=outcome.breakdown,
        events=[
            ProctorEventOut(
                id=e.id,
                event_type=e.event_type,
                severity=e.severity,
                occurred_at=e.occurred_at,
                server_received_at=e.server_received_at,
                duration_ms=e.duration_ms,
                weight=e.weight,
                metadata=e.event_metadata,
                snapshot_url=presigned_url(e.snapshot_object_key),
            )
            for e in events
        ],
    )


@router.post("/proctoring/sessions/{session_id}/terminate", response_model=ProctorReview)
def terminate_session(
    session_id: uuid.UUID, staff: CurrentStaff, db: DbSession, reason: str = Query(...)
) -> ProctorReview:
    """Manual termination by an invigilator watching the review panel."""
    session = exam_engine.load_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status is not SessionStatus.IN_PROGRESS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That session is not live")

    exam_engine.finalize_session(
        db,
        session,
        status=SessionStatus.TERMINATED,
        reason=f"Terminated by {staff.email}: {reason}",
    )
    session.is_flagged = True
    db.flush()
    logger.warning("%s terminated session %s: %s", staff.email, session_id, reason)
    return review_session(session_id, staff, db)
