"""add_user_preferred_locale

Revision ID: f3b2d6a0c4e8
Revises: e2a1c5f9b3d7
Create Date: 2026-09-20 00:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f3b2d6a0c4e8'
down_revision: str | None = 'e2a1c5f9b3d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('preferred_locale', sa.String(length=5), nullable=False, server_default='en'),
    )
    op.create_check_constraint(
        'ck_users_locale_supported',
        'users',
        "preferred_locale IN ('en', 'te', 'hi', 'ta', 'ml', 'kn')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_locale_supported', 'users', type_='check')
    op.drop_column('users', 'preferred_locale')
