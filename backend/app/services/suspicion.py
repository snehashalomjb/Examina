"""Per-session suspicion scoring from persisted proctor events.

The score is a weighted sum, not a probability. Weights come from the exam's
``proctor_config`` so a low-stakes quiz and a final exam can use the same engine with
different strictness. Repeat offences of the same type decay so that one flickering
webcam does not run the score to a termination on its own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.db.models import DEFAULT_PROCTOR_CONFIG, ProctorEvent, ProctorEventType, ProctorSeverity

# Each additional occurrence of the same event type counts a little less than the last.
REPEAT_DECAY = 0.75
MIN_MULTIPLIER = 0.25

SEVERITY_MULTIPLIER = {
    ProctorSeverity.INFO: 0.5,
    ProctorSeverity.WARNING: 1.0,
    ProctorSeverity.CRITICAL: 1.5,
}


@dataclass(frozen=True)
class SuspicionOutcome:
    score: float
    tab_switch_count: int
    should_flag: bool
    should_terminate: bool
    breakdown: dict[str, float]


def event_weight(event_type: ProctorEventType, config: dict) -> float:
    weights = {**DEFAULT_PROCTOR_CONFIG["weights"], **(config.get("weights") or {})}
    return float(weights.get(event_type.value, 1.0))


def score_events(
    events: Iterable[ProctorEvent], proctor_config: dict | None = None
) -> SuspicionOutcome:
    config = {**DEFAULT_PROCTOR_CONFIG, **(proctor_config or {})}

    seen: dict[str, int] = {}
    breakdown: dict[str, float] = {}
    total = 0.0
    tab_switches = 0

    for event in sorted(events, key=lambda e: e.occurred_at):
        key = event.event_type.value
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1

        multiplier = max(REPEAT_DECAY**occurrence, MIN_MULTIPLIER)
        multiplier *= SEVERITY_MULTIPLIER.get(event.severity, 1.0)

        contribution = event_weight(event.event_type, config) * multiplier
        total += contribution
        breakdown[key] = round(breakdown.get(key, 0.0) + contribution, 2)

        if event.event_type is ProctorEventType.TAB_SWITCH:
            tab_switches += 1

    total = round(total, 2)
    max_tab_switches = int(config.get("max_tab_switches", 3))
    flag_at = float(config.get("flag_on_score", 45.0))
    terminate_at = float(config.get("terminate_on_score", 100.0))

    return SuspicionOutcome(
        score=total,
        tab_switch_count=tab_switches,
        should_flag=total >= flag_at or tab_switches > max_tab_switches,
        should_terminate=total >= terminate_at,
        breakdown=breakdown,
    )


def severity_for(event_type: ProctorEventType) -> ProctorSeverity:
    """Default severity when the client does not supply one."""
    critical = {
        ProctorEventType.MULTIPLE_FACES,
        ProctorEventType.CAMERA_BLOCKED,
        ProctorEventType.DEVTOOLS_OPEN,
    }
    warning = {
        ProctorEventType.TAB_SWITCH,
        ProctorEventType.FULLSCREEN_EXIT,
        ProctorEventType.PASTE_ATTEMPT,
        ProctorEventType.FACE_MISSING,
    }
    if event_type in critical:
        return ProctorSeverity.CRITICAL
    if event_type in warning:
        return ProctorSeverity.WARNING
    return ProctorSeverity.INFO
