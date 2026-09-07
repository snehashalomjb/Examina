"""Offline grader - the default provider.

Produces a deterministic, defensible-looking first-pass score with no network call and no
API key, so the whole submit -> grade -> examiner-review pipeline is exercisable (and
testable) before any model is wired up.

It is explicitly *not* intelligent: the justification says so, and every score it emits is
labelled as provisional in the examiner queue.
"""

from __future__ import annotations

import re
from hashlib import blake2b

from app.db.models import Answer, Question, QuestionType
from app.services.grading.base import GradeResult

_WORD_RE = re.compile(r"[a-z0-9']+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "then",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
}


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


class StubGrader:
    """Keyword-overlap heuristic + a deterministic jitter derived from the answer text."""

    name = "stub"
    model = None

    def grade(self, *, question: Question, answer: Answer, max_marks: float) -> GradeResult:
        if question.question_type is QuestionType.IMAGE_UPLOAD:
            return self._grade_image(answer=answer, max_marks=max_marks)

        text = (answer.text_answer or "").strip()
        if not text:
            return GradeResult(
                score=0.0,
                max_score=max_marks,
                justification="No answer was submitted for this question.",
                confidence=1.0,
            )

        model_answer = question.model_answer or ""
        expected = _keywords(model_answer)
        given = _keywords(text)

        if expected:
            overlap = len(expected & given) / len(expected)
        else:
            overlap = 0.5

        # Length sanity: a two-word reply to a long-answer question is not a full answer.
        target_words = 120 if question.question_type is QuestionType.LONG_ANSWER else 30
        length_ratio = min(len(given) / target_words, 1.0)

        raw = 0.7 * overlap + 0.3 * length_ratio

        # Deterministic +/-5% jitter so identical heuristics do not produce identical
        # scores across every script - keeps the examiner queue realistic to review.
        digest = blake2b(text.encode("utf-8"), digest_size=2).digest()
        jitter = ((int.from_bytes(digest, "big") / 65535) - 0.5) * 0.1
        fraction = max(0.0, min(raw + jitter, 1.0))

        score = round(max_marks * fraction, 2)
        matched = sorted(expected & given)[:6]

        justification = (
            f"[Provisional offline score - no model configured] "
            f"Matched {len(expected & given)}/{len(expected)} key concepts"
            + (f" ({', '.join(matched)})" if matched else "")
            + f". Answer length {len(given)} significant words against a target of "
            f"{target_words}. Examiner review required."
        )

        return GradeResult(
            score=score,
            max_score=max_marks,
            justification=justification,
            confidence=round(0.35 + 0.3 * overlap, 2),
        ).clamped()

    def _grade_image(self, *, answer: Answer, max_marks: float) -> GradeResult:
        """A handwritten scan cannot be read without a vision model - defer to the examiner."""
        if not answer.image_object_key:
            return GradeResult(
                score=0.0,
                max_score=max_marks,
                justification="No image was uploaded for this question.",
                confidence=1.0,
            )
        return GradeResult(
            score=0.0,
            max_score=max_marks,
            justification=(
                "[Provisional offline score - no model configured] A handwritten answer "
                "image was submitted but cannot be read without a vision-capable grader. "
                "Full examiner review required."
            ),
            confidence=0.0,
        )
