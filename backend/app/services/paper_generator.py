"""Deterministic per-candidate paper generation.

The same (exam, candidate) pair always produces byte-identical papers - a refresh, a
server restart, or a re-issued session token never reshuffles a live exam. Two different
candidates get different papers.

Determinism comes from seeding ``random.Random`` with a blake2b digest of
``exam_id : candidate_id : exam.paper_salt``. The salt keeps the ordering unguessable to
anyone who only knows the two ids.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Any

from app.db.models import Exam, ExamQuestion, QuestionType
from app.services.validators import ValidationError, normalise_selection_rules


@dataclass
class PaperEntry:
    question_id: uuid.UUID
    option_order: list[uuid.UUID] = field(default_factory=list)
    marks: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": str(self.question_id),
            "option_order": [str(o) for o in self.option_order],
            "marks": self.marks,
        }


def compute_seed(*, exam_id: uuid.UUID, candidate_id: uuid.UUID, salt: str) -> str:
    payload = f"{exam_id}:{candidate_id}:{salt}".encode()
    return blake2b(payload, digest_size=16).hexdigest()


def _pool_matching(
    exam_questions: list[ExamQuestion], question_type: str, difficulty: str | None
) -> list[ExamQuestion]:
    return [
        eq
        for eq in exam_questions
        if eq.question.is_active
        and eq.question.question_type.value == question_type
        and (difficulty is None or eq.question.difficulty.value == difficulty)
    ]


def _rule_label(rule: dict) -> str:
    label = rule["question_type"]
    if rule["difficulty"]:
        label += f"/{rule['difficulty']}"
    return label


def _ordered_rules(rules: list[dict]) -> list[dict]:
    """Satisfy the most specific rules first.

    A rule with ``difficulty: null`` can draw from any difficulty, so if it ran first it
    could eat the only 'hard' questions and starve a later hard-specific rule. Ordering
    specific rules ahead of catch-alls removes that failure mode, and the ordering is
    stable so determinism is unaffected.
    """
    return sorted(rules, key=lambda r: (r["difficulty"] is None, r["question_type"]))


def check_pool_satisfies_rules(exam: Exam) -> list[str]:
    """Return a list of human-readable shortfalls; empty means the exam can be published.

    Walks the rules in the same order and with the same consumption the generator uses,
    so 'publishable' here means 'every candidate's paper can actually be built'.
    """
    problems: list[str] = []
    try:
        rules = normalise_selection_rules(exam.selection_rules)
    except ValidationError as exc:
        return [str(exc)]

    used: set[uuid.UUID] = set()
    for rule in _ordered_rules(rules):
        available = [
            eq
            for eq in _pool_matching(exam.exam_questions, rule["question_type"], rule["difficulty"])
            if eq.question_id not in used
        ]
        if len(available) < rule["count"]:
            problems.append(
                f"Need {rule['count']} {_rule_label(rule)} question(s), "
                f"pool only has {len(available)} left"
            )
            continue
        # Reserve deterministically so the next rule sees a realistic remainder.
        for eq in sorted(available, key=lambda e: str(e.question_id))[: rule["count"]]:
            used.add(eq.question_id)
    return problems


def generate_paper(*, exam: Exam, candidate_id: uuid.UUID) -> tuple[str, list[PaperEntry]]:
    """Build one candidate's paper. Returns ``(seed, entries)``."""
    seed = compute_seed(exam_id=exam.id, candidate_id=candidate_id, salt=exam.paper_salt)
    rng = random.Random(seed)

    rules = normalise_selection_rules(exam.selection_rules)

    chosen: list[ExamQuestion] = []
    used: set[uuid.UUID] = set()

    for rule in _ordered_rules(rules):
        pool = [
            eq
            for eq in _pool_matching(exam.exam_questions, rule["question_type"], rule["difficulty"])
            if eq.question_id not in used
        ]
        if len(pool) < rule["count"]:
            raise ValidationError(
                f"Question pool cannot satisfy the rule for {_rule_label(rule)}: "
                f"need {rule['count']}, have {len(pool)}"
            )

        # Sort by a stable key first so the pool order out of the DB cannot leak in.
        pool.sort(key=lambda eq: str(eq.question_id))
        picked = rng.sample(pool, rule["count"]) if exam.randomize else pool[: rule["count"]]
        for eq in picked:
            used.add(eq.question_id)
        chosen.extend(picked)

    if exam.randomize:
        rng.shuffle(chosen)
    else:
        chosen.sort(key=lambda eq: (eq.order_index, str(eq.question_id)))

    entries: list[PaperEntry] = []
    for eq in chosen:
        option_ids = [o.id for o in sorted(eq.question.options, key=lambda o: o.order_index)]
        if (
            exam.shuffle_options
            and exam.randomize
            and eq.question.question_type in {QuestionType.MCQ, QuestionType.MULTI_SELECT}
        ):
            rng.shuffle(option_ids)
        entries.append(
            PaperEntry(
                question_id=eq.question_id,
                option_order=option_ids,
                marks=eq.effective_marks,
            )
        )

    return seed, entries
