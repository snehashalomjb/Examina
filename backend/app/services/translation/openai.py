"""OpenAI-backed translator.

Inactive by default: it is only constructed when ``TRANSLATION_PROVIDER=openai`` and a
key is set (``TRANSLATION_API_KEY``, falling back to ``OPENAI_API_KEY``), so nothing in
the platform hard-depends on a model being reachable. Mirrors
``app.services.grading.openai`` - ``client.responses.parse(..., text_format=...)``
returns a validated Pydantic object, no hand-rolled JSON parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, create_model

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.translation.base import LOCALE_LABELS

logger = get_logger("translation.openai")

DEFAULT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are translating examination content (question text, answer options, "
    "instructions, explanations) from English into {language}. Translate naturally and "
    "precisely for a student audience. Preserve well-known technical and academic terms "
    "that are commonly used in English even in {language} speech or writing (for example: "
    "Machine Learning, Artificial Intelligence, Python, SQL, API, HTTP, Neural Network, "
    "React, JavaScript, FastAPI, PostgreSQL) - keep the term in English and, if it "
    "clarifies meaning, follow it with the {language} equivalent in brackets. Never "
    "translate proper nouns, code, or numbers. Return every key you were given, "
    "translated; never leave a key out and never return an empty string for a non-empty "
    "input."
)


class OpenAITranslator:
    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "The 'openai' package is not installed. "
                "Install it with: uv pip install '.[openai]'"
            ) from exc

        self.model = model or settings.TRANSLATION_MODEL or DEFAULT_MODEL
        api_key = settings.TRANSLATION_API_KEY or settings.OPENAI_API_KEY
        self._client = OpenAI(api_key=api_key)

    def translate(self, *, texts: dict[str, str], target_locale: str) -> dict[str, str]:
        non_empty = {k: v for k, v in texts.items() if v and v.strip()}
        if not non_empty:
            return {}

        language = LOCALE_LABELS.get(target_locale, target_locale)
        # A field-per-property schema built at call time, so the model's structured
        # output is validated against exactly the keys we asked it to translate.
        fields = {key: (str, ...) for key in non_empty}
        ResponseModel: type[BaseModel] = create_model("TranslationResponse", **fields)  # type: ignore[call-overload]

        response = self._client.responses.parse(
            model=self.model,
            temperature=0,
            instructions=SYSTEM_PROMPT.format(language=language),
            input=[{"role": "user", "content": [{"type": "input_text", "text": str(non_empty)}]}],
            text_format=ResponseModel,
        )
        result = response.output_parsed
        if result is None:
            raise RuntimeError("The translator returned no parseable output")

        logger.info(
            "Translated %d field(s) to %s with %s", len(non_empty), target_locale, self.model
        )
        return result.model_dump()
