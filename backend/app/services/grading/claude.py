"""Claude-backed grader.

Inactive by default. It only takes over when ``GRADER_PROVIDER=claude`` and an API key is
present; otherwise the factory hands back the stub, so the platform never hard-depends on
a model being available.

Notes on the API shape used here:
- ``client.messages.parse(..., output_format=GradeResult)`` gives a validated Pydantic
  object back on ``.parsed_output`` - no JSON parsing by hand.
- Handwritten ``image_upload`` answers are sent as a base64 image content block.
- The rubric/model-answer prefix carries ``cache_control`` so re-grading many scripts for
  the same question reads the prefix from cache instead of paying for it every time.
"""

from __future__ import annotations

import base64

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.storage import get_object_bytes
from app.db.models import Answer, Question, QuestionType
from app.services.grading.base import GradeResult

logger = get_logger("grading.claude")

SYSTEM_PROMPT = (
    "You are an experienced examiner grading a written answer for a university-level "
    "examination. Award marks strictly against the model answer and rubric supplied. "
    "Give partial credit where the candidate demonstrates partial understanding. "
    "Never award more than the maximum marks. Justify the score in two or three "
    "sentences, naming what was present and what was missing. Be consistent: the same "
    "answer must always receive the same score."
)


class ClaudeGrader:
    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "The 'anthropic' package is not installed. "
                "Install it with: uv pip install '.[claude]'"
            ) from exc

        self.model = model or settings.GRADER_MODEL
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _rubric_prefix(self, question: Question, max_marks: float) -> str:
        parts = [
            f"QUESTION ({question.question_type.value}, worth {max_marks} marks):",
            question.body.strip(),
        ]
        if question.model_answer:
            parts += ["", "MODEL ANSWER:", question.model_answer.strip()]
        if question.rubric:
            parts += ["", f"RUBRIC: {question.rubric}"]
        return "\n".join(parts)

    def grade(self, *, question: Question, answer: Answer, max_marks: float) -> GradeResult:
        content: list[dict] = [
            {
                "type": "text",
                "text": self._rubric_prefix(question, max_marks),
                # Stable prefix - cached across every script for this question.
                "cache_control": {"type": "ephemeral"},
            }
        ]

        if question.question_type is QuestionType.IMAGE_UPLOAD:
            if not answer.image_object_key:
                return GradeResult(
                    score=0.0,
                    max_score=max_marks,
                    justification="No image was uploaded for this question.",
                    confidence=1.0,
                )
            image_bytes = get_object_bytes(answer.image_object_key)
            if image_bytes is None:
                raise RuntimeError("Could not read the uploaded answer image from storage")
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": _media_type_for(answer.image_object_key),
                        "data": base64.standard_b64encode(image_bytes).decode("utf-8"),
                    },
                }
            )
            content.append(
                {
                    "type": "text",
                    "text": (
                        "CANDIDATE ANSWER: the handwritten image above. Transcribe it "
                        "mentally, then grade it against the model answer."
                    ),
                }
            )
        else:
            content.append(
                {
                    "type": "text",
                    "text": f"CANDIDATE ANSWER:\n{(answer.text_answer or '').strip()}",
                }
            )

        response = self._client.messages.parse(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_format=GradeResult,
        )
        result: GradeResult = response.parsed_output
        logger.info(
            "Graded answer %s with %s: %.2f/%.2f", answer.id, self.model, result.score, max_marks
        )
        return result.model_copy(update={"max_score": max_marks}).clamped()


def _media_type_for(key: str) -> str:
    lowered = key.lower()
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
