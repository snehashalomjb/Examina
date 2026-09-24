"""Translator factory.

Resolution order: ``settings.TRANSLATION_PROVIDER`` (``stub`` | ``google`` | ``openai``), falling
back to the stub if a provider is requested but cannot be constructed - missing
package, missing key - so "Generate Translations" degrades to a clearly-unfinished
draft rather than a 500. Same shape as ``app.services.grading``.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.translation.base import LOCALE_LABELS, Translator
from app.services.translation.stub import StubTranslator

logger = get_logger("translation")

__all__ = ["LOCALE_LABELS", "StubTranslator", "Translator", "get_translator"]


def get_translator() -> Translator:
    provider = (settings.TRANSLATION_PROVIDER or "stub").lower()

    if provider == "stub":
        return StubTranslator()

    if provider == "google":
        try:
            from app.services.translation.google import GoogleTranslator

            return GoogleTranslator()
        except Exception as exc:  # noqa: BLE001 - never fail the request over a config problem
            logger.error("Could not build the Google translator (%s) - using the stub", exc)
            return StubTranslator()

    if provider == "openai":
        api_key = settings.TRANSLATION_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            logger.warning(
                "TRANSLATION_PROVIDER=openai but no TRANSLATION_API_KEY/OPENAI_API_KEY is "
                "set - using the stub translator"
            )
            return StubTranslator()
        try:
            from app.services.translation.openai import OpenAITranslator

            return OpenAITranslator(model=settings.TRANSLATION_MODEL)
        except Exception as exc:  # noqa: BLE001 - never fail the request over a config problem
            logger.error("Could not build the OpenAI translator (%s) - using the stub", exc)
            return StubTranslator()

    logger.warning("Unknown translation provider %r - using the stub translator", provider)
    return StubTranslator()
