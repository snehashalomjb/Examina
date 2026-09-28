"""Typed question-bank fixture catalogue.

The catalogue is data-only: :mod:`app.seed_questions` owns persistence and
verification. Each subject supplies six concept cards. The catalogue expands
 every card into MCQ, multi-select, and short-answer questions, with two cards
allocated to each difficulty, so every subject has 18 unique fixtures.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from app.db.models import Difficulty, QuestionCategory


@dataclass(frozen=True)
class FixtureOption:
    text: str
    is_correct: bool


@dataclass(frozen=True)
class FixtureQuestion:
    topic: str
    body: str
    difficulty: Difficulty
    question_type: str
    options: tuple[FixtureOption, ...]
    model_answer: str
    explanation: str
    marks: float
    negative_marks: float
    min_words: int | None = None
    max_words: int | None = None


@dataclass(frozen=True)
class SubjectDefinition:
    code: str
    name: str
    description: str
    category: QuestionCategory
    questions: tuple[FixtureQuestion, ...]
    create_if_missing: bool = True


@dataclass(frozen=True)
class Concept:
    """One subject fact expanded into the three supported question types."""

    topic: str
    term: str
    statement: str
    also_true: str
    misconception: str
    distractors: tuple[str, str, str]
    significance: str


_MARKS = {Difficulty.EASY: 1.0, Difficulty.MEDIUM: 2.0, Difficulty.HARD: 3.0}


def fact(
    topic: str,
    term: str,
    statement: str,
    also_true: str,
    significance: str,
) -> Concept:
    """Build a card with deliberately false, subject-relevant distractors."""
    return Concept(
        topic=topic,
        term=term,
        statement=statement,
        also_true=also_true,
        misconception=f"{term} is always correct regardless of context.",
        distractors=(
            f"{term} has no role in {topic}.",
            f"{term} means the same thing in every {topic} context.",
            f"{term} is the only valid choice for every {topic} question.",
        ),
        significance=significance,
    )


def _ordered_options(
    *, body: str, correct: tuple[str, ...], incorrect: tuple[str, ...]
) -> tuple[FixtureOption, ...]:
    """Mix answer positions deterministically so tests do not learn 'always A'."""
    values = [*correct, *incorrect]
    random.Random(body).shuffle(values)
    correct_set = set(correct)
    return tuple(FixtureOption(value, value in correct_set) for value in values)


def mcq(
    topic: str,
    difficulty: Difficulty,
    body: str,
    correct: str,
    incorrect: tuple[str, str, str],
    explanation: str,
) -> FixtureQuestion:
    marks = _MARKS[difficulty]
    return FixtureQuestion(
        topic=topic,
        body=body,
        difficulty=difficulty,
        question_type="mcq",
        options=_ordered_options(body=body, correct=(correct,), incorrect=incorrect),
        model_answer=correct,
        explanation=explanation,
        marks=marks,
        negative_marks=round(marks / 4, 2),
    )


def multi(
    topic: str,
    difficulty: Difficulty,
    body: str,
    correct: tuple[str, str],
    incorrect: tuple[str, str],
    explanation: str,
) -> FixtureQuestion:
    marks = _MARKS[difficulty] + 1
    return FixtureQuestion(
        topic=topic,
        body=body,
        difficulty=difficulty,
        question_type="multi_select",
        options=_ordered_options(body=body, correct=correct, incorrect=incorrect),
        model_answer="Select: " + " and ".join(correct),
        explanation=explanation,
        marks=marks,
        negative_marks=round(marks / 4, 2),
    )


def short(
    topic: str,
    difficulty: Difficulty,
    body: str,
    answer: str,
    explanation: str,
) -> FixtureQuestion:
    return FixtureQuestion(
        topic=topic,
        body=body,
        difficulty=difficulty,
        question_type="short_answer",
        options=(),
        model_answer=answer,
        explanation=explanation,
        marks=_MARKS[difficulty] + 2,
        negative_marks=0.0,
        min_words=3,
        max_words=120,
    )


def _questions_for(
    concepts: tuple[Concept, ...], *, subject_name: str
) -> tuple[FixtureQuestion, ...]:
    """Expand six cards, two per difficulty, into all requested question types."""
    if len(concepts) != 6:
        raise ValueError(f"{subject_name} must provide exactly six concept cards")
    questions: list[FixtureQuestion] = []
    for pair_start, difficulty in enumerate(Difficulty):
        for concept in concepts[pair_start * 2 : pair_start * 2 + 2]:
            context = f"{subject_name}, within {concept.topic}"
            if difficulty is Difficulty.EASY:
                mcq_body = f"In {context}, which statement about {concept.term} is correct?"
                multi_body = f"Which two statements about {concept.term} in {context} are accurate?"
                short_body = f"In {context}, define {concept.term} and give one relevant fact."
            elif difficulty is Difficulty.MEDIUM:
                mcq_body = f"Which statement best describes {concept.term} in {context}?"
                multi_body = (
                    f"Which two claims accurately characterize {concept.term} "
                    f"in {context}?"
                )
                short_body = f"In {context}, explain {concept.term} and why it matters."
            else:
                mcq_body = (
                    f"A practitioner must reason about {concept.term} in {context}. "
                    "Which statement is valid?"
                )
                multi_body = (
                    f"Which two conclusions are valid when reasoning about {concept.term} "
                    f"in {context}?"
                )
                short_body = (
                    f"In {context}, explain {concept.term}, address the misconception that "
                    f"{concept.misconception}, and describe the practical consequence."
                )
            questions.extend(
                (
                    mcq(
                        concept.topic,
                        difficulty,
                        mcq_body,
                        concept.statement,
                        concept.distractors,
                        concept.statement,
                    ),
                    multi(
                        concept.topic,
                        difficulty,
                        multi_body,
                        (concept.statement, concept.also_true),
                        (concept.misconception, concept.distractors[0]),
                        f"Both {concept.statement} and {concept.also_true} are correct.",
                    ),
                    short(
                        concept.topic,
                        difficulty,
                        short_body,
                        f"{concept.statement} {concept.significance}",
                        concept.significance,
                    ),
                )
            )
    return tuple(questions)


def subject(
    code: str,
    name: str,
    description: str,
    category: QuestionCategory,
    concepts: tuple[Concept, ...],
    *,
    create_if_missing: bool = True,
) -> SubjectDefinition:
    return SubjectDefinition(
        code=code,
        name=name,
        description=description,
        category=category,
        questions=_questions_for(concepts, subject_name=name),
        create_if_missing=create_if_missing,
    )


def _load_subject_fixtures() -> dict[str, SubjectDefinition]:
    from app.seed_question_data import SUBJECTS as CORE_SUBJECTS
    from app.seed_question_data_ai import SUBJECTS as AI_SUBJECTS
    from app.seed_question_data_hiring import SUBJECTS as HIRING_SUBJECTS
    from app.seed_question_data_legacy import SUBJECTS as LEGACY_SUBJECTS

    subjects = (*CORE_SUBJECTS, *AI_SUBJECTS, *HIRING_SUBJECTS, *LEGACY_SUBJECTS)
    duplicates = sorted(
        code for code, count in Counter(item.code for item in subjects).items() if count > 1
    )
    if duplicates:
        raise RuntimeError(f"Duplicate subject definitions: {', '.join(duplicates)}")
    return {item.code: item for item in subjects}


SUBJECT_FIXTURES = _load_subject_fixtures()