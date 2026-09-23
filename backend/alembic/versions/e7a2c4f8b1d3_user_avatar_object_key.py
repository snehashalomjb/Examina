"""user_avatar_object_key

Revision ID: e7a2c4f8b1d3
Revises: d3f6a1b7c9e2
Create Date: 2026-09-18 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e7a2c4f8b1d3'
down_revision: str | None = 'd3f6a1b7c9e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('avatar_object_key', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'avatar_object_key')
