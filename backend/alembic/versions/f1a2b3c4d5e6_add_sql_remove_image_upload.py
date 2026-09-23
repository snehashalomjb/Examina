"""add sql question type, remove image_upload

Revision ID: f1a2b3c4d5e6
Revises: d3f6a1b7c9e2
Create Date: 2026-09-23 17:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "d3f6a1b7c9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Step 1: Add the new 'sql' value to the enum ───────────────────────────
    # PostgreSQL allows ADD VALUE without a table rewrite.
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'sql'")

    # ── Step 2: Convert existing image_upload rows → long_answer ──────────────
    # Do this before dropping the old value so the column still accepts it.
    op.execute(
        "UPDATE questions SET question_type = 'long_answer' "
        "WHERE question_type = 'image_upload'"
    )

    # ── Step 3: Remove 'image_upload' from the enum ───────────────────────────
    # PostgreSQL has no ALTER TYPE … DROP VALUE, so we recreate the enum.
    op.execute("ALTER TYPE question_type RENAME TO question_type_old")
    op.execute(
        "CREATE TYPE question_type AS ENUM ("
        "'mcq', 'multi_select', 'short_answer', 'long_answer', "
        "'true_false', 'fill_blank', 'numerical', 'passage', 'coding', 'sql'"
        ")"
    )
    op.execute(
        "ALTER TABLE questions "
        "ALTER COLUMN question_type TYPE question_type "
        "USING question_type::text::question_type"
    )
    op.execute("DROP TYPE question_type_old")


def downgrade() -> None:
    # Re-add image_upload, remove sql, convert sql rows → long_answer.
    op.execute("ALTER TYPE question_type RENAME TO question_type_old")
    op.execute(
        "CREATE TYPE question_type AS ENUM ("
        "'mcq', 'multi_select', 'short_answer', 'long_answer', "
        "'image_upload', 'true_false', 'fill_blank', 'numerical', 'passage', 'coding'"
        ")"
    )
    op.execute(
        "UPDATE questions SET question_type = 'long_answer' "
        "WHERE question_type = 'sql'"
    )
    op.execute(
        "ALTER TABLE questions "
        "ALTER COLUMN question_type TYPE question_type "
        "USING question_type::text::question_type"
    )
    op.execute("DROP TYPE question_type_old")
