from __future__ import annotations

import copy

import pytest

from wilson_eval3ngine.domain.contracts import ExperimentManifest
from wilson_eval3ngine.domain.io import load_dataset, load_experiment, resolve_dataset_path


def test_foundation_contracts_validate(foundation_manifest):
    manifest = load_experiment(foundation_manifest)
    dataset = load_dataset(resolve_dataset_path(foundation_manifest, manifest))
    assert manifest.schema_version == "we3.experiment.v1"
    assert dataset.schema_version == "we3.dataset.v1"
    assert len(dataset.cases) == 8
    assert len({case.prompt_family_id for case in dataset.cases}) == 8


def test_certification_rejects_response_cache(foundation_manifest):
    manifest = load_experiment(foundation_manifest)
    payload = manifest.model_dump(mode="json", by_alias=True)
    payload["execution"]["response_cache"] = "enabled"
    with pytest.raises(ValueError, match="caching"):
        ExperimentManifest.model_validate(payload)


def test_certification_requires_candidate(foundation_manifest):
    manifest = load_experiment(foundation_manifest)
    payload = manifest.model_dump(mode="json", by_alias=True)
    payload["models"] = [payload["models"][0]]
    with pytest.raises(ValueError, match="candidate"):
        ExperimentManifest.model_validate(payload)
