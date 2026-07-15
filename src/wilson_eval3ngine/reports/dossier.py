from __future__ import annotations

from html import escape
from pathlib import Path
import json
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..domain.contracts import GateDecision, MetricSnapshot
from ..security.signing import SignatureEnvelope, sign_bytes, verify_bytes
from ..util import canonical_json, sha256_hex, utc_now


def build_dossier(
    *,
    experiment_id: str,
    project_id: str,
    manifest_hash: str,
    dataset_hash: str,
    snapshots: list[MetricSnapshot],
    gates: list[GateDecision],
    artifact_index: list[dict[str, Any]],
    audit_chain_verified: bool,
    limitations: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "we3.release_dossier.v1",
        "generated_at": utc_now().isoformat(),
        "experiment_id": experiment_id,
        "project_id": project_id,
        "manifest_hash": manifest_hash,
        "dataset_hash": dataset_hash,
        "metric_snapshots": [
            snapshot.model_dump(mode="json") for snapshot in snapshots
        ],
        "gate_decisions": [gate.model_dump(mode="json") for gate in gates],
        "artifact_index": artifact_index,
        "audit_chain_verified": audit_chain_verified,
        "limitations": limitations,
    }


def write_signed_dossier(
    output_dir: str | Path,
    dossier: dict[str, Any],
    private_key: Ed25519PrivateKey,
) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    unsigned = canonical_json(dossier)
    envelope = sign_bytes(unsigned, private_key)
    signed = {
        **dossier,
        "dossier_sha256": sha256_hex(unsigned),
        "signature": envelope.to_dict(),
    }
    target = target_dir / "release_dossier.json"
    target.write_text(
        json.dumps(signed, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def write_safe_html(
    output_dir: str | Path,
    dossier: dict[str, Any],
) -> Path:
    """Writes a report that never embeds raw prompts or model responses."""
    rows: list[str] = []
    for gate in dossier["gate_decisions"]:
        rows.append(
            "<tr>"
            f"<td>{escape(gate['model_config_id'])}</td>"
            f"<td>{escape(gate['status'])}</td>"
            f"<td>{escape('; '.join(gate['reasons']) or 'none')}</td>"
            "</tr>"
        )

    metric_sections: list[str] = []
    for snapshot in dossier["metric_snapshots"]:
        metric_rows = []
        for metric in snapshot["metrics"]:
            value = "undefined" if metric["value"] is None else f"{metric['value']:.4f}"
            interval = metric.get("interval")
            ci = (
                "undefined"
                if interval is None
                else f"[{interval['lower']:.4f}, {interval['upper']:.4f}]"
            )
            metric_rows.append(
                "<tr>"
                f"<td>{escape(metric['metric_id'])}</td>"
                f"<td>{metric['numerator']}</td>"
                f"<td>{metric['denominator']}</td>"
                f"<td>{value}</td>"
                f"<td>{ci}</td>"
                "</tr>"
            )
        metric_sections.append(
            f"<h2>{escape(snapshot['model_config_id'])}</h2>"
            "<table><thead><tr><th>Metric</th><th>Numerator</th>"
            "<th>Denominator</th><th>Value</th><th>95% CI</th></tr></thead>"
            f"<tbody>{''.join(metric_rows)}</tbody></table>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wilson Eval3ngine Release Dossier</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #777; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #eee; }}
code {{ overflow-wrap: anywhere; }}
.warning {{ border-left: .4rem solid #a66a00; padding-left: 1rem; }}
</style>
</head>
<body>
<h1>Wilson Eval3ngine Release Dossier</h1>
<p><strong>Experiment:</strong> <code>{escape(dossier['experiment_id'])}</code></p>
<p><strong>Manifest hash:</strong> <code>{escape(dossier['manifest_hash'])}</code></p>
<div class="warning"><strong>Safety:</strong> This report intentionally excludes raw prompts and responses. Evidence access must use the authorized artifact path.</div>
<h2>Gate decisions</h2>
<table><thead><tr><th>Model</th><th>Status</th><th>Reasons</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{''.join(metric_sections)}
<h2>Known limitations</h2>
<ul>{''.join(f'<li>{escape(item)}</li>' for item in dossier['limitations'])}</ul>
</body>
</html>
"""
    target = Path(output_dir) / "report.safe.html"
    target.write_text(html, encoding="utf-8")
    return target


def verify_signed_dossier(path: str | Path) -> dict[str, Any]:
    """Verify the embedded digest and Ed25519 signature of a dossier.

    The public key is carried in the signature envelope so this proves artifact
    integrity, not organizational trust. Production deployments must additionally
    validate the public-key fingerprint against an approved trust registry.
    """

    source = Path(path)
    try:
        signed = json.loads(source.read_text(encoding="utf-8"))
        signature = SignatureEnvelope(**signed["signature"])
        declared_digest = str(signed["dossier_sha256"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {
            "valid": False,
            "hash_valid": False,
            "signature_valid": False,
            "error": f"invalid_dossier: {exc}",
        }

    unsigned = {
        key: value
        for key, value in signed.items()
        if key not in {"dossier_sha256", "signature"}
    }
    payload = canonical_json(unsigned)
    actual_digest = sha256_hex(payload)
    hash_valid = actual_digest == declared_digest
    signature_valid = verify_bytes(payload, signature)
    return {
        "valid": hash_valid and signature_valid,
        "hash_valid": hash_valid,
        "signature_valid": signature_valid,
        "dossier_sha256": actual_digest,
        "public_key_fingerprint_sha256": (
            signature.public_key_fingerprint_sha256
        ),
        "trust_registry_validated": False,
    }
