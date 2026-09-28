"""Submission notifications for the dashboard bell.

Two halves, same split as :mod:`app.services.live_signal`: this module owns the
durable side (writing ``Notification`` rows, one per recipient) and an in-memory
registry of currently-connected staff sockets so a fresh row can be pushed live the
moment it is created. Single-process, same scale assumption as the live-signal relay -
a socket that misses a push still sees the row on next page load or reconnect, so
nothing is lost, only delayed.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import ExamSession, Notification, User, UserRole

logger = get_logger("notifications")

NOTIFICATION_SUBMISSION = "exam_submission"


def _recipients(db: Session, session: ExamSession) -> list[User]:
    """The owning examiner (if the exam still has one) plus every admin.

    Mirrors the visibility rule ``exam_engine.assert_exam_owned`` already enforces for
    reading results: an examiner only ever sees their own exams, an admin sees all.
    """
    recipients: dict[uuid.UUID, User] = {}
    exam = session.exam
    if exam.created_by_id is not None and exam.created_by is not None:
        recipients[exam.created_by.id] = exam.created_by
    for admin in db.scalars(select(User).where(User.role == UserRole.ADMIN)):
        recipients[admin.id] = admin
    return list(recipients.values())


def notify_submission(db: Session, session: ExamSession) -> list[dict[str, Any]]:
    """Create one notification per relevant examiner/admin, returning plain payloads.

    Called right after ``exam_engine.finalize_session`` inside the submit endpoint, so
    ``session.result`` already exists - every exam gets a ``Result`` row synchronously at
    submit time, whether or not scoring is complete. Safe to call more than once for the
    same session: the per-recipient unique constraint on (recipient_id, session_id, type)
    turns a duplicate call into a no-op instead of a second bell entry.

    Returns plain dicts, not the ORM rows: the caller schedules the live push as a
    ``BackgroundTasks`` job, which runs after the request's session has committed and
    closed (``expire_on_commit`` is on), so touching an attribute on the row itself at
    that point would raise ``DetachedInstanceError``.
    """
    exam = session.exam
    candidate = session.candidate
    result = session.result
    if result is None:
        # finalize_session always creates one; a missing result means submit() was not
        # called in the order this function expects, so there is nothing to link to yet.
        logger.warning("notify_submission called before a result exists for session %s", session.id)
        return []

    title = f"{candidate.full_name} has completed the exam"
    body = f"Subject: {exam.subject.name}\nExam: {exam.title}"

    created: list[dict[str, Any]] = []
    for recipient in _recipients(db, session):
        notification = Notification(
            recipient_id=recipient.id,
            type=NOTIFICATION_SUBMISSION,
            title=title,
            body=body,
            session_id=session.id,
            result_id=result.id,
        )
        try:
            # A SAVEPOINT, not a full rollback: the outer request transaction already
            # holds finalize_session's uncommitted changes (session status, answers,
            # result), and get_db only commits once at the end of the request. Rolling
            # back the whole session here to swallow one duplicate insert would silently
            # discard that work too.
            with db.begin_nested():
                db.add(notification)
                db.flush()
        except IntegrityError:
            # Already notified this recipient for this session - the unique constraint
            # caught it, not a race we need to log about.
            continue
        created.append(
            {
                "id": str(notification.id),
                "recipient_id": notification.recipient_id,
                "type": notification.type,
                "title": notification.title,
                "body": notification.body,
                "session_id": str(notification.session_id),
                "result_id": str(notification.result_id),
                "is_read": False,
                "created_at": notification.created_at.isoformat(),
            }
        )

    return created


# --------------------------------------------------------------------------
# Live push: in-memory per-user socket registry
# --------------------------------------------------------------------------


@dataclass
class _Peer:
    websocket: WebSocket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, message: dict[str, Any]) -> None:
        async with self.lock:
            try:
                await self.websocket.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket is the disconnect handler's job
                pass


_sockets: dict[uuid.UUID, dict[str, _Peer]] = {}
_guard = asyncio.Lock()


async def register_socket(user_id: uuid.UUID, websocket: WebSocket) -> str:
    connection_id = uuid.uuid4().hex
    async with _guard:
        _sockets.setdefault(user_id, {})[connection_id] = _Peer(websocket)
    return connection_id


async def unregister_socket(user_id: uuid.UUID, connection_id: str) -> None:
    async with _guard:
        peers = _sockets.get(user_id)
        if peers is None:
            return
        peers.pop(connection_id, None)
        if not peers:
            _sockets.pop(user_id, None)


async def push_to_recipients(notifications: list[dict[str, Any]]) -> None:
    """Send each freshly-created row (as a plain dict from ``notify_submission``) to its
    recipient's open sockets, if any."""
    for notification in notifications:
        recipient_id = notification["recipient_id"]
        peers = list(_sockets.get(recipient_id, {}).values())
        if not peers:
            continue
        payload = {
            "type": "notification",
            "notification": {k: v for k, v in notification.items() if k != "recipient_id"},
        }
        for peer in peers:
            await peer.send(payload)
