"""One-off cleanup: merge duplicate Subject rows left behind by earlier spreadsheet
imports (each import that named a subject the bank didn't already have by *code* created
a fresh ``QA-<NAME>-<random>`` subject, even when a subject of that exact *name* already
existed under a cleaner code).

For each group of subjects sharing an exact (case-insensitive) name:
  - pick a winner (most questions, then the least-ugly code),
  - move every question and exam pointing at a loser onto the winner,
  - delete the now-empty losers,
  - if the winner's own code is one of the ugly generated ones, give it a clean code.

Idempotent: a group with only one subject is left alone, so re-running after the first
clean-up is a no-op.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select

from app.core.logging_config import get_logger, setup_logging
from app.db.models import Exam, Question, Subject
from app.db.session import SessionLocal

logger = get_logger("dedupe_subjects")

#: Subjects worth a clean, memorable code once they stop being import stragglers - these
#: are exactly the ones the platform's own requirements call out by name.
_CLEAN_CODES = {
    "python": "PY101",
    "sql": "SQL101",
}


def _is_generated_code(code: str) -> bool:
    return code.startswith("QA-")


def dedupe(db) -> int:
    subjects = list(db.scalars(select(Subject)))
    groups: dict[str, list[Subject]] = defaultdict(list)
    for s in subjects:
        groups[s.name.strip().lower()].append(s)

    removed = 0
    for name_key, group in groups.items():
        if len(group) < 2:
            continue

        counts = dict(
            db.execute(
                select(Question.subject_id, func.count(Question.id))
                .where(Question.subject_id.in_([s.id for s in group]))
                .group_by(Question.subject_id)
            ).all()
        )

        def sort_key(s: Subject) -> tuple[int, int]:
            return (-counts.get(s.id, 0), 0 if not _is_generated_code(s.code) else 1)

        group_sorted = sorted(group, key=sort_key)
        winner = group_sorted[0]
        losers = group_sorted[1:]

        for loser in losers:
            moved_q = (
                db.query(Question)
                .filter(Question.subject_id == loser.id)
                .update({"subject_id": winner.id})
            )
            moved_e = (
                db.query(Exam)
                .filter(Exam.subject_id == loser.id)
                .update({"subject_id": winner.id})
            )
            logger.info(
                "Merging subject %s (%s) into %s (%s): moved %d question(s), %d exam(s)",
                loser.code,
                loser.name,
                winner.code,
                winner.name,
                moved_q,
                moved_e,
            )
            db.delete(loser)
            removed += 1

        clean_code = _CLEAN_CODES.get(name_key)
        if clean_code and _is_generated_code(winner.code):
            existing = db.scalar(select(Subject).where(Subject.code == clean_code))
            if existing is None or existing.id == winner.id:
                logger.info("Renaming subject code %s -> %s (%s)", winner.code, clean_code, winner.name)
                winner.code = clean_code

    db.flush()
    return removed


def main() -> None:
    setup_logging()
    db = SessionLocal()
    try:
        removed = dedupe(db)
        db.commit()
        logger.info("Dedupe complete: removed %d duplicate subject(s)", removed)
    finally:
        db.close()


if __name__ == "__main__":
    main()
