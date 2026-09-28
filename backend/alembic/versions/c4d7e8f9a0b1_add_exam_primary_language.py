"""add_exam_primary_language

One code per exam: the language the paper is written and sat in. Backed by a CHECK
constraint rather than left to the application, because this value decides what
locale a candidate's paper is rendered in - a typo here would be a blank paper
rather than a fallback.

Revision ID: c4d7e8f9a0b1
Revises: 0b9e7d3c2a11
Create Date: 2026-09-25 21:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c4d7e8f9a0b1'
down_revision: str | None = '0b9e7d3c2a11'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'exams',
        sa.Column('primary_language', sa.String(length=8), nullable=False, server_default='en'),
    )
    op.create_check_constraint(
        'ck_exams_primary_language_supported',
        'exams',
        "primary_language IN ('en', 'te', 'hi', 'ta', 'ml', 'kn')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_exams_primary_language_supported', 'exams', type_='check')
    op.drop_column('exams', 'primary_language')
