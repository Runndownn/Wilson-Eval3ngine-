import pytest

from wilson_eval3ngine.statistics.intervals import wilson_interval


def test_wilson_reference_value():
    interval = wilson_interval(5, 10)
    assert interval is not None
    assert interval.lower == pytest.approx(0.2366, abs=0.0002)
    assert interval.upper == pytest.approx(0.7634, abs=0.0002)


def test_wilson_empty_population_is_undefined():
    assert wilson_interval(0, 0) is None
