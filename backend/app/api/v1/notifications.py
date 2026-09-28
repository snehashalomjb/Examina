"""Dashboard bell: list/read notifications, and the live push socket for them.

REST covers what a page load needs (the list, an unread count, marking one read); the
websocket is purely additive - a connected bell gets pushed a fresh row the moment
:func:`app.services.notifications.notify_submission` creates it, but a bell that never
connects (or missed a push) sees the same row on its next ``GET``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.deps import CurrentStaff, DbSession, WebSocketAuthError, authenticate_staff_ws
from app.db.models import Notification
from app.db.session import get_db
from app.schemas.notification import NotificationOut
from app.services import notifications as notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

WS_SUBPROTOCOL = "exam-notifications.v1"


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: CurrentStaff,
    db: DbSession,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(min(limit, 200))
    return list(db.scalars(stmt))


@router.get("/unread-count")
def unread_count(user: CurrentStaff, db: DbSession) -> dict[str, int]:
    stmt = select(Notification).where(
        Notification.recipient_id == user.id, Notification.is_read.is_(False)
    )
    return {"count": len(list(db.scalars(stmt)))}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, user: CurrentStaff, db: DbSession) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.recipient_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
    return notification


@router.websocket("/ws")
async def notifications_socket(websocket: WebSocket) -> None:
    """Push channel for the currently signed-in examiner/admin's own notifications."""
    offered = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(offered) < 2 or offered[0] != WS_SUBPROTOCOL:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")
        return

    db = next(get_db())
    try:
        staff = authenticate_staff_ws(db, access_token=offered[1])
    except WebSocketAuthError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.reason)
        return
    finally:
        db.close()

    await websocket.accept(subprotocol=WS_SUBPROTOCOL)
    connection_id = await notification_service.register_socket(staff.id, websocket)

    try:
        while True:
            # This socket only ever pushes; nothing meaningful arrives from the client,
            # but the receive keeps the connection alive and detects a client-side close.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - a push-socket fault must not take the worker down
        pass
    finally:
        await notification_service.unregister_socket(staff.id, connection_id)
