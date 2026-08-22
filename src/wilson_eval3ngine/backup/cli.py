"""Dedicated recovery CLI.

This CLI intentionally requires explicit PostgreSQL, KMS, signing, and trust
configuration. It does not default a physical backup command to SQLite or a
development key because those defaults make recovery evidence ambiguous.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from ..security.signing import TrustRegistry
from .backup_manager import (
    BackupManager,
    RecoveryBaseline,
    RecoveryOrchestrator,
    capture_recovery_baseline,
)
from .kms import build_backup_kms_from_env


app = typer.Typer(
    name="we3-backup",
    help="Encrypted PostgreSQL backup, WAL archival, PITR planning, and recovery.",
    no_args_is_help=True,
)


def _database_url(explicit: str | None = None) -> str:
    value = explicit or os.environ.get("WE3_DATABASE_URL", "")
    if not value:
        raise typer.BadParameter(
            "PostgreSQL URL is required via --database-url or WE3_DATABASE_URL"
        )
    if not value.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        raise typer.BadParameter(
            "Physical backup/PITR supports PostgreSQL only; a SQLite fallback is not valid"
        )
    return value


def _backup_root(explicit: Path | None = None) -> Path:
    return explicit or Path(os.environ.get("WE3_BACKUP_ROOT", "./var/backups"))


def _trust_registry() -> TrustRegistry:
    registry = TrustRegistry()
    values = os.environ.get("WE3_BACKUP_TRUSTED_SIGNER_FINGERPRINTS", "")
    for fingerprint in values.split(","):
        fingerprint = fingerprint.strip()
        if fingerprint:
            registry.trust_key(fingerprint)
    return registry


def _manager(
    *,
    database_url: str | None = None,
    backup_root: Path | None = None,
) -> BackupManager:
    return BackupManager(
        _database_url(database_url),
        _backup_root(backup_root),
        kms_client=build_backup_kms_from_env(),
        trust_registry=_trust_registry(),
    )


def _baseline(path: Path) -> RecoveryBaseline:
    try:
        return RecoveryBaseline.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise typer.BadParameter(f"Invalid recovery baseline {path}: {exc}") from exc


@app.command("create")
def create(
    key_id: str = typer.Option(..., "--key-id", help="External KMS key ID/ARN"),
    signing_key: Path = typer.Option(
        ..., "--signing-key", exists=True, dir_okay=False, readable=True
    ),
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Create a signed, KMS-envelope-encrypted physical PostgreSQL backup."""
    manager = _manager(database_url=database_url, backup_root=backup_root)
    metadata = manager.create_full_backup(key_id, signing_key)
    typer.echo(json.dumps(metadata.to_dict(), indent=2, sort_keys=True))


@app.command("wal-archive")
def wal_archive(
    wal_file: Path = typer.Option(
        ..., "--wal-file", exists=True, dir_okay=False, readable=True
    ),
    key_id: str = typer.Option(..., "--key-id", help="External KMS key ID/ARN"),
    signing_key: Path = typer.Option(
        ..., "--signing-key", exists=True, dir_okay=False, readable=True
    ),
    base_backup_id: str | None = typer.Option(None, "--base-backup-id"),
    wal_start_lsn: str = typer.Option("", "--start-lsn"),
    wal_end_lsn: str = typer.Option("", "--end-lsn"),
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Encrypt/sign one real PostgreSQL WAL segment from an archive location."""
    manager = _manager(database_url=database_url, backup_root=backup_root)
    metadata = manager.create_wal_archive(
        wal_file,
        key_id,
        signing_key,
        base_backup_id=base_backup_id,
        wal_start_lsn=wal_start_lsn,
        wal_end_lsn=wal_end_lsn,
    )
    typer.echo(json.dumps(metadata.to_dict(), indent=2, sort_keys=True))


@app.command("list")
def list_backups(
    limit: int = typer.Option(20, "--limit", min=1, max=1000),
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Read the durable backup-root catalogue."""
    manager = _manager(database_url=database_url, backup_root=backup_root)
    backups = manager.list_backups(limit=limit)
    typer.echo(
        json.dumps(
            {"count": len(backups), "backups": [item.to_dict() for item in backups]},
            indent=2,
            sort_keys=True,
        )
    )


@app.command("verify")
def verify(
    backup_id: str,
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Verify manifest hash/signature/trust, ciphertext, KMS unwrap, and AEAD tag."""
    manager = _manager(database_url=database_url, backup_root=backup_root)
    valid = manager.verify_backup_integrity(backup_id)
    typer.echo(json.dumps({"backup_id": backup_id, "valid": valid}, indent=2))
    if not valid:
        raise typer.Exit(code=1)


@app.command("capture-baseline")
def capture_baseline(
    output: Path = typer.Option(..., "--output", dir_okay=False),
    signing_key: Path = typer.Option(
        ..., "--signing-key", exists=True, dir_okay=False, readable=True
    ),
    database_url: str | None = typer.Option(None, "--database-url"),
) -> None:
    """Capture the signed pre-failure state that a restore must reconcile to."""
    baseline = capture_recovery_baseline(
        _database_url(database_url),
        signing_key_path=signing_key,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(baseline.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    typer.echo(
        json.dumps(
            {"output": str(output.resolve()), "payload_sha256": baseline.payload_sha256},
            indent=2,
        )
    )


@app.command("plan")
def plan(
    timestamp: str = typer.Option(..., "--timestamp", help="Target ISO-8601 timestamp"),
    baseline: Path = typer.Option(
        ..., "--baseline", exists=True, dir_okay=False, readable=True
    ),
    target_lsn: str | None = typer.Option(None, "--target-lsn"),
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Build a PITR plan only when real encrypted WAL coverage is continuous."""
    from datetime import datetime

    manager = _manager(database_url=database_url, backup_root=backup_root)
    try:
        target = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid ISO-8601 timestamp: {timestamp}") from exc
    result = manager.generate_restore_plan(
        target,
        recovery_baseline=_baseline(baseline),
        target_lsn=target_lsn,
    )
    typer.echo(json.dumps(result.to_dict(), indent=2, sort_keys=True))


@app.command("restore")
def restore(
    timestamp: str = typer.Option(..., "--timestamp"),
    baseline: Path = typer.Option(
        ..., "--baseline", exists=True, dir_okay=False, readable=True
    ),
    isolated_database_url: str = typer.Option(..., "--isolated-database-url"),
    data_directory: Path = typer.Option(..., "--data-directory"),
    target_lsn: str | None = typer.Option(None, "--target-lsn"),
    signing_key: Path | None = typer.Option(
        None, "--signing-key", exists=True, dir_okay=False, readable=True
    ),
    database_url: str | None = typer.Option(None, "--database-url"),
    backup_root: Path | None = typer.Option(None, "--backup-root"),
) -> None:
    """Execute an isolated PITR restore and reconcile it to the signed baseline."""
    from datetime import datetime

    manager = _manager(database_url=database_url, backup_root=backup_root)
    expected = _baseline(baseline)
    try:
        target = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid ISO-8601 timestamp: {timestamp}") from exc
    plan_value = manager.generate_restore_plan(
        target,
        recovery_baseline=expected,
        target_lsn=target_lsn,
    )
    orchestrator = RecoveryOrchestrator(
        manager,
        manager.database_url,
        trust_registry=manager.trust_registry or TrustRegistry(),
    )
    result = orchestrator.execute_isolated_restore(
        plan_value,
        isolated_database_url,
        data_directory=data_directory,
        recovery_baseline=expected,
        signing_key_path=signing_key,
    )
    typer.echo(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
