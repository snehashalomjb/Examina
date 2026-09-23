"""add_translation_tables

Adds one sibling translations table per translatable content table
(questions, question_options, exams, subjects, exam_sections) and backfills
an 'en' row for every existing record from its current base columns. Purely
additive: no existing table, column or id is touched, so grading, exports and
the exam engine are unaffected.

Revision ID: e2a1c5f9b3d7
Revises: e7a2c4f8b1d3
Create Date: 2026-09-20 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e2a1c5f9b3d7'
down_revision: str | None = 'e7a2c4f8b1d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCALE_CHECK = "locale IN ('en', 'te', 'hi', 'ta', 'ml', 'kn')"


def upgrade() -> None:
    op.create_table(
        'question_translations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('question_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('model_answer', sa.Text(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('question_id', 'locale', name='uq_question_translations_locale'),
        sa.CheckConstraint(_LOCALE_CHECK, name='ck_question_translations_locale_supported'),
    )
    op.create_index('ix_question_translations_question_id', 'question_translations', ['question_id'])
    op.create_index('ix_question_translations_locale', 'question_translations', ['locale'])

    op.create_table(
        'option_translations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('option_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['option_id'], ['question_options.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('option_id', 'locale', name='uq_option_translations_locale'),
        sa.CheckConstraint(_LOCALE_CHECK, name='ck_option_translations_locale_supported'),
    )
    op.create_index('ix_option_translations_option_id', 'option_translations', ['option_id'])
    op.create_index('ix_option_translations_locale', 'option_translations', ['locale'])

    op.create_table(
        'exam_translations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('exam_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('course', sa.String(length=150), nullable=True),
        sa.Column('department', sa.String(length=150), nullable=True),
        sa.Column('semester', sa.String(length=40), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('job_role', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('exam_id', 'locale', name='uq_exam_translations_locale'),
        sa.CheckConstraint(_LOCALE_CHECK, name='ck_exam_translations_locale_supported'),
    )
    op.create_index('ix_exam_translations_exam_id', 'exam_translations', ['exam_id'])
    op.create_index('ix_exam_translations_locale', 'exam_translations', ['locale'])

    op.create_table(
        'subject_translations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('subject_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('subject_id', 'locale', name='uq_subject_translations_locale'),
        sa.CheckConstraint(_LOCALE_CHECK, name='ck_subject_translations_locale_supported'),
    )
    op.create_index('ix_subject_translations_subject_id', 'subject_translations', ['subject_id'])
    op.create_index('ix_subject_translations_locale', 'subject_translations', ['locale'])

    op.create_table(
        'exam_section_translations',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('exam_section_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('locale', sa.String(length=5), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['exam_section_id'], ['exam_sections.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('exam_section_id', 'locale', name='uq_exam_section_translations_locale'),
        sa.CheckConstraint(_LOCALE_CHECK, name='ck_exam_section_translations_locale_supported'),
    )
    op.create_index(
        'ix_exam_section_translations_exam_section_id', 'exam_section_translations', ['exam_section_id']
    )
    op.create_index('ix_exam_section_translations_locale', 'exam_section_translations', ['locale'])

    # Backfill: every existing row gets an 'en' translation seeded from its own base
    # columns, so the fallback chain (locale -> en -> base column) never has to reach
    # the base column for pre-existing content - reads stay uniform from day one.
    op.execute(
        """
        INSERT INTO question_translations (id, question_id, locale, body, model_answer, explanation, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', body, model_answer, explanation, now(), now() FROM questions
        """
    )
    op.execute(
        """
        INSERT INTO option_translations (id, option_id, locale, text, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', text, now(), now() FROM question_options
        """
    )
    op.execute(
        """
        INSERT INTO exam_translations (id, exam_id, locale, title, description, instructions, course, department, semester, company_name, job_role, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', title, description, instructions, course, department, semester, company_name, job_role, now(), now() FROM exams
        """
    )
    op.execute(
        """
        INSERT INTO subject_translations (id, subject_id, locale, name, description, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', name, description, now(), now() FROM subjects
        """
    )
    op.execute(
        """
        INSERT INTO exam_section_translations (id, exam_section_id, locale, name, description, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'en', name, description, now(), now() FROM exam_sections
        """
    )


def downgrade() -> None:
    op.drop_table('exam_section_translations')
    op.drop_table('subject_translations')
    op.drop_table('exam_translations')
    op.drop_table('option_translations')
    op.drop_table('question_translations')
