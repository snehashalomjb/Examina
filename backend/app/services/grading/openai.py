"""OpenAI-backed grader (GPT-4o and later).

Inactive by default, exactly like the Claude adapter: it is only constructed when
``GRADER_PROVIDER=openai`` and ``OPENAI_API_KEY`` is set, so nothing in the platform
hard-depends on a model being reachable.

Notes on the API shape used here:
- ``client.responses.parse(..., text_format=GradeResult)`` returns a validated Pydantic
  object on ``.output_parsed`` - no hand-rolled JSON parsing, no repair prompts.
- Handwritten ``image_upload`` answers are sent as a base64 ``input_image`` data URL.
- ``temperature=0`` because the same script must score the same on a re-grade.
"""

from __future__ import annotations

import base64

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.storage import get_object_bytes
from app.db.models import Answer, Question, QuestionType
from app.services.grading.base import GradeResult

logger = get_logger("grading.openai")

DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = (
    "You are an experienced examiner grading a written answer for a university-level "
    "examination. Award marks strictly against the model answer and rubric supplied. "
    "Give partial credit where the candidate demonstrates partial understanding. "
    "Never award more than the maximum marks. Justify the score in two or three "
    "sentences, naming what was present and what was missing. Be consistent: the same "
    "answer must always receive the same score."
)


class OpenAIGrader:
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "The 'openai' package is not installed. "
                "Install it with: uv pip install '.[openai]'"
            ) from exc

        # The shared GRADER_MODEL default names a Claude model, so an OpenAI deployment
        # that has not set its own model must not inherit it.
        self.model = model if model and not model.startswith("claude") else DEFAULT_MODEL
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

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
            {"type": "input_text", "text": self._rubric_prefix(question, max_marks)}
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
            encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
            media_type = _media_type_for(answer.image_object_key)
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{media_type};base64,{encoded}",
                    "detail": "high",
                }
            )
            transcript = (answer.ocr_text or "").strip()
            hint = (
                "CANDIDATE ANSWER: the handwritten image above. Read it, then grade it "
                "against the model answer."
            )
            if transcript:
                # The OCR pass is a hint, never the source of truth - the model sees the
                # image and is told to prefer it.
                hint += (
                    "\n\nAn OCR pre-pass read the image as the following. It is unreliable "
                    "on handwriting; trust the image where the two disagree.\n"
                    f"---\n{transcript[:4000]}\n---"
                )
            content.append({"type": "input_text", "text": hint})
        else:
            content.append(
                {
                    "type": "input_text",
                    "text": f"CANDIDATE ANSWER:\n{(answer.text_answer or '').strip()}",
                }
            )

        response = self._client.responses.parse(
            model=self.model,
            temperature=0,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": content}],
            text_format=GradeResult,
        )
        result: GradeResult | None = response.output_parsed
        if result is None:
            raise RuntimeError("The grader returned no parseable evaluation")

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
