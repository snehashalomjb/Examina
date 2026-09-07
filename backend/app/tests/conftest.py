"""Test fixtures.

Each test runs inside a transaction that is rolled back afterwards, so the tests share one
schema without sharing state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import generate_salt, hash_password
from app.db.models import (
    AccessStatus,
    Base,
    Difficulty,
    Exam,
    ExamEnrollment,
    ExamQuestion,
    ExamStatus,
    LoginAccessRequest,
    LoginAccessStatus,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionType,
    Subject,
    User,
    UserRole,
)
from app.db.models.exam import DEFAULT_GRADING_CONFIG, DEFAULT_PROCTOR_CONFIG
from app.db.session import get_db
from app.main import app

TEST_PASSWORD = "Passw0rd!"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """A session bound to a transaction that is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db) -> TestClient:
    def _override():
        # Hand the request the fixture's session and let the fixture own the transaction.
        # Deliberately no commit and no rollback here: the real get_db rolls back on any
        # exception, which inside a test would also discard the fixtures set up before the
        # request - so a route returning 403 would wipe the users the test just created.
        yield db
        db.flush()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------- factories
def make_user(
    db: Session,
    *,
    role: UserRole = UserRole.CANDIDATE,
    access: AccessStatus = AccessStatus.APPROVED,
    email: str | None = None,
    login_access: LoginAccessStatus | None = LoginAccessStatus.APPROVED,
) -> User:
    user = User(
        email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@test.edu",
        password_hash=hash_password(TEST_PASSWORD),
        full_name=f"Test {role.value.title()}",
        role=role,
        access_status=access,
    )
    user.set_name("Test", role.value.title())
    db.add(user)
    db.flush()

    # Candidates in tests are usable by default; pass login_access explicitly to
    # exercise the pending/rejected paths.
    if role is UserRole.CANDIDATE and login_access is not None:
        db.add(
            LoginAccessRequest(
                candidate_id=user.id,
                status=login_access,
                requested_at=datetime.now(UTC),
                reviewed_at=datetime.now(UTC)
                if login_access is not LoginAccessStatus.PENDING
                else None,
            )
        )
        db.flush()
    return user


def auth_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_subject(db: Session, code: str | None = None) -> Subject:
    subject = Subject(code=code or f"S{uuid.uuid4().hex[:6].upper()}", name="Test Subject")
    db.add(subject)
    db.flush()
    return subject


def make_question(
    db: Session,
    subject: Subject,
    *,
    qtype: QuestionType = QuestionType.MCQ,
    difficulty: Difficulty = Difficulty.EASY,
    marks: float = 2.0,
    negative: float = 0.5,
    correct_indices: list[int] | None = None,
    option_count: int = 4,
    body: str | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
    category: QuestionCategory = QuestionCategory.ACADEMIC,
    topic: str | None = None,
    spec: dict | None = None,
) -> Question:
    question = Question(
        subject_id=subject.id,
        question_type=qtype,
        category=category,
        topic=topic,
        difficulty=difficulty,
        body=body or f"Question {uuid.uuid4().hex[:6]}?",
        marks=marks,
        negative_marks=negative,
        min_words=min_words,
        max_words=max_words,
        spec=spec,
        model_answer=(
            "A model answer mentioning normalisation, redundancy and integrity."
            if qtype in {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}
            else None
        ),
    )
    if qtype is QuestionType.TRUE_FALSE:
        # Two options, the first one right unless told otherwise - the same shape an MCQ
        # has, which is exactly why true/false scores through the same path.
        correct = correct_indices if correct_indices is not None else [0]
        for i, label in enumerate(("True", "False")):
            question.options.append(
                QuestionOption(text=label, is_correct=i in correct, order_index=i)
            )
    elif qtype in {QuestionType.MCQ, QuestionType.MULTI_SELECT}:
        correct = correct_indices if correct_indices is not None else [0]
        for i in range(option_count):
            question.options.append(
                QuestionOption(text=f"Option {i}", is_correct=i in correct, order_index=i)
            )
    db.add(question)
    db.flush()
    return question


def enroll(db: Session, exam: Exam, *candidates: User) -> None:
    """Assign candidates to an exam - without this they cannot see or start it."""
    for candidate in candidates:
        db.add(
            ExamEnrollment(
                exam_id=exam.id,
                candidate_id=candidate.id,
                assigned_at=datetime.now(UTC),
            )
        )
    db.flush()


def make_exam(
    db: Session,
    subject: Subject,
    creator: User,
    *,
    questions: list[Question],
    candidates: list[User] | None = None,
    rules: list[dict] | None = None,
    duration_minutes: int = 30,
    status: ExamStatus = ExamStatus.PUBLISHED,
    negative_marking: bool = True,
    randomize: bool = True,
    grading_config: dict | None = None,
) -> Exam:
    now = datetime.now(UTC)
    exam = Exam(
        subject_id=subject.id,
        title=f"Exam {uuid.uuid4().hex[:6]}",
        duration_minutes=duration_minutes,
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(days=1),
        selection_rules={
            "rules": rules
            or [{"question_type": "mcq", "difficulty": "easy", "count": len(questions)}]
        },
        randomize=randomize,
        shuffle_options=True,
        negative_marking=negative_marking,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG, **(grading_config or {})},
        status=status,
        created_by_id=creator.id,
    )
    for index, question in enumerate(questions):
        exam.exam_questions.append(ExamQuestion(question_id=question.id, order_index=index))
    db.add(exam)
    db.flush()

    if candidates:
        enroll(db, exam, *candidates)
    return exam
