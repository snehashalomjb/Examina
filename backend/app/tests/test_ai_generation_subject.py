"""AI generation actually knows which subject it is generating for.

The bug: choosing a subject on the generation form only tagged the resulting draft's
``subject_id`` column - the name never reached the prompt, so a Databases subject and an
Algorithms subject asked for "Normalisation" got identical output. These tests cover the
fix at both ends: the prompt builder folds the subject in, and the API route looks the
subject up and passes its name through rather than just its id.
"""

from __future__ import annotations

from app.db.models import UserRole
from app.db.models.enums import Difficulty, QuestionCategory, QuestionType
from app.services import ai_generator
from app.tests.conftest import auth_headers, make_subject, make_user


class TestThePromptCarriesTheSubject:
    def test_a_named_subject_appears_in_the_prompt(self):
        prompt = ai_generator._build_prompt(
            category=QuestionCategory.TECHNICAL,
            topic="Normalisation",
            difficulty=Difficulty.MEDIUM,
            question_type=QuestionType.MCQ,
            count=3,
            extra_instructions=None,
            subject_name="Database Systems",
        )

        assert "Database Systems" in prompt

    def test_no_subject_reads_naturally_without_one(self):
        """Optional stays optional - a request with no subject asks for nothing broken."""
        prompt = ai_generator._build_prompt(
            category=QuestionCategory.TECHNICAL,
            topic="Normalisation",
            difficulty=Difficulty.MEDIUM,
            question_type=QuestionType.MCQ,
            count=3,
            extra_instructions=None,
            subject_name=None,
        )

        assert "for the subject" not in prompt
        assert "on the topic 'Normalisation'" in prompt

    def test_the_stub_tags_a_named_subject_even_offline(self):
        """The stub cannot read a prompt, but the subject should still be traceable."""
        drafts = ai_generator.generate_questions(
            category=QuestionCategory.TECHNICAL,
            topic=None,
            difficulty=Difficulty.EASY,
            question_type=QuestionType.MCQ,
            count=1,
            subject_name="Operating Systems",
        )

        assert "Operating Systems" in drafts[0]["payload"]["tags"]


class TestTheApiLooksUpTheSubjectName:
    def test_generating_with_a_subject_passes_its_name_through(
        self, client, db, monkeypatch
    ):
        captured: dict = {}

        def fake_generate_questions(**kwargs):
            captured.update(kwargs)
            return [{"payload": {"body": "stub question"}, "provider": "stub"}]

        monkeypatch.setattr(
            "app.api.v1.ai_questions.generate_questions", fake_generate_questions
        )

        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db, code="DB101")
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions/ai-generate",
            json={
                "subject_id": str(subject.id),
                "category": "technical",
                "topic": "Normalisation",
                "difficulty": "medium",
                "question_type": "mcq",
                "count": 1,
            },
            headers=headers,
        )

        assert response.status_code == 201, response.text
        assert captured.get("subject_name") == subject.name

    def test_generating_without_a_subject_passes_none(self, client, db, monkeypatch):
        captured: dict = {}

        def fake_generate_questions(**kwargs):
            captured.update(kwargs)
            return [{"payload": {"body": "stub question"}, "provider": "stub"}]

        monkeypatch.setattr(
            "app.api.v1.ai_questions.generate_questions", fake_generate_questions
        )

        examiner = make_user(db, role=UserRole.EXAMINER)
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions/ai-generate",
            json={
                "category": "technical",
                "difficulty": "medium",
                "question_type": "mcq",
                "count": 1,
            },
            headers=headers,
        )

        assert response.status_code == 201, response.text
        assert captured.get("subject_name") is None
