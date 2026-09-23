"""Locale resolution, translation fallback and the grading-language invariant."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Question, QuestionOption
from app.db.models.translations import OptionTranslation, QuestionTranslation
from app.services.i18n import resolve_locale, translated_field, upsert_translations
from app.tests.conftest import auth_headers, make_question, make_subject, make_user


def test_resolve_locale_precedence() -> None:
    # explicit query param wins over everything
    assert resolve_locale(query_lang="te", user_locale="hi", accept_language="ta") == "te"
    # then the signed-in user's own preference
    assert resolve_locale(query_lang=None, user_locale="hi", accept_language="ta") == "hi"
    # then the Accept-Language header
    assert resolve_locale(query_lang=None, user_locale=None, accept_language="ta-IN,ta;q=0.9") == "ta"
    # unsupported/garbled values are ignored, not fatal
    assert resolve_locale(query_lang="xx", user_locale=None, accept_language=None) == "en"
    assert resolve_locale(query_lang=None, user_locale=None, accept_language=None) == "en"


def test_translated_field_falls_back_locale_then_en_then_base(db: Session) -> None:
    subject = make_subject(db)
    question = make_question(db, subject, body="What is 2+2?")
    db.add(QuestionTranslation(question_id=question.id, locale="en", body="What is 2+2?"))
    db.add(QuestionTranslation(question_id=question.id, locale="hi", body="2+2 क्या है?"))
    db.flush()
    db.refresh(question)

    # a locale with a real row gets its own text
    assert (
        translated_field(question.body, question.translations, "hi", "body") == "2+2 क्या है?"
    )
    # a locale with no row at all falls back to the en row
    assert (
        translated_field(question.body, question.translations, "te", "body") == "What is 2+2?"
    )
    # no translations at all falls back to the base column, never blank
    assert translated_field("fallback", [], "te", "body") == "fallback"


def test_upsert_translations_writes_en_from_base_and_other_locales(db: Session) -> None:
    subject = make_subject(db)
    question = make_question(db, subject, body="Original body")

    upsert_translations(
        db,
        model_cls=QuestionTranslation,
        parent_fk="question_id",
        parent_id=question.id,
        kind="question",
        base_values={"body": question.body, "model_answer": None, "explanation": None},
        translations_payload={"te": {"body": "తెలుగు వచనం"}},
    )
    db.flush()

    rows = {r.locale: r for r in db.query(QuestionTranslation).filter_by(question_id=question.id)}
    assert rows["en"].body == "Original body"
    assert rows["te"].body == "తెలుగు వచనం"

    # calling again with a changed base value updates the existing en row rather than
    # duplicating it - the (parent_id, locale) unique constraint is the write-path contract.
    upsert_translations(
        db,
        model_cls=QuestionTranslation,
        parent_fk="question_id",
        parent_id=question.id,
        kind="question",
        base_values={"body": "Edited body", "model_answer": None, "explanation": None},
        translations_payload=None,
    )
    db.flush()
    count = db.query(QuestionTranslation).filter_by(question_id=question.id, locale="en").count()
    assert count == 1


def test_get_question_falls_back_to_english_when_locale_missing(db: Session, client) -> None:
    examiner = make_user(db, role=__import__("app.db.models", fromlist=["UserRole"]).UserRole.EXAMINER)
    subject = make_subject(db)
    question = make_question(db, subject, body="English body")
    headers = auth_headers(client, examiner)

    resp = client.get(f"/api/v1/questions/{question.id}?lang=te", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["body"] == "English body"


def test_get_question_returns_locale_text_when_translation_exists(db: Session, client) -> None:
    from app.db.models import UserRole

    examiner = make_user(db, role=UserRole.EXAMINER)
    subject = make_subject(db)
    question = make_question(db, subject, body="English body")
    db.add(QuestionTranslation(question_id=question.id, locale="hi", body="हिन्दी वाक्य"))
    for option in question.options:
        db.add(OptionTranslation(option_id=option.id, locale="hi", text=f"{option.text} (hi)"))
    db.flush()
    headers = auth_headers(client, examiner)

    resp = client.get(f"/api/v1/questions/{question.id}?lang=hi", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["body"] == "हिन्दी वाक्य"
    assert all(o["text"].endswith("(hi)") for o in body["options"])


def test_create_question_writes_translations_payload(db: Session, client) -> None:
    from app.db.models import UserRole

    examiner = make_user(db, role=UserRole.EXAMINER)
    subject = make_subject(db)
    headers = auth_headers(client, examiner)

    resp = client.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "subject_id": str(subject.id),
            "question_type": "mcq",
            "body": "What is the capital of France?",
            "marks": 1,
            "options": [
                {"text": "Paris", "is_correct": True, "order_index": 0},
                {"text": "Lyon", "is_correct": False, "order_index": 1},
            ],
            "translations": {"te": {"body": "ఫ్రాన్స్ రాజధాని ఏది?"}},
        },
    )
    assert resp.status_code == 201, resp.text
    question_id = resp.json()["id"]

    rows = {
        r.locale: r for r in db.query(QuestionTranslation).filter_by(question_id=question_id)
    }
    assert rows["en"].body == "What is the capital of France?"
    assert rows["te"].body == "ఫ్రాన్స్ రాజధాని ఏది?"


def test_grading_context_always_reads_base_english_columns() -> None:
    """The subjective-grading prompt builder reads ``question.body``/``model_answer``
    directly - i.e. the base ORM columns - never a locale-resolved string, so a candidate
    who answered in Telugu is graded against the same canonical rubric as one who saw the
    English version. This is a static/structural check: translated_field is simply never
    called in that code path."""
    import inspect

    from app.services.grading.openai import OpenAIGrader

    source = inspect.getsource(OpenAIGrader._rubric_prefix)
    assert "translated_field" not in source
    assert "question.body" in source
    assert "question.model_answer" in source
