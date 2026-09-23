"""Locale resolution and translated-field lookup for multilingual content.

Reading translated text never requires a caller to know whether a translation
exists: :func:`translated_field` always falls back ``locale -> en -> base column``,
so a candidate never sees blank content because a translator hasn't reached a
row yet. Writing goes through :func:`upsert_translations`, which treats writing
the base column as sugar for writing the ``en`` row - every existing caller
that only ever set ``question.body`` etc keeps working unmodified.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.db.models.enums import DEFAULT_LOCALE, SUPPORTED_LOCALES


class _HasLocale(Protocol):
    locale: str


def _normalize(code: str | None) -> str | None:
    if not code:
        return None
    base = code.strip().split("-")[0].split("_")[0].lower()
    return base if base in SUPPORTED_LOCALES else None


def _parse_accept_language(header: str | None) -> list[str]:
    if not header:
        return []
    # "te-IN,te;q=0.9,en;q=0.8" -> ["te-IN", "te", "en"], ignoring q-weights (we only
    # need the first supported match, not a full weighted negotiation).
    return [part.split(";")[0].strip() for part in header.split(",") if part.strip()]


def resolve_locale(
    *,
    query_lang: str | None = None,
    user_locale: str | None = None,
    accept_language: str | None = None,
) -> str:
    """Precedence: explicit ``?lang=`` > the signed-in user's preference > the browser's
    ``Accept-Language`` header > ``en``. Anything outside ``SUPPORTED_LOCALES`` is ignored
    rather than raising, so a stray/garbled header never 500s a request.
    """
    for candidate in (query_lang, user_locale, *_parse_accept_language(accept_language)):
        normalized = _normalize(candidate)
        if normalized:
            return normalized
    return DEFAULT_LOCALE


def translated_field(
    base_value: str | None,
    translations: list[_HasLocale],
    locale: str,
    field: str,
) -> str | None:
    """``locale`` row's ``field`` -> the ``en`` row's ``field`` -> ``base_value``.

    Blank/None values at a given step are treated as "not translated yet" and fall
    through, so a translation row that exists but hasn't filled every field yet still
    resolves sensibly rather than showing an empty string.
    """
    by_locale = {t.locale: t for t in translations}

    row = by_locale.get(locale)
    if row is not None:
        value = getattr(row, field, None)
        if value:
            return value

    if locale != DEFAULT_LOCALE:
        en_row = by_locale.get(DEFAULT_LOCALE)
        if en_row is not None:
            value = getattr(en_row, field, None)
            if value:
                return value

    return base_value


#: Translatable field names per parent model, shared by the read and write paths so
#: there is exactly one list to update when a new translatable field is added.
TRANSLATABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "question": ("body", "model_answer", "explanation"),
    "option": ("text",),
    "exam": (
        "title",
        "description",
        "instructions",
        "course",
        "department",
        "semester",
        "company_name",
        "job_role",
    ),
    "subject": ("name", "description"),
    "exam_section": ("name", "description"),
}


def upsert_translations(
    db: Session,
    *,
    model_cls: type,
    parent_fk: str,
    parent_id: uuid.UUID,
    kind: str,
    base_values: dict[str, Any],
    translations_payload: dict[str, dict[str, str]] | None,
) -> None:
    """Upsert per-locale rows for one parent record.

    ``base_values`` is whatever the caller just wrote to the base columns (e.g. the
    ``body``/``model_answer``/``explanation`` a legacy single-locale caller sent) - it is
    always upserted as the ``en`` row unless ``translations_payload`` explicitly overrides
    ``en`` itself. Every other locale in ``translations_payload`` is upserted as-is;
    locales the caller didn't send are simply left alone (read-side fallback covers them).
    """
    allowed_fields = set(TRANSLATABLE_FIELDS[kind])
    payload = {k: v for k, v in (translations_payload or {}).items() if k in SUPPORTED_LOCALES}

    merged: dict[str, dict[str, str]] = {"en": dict(base_values)}
    for locale, fields in payload.items():
        merged.setdefault(locale, {})
        merged[locale].update({k: v for k, v in fields.items() if k in allowed_fields})

    existing_rows = {
        row.locale: row
        for row in db.query(model_cls).filter(getattr(model_cls, parent_fk) == parent_id).all()
    }

    for locale, fields in merged.items():
        if not fields:
            continue
        row = existing_rows.get(locale)
        if row is None:
            row = model_cls(**{parent_fk: parent_id, "locale": locale})
            db.add(row)
        for field, value in fields.items():
            setattr(row, field, value)
