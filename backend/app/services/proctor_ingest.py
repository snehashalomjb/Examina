"""Server-side proctoring intake, shared by the HTTP and WebSocket transports.

The candidate's browser can deliver its event buffer over either transport - a socket
while the network cooperates, plain POSTs when it does not - and both land here. Keeping
the decision logic in one place is what makes the fallback safe: whichever way an event
arrives, it is weighted, persisted and rescored identically.

The score is always recomputed from the *stored* events. A client-supplied score is never
believed, because the client is the thing being invigilated.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import ExamSession, ProctorEvent, ProctorEventType, SessionStatus
from app.schemas.proctor import ProctorBatchOut, ProctorEventIn
from app.services import exam_engine
from app.services.suspicion import event_weight, score_events, severity_for

logger = get_logger("proctor")


def recompute(db: Session, session: ExamSession) -> tuple[float, bool, bool]:
    """Rescore the session from every persisted event. Returns (score, flagged, terminate)."""
    events = list(db.scalars(select(ProctorEvent).where(ProctorEvent.session_id == session.id)))
    outcome = score_events(events, session.exam.proctor_config)

    session.suspicion_score = outcome.score
    session.tab_switch_count = outcome.tab_switch_count
    if outcome.should_flag and not session.is_flagged:
        session.is_flagged = True
        logger.warning(
            "Session %s flagged: score=%.1f tab_switches=%d",
            session.id,
            outcome.score,
            outcome.tab_switch_count,
        )
    db.flush()
    return outcome.score, session.is_flagged, outcome.should_terminate


def ingest_batch(
    db: Session, *, session: ExamSession, events: Sequence[ProctorEventIn]
) -> ProctorBatchOut:
    """Persist one flush of the client buffer, rescore, and decide warn/terminate.

    Events from a closed session are still recorded - they are evidence - but they no
    longer change the candidate's fate.
    """
    received = exam_engine.now()
    config = session.exam.proctor_config

    for item in events:
        occurred = item.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=UTC)
        # A client clock ahead of the server would corrupt the timeline ordering.
        occurred = min(occurred, received)

        db.add(
            ProctorEvent(
                session_id=session.id,
                event_type=item.event_type,
                severity=item.severity or severity_for(item.event_type),
                occurred_at=occurred,
                server_received_at=received,
                duration_ms=item.duration_ms,
                weight=event_weight(item.event_type, config),
                event_metadata=item.metadata,
            )
        )
    db.flush()

    score, flagged, should_terminate = recompute(db, session)
    warnings = _warnings(session, events, config)

    terminated = False
    if should_terminate and session.status is SessionStatus.IN_PROGRESS:
        exam_engine.finalize_session(
            db,
            session,
            status=SessionStatus.TERMINATED,
            reason=f"Automatically terminated: suspicion score {score:.1f}",
        )
        terminated = True
        warnings.append("Your session has been terminated by the proctoring system.")
        logger.warning("Session %s TERMINATED at score %.1f", session.id, score)

    return ProctorBatchOut(
        accepted=len(events),
        suspicion_score=score,
        tab_switch_count=session.tab_switch_count,
        is_flagged=flagged,
        terminated=terminated,
        warnings=warnings,
    )


def _warnings(
    session: ExamSession, events: Sequence[ProctorEventIn], config: dict
) -> list[str]:
    warnings: list[str] = []
    types = {e.event_type for e in events}

    max_tabs = int(config.get("max_tab_switches", 3))
    if session.tab_switch_count > max_tabs:
        warnings.append(
            f"You have left the exam tab {session.tab_switch_count} times. The limit is {max_tabs}."
        )
    elif ProctorEventType.TAB_SWITCH in types:
        warnings.append(
            f"Leaving the exam tab is recorded. "
            f"{max_tabs - session.tab_switch_count} warning(s) remaining."
        )

    if ProctorEventType.MULTIPLE_FACES in types:
        warnings.append("More than one person was detected in the camera frame.")
    if ProctorEventType.FACE_MISSING in types:
        warnings.append("Your face was not visible. Stay in frame.")
    if ProctorEventType.CAMERA_BLOCKED in types:
        warnings.append("Your camera appears blocked or disabled.")

    return warnings
