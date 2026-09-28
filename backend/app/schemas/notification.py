"""Dashboard bell notifications."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    session_id: uuid.UUID | None
    result_id: uuid.UUID | None
    is_read: bool
    created_at: datetime
