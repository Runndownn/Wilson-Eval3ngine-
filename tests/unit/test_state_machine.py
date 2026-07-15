import pytest

from wilson_eval3ngine.domain.enums import RunState
from wilson_eval3ngine.domain.state import InvalidStateTransition, validate_run_transition


def test_valid_run_transition():
    validate_run_transition(RunState.PENDING, RunState.LEASED)


def test_invalid_run_transition():
    with pytest.raises(InvalidStateTransition):
        validate_run_transition(RunState.PENDING, RunState.COMPLETED)
