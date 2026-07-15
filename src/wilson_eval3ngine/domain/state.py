from __future__ import annotations

from .enums import RunState


_ALLOWED: dict[RunState, set[RunState]] = {
    RunState.PENDING: {RunState.LEASED, RunState.CANCELLED},
    RunState.LEASED: {RunState.RENDERING, RunState.PENDING, RunState.CANCELLED},
    RunState.RENDERING: {RunState.REQUESTING, RunState.MALFORMED, RunState.CANCELLED},
    RunState.REQUESTING: {
        RunState.RESPONSE_RECEIVED,
        RunState.PROVIDER_ERROR,
        RunState.TIMEOUT,
        RunState.EXHAUSTED_RETRIES,
        RunState.CANCELLED,
    },
    RunState.RESPONSE_RECEIVED: {RunState.PERSISTED, RunState.MALFORMED},
    RunState.PERSISTED: {RunState.GRADING, RunState.POISONED},
    RunState.GRADING: {
        RunState.REVIEW_PENDING,
        RunState.CLASSIFIED,
        RunState.POISONED,
    },
    RunState.REVIEW_PENDING: {
        RunState.ADJUDICATION_PENDING,
        RunState.CLASSIFIED,
        RunState.CANCELLED,
    },
    RunState.ADJUDICATION_PENDING: {RunState.CLASSIFIED, RunState.CANCELLED},
    RunState.CLASSIFIED: {RunState.METRIC_READY},
    RunState.METRIC_READY: {RunState.COMPLETED},
    RunState.COMPLETED: set(),
    RunState.PROVIDER_ERROR: set(),
    RunState.TIMEOUT: set(),
    RunState.CANCELLED: set(),
    RunState.MALFORMED: set(),
    RunState.POISONED: set(),
    RunState.EXHAUSTED_RETRIES: set(),
}


class InvalidStateTransition(ValueError):
    pass


def validate_run_transition(current: RunState, target: RunState) -> None:
    if target not in _ALLOWED[current]:
        raise InvalidStateTransition(f"invalid run transition: {current} -> {target}")
