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
from app.services.suspicion import (
    FOCUS_VIOLATION_TYPES,
    SuspicionOutcome,
    event_weight,
    score_events,
    severity_for,
)

logger = get_logger("proctor")


def recompute(db: Session, session: ExamSession) -> SuspicionOutcome:
    """Rescore the session from every persisted event.

    The counts on the session row are a cache of what the events say, refreshed here on
    every flush. That is what makes a tampered client harmless: it can withhold events
    (which the snapshot trail exposes) but it cannot talk the server out of the ones it
    has already delivered.
    """
    events = list(db.scalars(select(ProctorEvent).where(ProctorEvent.session_id == session.id)))
    outcome = score_events(events, session.exam.proctor_config)

    session.suspicion_score = outcome.score
    session.tab_switch_count = outcome.tab_switch_count
    session.focus_violation_count = outcome.focus_violation_count
    if outcome.should_flag and not session.is_flagged:
        session.is_flagged = True
        logger.warning(
            "Session %s flagged: score=%.1f tab_switches=%d left_exam=%d",
            session.id,
            outcome.score,
            outcome.tab_switch_count,
            outcome.focus_violation_count,
        )
    db.flush()
    return outcome


def ingest_batch(
    db: Session, *, session: ExamSession, events: Sequence[ProctorEventIn]
) -> ProctorBatchOut:
    """Persist one flush of the client buffer, rescore, and decide warn/terminate.

    Events from a closed session are still recorded - they are evidence - but they no
    longer change the candidate's fate.
    """
    received = exam_engine.now()
    config = session.exam.proctor_config

    # Any flush - including an empty one - proves the candidate's channel is alive, so it
    # counts as a heartbeat exactly like the dedicated endpoint. Without this, a candidate
    # who never calls /heartbeat (the WebSocket transport pushes every ~10s on its own)
    # would look stale to anything that reads last_heartbeat_at.
    session.last_heartbeat_at = received

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
                confidence=item.confidence,
                question_id=item.question_id,
                event_metadata=item.metadata,
            )
        )
    db.flush()

    outcome = recompute(db, session)
    warnings = _warnings(events, config, outcome)

    terminated = False
    auto_submitted = False

    if session.status is SessionStatus.IN_PROGRESS:
        if outcome.should_auto_submit:
            # Submitted, not terminated - and the distinction is the whole point. The
            # paper is scored, queued for review and published through the ordinary
            # workflow, exactly as if the candidate had pressed submit themselves.
            # Leaving the window repeatedly is a fact worth recording and worth stopping
            # the sitting over; it is not a finding of malpractice, and a genuine
            # candidate must not lose their marks because their laptop misbehaved.
            # The examiner sees the flag and rules on it afterwards.
            reason = (
                f"Automatically submitted: the candidate left the exam window "
                f"{outcome.focus_violation_count} times "
                f"(limit {int(config.get('max_focus_violations', 3))})"
            )
            exam_engine.finalize_session(
                db, session, status=SessionStatus.AUTO_SUBMITTED, reason=reason
            )
            auto_submitted = True
            warnings.append(
                "You left the exam too many times. Your answers have been submitted "
                "and the exam is now closed."
            )
            logger.warning(
                "Session %s AUTO-SUBMITTED after %d focus violation(s)",
                session.id,
                outcome.focus_violation_count,
            )
        elif outcome.should_terminate:
            exam_engine.finalize_session(
                db,
                session,
                status=SessionStatus.TERMINATED,
                reason=f"Automatically terminated: suspicion score {outcome.score:.1f}",
            )
            terminated = True
            warnings.append("Your session has been terminated by the proctoring system.")
            logger.warning("Session %s TERMINATED at score %.1f", session.id, outcome.score)

    return ProctorBatchOut(
        accepted=len(events),
        suspicion_score=outcome.score,
        tab_switch_count=session.tab_switch_count,
        focus_violation_count=session.focus_violation_count,
        focus_violations_left=outcome.focus_violations_left,
        is_flagged=session.is_flagged,
        terminated=terminated,
        auto_submitted=auto_submitted,
        warnings=warnings,
    )


def _warnings(
    events: Sequence[ProctorEventIn], config: dict, outcome: SuspicionOutcome
) -> list[str]:
    """What the candidate is told, worded so the next consequence is never a surprise.

    The escalation is deliberate and stated up front: a warning, a final warning, then
    the paper is submitted. A candidate who is about to lose their sitting deserves to
    know it on the step before, not afterwards.
    """
    warnings: list[str] = []
    types = {e.event_type for e in events}
    left_the_exam = bool(types & FOCUS_VIOLATION_TYPES)

    max_focus = int(config.get("max_focus_violations", 3))
    ladder_on = max_focus > 0
    if ladder_on and left_the_exam and not outcome.should_auto_submit:
        remaining = outcome.focus_violations_left
        if remaining == 1:
            warnings.append(
                "Final warning: leaving the exam again will submit your answers "
                "and close the exam."
            )
        else:
            warnings.append(
                f"Warning {outcome.focus_violation_count} of {max_focus}: leaving the "
                f"exam window is recorded. {remaining} more will submit your answers "
                f"and close the exam."
            )
    elif not ladder_on and ProctorEventType.TAB_SWITCH in types:
        # The ladder is off, so the honest thing to say is that it was noted. Guarded on
        # ladder_on: without it, this fired on the *final* violation too - telling a
        # candidate their tab switch "has been recorded" in the same breath as closing
        # their exam, which reads as though nothing much had happened.
        warnings.append("Leaving the exam tab has been recorded for the examiner.")

    if ProctorEventType.MULTIPLE_FACES in types:
        warnings.append("More than one person was detected in the camera frame.")
    if ProctorEventType.FACE_MISSING in types:
        warnings.append("Your face was not visible. Stay in frame.")
    if ProctorEventType.CAMERA_BLOCKED in types:
        warnings.append("Your camera appears blocked or disabled.")
    if ProctorEventType.ADDITIONAL_PERSON in types:
        warnings.append("Another person appears to be in view of the camera.")
    if ProctorEventType.MIC_DISCONNECTED in types:
        warnings.append("Your microphone appears disconnected.")
    if ProctorEventType.NETWORK_LOST in types:
        warnings.append("Your internet connection dropped. Reconnect to continue.")

    return warnings
