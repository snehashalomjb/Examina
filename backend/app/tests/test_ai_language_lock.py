"""AI-generated drafts live in the English-only question bank: a non-English
generation request is refused outright, a draft carries its language explicitly (not
inferred from prompt text), and approval stamps ``Question.language`` while refusing
any draft that declares a non-English language.
"""

from __future__ import annotations

from app.db.models import DraftStatus, Question, UserRole
from app.tests.conftest import auth_headers, make_subject, make_user


class TestLanguageDirectiveInThePrompt:
    def test_non_english_request_gets_a_strict_directive(self):
        from app.api.v1.ai_questions import _language_directive

        directive = _language_directive("te")
        assert directive is not None
        assert "Telugu" in directive
        assert "ENTIRE draft" in directive

    def test_english_request_gets_no_directive(self):
        from app.api.v1.ai_questions import _language_directive

        assert _language_directive("en") is None

    def test_unsupported_language_is_rejected_by_the_request_schema(self, client, db):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)
        response = client.post(
            "/api/v1/questions/ai-generate",
            json={
                "subject_id": str(subject.id),
                "category": "technical",
                "difficulty": "medium",
                "question_type": "mcq",
                "count": 1,
                "language": "fr",
            },
            headers=headers,
        )
        assert response.status_code == 422


class TestEnglishOnlyGenerationAndApproval:
    """The bank is English-only, so generation and approval only ever deal in ``en``."""

    def _generate(self, client, db, monkeypatch, *, language, body, options):
        def fake_generate_questions(**kwargs):
            return [
                {
                    "payload": {
                        "body": body,
                        "options": options,
                        "marks": 1.0,
                        "negative_marks": 0.0,
                    },
                    "provider": "stub",
                }
            ]

        monkeypatch.setattr(
            "app.api.v1.ai_questions.generate_questions", fake_generate_questions
        )
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        resp = client.post(
            "/api/v1/questions/ai-generate",
            json={
                "subject_id": str(subject.id),
                "category": "technical",
                "difficulty": "medium",
                "question_type": "mcq",
                "count": 1,
                "language": language,
            },
            headers=headers,
        )
        return headers, resp

    def test_english_request_is_stamped_onto_the_draft(self, client, db, monkeypatch):
        _, resp = self._generate(
            client, db, monkeypatch,
            language="en",
            body="What is an operating system?",
            options=[
                {"text": "Hardware", "is_correct": False},
                {"text": "Software", "is_correct": True},
            ],
        )
        assert resp.status_code == 201, resp.text
        draft = resp.json()[0]
        assert draft["payload"]["language"] == "en"

    def test_non_english_generation_request_is_refused(self, client, db, monkeypatch):
        _, resp = self._generate(
            client, db, monkeypatch,
            language="ta",
            body="இயக்க முறைமை என்றால் என்ன?",
            options=[{"text": "வன்பொருள்", "is_correct": False}],
        )
        assert resp.status_code == 422
        assert "english-only" in resp.text.lower()

    def test_approving_an_english_draft_stamps_the_question_language(
        self, client, db, monkeypatch
    ):
        headers, resp = self._generate(
            client, db, monkeypatch,
            language="en",
            body="What is an operating system?",
            options=[
                {"text": "Hardware", "is_correct": False},
                {"text": "Software", "is_correct": True},
            ],
        )
        assert resp.status_code == 201, resp.text
        draft = resp.json()[0]
        resp = client.put(
            f"/api/v1/questions/ai-drafts/{draft['id']}/approve",
            json={"payload": draft["payload"]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        question_id = resp.json()["published_question_id"]
        assert question_id is not None
        stored = db.get(Question, question_id)
        assert stored.language == "en"

    def test_approving_a_draft_declaring_a_non_english_language_is_refused(
        self, client, db, monkeypatch
    ):
        # A draft that claims a non-English language can never reach the bank, whatever
        # its text looks like - the English-only gate fires before content validation.
        headers, resp = self._generate(
            client, db, monkeypatch,
            language="en",
            body="What is an operating system?",
            options=[
                {"text": "Hardware", "is_correct": False},
                {"text": "Software", "is_correct": True},
            ],
        )
        assert resp.status_code == 201, resp.text
        draft = resp.json()[0]
        draft["payload"]["language"] = "te"
        resp = client.put(
            f"/api/v1/questions/ai-drafts/{draft['id']}/approve",
            json={"payload": draft["payload"]},
            headers=headers,
        )
        assert resp.status_code == 422
        assert "english-only" in resp.json()["detail"].lower()

        # The draft stays pending - a refused approval never half-commits it.
        from app.db.models import AiQuestionDraft

        stored_draft = db.get(AiQuestionDraft, draft["id"])
        assert stored_draft.status is DraftStatus.PENDING
