"""The translator seam.

Nothing in the platform depends on a translation provider being configured. Everything
talks to ``Translator``; the active implementation is chosen at runtime from settings -
same shape as ``app.services.grading``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

#: English display name per locale, for prompting a translation model. Not the same as
#: the frontend's ``LOCALE_NAMES`` (which is each language's own name, for the UI) - this
#: one is always English, because that is what a translation prompt needs to say.
LOCALE_LABELS: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
}


@runtime_checkable
class Translator(Protocol):
    """Implemented by every translation backend."""

    name: str

    def translate(self, *, texts: dict[str, str], target_locale: str) -> dict[str, str]:
        """Translate every value in ``texts`` into ``target_locale``, keys unchanged.

        Blank values are skipped (an empty explanation stays empty rather than becoming
        a translated empty string). Implementations should preserve well-known technical
        terms (e.g. "Machine Learning", "SQL", "API") rather than translating them
        literally, appending the English term in brackets where useful.
        """
        ...
