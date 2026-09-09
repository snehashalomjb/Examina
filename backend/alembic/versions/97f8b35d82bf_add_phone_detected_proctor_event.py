"""add_phone_detected_proctor_event

Revision ID: 97f8b35d82bf
Revises: a7d787ede8d4
Create Date: 2026-09-09 12:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = '97f8b35d82bf'
down_revision: str | None = 'a7d787ede8d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE proctor_event_type ADD VALUE IF NOT EXISTS 'phone_detected'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value without rebuilding the type and every
    # column/index that uses it - not worth it for a value that, once seen, is
    # harmless to leave defined. Left as a no-op, same as the rest of this project's
    # enum-growing migrations would need to be.
    pass
