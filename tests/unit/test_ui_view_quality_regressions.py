from __future__ import annotations

import pytest

from wilson_eval3ngine.reports.models import CanonicalReport
from wilson_eval3ngine.ui.views import build_executive_summary


def test_executive_summary_does_not_fabricate_missing_aggregates() -> None:
    summary = build_executive_summary(
        CanonicalReport(
            experiment_id="exp",
            project_id="proj",
            gate_statuses={"model": "pass"},
        )
    )

    assert summary.release_status == "pass"
    assert summary.support_percentage is None
    assert summary.uncertainty_percentage is None


def test_unknown_gate_status_fails_closed() -> None:
    summary = build_executive_summary(
        CanonicalReport(
            experiment_id="exp",
            project_id="proj",
            gate_statuses={"model": "unexpected"},
        )
    )

    assert summary.release_status == "indeterminate"


def test_negative_executive_operational_values_are_rejected() -> None:
    report = CanonicalReport(experiment_id="exp", project_id="proj")
    with pytest.raises(ValueError, match="cost_usd"):
        build_executive_summary(report, cost_usd=-0.01)
    with pytest.raises(ValueError, match="freshness_hours"):
        build_executive_summary(report, freshness_hours=-0.01)
