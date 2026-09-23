"""integrity verdict, result publisher, exam difficulty

Adds the examiner's integrity ruling on a sitting (kept separate from the score, so a
flagged paper is judged by a human rather than auto-failed), records which examiner
released a result, and backfills the ``exams.difficulty`` column that the model already
declared but no migration had ever created.

Revision ID: 737b6543331b
Revises: b1c2d3e4f5a6
Create Date: 2026-09-10 00:10:37.667674
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '737b6543331b'
down_revision: str | None = 'b1c2d3e4f5a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

integrity_verdict = sa.Enum(
    'pending', 'cleared', 'malpractice', name='integrity_verdict'
)


def upgrade() -> None:
    # Existing sittings default to 'pending': nobody has reviewed them, which is the
    # honest state - not 'cleared'.
    integrity_verdict.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'exam_sessions',
        sa.Column(
            'integrity_verdict',
            integrity_verdict,
            server_default='pending',
            nullable=False,
        ),
    )
    op.add_column('exam_sessions', sa.Column('integrity_note', sa.Text(), nullable=True))
    op.add_column(
        'exam_sessions', sa.Column('integrity_reviewed_by_id', sa.UUID(), nullable=True)
    )
    op.add_column(
        'exam_sessions',
        sa.Column('integrity_reviewed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f('ix_exam_sessions_integrity_verdict'),
        'exam_sessions',
        ['integrity_verdict'],
        unique=False,
    )
    op.create_foreign_key(
        op.f('fk_exam_sessions_integrity_reviewed_by_id_users'),
        'exam_sessions',
        'users',
        ['integrity_reviewed_by_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Declared on the Exam model but never migrated - the dev database was missing it
    # while the test database, built from the models, had it.
    op.add_column(
        'exams',
        sa.Column(
            'difficulty',
            sa.Enum('easy', 'medium', 'hard', name='difficulty'),
            nullable=True,
        ),
    )

    op.add_column('results', sa.Column('published_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f('fk_results_published_by_id_users'),
        'results',
        'users',
        ['published_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_results_published_by_id_users'), 'results', type_='foreignkey'
    )
    op.drop_column('results', 'published_by_id')
    op.drop_column('exams', 'difficulty')
    op.drop_constraint(
        op.f('fk_exam_sessions_integrity_reviewed_by_id_users'),
        'exam_sessions',
        type_='foreignkey',
    )
    op.drop_index(op.f('ix_exam_sessions_integrity_verdict'), table_name='exam_sessions')
    op.drop_column('exam_sessions', 'integrity_reviewed_at')
    op.drop_column('exam_sessions', 'integrity_reviewed_by_id')
    op.drop_column('exam_sessions', 'integrity_note')
    op.drop_column('exam_sessions', 'integrity_verdict')
    # Dropping the column leaves the type behind in Postgres, and a re-upgrade would
    # then fail with "type already exists".
    integrity_verdict.drop(op.get_bind(), checkfirst=True)
