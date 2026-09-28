"""Downloading a result as a PDF, from the endpoint the staff screens call.

Only the PDF generator was tested before, never the endpoint, so a crash inside the
endpoint went unnoticed: it called the result-detail endpoint function directly, whose
``Accept-Language`` default is FastAPI's ``Header`` marker rather than ``None`` when
called that way, and every download - by an examiner, an admin, anyone - returned 500.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Difficulty, ExamStatus, UserRole
from app.tests.conftest import auth_headers, make_exam, make_question, make_subject, make_user
from app.tests.test_ranking_and_results import _sit_and_score

API = "/api/v1"


@pytest.fixture
def published_result(db: Session):
    examiner = make_user(db, role=UserRole.EXAMINER)
    candidate = make_user(db, role=UserRole.CANDIDATE)
    subject = make_subject(db)
    question = make_question(db, subject, difficulty=Difficulty.EASY)
    exam = make_exam(db, subject, examiner, questions=[question], status=ExamStatus.PUBLISHED)
    result = _sit_and_score(
        db, exam, candidate, obtained=8, total=10, correct=4, incorrect=1, unanswered=0
    )
    return examiner, candidate, result


@pytest.mark.parametrize("simple", ["", "?simple=true"])
@pytest.mark.parametrize("role", ["examiner", "admin"])
def test_staff_can_download_a_published_result(
    client: TestClient, db: Session, published_result, role, simple
):
    examiner, _, result = published_result
    user = examiner if role == "examiner" else make_user(db, role=UserRole.ADMIN)
    response = client.get(
        f"{API}/results/{result.id}/pdf{simple}",
        headers={**auth_headers(client, user), "Accept-Language": "hi"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response.headers["content-disposition"]


def test_a_candidate_downloads_their_own_published_result(
    client: TestClient, published_result
):
    _, candidate, result = published_result
    response = client.get(f"{API}/results/{result.id}/pdf", headers=auth_headers(client, candidate))
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")


def test_another_candidate_cannot_download_it(client: TestClient, db: Session, published_result):
    _, _, result = published_result
    stranger = make_user(db, role=UserRole.CANDIDATE)
    response = client.get(f"{API}/results/{result.id}/pdf", headers=auth_headers(client, stranger))
    assert response.status_code in (403, 404), response.text
