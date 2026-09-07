"""Word counting and word-bound enforcement for written answers.

One definition of "a word" for the whole platform: the runner's live counter, the
server's save-time check and the stored ``answers.word_count`` all come through here, so
a candidate can never be told 249 words by the UI and rejected for 251 by the API.
"""

from __future__ import annotations

import re

from app.db.models import Question, QuestionType

# A word is a run of letters/digits, with internal apostrophes and hyphens kept whole
# ("candidate's", "well-formed" are one word each). Punctuation and markup are not words.
_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)

#: Types whose answer is free text, and therefore countable.
_TEXT_TYPES = {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}


class WordCountError(ValueError):
    """A written answer is outside the bounds the examiner set for the question."""


def count_words(text: str | None) -> int:
    if not text:
        return 0
    return len(_WORD_RE.findall(text))


def validate_word_bounds(
    *, min_words: int | None, max_words: int | None, question_type: QuestionType | None = None
) -> None:
    """Check the bounds an examiner is *configuring* (not an answer against them)."""
    for label, value in (("min_words", min_words), ("max_words", max_words)):
        if value is not None and value < 0:
            raise ValueError(f"{label} cannot be negative")
        if value is not None and value > 100_000:
            raise ValueError(f"{label} is unreasonably large")

    if min_words is not None and max_words is not None and min_words > max_words:
        raise ValueError("min_words cannot exceed max_words")

    if (
        question_type is not None
        and question_type not in _TEXT_TYPES
        and (min_words is not None or max_words is not None)
    ):
        raise ValueError(
            f"{question_type.value} questions do not take a word limit - "
            "word bounds apply to short_answer and long_answer only"
        )


def check_answer_words(question: Question, text: str | None) -> int:
    """Count an answer and enforce the question's **maximum**. Returns the count.

    Only the ceiling is enforced here, and deliberately so. Autosave fires while the
    candidate is still typing, so rejecting a half-written answer for being under
    ``min_words`` would throw away work at word three of a hundred-word question. The
    floor is advisory until submit - see :func:`shortfall`.

    An empty answer is always accepted: clearing the box must be possible, and an
    unanswered question is scored as unanswered rather than refused at save time.
    """
    count = count_words(text)
    if question.question_type not in _TEXT_TYPES or count == 0:
        return count

    max_words = question.max_words
    if max_words is not None and count > max_words:
        raise WordCountError(
            f"This answer is {count} words. The limit for this question is {max_words}."
        )
    return count


def shortfall(question: Question, text: str | None) -> int:
    """How many words an answer is *below* the question's minimum. 0 when it is fine.

    Used to warn at submit, never to block a save.
    """
    if question.question_type not in _TEXT_TYPES or not question.min_words:
        return 0
    count = count_words(text)
    if count == 0:  # unanswered, not under-answered
        return 0
    return max(0, question.min_words - count)
