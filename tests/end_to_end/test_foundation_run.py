import json

from wilson_eval3ngine.application.service import EvaluationService
from wilson_eval3ngine.security.signing import SignatureEnvelope, verify_bytes
from wilson_eval3ngine.reports.dossier import verify_signed_dossier
from wilson_eval3ngine.util import canonical_json


def test_foundation_run_is_reproducible_and_signed(tmp_path, foundation_manifest):
    service = EvaluationService(
        database_url=f"sqlite:///{tmp_path / 'we3.db'}",
        artifact_root=tmp_path / "artifacts",
    )
    outcome = service.run_manifest(
        foundation_manifest,
        output_dir=tmp_path / "output",
    )

    assert outcome.dossier_path.exists()
    assert outcome.safe_html_path.exists()
    assert outcome.result_index_path.exists()
    assert outcome.gate_statuses["mdl_mock_balanced"] == "indeterminate"

    signed = json.loads(outcome.dossier_path.read_text(encoding="utf-8"))
    envelope = SignatureEnvelope(**signed["signature"])
    unsigned = {
        key: value
        for key, value in signed.items()
        if key not in {"dossier_sha256", "signature"}
    }
    assert verify_bytes(canonical_json(unsigned), envelope)

    snapshots = {
        item["model_config_id"]: item for item in signed["metric_snapshots"]
    }
    balanced = {
        item["metric_id"]: item for item in snapshots["mdl_mock_balanced"]["metrics"]
    }
    over_refusal = {
        item["metric_id"]: item
        for item in snapshots["mdl_mock_over_refusal"]["metrics"]
    }
    assert balanced["WE3-HELP-FRR"]["value"] == 0.0
    assert over_refusal["WE3-HELP-FRR"]["value"] == 1.0
    assert signed["audit_chain_verified"] is True


def test_dossier_verifier_detects_tampering(tmp_path, foundation_manifest):
    service = EvaluationService(
        database_url=f"sqlite:///{tmp_path / 'verify.db'}",
        artifact_root=tmp_path / "artifacts",
    )
    outcome = service.run_manifest(
        foundation_manifest,
        output_dir=tmp_path / "output",
    )

    verified = verify_signed_dossier(outcome.dossier_path)
    assert verified["valid"] is True
    assert verified["trust_registry_validated"] is False

    tampered_path = tmp_path / "tampered.json"
    tampered = json.loads(outcome.dossier_path.read_text(encoding="utf-8"))
    tampered["experiment_id"] = "exp_tampered"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")

    rejected = verify_signed_dossier(tampered_path)
    assert rejected["valid"] is False
    assert rejected["hash_valid"] is False
    assert rejected["signature_valid"] is False
