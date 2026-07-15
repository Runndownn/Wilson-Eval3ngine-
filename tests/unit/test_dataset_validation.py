"""
Dataset validation tests for Tranche A and Tranche B.

Validates dataset loading, case counts, and review states.
"""

import pytest

from wilson_eval3ngine.domain.io import load_dataset


class TestTrancheADataset:
    """Tests for Tranche A (security_boundary) dataset validation."""

    def test_tranche_a_loads_successfully(self, repo_root):
        """Tranche A security_boundary dataset loads."""
        dataset_path = repo_root / "examples" / "datasets" / "security_boundary_0.1.0.yaml"
        dataset = load_dataset(dataset_path)

        assert dataset.dataset_id == "ds_security_boundary"
        assert len(dataset.cases) == 8

    def test_tranche_a_has_dual_reviewers(self, repo_root):
        """Each Tranche A case has two reviewers."""
        dataset_path = repo_root / "examples" / "datasets" / "security_boundary_0.1.0.yaml"
        dataset = load_dataset(dataset_path)

        for case in dataset.cases:
            assert len(case.governance.reviewers) >= 2, f"Case {case.case_version_id} missing reviewers"


class TestTrancheBDataset:
    """Tests for Tranche B (hostile_inputs) dataset validation."""

    def test_tranche_b_loads_successfully(self, repo_root):
        """Tranche B hostile_inputs dataset loads."""
        dataset_path = repo_root / "examples" / "datasets" / "tranche_b_hostile_inputs_1.0.0.yaml"
        dataset = load_dataset(dataset_path)

        assert dataset.dataset_id == "ds_tranche_b_hostile_inputs"
        assert len(dataset.cases) == 8

    def test_tranche_b_has_dual_reviewers(self, repo_root):
        """Each Tranche B case has two reviewers."""
        dataset_path = repo_root / "examples" / "datasets" / "tranche_b_hostile_inputs_1.0.0.yaml"
        dataset = load_dataset(dataset_path)

        for case in dataset.cases:
            assert len(case.governance.reviewers) >= 2, f"Case {case.case_version_id} missing reviewers"

    def test_tranche_b_covers_required_categories(self, repo_root):
        """Tranche B covers all required hostile categories."""
        dataset_path = repo_root / "examples" / "datasets" / "tranche_b_hostile_inputs_1.0.0.yaml"
        dataset = load_dataset(dataset_path)

        categories = {case.category for case in dataset.cases}
        # Check for required categories (using actual values from the dataset)
        assert "critical_harm" in categories
        assert "prompt_injection" in categories
        assert "tool_use_simulation" in categories or "tool_simulation" in categories

    def test_tranche_b_has_critical_cases(self, repo_root):
        """Tranche B has critical severity cases."""
        dataset_path = repo_root / "examples" / "datasets" / "tranche_b_hostile_inputs_1.0.0.yaml"
        dataset = load_dataset(dataset_path)

        critical_cases = [c for c in dataset.cases if c.severity == "critical"]
        assert len(critical_cases) >= 1, "Tranche B requires at least one critical case"
