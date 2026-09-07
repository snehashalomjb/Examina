"""Uploading a handwritten answer: storage, thumbnail, and the OCR hand-off.

Object storage is stubbed with an in-memory dict so the real thumbnail code runs without
needing MinIO. The OCR task is stubbed too - it is a background job with its own session,
covered directly in test_media_and_ocr.py; what matters here is that the endpoint schedules
it and records the keys.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.db.models import AccessStatus, Answer, Difficulty, QuestionType, UserRole
from app.services import answer_media
from app.tests.conftest import (
    auth_headers,
    make_exam,
    make_question,
    make_subject,
    make_user,
)


@pytest.fixture
def store(monkeypatch) -> dict[str, bytes]:
    """Replace object storage at both call sites with an in-memory bucket."""
    bucket: dict[str, bytes] = {}

    def fake_put(*, key: str, data: bytes, content_type: str) -> str:
        bucket[key] = data
        return key

    monkeypatch.setattr("app.api.v1.exam_sessions.put_object", fake_put)
    monkeypatch.setattr("app.services.answer_media.put_object", fake_put)
    monkeypatch.setattr("app.api.v1.exam_sessions.presigned_url", lambda key, *a, **k: (
        f"https://example.invalid/{key}" if key else None
    ))
    return bucket


@pytest.fixture
def ocr_calls(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []
    monkeypatch.setattr(answer_media, "run_ocr", lambda *args: calls.append(args))
    return calls


@pytest.fixture
def scenario(db):
    subject = make_subject(db)
    examiner = make_user(db, role=UserRole.EXAMINER, access=AccessStatus.APPROVED)
    candidate = make_user(db, role=UserRole.CANDIDATE)

    scan = make_question(
        db,
        subject,
        qtype=QuestionType.IMAGE_UPLOAD,
        difficulty=Difficulty.MEDIUM,
        marks=15.0,
        negative=0.0,
        body="Derive the result on paper and upload a photo of your working.",
    )
    exam = make_exam(
        db,
        subject,
        examiner,
        questions=[scan],
        candidates=[candidate],
        rules=[{"question_type": "image_upload", "difficulty": None, "count": 1}],
    )
    return {"examiner": examiner, "candidate": candidate, "exam": exam, "question": scan}


def _start(client, scenario):
    headers = auth_headers(client, scenario["candidate"])
    response = client.post(f"/api/v1/exams/{scenario['exam'].id}/start", headers=headers)
    assert response.status_code == 200, response.text
    paper = response.json()
    return paper, {**headers, "X-Exam-Token": paper["exam_token"]}


def _jpeg(width: int = 1800, height: int = 1200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (240, 240, 235)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload(client, paper, headers, data: bytes = None, filename: str = "answer.jpg"):
    qid = paper["questions"][0]["question_id"]
    return qid, client.post(
        f"/api/v1/sessions/{paper['session_id']}/answers/{qid}/image",
        headers=headers,
        files={"file": (filename, data if data is not None else _jpeg(), "image/jpeg")},
    )


class TestUpload:
    def test_a_scan_is_stored_with_a_thumbnail(self, client, db, scenario, store, ocr_calls):
        paper, headers = _start(client, scenario)
        qid, response = _upload(client, paper, headers)
        assert response.status_code == 200, response.text

        answer = db.scalar(select(Answer).where(Answer.question_id == qid))
        assert answer is not None
        assert answer.image_object_key in store
        assert answer.image_thumb_key in store
        assert answer.image_thumb_key.startswith("answers/thumbs/")

    def test_the_thumbnail_is_smaller_than_the_original(
        self, client, db, scenario, store, ocr_calls
    ):
        paper, headers = _start(client, scenario)
        qid, response = _upload(client, paper, headers)
        assert response.status_code == 200, response.text

        answer = db.scalar(select(Answer).where(Answer.question_id == qid))
        thumb = Image.open(io.BytesIO(store[answer.image_thumb_key]))
        assert max(thumb.size) == 512
        assert len(store[answer.image_thumb_key]) < len(store[answer.image_object_key])

    def test_ocr_is_scheduled_for_the_new_answer(self, client, db, scenario, store, ocr_calls):
        paper, headers = _start(client, scenario)
        qid, response = _upload(client, paper, headers)
        assert response.status_code == 200, response.text

        answer = db.scalar(select(Answer).where(Answer.question_id == qid))
        assert [call[0] for call in ocr_calls] == [answer.id]

    def test_a_corrupt_image_still_stores_the_original(
        self, client, db, scenario, store, ocr_calls
    ):
        """A thumbnail is a convenience. Failing to make one must not lose the answer."""
        paper, headers = _start(client, scenario)
        qid, response = _upload(client, paper, headers, data=b"not really a JPEG")
        assert response.status_code == 200, response.text

        answer = db.scalar(select(Answer).where(Answer.question_id == qid))
        assert answer.image_object_key in store
        assert answer.image_thumb_key is None

    def test_a_non_image_content_type_is_refused(self, client, scenario, store, ocr_calls):
        paper, headers = _start(client, scenario)
        response = client.post(
            f"/api/v1/sessions/{paper['session_id']}/answers/"
            f"{paper['questions'][0]['question_id']}/image",
            headers=headers,
            files={"file": ("answer.pdf", b"%PDF-1.7", "application/pdf")},
        )
        assert response.status_code == 415


class TestGradingQueue:
    def test_the_scan_reaches_the_examiner_with_a_thumbnail_url(
        self, client, db, scenario, store, ocr_calls, monkeypatch
    ):
        monkeypatch.setattr(
            "app.api.v1.grading.presigned_url",
            lambda key, *a, **k: (f"https://example.invalid/{key}" if key else None),
        )
        paper, headers = _start(client, scenario)
        _upload(client, paper, headers)
        client.post(f"/api/v1/sessions/{paper['session_id']}/submit", headers=headers)

        queue = client.get(
            "/api/v1/grading/queue", headers=auth_headers(client, scenario["examiner"])
        ).json()
        item = next(i for i in queue if i["question_id"] == paper["questions"][0]["question_id"])
        assert item["image_url"] is not None
        assert item["image_thumb_url"] is not None
        assert item["image_thumb_url"] != item["image_url"]
