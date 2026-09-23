"""In-memory WebRTC signaling relay for live candidate monitoring.

This module never looks inside a message: it only forwards SDP offers/answers and ICE
candidates between a candidate's exam tab and any number of staff browsers watching that
same session, so the two sides can negotiate a direct (or STUN-assisted) peer-to-peer
video connection. All camera capture, encoding and NAT traversal is the browsers' own
WebRTC stack; the server's only job is the handshake postbox neither side can reach the
other without.

Deliberately a mesh, not an SFU: the candidate's browser opens one ``RTCPeerConnection``
per examiner watching, same as any small WebRTC call. That is the right trade-off for a
handful of invigilators watching a handful of candidates each - it stops being one the
moment an exam needs dozens of staff on one candidate at once, which this deployment does
not.

Single-process, in-memory registry - the same scale assumption every other "live" panel in
this app already makes (the analytics live-dashboard is a 15s poll, not a pub/sub fan-out).
Restarting the API process drops every open signaling channel; a reconnecting client just
re-joins and renegotiates, which is why the frontend always treats a closed socket as
"reconnect", never as a fatal error.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.core.logging_config import get_logger

logger = get_logger("live_signal")


@dataclass
class _Peer:
    """One open socket, plus a lock so two concurrent relays never interleave frames."""

    websocket: WebSocket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, message: dict[str, Any]) -> None:
        async with self.lock:
            try:
                await self.websocket.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket is the disconnect handler's job
                pass


@dataclass
class _Channel:
    """Everyone currently signaling about one exam session."""

    candidate: _Peer | None = None
    viewers: dict[str, _Peer] = field(default_factory=dict)


_channels: dict[uuid.UUID, _Channel] = {}
_guard = asyncio.Lock()


async def register_candidate(session_id: uuid.UUID, websocket: WebSocket) -> _Channel:
    """The candidate's broadcast socket just opened.

    Every viewer already waiting is told a stream now exists, and the candidate is told
    about every viewer already waiting, so a candidate who reconnects mid-exam re-offers
    to an examiner who opened the console first.
    """
    async with _guard:
        channel = _channels.setdefault(session_id, _Channel())
        channel.candidate = _Peer(websocket)
        waiting_viewer_ids = list(channel.viewers.keys())
        candidate = channel.candidate

    for viewer_id in waiting_viewer_ids:
        peer = channel.viewers.get(viewer_id)
        if peer is not None:
            await peer.send({"type": "candidate-online"})
    for viewer_id in waiting_viewer_ids:
        await candidate.send({"type": "viewer-join", "viewer_id": viewer_id})
    return channel


async def unregister_candidate(session_id: uuid.UUID) -> None:
    async with _guard:
        channel = _channels.get(session_id)
        if channel is None:
            return
        channel.candidate = None
        viewers = list(channel.viewers.values())
        if not channel.viewers:
            _channels.pop(session_id, None)

    for peer in viewers:
        await peer.send({"type": "candidate-offline"})


async def register_viewer(session_id: uuid.UUID, websocket: WebSocket) -> tuple[str, _Channel]:
    """A staff socket just opened to watch this session. Returns its viewer id."""
    viewer_id = uuid.uuid4().hex
    async with _guard:
        channel = _channels.setdefault(session_id, _Channel())
        channel.viewers[viewer_id] = _Peer(websocket)
        candidate = channel.candidate

    if candidate is not None:
        await candidate.send({"type": "viewer-join", "viewer_id": viewer_id})
    return viewer_id, channel


async def unregister_viewer(session_id: uuid.UUID, viewer_id: str) -> None:
    async with _guard:
        channel = _channels.get(session_id)
        if channel is None:
            return
        channel.viewers.pop(viewer_id, None)
        candidate = channel.candidate
        if candidate is None and not channel.viewers:
            _channels.pop(session_id, None)

    if candidate is not None:
        await candidate.send({"type": "viewer-leave", "viewer_id": viewer_id})


async def relay_from_candidate(session_id: uuid.UUID, message: dict[str, Any]) -> None:
    """An offer or ICE candidate the candidate addressed to one specific viewer."""
    viewer_id = message.get("viewer_id")
    if not isinstance(viewer_id, str):
        return
    channel = _channels.get(session_id)
    if channel is None:
        return
    peer = channel.viewers.get(viewer_id)
    if peer is not None:
        await peer.send(message)


async def relay_from_viewer(session_id: uuid.UUID, viewer_id: str, message: dict[str, Any]) -> None:
    """An answer or ICE candidate from one viewer, always addressed to the candidate."""
    channel = _channels.get(session_id)
    if channel is None or channel.candidate is None:
        return
    await channel.candidate.send({**message, "viewer_id": viewer_id})


def is_candidate_online(session_id: uuid.UUID) -> bool:
    channel = _channels.get(session_id)
    return channel is not None and channel.candidate is not None
