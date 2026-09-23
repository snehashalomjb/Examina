"""Offline translator - the default provider.

Returns the source text unchanged for every field, so the examiner's "Generate
Translations" preview is honestly a no-op: every field is clearly still English and
begs to be edited, rather than a plausible-looking translation nobody asked for. This
keeps the whole draft -> review -> publish pipeline exercisable (and testable) with no
network call and no API key, exactly like ``app.services.grading.stub``.
"""

from __future__ import annotations


class StubTranslator:
    name = "stub"

    def translate(self, *, texts: dict[str, str], target_locale: str) -> dict[str, str]:
        return {key: value for key, value in texts.items() if value and value.strip()}
