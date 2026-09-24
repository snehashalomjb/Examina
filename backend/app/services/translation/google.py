"""Google Translate-backed translator (free web endpoint, no API key).

Uses ``deep-translator``'s ``GoogleTranslator``, which calls the same public endpoint the
translate.google.com page uses. No key and no billing, which makes it the practical
default for a demo or a development box - but it is unofficial: Google rate-limits it
and will serve a captcha to an IP it considers too busy. Every failure is raised as a
``RuntimeError`` with a plain message, so the caller can say "translation is unavailable
right now" instead of saving English text labelled as Hindi.

Technical terms examiners write in English (SQL, API, Python ...) are shielded from
translation with placeholder tokens and restored afterwards - Google would otherwise
render "SELECT" or "ORDER BY" as ordinary words, which breaks a SQL question.
"""

from __future__ import annotations

import re
import time

from app.core.logging_config import get_logger

logger = get_logger("translation.google")

#: Google's endpoint rejects a single request much above this; long fields are split.
_MAX_CHARS = 4500
_RETRIES = 3

#: Terms kept in English. Matched case-sensitively as whole words, plus anything in
#: backticks and any all-caps token of 2+ letters (SQL keywords, acronyms).
_KEEP_TERMS = (
    "Machine Learning", "Artificial Intelligence", "Deep Learning", "Neural Network",
    "Python", "Java", "JavaScript", "TypeScript", "React", "FastAPI", "PostgreSQL",
    "MySQL", "Docker", "Kubernetes", "Linux", "Git", "NumPy", "Pandas",
)
_PROTECT = re.compile(
    r"`[^`]+`"
    r"|\b(?:" + "|".join(re.escape(t) for t in _KEEP_TERMS) + r")\b"
    r"|\b[A-Z][A-Z0-9_]{1,}(?:\(\))?"
    r"|\b\w+\(\)"
)


def _shield(text: str) -> tuple[str, list[str]]:
    kept: list[str] = []

    def keep(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"[[{len(kept) - 1}]]"

    return _PROTECT.sub(keep, text), kept


def _unshield(text: str, kept: list[str]) -> str:
    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return kept[index] if index < len(kept) else match.group(0)

    # Google sometimes adds spaces inside the brackets - "[[ 0 ]]" - tolerate that.
    return re.sub(r"\[\[\s*(\d+)\s*\]\]", restore, text)


def _chunks(text: str) -> list[str]:
    if len(text) <= _MAX_CHARS:
        return [text]
    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.?!\n])\s+", text):
        if current and len(current) + len(sentence) + 1 > _MAX_CHARS:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


class GoogleTranslator:
    name = "google"

    def __init__(self) -> None:
        try:
            from deep_translator import GoogleTranslator as _Google  # noqa: F401
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError(
                "The 'deep-translator' package is not installed on the server."
            ) from exc

    def _translate_one(self, text: str, target_locale: str) -> str:
        from deep_translator import GoogleTranslator as _Google
        from deep_translator.exceptions import TooManyRequests

        client = _Google(source="en", target=target_locale)
        shielded, kept = _shield(text)
        out: list[str] = []
        for chunk in _chunks(shielded):
            for attempt in range(_RETRIES):
                try:
                    out.append(client.translate(chunk) or chunk)
                    break
                except TooManyRequests as exc:
                    if attempt == _RETRIES - 1:
                        raise RuntimeError(
                            "Google Translate is rate-limiting this server. Try again "
                            "in a few minutes."
                        ) from exc
                    time.sleep(2 * (attempt + 1))
                except Exception as exc:  # noqa: BLE001 - network, parsing, captcha page
                    raise RuntimeError(f"Google Translate failed: {exc}") from exc
        return _unshield(" ".join(out), kept)

    def translate(self, *, texts: dict[str, str], target_locale: str) -> dict[str, str]:
        non_empty = {k: v for k, v in texts.items() if v and v.strip()}
        result = {
            key: self._translate_one(value, target_locale) for key, value in non_empty.items()
        }
        logger.info("Translated %d field(s) to %s with google", len(result), target_locale)
        return result
