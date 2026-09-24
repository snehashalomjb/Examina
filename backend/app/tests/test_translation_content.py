"""Machine translation of exam content: the Google provider and the bulk script.

No network here. The provider's HTTP client is replaced with a fake, since what matters
is what goes *around* the call: technical terms survive untouched, and a rate-limited
or unreachable service surfaces as an error instead of English text saved as Hindi.
"""

from __future__ import annotations

import pytest

from app.db.models import UserRole
from app.db.models.translations import OptionTranslation, QuestionTranslation
from app.services.translation import google as google_mod
from app.services.translation.google import GoogleTranslator, _shield, _unshield
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)
from app.translate_content import apply, collect, enable_locale


class TestShielding:
    def test_sql_keywords_and_acronyms_are_kept_out_of_translation(self):
        text = "Which clause follows GROUP BY in SQL? Use COUNT() or `avg_salary`."
        shielded, kept = _shield(text)
        assert "GROUP" not in shielded and "COUNT()" not in shielded
        assert "`avg_salary`" in kept
        assert _unshield(shielded, kept) == text

    def test_spaces_google_adds_inside_placeholders_are_tolerated(self):
        assert _unshield("[[ 0 ]] से पहले", ["WHERE"]) == "WHERE से पहले"


class _FakeGoogle:
    calls: list[str] = []

    def __init__(self, source: str, target: str) -> None:
        self.target = target

    def translate(self, text: str) -> str:
        _FakeGoogle.calls.append(text)
        return f"<{self.target}>{text}"


@pytest.fixture
def fake_google(monkeypatch):
    import deep_translator

    _FakeGoogle.calls = []
    monkeypatch.setattr(deep_translator, "GoogleTranslator", _FakeGoogle)
    return _FakeGoogle


class TestGoogleTranslator:
    def test_every_non_empty_field_is_translated_and_terms_restored(self, fake_google):
        out = GoogleTranslator().translate(
            texts={"body": "What does SELECT return?", "explanation": ""}, target_locale="hi"
        )
        assert out == {"body": "<hi>What does SELECT return?"}
        assert "SELECT" not in fake_google.calls[0]

    def test_a_rate_limit_becomes_a_plain_error(self, monkeypatch):
        import deep_translator
        from deep_translator.exceptions import TooManyRequests

        class Limited(_FakeGoogle):
            def translate(self, text: str) -> str:
                raise TooManyRequests()

        monkeypatch.setattr(deep_translator, "GoogleTranslator", Limited)
        monkeypatch.setattr(google_mod.time, "sleep", lambda _s: None)
        with pytest.raises(RuntimeError, match="rate-limiting"):
            GoogleTranslator().translate(texts={"body": "Hello"}, target_locale="hi")

    def test_endpoint_reports_an_unavailable_service_as_503(self, client, db, monkeypatch):
        from app.core.config import settings

        class Broken(_FakeGoogle):
            def translate(self, text: str) -> str:
                raise ConnectionError("captcha")

        import deep_translator

        monkeypatch.setattr(deep_translator, "GoogleTranslator", Broken)
        monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "google")
        examiner = make_user(db, role=UserRole.EXAMINER)
        question = make_question(db, make_subject(db), created_by=examiner)
        response = client.post(
            f"/api/v1/questions/{question.id}/generate-translations",
            headers=auth_headers(client, examiner),
            json={"locales": ["hi"]},
        )
        assert response.status_code == 503, response.text
        assert "unavailable" in response.json()["detail"].lower()


class TestBulkContentTranslation:
    def test_collect_then_apply_writes_hindi_rows_and_enables_the_locale(self, db):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        question = make_question(db, subject, created_by=examiner)
        exam = make_exam(db, subject, examiner, questions=[question])
        exams, items = collect(db, "hi", overwrite=False, exam_ids=[exam.id])
        kinds = {i["kind"] for i in items}
        assert {"exam", "question", "option"} <= kinds

        for item in items:
            item["fields"] = {k: f"हिन्दी {v}" for k, v in item["fields"].items()}
        written = apply(db, "hi", items)
        assert written == len(items)
        assert enable_locale(exams, "hi") == 1
        db.flush()

        assert "hi" in exam.languages
        assert db.query(QuestionTranslation).filter_by(locale="hi").count() >= 1
        assert db.query(OptionTranslation).filter_by(locale="hi").count() >= 1

        # Nothing left to do on a second pass; re-enabling is a no-op.
        db.expire_all()
        _exams, again = collect(db, "hi", overwrite=False, exam_ids=[exam.id])
        assert again == []
        assert enable_locale(_exams, "hi") == 0
