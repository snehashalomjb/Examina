"""answer word bounds, image thumbnails, OCR pre-pass

Revision ID: a17b4c9de204
Revises: f0c6eeb2272c
Create Date: 2026-09-01 10:12:03.881204
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a17b4c9de204'
down_revision: str | None = 'f0c6eeb2272c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('min_words', sa.Integer(), nullable=True))
    op.add_column('questions', sa.Column('max_words', sa.Integer(), nullable=True))

    op.add_column('answers', sa.Column('image_thumb_key', sa.String(length=512), nullable=True))
    op.add_column('answers', sa.Column('ocr_text', sa.Text(), nullable=True))
    op.add_column('answers', sa.Column('ocr_confidence', sa.Float(), nullable=True))
    op.add_column('answers', sa.Column('word_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('answers', 'word_count')
    op.drop_column('answers', 'ocr_confidence')
    op.drop_column('answers', 'ocr_text')
    op.drop_column('answers', 'image_thumb_key')

    op.drop_column('questions', 'max_words')
    op.drop_column('questions', 'min_words')
