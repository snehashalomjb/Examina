"""PDF import into the question bank.

The point of these tests is that an import cannot smuggle a question into the live bank.
Every draft it creates is PENDING and has to travel the same review route as anything
else the generator produces, and a PDF with no readable text is refused outright rather
than turned into questions generated from nothing.
"""

from __future__ import annotations

import io

import pytest
from reportlab.pdfgen import canvas

from app.db.models import AiQuestionDraft, DraftStatus, UserRole
from app.tests.conftest import auth_headers, make_subject, make_user

API = "/api/v1"
ENDPOINT = f"{API}/questions/ai-generate/from-pdf"


@pytest.fixture
def examiner(db):
    return make_user(db, role=UserRole.EXAMINER)


@pytest.fixture
def headers(client, examiner):
    return auth_headers(client, examiner)


def _pdf(pages: int = 2, lines_per_page: int = 30) -> bytes:
    """A digital PDF with a real text layer, built rather than checked in as a fixture."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for page in range(pages):
        y = 800
        for line in range(lines_per_page):
            pdf.drawString(
                50,
                y,
                f"Page {page + 1} line {line}: a subclass inherits the base implementation.",
            )
            y -= 20
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _blank_pdf() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _upload(client, headers, data: bytes, *, filename="notes.pdf", **fields):
    form = {"category": "technical", "question_type": "mcq", "difficulty": "easy", "count": "3"}
    form.update({k: str(v) for k, v in fields.items()})
    return client.post(
        ENDPOINT,
        headers=headers,
        files={"file": (filename, data, "application/pdf")},
        data=form,
    )


def test_import_creates_pending_drafts_only(client, headers, db):
    response = _upload(client, headers, _pdf())
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["filename"] == "notes.pdf"
    assert body["pages"] == 2
    assert body["characters"] > 200
    assert len(body["drafts"]) == 3

    # Nothing is published by the import itself.
    assert all(d["status"] == DraftStatus.PENDING.value for d in body["drafts"])
    assert all(d["published_question_id"] is None for d in body["drafts"])

    # The bank is untouched until an examiner approves.
    assert client.get(f"{API}/questions", headers=headers).json() == []


def test_import_records_provenance_on_every_draft(client, headers, db):
    response = _upload(client, headers, _pdf(), filename="syllabus-2026.pdf")
    assert response.status_code == 201, response.text

    for draft in response.json()["drafts"]:
        assert draft["payload"]["source_pdf"] == "syllabus-2026.pdf"

    stored = db.query(AiQuestionDraft).all()
    assert len(stored) == 3
    assert all(d.payload["source_pdf"] == "syllabus-2026.pdf" for d in stored)


def test_stub_run_is_flagged_as_not_drawn_from_the_pdf(client, headers):
    """With no provider key configured the stub answers, and the response says so.

    An examiner who cannot tell a template question from one grounded in their document
    will approve the wrong thing, so this flag is load-bearing, not decoration.
    """
    response = _upload(client, headers, _pdf())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_grounded"] is False
    assert all(d["payload"]["source_grounded"] is False for d in body["drafts"])


def test_scanned_pdf_with_no_text_layer_is_refused(client, headers, db):
    response = _upload(client, headers, _blank_pdf())
    assert response.status_code == 422, response.text
    assert "no readable text" in response.json()["detail"].lower()
    assert db.query(AiQuestionDraft).count() == 0


def test_non_pdf_upload_is_refused(client, headers, db):
    response = client.post(
        ENDPOINT,
        headers=headers,
        files={"file": ("notes.txt", b"inheritance lets a subclass reuse code", "text/plain")},
        data={"category": "technical", "question_type": "mcq", "count": "2"},
    )
    assert response.status_code == 415, response.text
    assert db.query(AiQuestionDraft).count() == 0


def test_unknown_subject_is_refused_before_any_generation(client, headers, db):
    response = _upload(
        client, headers, _pdf(), subject_id="00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404, response.text
    assert db.query(AiQuestionDraft).count() == 0


def test_subject_tag_is_carried_onto_the_drafts(client, headers, db):
    subject = make_subject(db)
    response = _upload(client, headers, _pdf(), subject_id=str(subject.id), topic="Inheritance")
    assert response.status_code == 201, response.text

    for draft in response.json()["drafts"]:
        assert draft["subject_id"] == str(subject.id)
        assert draft["topic"] == "Inheritance"


def test_import_needs_staff(client, db):
    candidate = make_user(db, role=UserRole.CANDIDATE)
    response = _upload(client, auth_headers(client, candidate), _pdf())
    assert response.status_code == 403, response.text
    assert db.query(AiQuestionDraft).count() == 0


def test_imported_draft_can_be_approved_into_the_bank(client, headers, db):
    """The import feeds the existing review route - no second door into the bank."""
    subject = make_subject(db)
    imported = _upload(client, headers, _pdf(), subject_id=str(subject.id), count=1)
    assert imported.status_code == 201, imported.text
    draft = imported.json()["drafts"][0]

    approved = client.put(
        f"{API}/questions/ai-drafts/{draft['id']}/approve",
        headers=headers,
        json={"payload": draft["payload"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == DraftStatus.APPROVED.value
    assert approved.json()["published_question_id"] is not None

    bank = client.get(f"{API}/questions", headers=headers).json()
    assert len(bank) == 1
