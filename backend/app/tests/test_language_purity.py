"""Language purity: a non-English question must be written entirely in that language.

Covers the standalone checker (``app.services.language_purity``) and the English-only
gate now wired into question create/update, the bulk-import path, and AI-draft
approval - a non-English ``language`` is refused by the schema before the checker
would ever run, so no non-English row can enter the bank.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import AccessStatus, UserRole
from app.services.language_purity import check_language_purity, find_impure_terms
from app.services.validators import ValidationError
from app.tests.conftest import auth_headers, make_subject, make_user


class TestFindImpureTerms:
    def test_pure_native_text_has_no_hits(self) -> None:
        assert find_impure_terms("இரண்டு எண்களின் கூட்டுத்தொகையைக் காண்க.") == []

    def test_english_content_is_not_checked_by_the_wrapper(self) -> None:
        # find_impure_terms itself is script-agnostic - the "skip English" rule lives
        # in check_language_purity, not here.
        check_language_purity(language="en", fields={"question": "What is a router?"})

    def test_acronyms_and_code_identifiers_are_allowed(self) -> None:
        text = "DNS ஒரு domain name-ஐ IP address ஆக மாற்றுகிறது."
        # "DNS" and "IP" are allowed; "domain", "name" and "address" are not.
        bad = find_impure_terms(text)
        assert "DNS" not in bad
        assert "IP" not in bad
        assert any(t.lower() == "domain" for t in bad)

    def test_a_stray_english_common_noun_is_flagged(self) -> None:
        bad = find_impure_terms("Routing செயல்முறை எந்த layer-இல் நடைபெறுகிறது?")
        lowered = {t.lower() for t in bad}
        assert "routing" in lowered
        assert "layer" in lowered

    def test_quoted_code_literals_are_not_treated_as_prose(self) -> None:
        # len("hello") - "hello" is a literal string argument, not an English word
        # the author needs to translate.
        assert find_impure_terms('len("hello") இன் மதிப்பு என்ன?') == []

    def test_python_keywords_are_allowed_in_any_language(self) -> None:
        assert find_impure_terms("பைத்தானில் function ஐ def keyword-ஆல் வரையறுக்கலாம்.") == (
            find_impure_terms("பைத்தானில் function ஐ def keyword-ஆல் வரையறுக்கலாம்.")
        )
        bad = find_impure_terms("பைத்தானில் ஒரு function-ஐ def keyword பயன்படுத்தி வரையறுக்கலாம்.")
        assert not any(t.lower() == "def" for t in bad)
        assert any(t.lower() == "function" for t in bad)


class TestCheckLanguagePurity:
    def test_english_is_never_checked(self) -> None:
        check_language_purity(
            language="en", fields={"question": "What is an operating system?"}
        )

    def test_raises_for_mixed_content(self) -> None:
        with pytest.raises(ValidationError, match="Language validation failed"):
            check_language_purity(
                language="te",
                fields={"question": "IPv6 addresses ____ bits ఉంటాయి."},
            )

    def test_passes_for_genuinely_native_content(self) -> None:
        check_language_purity(
            language="ta",
            fields={
                "question": "TCP நெறிமுறை நம்பகமான தரவுப் பரிமாற்றத்தை உறுதி செய்கிறது.",
                "option A": "சரி",
                "option B": "தவறு",
            },
        )


class TestWiredIntoQuestionCreate:
    """The create path is English-only: a non-English ``language`` is refused by the
    schema before any content check, so no non-English row can ever enter the bank.
    The purity checker itself is still exercised directly above."""

    def _mcq_payload(self, subject_id, **extra) -> dict:
        return {
            "subject_id": str(subject_id),
            "question_type": "mcq",
            "difficulty": "medium",
            "marks": 2,
            "negative_marks": 0,
            "options": [
                {"text": "சரி", "is_correct": True, "order_index": 0},
                {"text": "தவறு", "is_correct": False, "order_index": 1},
            ],
            **extra,
        }

    def test_non_english_language_is_refused_even_for_pure_content(self, client, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(
                subject.id,
                language="ta",
                body="TCP நெறிமுறை எந்த அடுக்கில் செயல்படுகிறது?",
            ),
            headers=headers,
        )
        assert response.status_code == 422
        assert "english-only" in response.json()["detail"].lower()

    def test_non_english_language_is_refused_for_mixed_content(self, client, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(
                subject.id,
                language="ta",
                body="Routing செயல்முறை எந்த layer-இல் நடைபெறுகிறது?",
            ),
            headers=headers,
        )
        assert response.status_code == 422
        assert "english-only" in response.json()["detail"].lower()

    def test_english_question_is_never_checked(self, client, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        response = client.post(
            "/api/v1/questions",
            json=self._mcq_payload(subject.id, body="Which layer does routing happen at?"),
            headers=headers,
        )
        assert response.status_code == 201, response.text
