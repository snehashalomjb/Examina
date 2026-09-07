"""Grader factory.

Resolution order for a given exam:
1. ``exam.grading_config["grader_provider"]`` (per-exam override)
2. ``settings.GRADER_PROVIDER`` (deployment default)
3. ``stub`` (always available, offline)

Providers: ``stub`` (offline), ``claude``, ``openai``.

If a provider is requested but cannot be constructed - missing package, missing API key -
the factory logs it and falls back to the stub rather than failing a candidate's grading.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.grading.base import Grader, GradeResult
from app.services.grading.stub import StubGrader

logger = get_logger("grading")

__all__ = ["GradeResult", "Grader", "StubGrader", "get_grader"]


def get_grader(grading_config: dict | None = None) -> Grader:
    config = grading_config or {}
    provider = (config.get("grader_provider") or settings.GRADER_PROVIDER or "stub").lower()
    model = config.get("grader_model") or settings.GRADER_MODEL

    if provider == "stub":
        return StubGrader()

    if provider == "claude":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning(
                "GRADER_PROVIDER=claude but ANTHROPIC_API_KEY is unset - using the stub grader"
            )
            return StubGrader()
        try:
            from app.services.grading.claude import ClaudeGrader

            return ClaudeGrader(model=model)
        except Exception as exc:  # noqa: BLE001 - never fail grading over a config problem
            logger.error("Could not build the Claude grader (%s) - using the stub grader", exc)
            return StubGrader()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "GRADER_PROVIDER=openai but OPENAI_API_KEY is unset - using the stub grader"
            )
            return StubGrader()
        try:
            from app.services.grading.openai import OpenAIGrader

            return OpenAIGrader(model=model)
        except Exception as exc:  # noqa: BLE001 - never fail grading over a config problem
            logger.error("Could not build the OpenAI grader (%s) - using the stub grader", exc)
            return StubGrader()

    logger.warning("Unknown grader provider %r - using the stub grader", provider)
    return StubGrader()
