"""The exam's own language: persisted, validated, and what the candidate is shown.

Covers the contract added alongside ``Exam.primary_language``:

- the wizard's "Exam Language" round-trips through create/read/update,
- an unsupported code is rejected rather than silently stored,
- the exam's declared language is locked and authoritative: the candidate is sat in it
  regardless of their own preference, and cannot override it via ``?lang=`` - there is
  no in-exam language selector any more, and the backend must not honour one smuggled
  in by hand (see ``_candidate_locale`` in ``exam_sessions.py``),
- an *English* exam (no declared language) is locked to English the same way,
- the question bank defaults to English when no content ``language`` is given, a saved
  translation row is never surfaced as paper content, and passing ``language`` genuinely
  scopes the browse to that content language (used for standalone-language banks like
  Kannada - see ``app.seed_kannada_question_bank``) rather than being ignored.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AccessStatus, QuestionType, UserRole
from app.db.models.translations import QuestionTranslation
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)

API = "/api/v1"

TAMIL = "ஒழுங்குபடுத்தும் அமைப்பு என்றால் என்ன?"


def _scenario(db: Session, *, language: str = "ta", candidate_locale: str = "en"):
    """A published, enrolled, one-question exam declaring ``language``."""
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)
    candidate.preferred_locale = candidate_locale
    question = make_question(
        db, subject, qtype=QuestionType.MCQ, body="What is an operating system?"
    )
    db.add(QuestionTranslation(question_id=question.id, locale="ta", body=TAMIL))
    exam = make_exam(db, subject, examiner, questions=[question], candidates=[candidate])
    exam.primary_language = language
    db.flush()
    return {
        "subject": subject,
        "examiner": examiner,
        "candidate": candidate,
        "exam": exam,
        "question": question,
    }


def _create(client, db, scenario, **overrides):
    """POST /exams with a minimal valid body, plus any field under test."""
    body = {
        "subject_id": str(scenario["subject"].id),
        "title": "An exam",
        "duration_minutes": 30,
        "starts_at": "2026-01-01T00:00:00Z",
        "ends_at": "2026-01-02T00:00:00Z",
        "selection_rules": {"rules": [{"question_type": "mcq", "count": 1}]},
    }
    body.update(overrides)
    return client.post(
        f"{API}/exams", headers=auth_headers(client, scenario["examiner"]), json=body
    )


class TestExamLanguagePersistence:
    def test_create_saves_and_returns_the_exam_language(self, client, db) -> None:
        s = _scenario(db)
        resp = _create(client, db, s, title="Tamil exam", primary_language="ta")
        assert resp.status_code == 201, resp.text
        assert resp.json()["primary_language"] == "ta"

    def test_exam_language_defaults_to_english(self, client, db) -> None:
        s = _scenario(db, language="en")
        resp = client.get(
            f"{API}/exams/{s['exam'].id}", headers=auth_headers(client, s["examiner"])
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["primary_language"] == "en"

    def test_unsupported_exam_language_is_rejected(self, client, db) -> None:
        s = _scenario(db)
        assert _create(client, db, s, primary_language="fr").status_code == 422

    def test_update_changes_the_exam_language(self, client, db) -> None:
        s = _scenario(db, language="en")
        resp = client.patch(
            f"{API}/exams/{s['exam'].id}",
            headers=auth_headers(client, s["examiner"]),
            json={"primary_language": "kn"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["primary_language"] == "kn"


class TestCandidateSeesTheExamLanguage:
    def _start(self, client, scenario):
        headers = auth_headers(client, scenario["candidate"])
        resp = client.post(f"{API}/exams/{scenario['exam'].id}/start", headers=headers)
        assert resp.status_code == 200, resp.text
        return headers, resp.json()

    def test_non_english_exam_reports_its_locale_but_content_is_english(
        self, client, db
    ) -> None:
        # The candidate asked for English; the examiner declared a Tamil paper. The
        # exam's language is still reported, but the question bank is English-only, so
        # the paper's content is the English base text even with a Tamil row on file.
        s = _scenario(db, language="ta", candidate_locale="en")
        _, paper = self._start(client, s)
        assert paper["locale"] == "ta"
        assert paper["questions"][0]["body"] == "What is an operating system?"

    def test_explicit_lang_query_param_is_ignored(self, client, db) -> None:
        # A candidate hand-crafting ?lang=hi on a Tamil exam gets Tamil back anyway -
        # the examiner's declared language is the only source of truth, never a
        # request parameter the candidate controls.
        s = _scenario(db, language="ta", candidate_locale="en")
        headers, paper = self._start(client, s)
        resp = client.get(
            f"{API}/sessions/{paper['session_id']}?lang=hi", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["locale"] == "ta"
        assert resp.json()["questions"][0]["body"] == "What is an operating system?"

    def test_english_exam_is_locked_to_english_regardless_of_candidate_preference(
        self, client, db
    ) -> None:
        # An exam with no declared language is English, and that is now just as locked
        # as any declared language - a Tamil-reading candidate does not get a Tamil
        # rendering of an English exam any more.
        s = _scenario(db, language="en", candidate_locale="ta")
        _, paper = self._start(client, s)
        assert paper["locale"] == "en"

    def test_exam_language_is_offered_on_the_candidate_card(self, client, db) -> None:
        s = _scenario(db, language="kn", candidate_locale="en")
        resp = client.get(f"{API}/my/exams", headers=auth_headers(client, s["candidate"]))
        assert resp.status_code == 200, resp.text
        card = next(c for c in resp.json() if c["exam_id"] == str(s["exam"].id))
        assert "kn" in card["available_languages"]


class TestBankIsEnglishOnly:
    def test_lang_display_filter_never_changes_the_bank(self, client, db) -> None:
        """``lang`` only ever picks a display-label locale for subjects/translations - it
        is not a content filter, so it never changes which questions come back or what
        their own text is (a saved translation row is never surfaced as paper content)."""
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        question = make_question(db, subject, qtype=QuestionType.MCQ, body="English only one")
        db.add(QuestionTranslation(question_id=question.id, locale="ml", body="വിവർത്തനം ചെയ്തത്"))
        db.flush()
        headers = auth_headers(client, examiner)

        for extra in ("", "&lang=ml", "&lang=ml&translated_only=true"):
            resp = client.get(f"{API}/questions?subject_id={subject.id}{extra}", headers=headers)
            assert resp.status_code == 200, resp.text
            rows = resp.json()
            assert [r["body"] for r in rows] == ["English only one"]
            assert [r["language"] for r in rows] == ["en"]

    def test_content_language_param_genuinely_scopes_the_bank(self, client, db) -> None:
        """Unlike ``lang``, ``language`` is a real content filter: omitted, the bank
        defaults to English as always; given, it returns only that language's own rows -
        never a translation of the English question - and nothing else for that subject."""
        subject = make_subject(db)
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        make_question(db, subject, qtype=QuestionType.MCQ, body="English only one")
        db.flush()
        headers = auth_headers(client, examiner)

        resp = client.get(f"{API}/questions?subject_id={subject.id}&language=hi", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

        resp = client.get(f"{API}/questions?subject_id={subject.id}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert [r["body"] for r in resp.json()] == ["English only one"]


def _exam_payload(subject_id, **overrides) -> dict:
    payload = {
        "subject_id": str(subject_id),
        "title": "Language/subject validation exam",
        "duration_minutes": 30,
        "starts_at": "2026-01-01T00:00:00Z",
        "ends_at": "2026-01-02T00:00:00Z",
        "selection_rules": {"rules": [{"question_type": "mcq", "count": 1}]},
    }
    payload.update(overrides)
    return payload


class TestSubjectMustMatchExamLanguage:
    """A subject whose own content is a different language than the exam's declared one
    is an invalid combination - e.g. a Kannada-only subject on an English or Malayalam
    exam - and the backend must refuse it, not just hide it in the dropdown."""

    def test_kannada_only_subject_is_rejected_for_an_english_exam(self, client, db) -> None:
        subject = make_subject(db, code="KA-AI")
        question = make_question(db, subject, qtype=QuestionType.MCQ)
        question.language = "kn"
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        db.flush()
        headers = auth_headers(client, examiner)

        resp = client.post(f"{API}/exams", headers=headers, json=_exam_payload(subject.id))
        assert resp.status_code == 422, resp.text

    def test_kannada_only_subject_is_rejected_for_a_malayalam_exam(self, client, db) -> None:
        subject = make_subject(db, code="KA-AI")
        question = make_question(db, subject, qtype=QuestionType.MCQ)
        question.language = "kn"
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        db.flush()
        headers = auth_headers(client, examiner)

        resp = client.post(
            f"{API}/exams",
            headers=headers,
            json=_exam_payload(subject.id, primary_language="ml", enabled_languages=["ml"]),
        )
        assert resp.status_code == 422, resp.text

    def test_kannada_only_subject_is_accepted_for_a_kannada_exam(self, client, db) -> None:
        subject = make_subject(db, code="KA-AI")
        question = make_question(db, subject, qtype=QuestionType.MCQ)
        question.language = "kn"
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        db.flush()
        headers = auth_headers(client, examiner)

        resp = client.post(
            f"{API}/exams",
            headers=headers,
            json=_exam_payload(subject.id, primary_language="kn", enabled_languages=["kn"]),
        )
        assert resp.status_code == 201, resp.text

    def test_a_brand_new_subject_with_no_questions_yet_is_accepted_for_any_language(
        self, client, db
    ) -> None:
        """An examiner may create a subject from the exam wizard and author its first
        question afterwards - it has no language of its own yet, so it is never a
        mismatch, whatever language the exam declares."""
        subject = make_subject(db, code="BRAND-NEW")
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        db.flush()
        headers = auth_headers(client, examiner)

        resp = client.post(
            f"{API}/exams",
            headers=headers,
            json=_exam_payload(subject.id, primary_language="kn", enabled_languages=["kn"]),
        )
        assert resp.status_code == 201, resp.text

    def test_update_rejects_moving_to_a_mismatched_subject(self, client, db) -> None:
        english_subject = make_subject(db, code="ENG-SUBJ")
        make_question(db, english_subject, qtype=QuestionType.MCQ)
        kn_subject = make_subject(db, code="KA-AI")
        kn_question = make_question(db, kn_subject, qtype=QuestionType.MCQ)
        kn_question.language = "kn"
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        db.flush()
        headers = auth_headers(client, examiner)

        create = client.post(
            f"{API}/exams", headers=headers, json=_exam_payload(english_subject.id)
        )
        assert create.status_code == 201, create.text
        exam_id = create.json()["id"]

        resp = client.patch(
            f"{API}/exams/{exam_id}", headers=headers, json={"subject_id": str(kn_subject.id)}
        )
        assert resp.status_code == 422, resp.text
