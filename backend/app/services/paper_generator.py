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
    #: Which section this entry belongs to, or None for an exam with no sections.
    section_id: uuid.UUID | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": str(self.question_id),
            "option_order": [str(o) for o in self.option_order],
            "marks": self.marks,
        }


def compute_seed(*, exam_id: uuid.UUID, candidate_id: uuid.UUID, salt: str) -> str:
    payload = f"{exam_id}:{candidate_id}:{salt}".encode()
    return blake2b(payload, digest_size=16).hexdigest()


def _matches(eq: ExamQuestion, rule: dict) -> bool:
    """Whether one pooled question satisfies one selection rule.

    Every narrowing the rule declares must hold; a narrowing the rule leaves null means
    "any". Topic is compared case-insensitively on trimmed text because it is free text
    typed by an examiner, and "OOP" and "oop " are the same topic to a human.
    """
    question = eq.question
    if not question.is_active:
        return False
    if question.question_type.value != rule["question_type"]:
        return False
    if rule.get("difficulty") and question.difficulty.value != rule["difficulty"]:
        return False
    if rule.get("category") and question.category.value != rule["category"]:
        return False
    topic = rule.get("topic")
    if topic:
        if not question.topic:
            return False
        if question.topic.strip().casefold() != topic.strip().casefold():
            return False
    if rule.get("subject_id") and str(question.subject_id) != rule["subject_id"]:
        return False
    tags = rule.get("tags")
    if tags and not (set(question.tags or []) & set(tags)):
        return False
    return True


def _pool_matching(
    exam_questions: list[ExamQuestion], rule: dict, section_id: uuid.UUID | None = None
) -> list[ExamQuestion]:
    """Questions a rule may draw, honouring what the examiner pinned where.

    A question pinned to a section belongs to that section alone: it must not turn up in
    a different section's questions just because the type and difficulty happen to fit.
    An unpinned question is free for whichever section's rules match it, which is how the
    pool has always behaved and what every exam built before pinning existed relies on.
    """
    return [
        eq
        for eq in exam_questions
        if _matches(eq, rule) and eq.section_id in (None, section_id)
    ]


def _sections_for(exam: Exam) -> list[tuple[uuid.UUID | None, list[dict]]]:
    """The exam as ``(section_id, rules)`` pairs, in the order candidates will see them.

    An exam with no sections yields a single implicit one carrying ``exam.selection_rules``
    - the shape every single-section exam has always had, on the same code path.
    """
    if not exam.sections:
        return [(None, normalise_selection_rules(exam.selection_rules))]

    pairs: list[tuple[uuid.UUID | None, list[dict]]] = []
    for section in sorted(exam.sections, key=lambda s: s.order_index):
        rules = normalise_selection_rules(section.selection_rules)
        if rules:
            pairs.append((section.id, rules))
    # Every section was empty, so fall back rather than build a paper with no questions.
    return pairs or [(None, normalise_selection_rules(exam.selection_rules))]


def _draw(
    pool: list[ExamQuestion],
    count: int,
    section_id: uuid.UUID | None,
    rng: random.Random | None,
) -> list[ExamQuestion]:
    """Take ``count`` questions, pinned ones first.

    A question the examiner chose *for this section* is not a candidate for a random
    draw - choosing it was the decision. So pinned questions are taken in pool order
    until the rule is satisfied, and only the remainder is sampled. Both halves are
    sorted by question id first so the order the database happened to return rows in can
    never influence a paper.
    """
    pinned = sorted(
        (eq for eq in pool if eq.section_id == section_id and section_id is not None),
        key=lambda eq: (eq.order_index, str(eq.question_id)),
    )
    free = sorted(
        (eq for eq in pool if eq.section_id is None),
        key=lambda eq: str(eq.question_id),
    )

    taken = pinned[:count]
    shortfall = count - len(taken)
    if shortfall > 0:
        taken += rng.sample(free, shortfall) if rng else free[:shortfall]
    return taken


def _rule_label(rule: dict) -> str:
    label = rule["question_type"]
    if rule.get("difficulty"):
        label += f"/{rule['difficulty']}"
    if rule.get("category"):
        label += f" in {rule['category']}"
    if rule.get("topic"):
        label += f" on '{rule['topic']}'"
    return label


