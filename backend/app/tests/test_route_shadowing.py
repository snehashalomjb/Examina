"""Literal /questions/* paths must not be swallowed by /questions/{question_id}.

Starlette matches in registration order, so `/questions/{question_id}` will happily
match the literal string "ai-drafts" and then fail to parse it as a UUID - a 422 that
reads like a client mistake but is really a routing bug. It took the whole AI draft
review queue offline once; these tests are here so it cannot do it again quietly.

The first test is the specific regression. The second is the general guard: it walks the
route table and fails for *any* literal segment registered after a parameter that would
shadow it, so a new `/questions/whatever` added below the parameterised route is caught
before anyone hits it in the browser.
"""

from __future__ import annotations

import re

import pytest

from app.db.models import UserRole
from app.main import app
from app.tests.conftest import auth_headers, make_user

API = "/api/v1"


@pytest.fixture
def headers(client, db):
    return auth_headers(client, make_user(db, role=UserRole.EXAMINER))


@pytest.mark.parametrize(
    "path",
    [
        f"{API}/questions/ai-drafts",
        f"{API}/questions/topics",
        f"{API}/questions/import/template",
    ],
)
def test_literal_question_routes_are_reachable(client, headers, path):
    """Each must reach its own handler, never the UUID parser."""
    response = client.get(path, headers=headers)

    assert response.status_code != 422, (
        f"{path} was captured by a parameterised route: {response.text}"
    )
    assert response.status_code == 200, response.text


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def test_no_literal_route_is_registered_behind_a_parameter_that_shadows_it():
    """Walk the whole table, not just /questions - the trap is not specific to it."""
    routes = [
        (r.path, method)
        for r in app.routes
        if getattr(r, "path", None) and getattr(r, "methods", None)
        for method in r.methods
        if method not in {"HEAD", "OPTIONS"}
    ]

    shadowed: list[str] = []
    for index, (path, method) in enumerate(routes):
        segments = _segments(path)
        if any(re.fullmatch(r"\{.+\}", s) for s in segments):
            continue  # this route is the parameterised one, not a victim

        for earlier_path, earlier_method in routes[:index]:
            if earlier_method != method:
                continue
            earlier = _segments(earlier_path)
            if len(earlier) != len(segments):
                continue
            # An earlier route shadows this one when every segment either matches
            # exactly or is a parameter standing where this route wants a literal.
            if all(
                e == s or re.fullmatch(r"\{.+\}", e)
                for e, s in zip(earlier, segments, strict=True)
            ):
                shadowed.append(f"{method} {path} is shadowed by {earlier_method} {earlier_path}")
                break

    assert not shadowed, "Literal routes registered behind a parameter:\n  " + "\n  ".join(
        shadowed
    )
