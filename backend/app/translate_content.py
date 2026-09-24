"""Translate exam content already in the database into another language.

Covers everything a candidate reads while sitting an exam: the exam's title and
instructions, its sections, its subject, and every question in its pool with that
question's options. English base columns are never touched - translations go into the
per-locale sibling tables, which the read path already prefers (see
``app.services.i18n.translated_field``), and the locale is switched on in each exam's
language selector.

Three modes:

    # machine-translate with the configured provider (TRANSLATION_PROVIDER)
    python -m app.translate_content auto --locale hi

    # or round-trip through a file, for a human or an offline translator
    python -m app.translate_content export --locale hi --out hi.json
    python -m app.translate_content import --file hi.json

Only fields with no translation yet are exported/translated, unless ``--overwrite``.
Re-running is safe: import upserts one row per (record, locale).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.logging_config import get_logger, setup_logging
from app.db.models import Exam, ExamQuestion, ExamSection, Question, QuestionOption, Subject
from app.db.models.enums import SUPPORTED_LOCALES
from app.db.models.translations import (
    ExamSectionTranslation,
    ExamTranslation,
    OptionTranslation,
    QuestionTranslation,
    SubjectTranslation,
)
from app.db.session import SessionLocal

logger = get_logger("translate_content")

#: kind -> (model, translation model, parent fk on the translation row, fields)
KINDS: dict[str, tuple[type, type, str, tuple[str, ...]]] = {
    "exam": (
        Exam,
        ExamTranslation,
        "exam_id",
        ("title", "description", "instructions", "course", "department", "semester",
         "company_name", "job_role"),
    ),
    "section": (ExamSection, ExamSectionTranslation, "exam_section_id", ("name", "description")),
    "subject": (Subject, SubjectTranslation, "subject_id", ("name", "description")),
    "question": (Question, QuestionTranslation, "question_id", ("body", "explanation")),
    "option": (QuestionOption, OptionTranslation, "option_id", ("text",)),
}


def _pending_fields(record: Any, kind: str, locale: str, overwrite: bool) -> dict[str, str]:
    fields = KINDS[kind][3]
    existing = next((t for t in record.translations if t.locale == locale), None)
    out: dict[str, str] = {}
    for field in fields:
        value = getattr(record, field, None)
        if not value or not str(value).strip():
            continue
        if existing is not None and getattr(existing, field, None) and not overwrite:
            continue
        out[field] = str(value)
    return out


def collect(db: Session, locale: str, *, overwrite: bool, exam_ids: list[uuid.UUID] | None):
    """Every record an exam's candidate reads, with the fields still untranslated."""
    query = select(Exam).options(
        selectinload(Exam.translations),
        selectinload(Exam.subject).selectinload(Subject.translations),
        selectinload(Exam.sections).selectinload(ExamSection.translations),
        selectinload(Exam.exam_questions)
        .selectinload(ExamQuestion.question)
        .selectinload(Question.translations),
        selectinload(Exam.exam_questions)
        .selectinload(ExamQuestion.question)
        .selectinload(Question.options)
        .selectinload(QuestionOption.translations),
    )
    if exam_ids:
        query = query.where(Exam.id.in_(exam_ids))
    exams = list(db.scalars(query))

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, uuid.UUID]] = set()

    def add(kind: str, record: Any) -> None:
        if record is None or (kind, record.id) in seen:
            return
        seen.add((kind, record.id))
        fields = _pending_fields(record, kind, locale, overwrite)
        if fields:
            items.append({"kind": kind, "id": str(record.id), "fields": fields})

    for exam in exams:
        add("exam", exam)
        add("subject", exam.subject)
        for section in exam.sections:
            add("section", section)
        for link in exam.exam_questions:
            add("question", link.question)
            for option in link.question.options:
                add("option", option)
    return exams, items


def apply(db: Session, locale: str, items: list[dict[str, Any]]) -> int:
    written = 0
    for item in items:
        _model, translation_model, parent_fk, allowed = KINDS[item["kind"]]
        parent_id = uuid.UUID(item["id"])
        values = {k: v for k, v in item["fields"].items() if k in allowed and v and v.strip()}
        if not values:
            continue
        row = db.scalar(
            select(translation_model).where(
                getattr(translation_model, parent_fk) == parent_id,
                translation_model.locale == locale,
            )
        )
        if row is None:
            row = translation_model(**{parent_fk: parent_id, "locale": locale})
            db.add(row)
        for field, value in values.items():
            setattr(row, field, value)
        written += 1
    return written


def enable_locale(exams: list[Exam], locale: str) -> int:
    changed = 0
    for exam in exams:
        current = list(exam.enabled_languages or ["en"])
        if locale not in current:
            exam.enabled_languages = [*current, locale]
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("auto", "export"):
        p = sub.add_parser(mode)
        targets = [loc for loc in SUPPORTED_LOCALES if loc != "en"]
        p.add_argument("--locale", required=True, choices=targets)
        p.add_argument("--overwrite", action="store_true")
        p.add_argument("--exam", action="append", type=uuid.UUID, help="limit to these exam ids")
        if mode == "export":
            p.add_argument("--out", required=True)
    p = sub.add_parser("import")
    p.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    setup_logging()
    with SessionLocal() as db:
        if args.mode == "export":
            _exams, items = collect(db, args.locale, overwrite=args.overwrite, exam_ids=args.exam)
            payload = {
                "locale": args.locale,
                "exam_ids": [str(e.id) for e in _exams],
                "items": items,
            }
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            chars = sum(len(v) for i in items for v in i["fields"].values())
            print(f"Exported {len(items)} records ({chars} chars) for {args.locale} -> {args.out}")
            return 0

        if args.mode == "import":
            with open(args.file, encoding="utf-8") as fh:
                payload = json.load(fh)
            locale = payload["locale"]
            written = apply(db, locale, payload["items"])
            exam_ids = [uuid.UUID(e) for e in payload.get("exam_ids", [])]
            exams = list(db.scalars(select(Exam).where(Exam.id.in_(exam_ids)))) if exam_ids else []
            enabled = enable_locale(exams, locale)
            db.commit()
            print(f"Imported {written} {locale} translations; enabled on {enabled} exam(s)")
            return 0

        from app.services.translation import get_translator

        translator = get_translator()
        if translator.name == "stub":
            print("TRANSLATION_PROVIDER is 'stub' - nothing would be translated.", file=sys.stderr)
            return 1
        exams, items = collect(db, args.locale, overwrite=args.overwrite, exam_ids=args.exam)
        print(f"Translating {len(items)} records to {args.locale} with {translator.name} ...")
        for n, item in enumerate(items, start=1):
            item["fields"] = translator.translate(texts=item["fields"], target_locale=args.locale)
            if n % 50 == 0:
                print(f"  {n}/{len(items)}")
        written = apply(db, args.locale, items)
        enabled = enable_locale(exams, args.locale)
        db.commit()
        print(f"Wrote {written} {args.locale} translations; enabled on {enabled} exam(s)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
