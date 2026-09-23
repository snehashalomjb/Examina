"""WebRTC signaling: pairs a candidate's exam tab with staff watching it live.

Two sockets, one relay. The candidate's browser broadcasts one offer per connected
viewer; a viewer's browser answers and exchanges ICE candidates back. Neither side's
media ever passes through this server - see :mod:`app.services.live_signal` for the
in-memory registry that only forwards these small JSON messages.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.deps import WebSocketAuthError, authenticate_staff_ws, authenticate_ws
from app.core.logging_config import get_logger
from app.db.session import get_db
from app.services import live_signal

router = APIRouter(tags=["live-signal"])
logger = get_logger("live_signal")

#: Must match the constants of the same name in the frontend broadcaster/viewer.
WS_SUBPROTOCOL = "exam-live-signal.v1"
#: Signaling frames are small JSON control messages, not media - nowhere near this size
#: unless something is wrong.
WS_MAX_FRAME_BYTES = 32 * 1024


@router.websocket("/ws/sessions/{session_id}/live-broadcast")
async def broadcast_socket(
    websocket: WebSocket, session_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """The candidate's side: offers this session's camera to whichever staff are watching.

    Auth mirrors the proctoring socket exactly - ``[subprotocol, access_token,
    exam_token]`` in ``Sec-WebSocket-Protocol`` - because it is gated by the same two
    facts: a signed-in candidate, holding a token for precisely this session.
    """
    offered = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(offered) < 3 or offered[0] != WS_SUBPROTOCOL:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")
        return

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
    await live_signal.register_candidate(session_id, websocket)
    logger.info("Live broadcast socket open for session %s", session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > WS_MAX_FRAME_BYTES:
                continue
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if isinstance(message, dict):
                await live_signal.relay_from_candidate(session_id, message)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - a signaling fault must not take the worker down
        logger.exception("Live broadcast socket failed for session %s", session_id)
    finally:
        await live_signal.unregister_candidate(session_id)
        logger.info("Live broadcast socket closed for session %s", session_id)


@router.websocket("/ws/sessions/{session_id}/live-view")
async def view_socket(
    websocket: WebSocket, session_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """The examiner/admin side: watches one candidate's session, if a stream is offered.

    Any number of staff can open this for the same session at once; each gets its own
    peer connection to the candidate's browser, tagged by the viewer id this socket
    hands back on connect. Access follows the same staff gate every proctoring review
    endpoint uses - any examiner or admin, not only the exam's owner - because that is
    the existing visibility model for ``GET /proctoring/sessions``.
    """
    offered = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    if len(offered) < 2 or offered[0] != WS_SUBPROTOCOL:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")
        return

    try:
        staff = authenticate_staff_ws(db, access_token=offered[1])
    except WebSocketAuthError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.reason)
        return

    await websocket.accept(subprotocol=WS_SUBPROTOCOL)
    viewer_id, channel = await live_signal.register_viewer(session_id, websocket)
    await websocket.send_json(
        {
            "type": "welcome",
            "viewer_id": viewer_id,
            "candidate_online": channel.candidate is not None,
        }
    )
    logger.info("%s watching live session %s (viewer %s)", staff.email, session_id, viewer_id)

    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > WS_MAX_FRAME_BYTES:
                continue
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if isinstance(message, dict):
                await live_signal.relay_from_viewer(session_id, viewer_id, message)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - a signaling fault must not take the worker down
        logger.exception(
            "Live view socket failed for session %s (viewer %s)", session_id, viewer_id
        )
    finally:
        await live_signal.unregister_viewer(session_id, viewer_id)
        logger.info("Viewer %s stopped watching session %s", viewer_id, session_id)
