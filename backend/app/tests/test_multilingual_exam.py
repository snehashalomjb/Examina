"""Exam-level language config, in-exam language switching, and translation generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AccessStatus, QuestionType, UserRole
from app.db.models.translations import OptionTranslation, QuestionTranslation
from app.tests.conftest import auth_headers, enroll, make_exam, make_question, make_subject, make_user


def _scenario(db: Session):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)
    question = make_question(db, subject, qtype=QuestionType.MCQ, body="What is an operating system?")
    db.add(QuestionTranslation(question_id=question.id, locale="hi", body="ऑपरेटिंग सिस्टम क्या है?"))
    for option, hi_text in zip(question.options, ["हार्डवेयर", "सॉफ्टवेयर", "नेटवर्क", "डेटाबेस"]):
        db.add(OptionTranslation(option_id=option.id, locale="hi", text=hi_text))
    db.flush()

    exam = make_exam(db, subject, examiner, questions=[question], candidates=[candidate])
    exam.enabled_languages = ["en", "hi", "ta"]
    db.flush()
    return {"subject": subject, "examiner": examiner, "candidate": candidate, "exam": exam, "question": question}


class TestExamLanguages:
    def test_languages_endpoint_always_leads_with_en(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["candidate"])
        resp = client.get(f"/api/v1/exams/{s['exam'].id}/languages", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["languages"] == ["en", "hi", "ta"]

    def test_exam_create_normalizes_and_validates_enabled_languages(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["examiner"])
        resp = client.post(
            "/api/v1/exams",
            headers=headers,
            json={
                "subject_id": str(s["subject"].id),
                "title": "Multilingual exam",
                "duration_minutes": 30,
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at": "2026-01-02T00:00:00Z",
                "selection_rules": {"rules": [{"question_type": "mcq", "count": 1}]},
                "enabled_languages": ["ta", "hi", "hi"],  # no "en", has a dup
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["languages"] == ["en", "ta", "hi"]

    def test_exam_create_rejects_unsupported_language(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["examiner"])
        resp = client.post(
            "/api/v1/exams",
            headers=headers,
            json={
                "subject_id": str(s["subject"].id),
                "title": "Bad language exam",
                "duration_minutes": 30,
                "starts_at": "2026-01-01T00:00:00Z",
                "ends_at": "2026-01-02T00:00:00Z",
                "selection_rules": {"rules": [{"question_type": "mcq", "count": 1}]},
                "enabled_languages": ["fr"],
            },
        )
        assert resp.status_code == 422


class TestInExamLanguageSwitch:
    def test_switching_language_changes_text_but_keeps_ids_answers_and_timer(
        self, client, db
    ) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["candidate"])

        started = client.post(f"/api/v1/exams/{s['exam'].id}/start", headers=headers)
        assert started.status_code == 200, started.text
        paper = started.json()
        session_id = paper["session_id"]
        exam_token = paper["exam_token"]
        question_id = paper["questions"][0]["question_id"]
        option_id = paper["questions"][0]["options"][0]["id"]

        # Save an answer before switching language.
        save = client.put(
            f"/api/v1/sessions/{session_id}/answers/{question_id}",
            headers={**headers, "X-Exam-Token": exam_token},
            json={"selected_option_ids": [option_id]},
        )
        assert save.status_code == 200, save.text

        # English by default.
        en = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert en.status_code == 200
        assert en.json()["locale"] == "en"
        assert en.json()["questions"][0]["body"] == "What is an operating system?"
        assert en.json()["available_languages"] == ["en", "hi", "ta"]

        # Switch to Hindi: text changes, ids and the saved answer do not.
        hi = client.get(f"/api/v1/sessions/{session_id}?lang=hi", headers=headers)
        assert hi.status_code == 200
        hi_body = hi.json()
        assert hi_body["locale"] == "hi"
        assert hi_body["questions"][0]["body"] == "ऑपरेटिंग सिस्टम क्या है?"
        assert hi_body["questions"][0]["question_id"] == question_id
        assert hi_body["questions"][0]["options"][0]["id"] == option_id
        assert hi_body["questions"][0]["saved_option_ids"] == [option_id]
        assert hi_body["session_id"] == session_id
        assert hi_body["seconds_remaining"] == en.json()["seconds_remaining"] or abs(
            hi_body["seconds_remaining"] - en.json()["seconds_remaining"]
        ) <= 2

        # A language this exam never enabled falls back to English rather than erroring.
        fallback = client.get(f"/api/v1/sessions/{session_id}?lang=kn", headers=headers)
        assert fallback.status_code == 200
        assert fallback.json()["locale"] == "en"

        # Switching language never touched the answer: re-fetching English still shows it.
        en_again = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert en_again.json()["questions"][0]["saved_option_ids"] == [option_id]


class TestGenerateTranslations:
    def test_generate_translations_returns_preview_without_saving(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["examiner"])
        question = s["question"]

        resp = client.post(
            f"/api/v1/questions/{question.id}/generate-translations",
            headers=headers,
            json={"locales": ["kn"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["provider"] == "stub"
        assert "kn" in body["translations"]
        # Nothing was persisted - no kn row exists until the examiner PATCHes it in.
        db.expire_all()
        rows = {r.locale for r in db.query(QuestionTranslation).filter_by(question_id=question.id)}
        assert "kn" not in rows

    def test_generate_translations_skips_existing_unless_overwrite(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["examiner"])
        question = s["question"]

        resp = client.post(
            f"/api/v1/questions/{question.id}/generate-translations",
            headers=headers,
            json={"locales": ["hi"]},  # already has a saved translation
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["skipped_existing"] == ["hi"]
        assert "hi" not in body["translations"]

        forced = client.post(
            f"/api/v1/questions/{question.id}/generate-translations",
            headers=headers,
            json={"locales": ["hi"], "overwrite_existing": True},
        )
        assert forced.status_code == 200, forced.text
        assert forced.json()["skipped_existing"] == []
        assert "hi" in forced.json()["translations"]

    def test_generate_translations_rejects_english_target(self, client, db) -> None:
        s = _scenario(db)
        headers = auth_headers(client, s["examiner"])
        resp = client.post(
            f"/api/v1/questions/{s['question'].id}/generate-translations",
            headers=headers,
            json={"locales": ["en"]},
        )
        assert resp.status_code == 422
