"""add_notifications

Revision ID: ac7ac40c4283
Revises: d1e2f3a4b5c6
Create Date: 2026-09-27 19:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'ac7ac40c4283'
down_revision: str | None = 'd1e2f3a4b5c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('recipient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['recipient_id'], ['users.id'], name='fk_notifications_recipient_id_users',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], ['exam_sessions.id'], name='fk_notifications_session_id_exam_sessions',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['result_id'], ['results.id'], name='fk_notifications_result_id_results',
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'recipient_id', 'session_id', 'type',
            name='uq_notification_recipient_session_type',
        ),
    )
    op.create_index('ix_notifications_recipient_id', 'notifications', ['recipient_id'])
    op.create_index('ix_notifications_type', 'notifications', ['type'])
    op.create_index('ix_notifications_session_id', 'notifications', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_notifications_session_id', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_recipient_id', table_name='notifications')
    op.drop_table('notifications')
