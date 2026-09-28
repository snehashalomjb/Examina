"""Exam-level language config and the exam-locked candidate locale.

The question bank is English-only: a translation row on file is never surfaced as
paper content, and question translation generation no longer exists.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AccessStatus, QuestionType, UserRole
from app.db.models.translations import OptionTranslation, QuestionTranslation
from app.tests.conftest import auth_headers, make_exam, make_question, make_subject, make_user


def _scenario(db: Session):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)
    question = make_question(db, subject, qtype=QuestionType.MCQ, body="What is an operating system?")
    db.add(QuestionTranslation(question_id=question.id, locale="hi", body="ऑपरेटिंग सिस्टम क्या है?"))
    for option, hi_text in zip(
        question.options, ["हार्डवेयर", "सॉफ्टवेयर", "नेटवर्क", "डेटाबेस"], strict=False
    ):
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


class TestExamLanguageIsLocked:
    """There is no in-exam language selector any more - the examiner's declared
    language (``Exam.primary_language``) is the sole source of truth, and a candidate
    cannot override it, whether by a UI control (removed) or by hand-crafting
    ``?lang=`` on the request. See ``_candidate_locale`` in ``exam_sessions.py``."""

    def test_lang_query_param_is_ignored_once_the_exam_has_a_declared_language(
        self, db
    ) -> None:
        from app.api.v1.exam_sessions import _candidate_locale

        s = _scenario(db)
        exam = s["exam"]
        exam.primary_language = "te"
        db.flush()

        candidate = s["candidate"]
        # Every attempt to override loses, including a saved preference and a
        # forged Accept-Language header - only the exam's own language wins.
        assert _candidate_locale(candidate, None, None, exam=exam) == "te"
        assert _candidate_locale(candidate, None, "en", exam=exam) == "te"
        assert _candidate_locale(candidate, None, "hi", exam=exam) == "te"
        assert _candidate_locale(candidate, "hi-IN,hi;q=0.9", "hi", exam=exam) == "te"

    def test_lang_query_param_is_ignored_even_for_an_english_exam(self, db) -> None:
        """An exam that never declared a language (the historical default, 'en')
        used to let the candidate's own preference or ``?lang=`` pick the paper's
        language. That is exactly the override this lock closes - 'en' is now just
        as authoritative as any other declared language."""
        from app.api.v1.exam_sessions import _candidate_locale

        s = _scenario(db)
        assert s["exam"].primary_language == "en"
        assert _candidate_locale(s["candidate"], None, "hi", exam=s["exam"]) == "en"

    def test_switching_language_via_the_api_never_changes_the_served_paper(
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

        save = client.put(
            f"/api/v1/sessions/{session_id}/answers/{question_id}",
            headers={**headers, "X-Exam-Token": exam_token},
            json={"selected_option_ids": [option_id]},
        )
        assert save.status_code == 200, save.text

        en = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
        assert en.status_code == 200
        assert en.json()["locale"] == "en"
        assert en.json()["questions"][0]["body"] == "What is an operating system?"

        # A candidate hand-crafting ?lang=hi gets exactly the same paper back - the
        # request is well-formed and 200s, but the content, locale and ids are
        # untouched, and the Hindi translation on file is never surfaced.
        attempt = client.get(f"/api/v1/sessions/{session_id}?lang=hi", headers=headers)
        assert attempt.status_code == 200
        body = attempt.json()
        assert body["locale"] == "en"
        assert body["questions"][0]["body"] == "What is an operating system?"
        assert body["questions"][0]["question_id"] == question_id
        assert body["questions"][0]["options"][0]["id"] == option_id
        assert body["questions"][0]["saved_option_ids"] == [option_id]
        assert body["session_id"] == session_id
