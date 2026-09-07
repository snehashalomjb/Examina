"""The question bank over HTTP: authoring the new types, filtering, and answer-key leaks.

The leak tests are the important ones. A numerical question's ``spec`` *is* its answer, so
anything that puts a spec on a candidate's paper hands them the marks.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.models import QuestionCategory, QuestionType, UserRole
from app.services.question_spec import candidate_spec
from app.tests.conftest import auth_headers, make_subject, make_user

API = "/api/v1"


@pytest.fixture
def examiner(db):
    return make_user(db, role=UserRole.EXAMINER)


@pytest.fixture
def headers(client, examiner):
    return auth_headers(client, examiner)


@pytest.fixture
def subject(db):
    return make_subject(db)


def _create(client, headers, **overrides) -> dict:
    payload = {
        "subject_id": str(overrides.pop("subject_id")),
        "question_type": "mcq",
        "body": "Which of these is a relational database?",
        "marks": 1,
        "negative_marks": 0,
        "options": [
            {"text": "PostgreSQL", "is_correct": True, "order_index": 0},
            {"text": "Redis", "is_correct": False, "order_index": 1},
        ],
    }
    payload.update(overrides)
    return client.post(f"{API}/questions", json=payload, headers=headers)


class TestAuthoringTheNewTypes:
    def test_a_numerical_question_round_trips(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="numerical",
            body="What is g, to 2 decimal places?",
            marks=2,
            options=[],
            category="academic",
            topic="Mechanics",
            spec={"answer": 9.81, "tolerance": 0.01, "unit": "m/s^2"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["spec"]["answer"] == 9.81
        assert body["topic"] == "Mechanics"

    def test_a_true_false_question_round_trips(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="true_false",
            body="Postgres supports native enum types.",
            options=[
                {"text": "True", "is_correct": True, "order_index": 0},
                {"text": "False", "is_correct": False, "order_index": 1},
            ],
        )
        assert response.status_code == 201, response.text

    def test_a_fill_blank_question_round_trips(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="fill_blank",
            body="The chemical formula for water is ____.",
            options=[],
            spec={"accepted_answers": ["H2O", "water"]},
        )
        assert response.status_code == 201, response.text
        assert response.json()["spec"]["accepted_answers"] == ["H2O", "water"]

    def test_a_coding_question_round_trips(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="coding",
            body="Return the nth Fibonacci number.",
            marks=10,
            options=[],
            category="coding",
            spec={
                "languages": ["python", "java"],
                "input_format": "A single integer n.",
                "output_format": "The nth Fibonacci number.",
                "constraints": "1 <= n <= 40",
                "sample_cases": [{"input": "5", "output": "5"}],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["spec"]["languages"] == ["python", "java"]

    def test_a_passage_and_its_children_link_up(self, client, headers, subject):
        passage = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="passage",
            body="Read the following extract about distributed systems...",
            marks=0,
            options=[],
        )
        assert passage.status_code == 201, passage.text
        passage_id = passage.json()["id"]

        child = _create(
            client,
            headers,
            subject_id=subject.id,
            body="What does the extract identify as the main trade-off?",
            parent_question_id=passage_id,
        )
        assert child.status_code == 201, child.text
        assert child.json()["parent_question_id"] == passage_id


class TestValidationOverHttp:
    def test_a_coding_question_without_a_spec_is_422(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="coding",
            body="Write a function.",
            marks=5,
            options=[],
        )
        assert response.status_code == 422
        assert "spec" in response.text

    def test_a_numerical_question_with_a_typo_in_its_spec_is_422(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="numerical",
            body="What is g?",
            options=[],
            spec={"answer": 9.81, "tolerence": 0.5},
        )
        assert response.status_code == 422

    def test_a_true_false_question_with_three_options_is_422(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="true_false",
            options=[
                {"text": "True", "is_correct": True, "order_index": 0},
                {"text": "False", "is_correct": False, "order_index": 1},
                {"text": "Maybe", "is_correct": False, "order_index": 2},
            ],
        )
        assert response.status_code == 422
        assert "exactly 2 options" in response.text

    def test_a_passage_with_marks_is_422(self, client, headers, subject):
        response = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="passage",
            body="An extract.",
            marks=5,
            options=[],
        )
        assert response.status_code == 422
        assert "carries no marks" in response.text


class TestFiltering:
    @pytest.fixture(autouse=True)
    def bank(self, client, headers, subject):
        _create(
            client,
            headers,
            subject_id=subject.id,
            body="A technical Python question about decorators.",
            category="technical",
            topic="Python",
            difficulty="hard",
            marks=2,
        )
        _create(
            client,
            headers,
            subject_id=subject.id,
            body="An aptitude question about percentages.",
            category="aptitude",
            topic="Percentages",
            difficulty="easy",
            marks=1,
        )
        _create(
            client,
            headers,
            subject_id=subject.id,
            body="A reasoning question about blood relations.",
            category="logical_reasoning",
            topic="Blood Relations",
            difficulty="medium",
            marks=1,
        )

    def _list(self, client, headers, **params):
        response = client.get(f"{API}/questions", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    def test_filter_by_category(self, client, headers):
        rows = self._list(client, headers, category="technical")
        assert rows and all(r["category"] == "technical" for r in rows)

    def test_filter_by_topic_is_case_insensitive(self, client, headers):
        rows = self._list(client, headers, topic="python")
        assert rows and all(r["topic"] == "Python" for r in rows)

    def test_filter_by_difficulty(self, client, headers):
        rows = self._list(client, headers, difficulty="hard")
        assert rows and all(r["difficulty"] == "hard" for r in rows)

    def test_filter_by_marks(self, client, headers):
        rows = self._list(client, headers, marks=2)
        assert rows and all(r["marks"] == 2 for r in rows)

    def test_filters_combine(self, client, headers):
        rows = self._list(client, headers, category="technical", difficulty="hard", marks=2)
        assert len(rows) == 1

    def test_search_matches_topic_as_well_as_body(self, client, headers):
        assert self._list(client, headers, search="percentages")

    def test_new_questions_default_to_published(self, client, headers):
        rows = self._list(client, headers, status="published")
        assert len(rows) >= 3

    def test_topics_endpoint_lists_what_is_in_use(self, client, headers):
        response = client.get(f"{API}/questions/topics", headers=headers)
        assert response.status_code == 200, response.text
        assert {"Python", "Percentages", "Blood Relations"} <= set(response.json())


class TestPassageChildrenAreNotLoose:
    def test_children_are_hidden_from_the_default_listing(self, client, headers, subject):
        passage = _create(
            client,
            headers,
            subject_id=subject.id,
            question_type="passage",
            body="An extract to reason about.",
            marks=0,
            options=[],
        )
        passage_id = passage.json()["id"]
        _create(
            client,
            headers,
            subject_id=subject.id,
            body="A question about the extract.",
            parent_question_id=passage_id,
        )

        default = client.get(f"{API}/questions", headers=headers).json()
        assert all(row["parent_question_id"] is None for row in default)

        with_children = client.get(
            f"{API}/questions", params={"include_children": True}, headers=headers
        ).json()
        assert any(row["parent_question_id"] == passage_id for row in with_children)


class TestTheAnswerKeyNeverReachesACandidate:
    """``candidate_spec`` is an allowlist, so a new spec field cannot leak by default."""

    def test_a_numerical_spec_projects_to_nothing(self):
        assert (
            candidate_spec(
                QuestionType.NUMERICAL,
                {"kind": "numerical", "answer": 9.81, "tolerance": 0.01},
            )
            is None
        )

    def test_a_fill_blank_spec_projects_to_nothing(self):
        assert (
            candidate_spec(
                QuestionType.FILL_BLANK,
                {"kind": "fill_blank", "accepted_answers": ["H2O"]},
            )
            is None
        )

    def test_a_coding_spec_keeps_the_problem_statement(self):
        projected = candidate_spec(
            QuestionType.CODING,
            {
                "kind": "coding",
                "languages": ["python"],
                "input_format": "n",
                "output_format": "fib(n)",
                "constraints": "1 <= n <= 40",
                "sample_cases": [{"input": "5", "output": "5"}],
            },
        )
        assert projected["languages"] == ["python"]
        assert projected["constraints"] == "1 <= n <= 40"

    def test_an_unlisted_field_is_dropped_even_on_an_allowed_type(self):
        # The allowlist is what makes this safe: a field added to CodingSpec later does
        # not reach the browser until someone names it in CANDIDATE_SAFE_FIELDS.
        projected = candidate_spec(
            QuestionType.CODING,
            {"languages": ["python"], "reference_solution": "def fib(n): ..."},
        )
        assert "reference_solution" not in projected

    def test_a_passage_keeps_its_text(self):
        projected = candidate_spec(
            QuestionType.PASSAGE, {"kind": "passage", "passage_text": "An extract.", "sticky": True}
        )
        assert projected["passage_text"] == "An extract."


class TestAccessControl:
    def test_a_candidate_cannot_read_the_bank(self, client, db):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = client.get(f"{API}/questions", headers=auth_headers(client, candidate))
        assert response.status_code == 403

    def test_a_candidate_cannot_author_a_question(self, client, db, subject):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = _create(
            client, auth_headers(client, candidate), subject_id=subject.id
        )
        assert response.status_code == 403

    def test_an_unknown_subject_is_404(self, client, headers):
        response = _create(client, headers, subject_id=uuid.uuid4())
        assert response.status_code == 404


class TestCategoryDefaults:
    def test_a_question_authored_without_a_category_is_academic(self, client, headers, subject):
        response = _create(client, headers, subject_id=subject.id)
        assert response.status_code == 201, response.text
        assert response.json()["category"] == QuestionCategory.ACADEMIC.value
