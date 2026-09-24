"""add sql question type

Revision ID: f1a2b3c4d5e6
Revises: d3f6a1b7c9e2
Create Date: 2026-09-23 17:00:00.000000

Originally this also dropped ``image_upload`` from the enum, but the application still
uses that type (handwritten answers), and the enum rebuild could never succeed anyway:
``ai_question_drafts.question_type`` also depends on the type, so ``DROP TYPE`` failed
and rolled the whole migration back. It now only adds ``sql``.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "d3f6a1b7c9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL allows ADD VALUE without a table rewrite.
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'sql'")


def downgrade() -> None:
    # PostgreSQL has no ALTER TYPE ... DROP VALUE; removing 'sql' would mean rebuilding
    # the enum across every table that uses it. Leaving the unused value is harmless.
    pass
