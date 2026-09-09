"""add_ai_evaluation_key_points

Revision ID: b1c2d3e4f5a6
Revises: 97f8b35d82bf
Create Date: 2026-09-09 13:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b1c2d3e4f5a6'
down_revision: str | None = '97f8b35d82bf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_evaluations",
        sa.Column(
            "key_points_matched",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "ai_evaluations",
        sa.Column(
            "key_points_missed",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_evaluations", "key_points_missed")
    op.drop_column("ai_evaluations", "key_points_matched")
