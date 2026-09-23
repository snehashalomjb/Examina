"""proctor_event_confidence_question_and_new_types

Revision ID: d3f6a1b7c9e2
Revises: 05483046fcc2
Create Date: 2026-09-17 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = 'd3f6a1b7c9e2'
down_revision: str | None = '05483046fcc2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENT_TYPES = (
    'right_click',
    'cut_attempt',
    'text_selection',
    'additional_person',
    'mic_disconnected',
    'network_lost',
    'headphones_manual',
)


def upgrade() -> None:
    for value in NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE proctor_event_type ADD VALUE IF NOT EXISTS '{value}'")

    op.add_column('proctor_events', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column(
        'proctor_events',
        sa.Column('question_id', pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_proctor_events_question_id',
        'proctor_events',
        'questions',
        ['question_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_proctor_events_question_id', 'proctor_events', type_='foreignkey')
    op.drop_column('proctor_events', 'question_id')
    op.drop_column('proctor_events', 'confidence')
    # Enum values are left in place - see 97f8b35d82bf for why.
