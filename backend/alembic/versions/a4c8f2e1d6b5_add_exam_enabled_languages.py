"""add_exam_enabled_languages

Revision ID: a4c8f2e1d6b5
Revises: f3b2d6a0c4e8
Create Date: 2026-09-22 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a4c8f2e1d6b5'
down_revision: str | None = 'f3b2d6a0c4e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'exams',
        sa.Column(
            'enabled_languages',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='["en"]',
        ),
    )


def downgrade() -> None:
    op.drop_column('exams', 'enabled_languages')
