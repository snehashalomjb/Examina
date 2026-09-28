"""add_question_language

A question's own content language - separate banks per language, not translation rows
over an English master. Backed by a CHECK constraint for the same reason
``primary_language`` on exams is: a typo here would silently mix a Tamil paper's pool
with English or Hindi material for the same subject.

Revision ID: d1e2f3a4b5c6
Revises: c4d7e8f9a0b1
Create Date: 2026-09-26 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd1e2f3a4b5c6'
down_revision: str | None = 'c4d7e8f9a0b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'questions',
        sa.Column('language', sa.String(length=8), nullable=False, server_default='en'),
    )
    op.create_check_constraint(
        'ck_questions_language_supported',
        'questions',
        "language IN ('en', 'te', 'hi', 'ta', 'ml', 'kn')",
    )
    op.create_index(
        'ix_questions_language_subject', 'questions', ['language', 'subject_id']
    )


def downgrade() -> None:
    op.drop_index('ix_questions_language_subject', table_name='questions')
    op.drop_constraint('ck_questions_language_supported', 'questions', type_='check')
    op.drop_column('questions', 'language')