def _specificity(rule: dict) -> int:
    """How many narrowings a rule declares. More specific rules draw first."""
    return sum(1 for key in ("difficulty", "category", "topic") if rule.get(key))


def _ordered_rules(rules: list[dict]) -> list[dict]:
    """Satisfy the most specific rules first.

    A rule with ``difficulty: null`` can draw from any difficulty, so if it ran first it
    could eat the only 'hard' questions and starve a later hard-specific rule. Ordering
    specific rules ahead of catch-alls removes that failure mode, and the ordering is
    stable so determinism is unaffected. Category and topic narrow the same way, so they
    count towards specificity too.
    """
    return sorted(rules, key=lambda r: (-_specificity(r), r["question_type"]))


def check_pool_satisfies_rules(exam: Exam) -> list[str]:
    """Return a list of human-readable shortfalls; empty means the exam can be published.

    Walks the rules in the same order and with the same consumption the generator uses,
    so 'publishable' here means 'every candidate's paper can actually be built'.
    """
    problems: list[str] = []
    try:
        sections = _sections_for(exam)
    except ValidationError as exc:
        return [str(exc)]

    names = {s.id: s.name for s in exam.sections}
    used: set[uuid.UUID] = set()

    for section_id, rules in sections:
        where = f" in {names[section_id]}" if section_id in names else ""
        for rule in _ordered_rules(rules):
            available = [
                eq
                for eq in _pool_matching(exam.exam_questions, rule, section_id)
                if eq.question_id not in used
            ]
            if len(available) < rule["count"]:
                problems.append(
                    f"Need {rule['count']} {_rule_label(rule)} question(s){where}, "
                    f"pool only has {len(available)} left"
                )
                continue
            # Reserve deterministically so the next rule sees a realistic remainder.
            for eq in _draw(available, rule["count"], section_id, None):
                used.add(eq.question_id)
    return problems


def generate_paper(*, exam: Exam, candidate_id: uuid.UUID) -> tuple[str, list[PaperEntry]]:
    """Build one candidate's paper. Returns ``(seed, entries)``."""
    seed = compute_seed(exam_id=exam.id, candidate_id=candidate_id, salt=exam.paper_salt)
    rng = random.Random(seed)

    chosen: list[tuple[uuid.UUID | None, ExamQuestion]] = []
    used: set[uuid.UUID] = set()

    for section_id, rules in _sections_for(exam):
        drawn: list[ExamQuestion] = []
        for rule in _ordered_rules(rules):
            pool = [
                eq
                for eq in _pool_matching(exam.exam_questions, rule, section_id)
                if eq.question_id not in used
            ]
            if len(pool) < rule["count"]:
                raise ValidationError(
                    f"Question pool cannot satisfy the rule for {_rule_label(rule)}: "
                    f"need {rule['count']}, have {len(pool)}"
                )

            picked = _draw(pool, rule["count"], section_id, rng if exam.randomize else None)
            for eq in picked:
                used.add(eq.question_id)
            drawn.extend(picked)

        # Shuffle within the section, never across it. A candidate sees Section A's
        # questions then Section B's; randomisation decides the order inside each, not
        # whether a Section B question can appear under Section A's heading.
        if exam.randomize:
            rng.shuffle(drawn)
        else:
            drawn.sort(key=lambda eq: (eq.order_index, str(eq.question_id)))
        chosen.extend((section_id, eq) for eq in drawn)

    entries: list[PaperEntry] = []
    for section_id, eq in chosen:
        option_ids = [o.id for o in sorted(eq.question.options, key=lambda o: o.order_index)]
        # Option order is its own setting, deliberately not gated on ``randomize``:
        # shuffling which questions appear and shuffling A/B/C/D answer different
        # worries, and an examiner who turns one on has not asked for the other.
        if exam.shuffle_options and eq.question.question_type in {
            QuestionType.MCQ,
            QuestionType.MULTI_SELECT,
        }:
            rng.shuffle(option_ids)
        entries.append(
            PaperEntry(
                question_id=eq.question_id,
                option_order=option_ids,
                marks=eq.effective_marks,
                section_id=section_id,
            )
        )

    return seed, entries
