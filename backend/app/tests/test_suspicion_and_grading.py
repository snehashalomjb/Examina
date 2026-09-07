"""Suspicion scoring maths and the offline stub grader."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.db.models import (
    DEFAULT_PROCTOR_CONFIG,
    ProctorEvent,
    ProctorEventType,
    ProctorSeverity,
    QuestionType,
)
from app.services.grading import get_grader
from app.services.grading.stub import StubGrader
from app.services.suspicion import score_events, severity_for
from app.tests.conftest import make_question, make_subject


def _event(kind: ProctorEventType, minutes: int = 0, severity=ProctorSeverity.WARNING):
    return ProctorEvent(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        event_type=kind,
        severity=severity,
        occurred_at=datetime.now(UTC) + timedelta(minutes=minutes),
        server_received_at=datetime.now(UTC),
        weight=0.0,
    )


class TestSuspicionScoring:
    def test_no_events_means_no_score(self):
        outcome = score_events([], DEFAULT_PROCTOR_CONFIG)
        assert outcome.score == 0.0
        assert not outcome.should_flag
        assert not outcome.should_terminate

    def test_repeat_offences_decay(self):
        one = score_events([_event(ProctorEventType.TAB_SWITCH)], DEFAULT_PROCTOR_CONFIG)
        three = score_events(
            [_event(ProctorEventType.TAB_SWITCH, i) for i in range(3)], DEFAULT_PROCTOR_CONFIG
        )
        # Decaying repeats means three events score less than three times one event.
        assert three.score < one.score * 3
        assert three.score > one.score

    def test_severity_scales_the_contribution(self):
        warning = score_events(
            [_event(ProctorEventType.GAZE_AWAY, severity=ProctorSeverity.WARNING)],
            DEFAULT_PROCTOR_CONFIG,
        )
        critical = score_events(
            [_event(ProctorEventType.GAZE_AWAY, severity=ProctorSeverity.CRITICAL)],
            DEFAULT_PROCTOR_CONFIG,
        )
        assert critical.score > warning.score

    def test_tab_switches_are_counted_separately(self):
        outcome = score_events(
            [_event(ProctorEventType.TAB_SWITCH, i) for i in range(4)], DEFAULT_PROCTOR_CONFIG
        )
        assert outcome.tab_switch_count == 4

    def test_exceeding_the_tab_limit_flags_even_at_a_low_score(self):
        config = {**DEFAULT_PROCTOR_CONFIG, "max_tab_switches": 2, "flag_on_score": 10_000}
        outcome = score_events([_event(ProctorEventType.TAB_SWITCH, i) for i in range(3)], config)
        assert outcome.should_flag

    def test_high_score_terminates(self):
        config = {**DEFAULT_PROCTOR_CONFIG, "terminate_on_score": 20.0, "flag_on_score": 10.0}
        outcome = score_events(
            [
                _event(ProctorEventType.DEVTOOLS_OPEN, severity=ProctorSeverity.CRITICAL),
                _event(ProctorEventType.CAMERA_BLOCKED, 1, severity=ProctorSeverity.CRITICAL),
            ],
            config,
        )
        assert outcome.should_terminate

    def test_custom_weights_are_honoured(self):
        default = score_events([_event(ProctorEventType.GAZE_AWAY)], DEFAULT_PROCTOR_CONFIG)
        strict = score_events(
            [_event(ProctorEventType.GAZE_AWAY)],
            {**DEFAULT_PROCTOR_CONFIG, "weights": {"gaze_away": 50.0}},
        )
        assert strict.score > default.score

    def test_breakdown_names_each_event_type(self):
        outcome = score_events(
            [_event(ProctorEventType.TAB_SWITCH), _event(ProctorEventType.GAZE_AWAY, 1)],
            DEFAULT_PROCTOR_CONFIG,
        )
        assert set(outcome.breakdown) == {"tab_switch", "gaze_away"}

    def test_default_severities_are_sensible(self):
        assert severity_for(ProctorEventType.MULTIPLE_FACES) is ProctorSeverity.CRITICAL
        assert severity_for(ProctorEventType.TAB_SWITCH) is ProctorSeverity.WARNING
        assert severity_for(ProctorEventType.WINDOW_BLUR) is ProctorSeverity.INFO


class TestStubGrader:
    def test_default_provider_is_the_stub(self):
        assert isinstance(get_grader({}), StubGrader)

    def test_unknown_provider_falls_back_to_the_stub(self):
        assert isinstance(get_grader({"grader_provider": "nonesuch"}), StubGrader)

    def test_claude_without_a_key_falls_back_to_the_stub(self):
        assert isinstance(get_grader({"grader_provider": "claude"}), StubGrader)

    def test_blank_answer_scores_zero(self, db):
        from app.db.models import Answer

        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.SHORT_ANSWER, marks=5)
        answer = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=5)
        answer.text_answer = ""

        result = StubGrader().grade(question=question, answer=answer, max_marks=5)
        assert result.score == 0.0
        assert "No answer" in result.justification

    def test_a_matching_answer_outscores_an_irrelevant_one(self, db):
        from app.db.models import Answer

        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.SHORT_ANSWER, marks=5)

        good = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=5)
        good.text_answer = (
            "Normalisation organises tables to reduce redundancy and improve integrity "
            "so that each fact is stored exactly once."
        )
        poor = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=5)
        poor.text_answer = "I do not know the answer to this."

        grader = StubGrader()
        assert (
            grader.grade(question=question, answer=good, max_marks=5).score
            > grader.grade(question=question, answer=poor, max_marks=5).score
        )

    def test_the_score_is_deterministic(self, db):
        from app.db.models import Answer

        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.SHORT_ANSWER, marks=5)
        answer = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=5)
        answer.text_answer = "Normalisation reduces redundancy."

        grader = StubGrader()
        first = grader.grade(question=question, answer=answer, max_marks=5)
        second = grader.grade(question=question, answer=answer, max_marks=5)
        assert first.score == second.score

    def test_the_score_never_exceeds_the_maximum(self, db):
        from app.db.models import Answer

        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.SHORT_ANSWER, marks=5)
        answer = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=5)
        answer.text_answer = (
            "normalisation redundancy integrity anomalies decomposing organising columns "
            "tables stored once benefit update avoided change fact place " * 20
        )
        result = StubGrader().grade(question=question, answer=answer, max_marks=5)
        assert 0 <= result.score <= 5

    def test_image_answers_are_deferred_to_the_examiner(self, db):
        from app.db.models import Answer

        subject = make_subject(db)
        question = make_question(db, subject, qtype=QuestionType.IMAGE_UPLOAD, marks=8)
        answer = Answer(session_id=uuid.uuid4(), question_id=question.id, max_marks=8)
        answer.image_object_key = "answers/x/y.jpg"

        result = StubGrader().grade(question=question, answer=answer, max_marks=8)
        assert result.score == 0.0
        assert result.confidence == 0.0
        assert "examiner review" in result.justification.lower()
