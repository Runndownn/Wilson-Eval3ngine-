from __future__ import annotations

import os

import pytest

from wilson_eval3ngine.backup import postgres as pg


def test_parse_postgresql_url_requires_explicit_user() -> None:
    with pytest.raises(pg.PostgreSQLBackupError, match="explicit least-privilege user"):
        pg.parse_postgresql_url("postgresql://db.example.test/eval")


def test_parse_postgresql_url_rejects_silently_dropped_options() -> None:
    with pytest.raises(pg.PostgreSQLBackupError, match="Unsupported PostgreSQL backup connection parameter"):
        pg.parse_postgresql_url(
            "postgresql://backup@db.example.test/eval?unknown_security_flag=required"
        )


def test_parse_postgresql_url_rejects_duplicate_connection_options() -> None:
    with pytest.raises(pg.PostgreSQLBackupError, match="Duplicate PostgreSQL backup connection parameter"):
        pg.parse_postgresql_url(
            "postgresql://backup@db.example.test/eval?sslmode=require&sslmode=verify-full"
        )


def test_subprocess_env_preserves_tls_policy_without_password_in_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "require_pg_tool", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv("PGPASSWORD", "wrong-inherited-secret")
    command, env = pg.basebackup_command(
        "postgresql://backup:correct-secret@db.example.test:5433/eval"
        "?sslmode=verify-full&sslrootcert=%2Fetc%2Fssl%2Fdb-ca.pem"
        "&channel_binding=require"
    )

    rendered = " ".join(command)
    assert "correct-secret" not in rendered
    assert "db.example.test" not in rendered
    assert env["PGHOST"] == "db.example.test"
    assert env["PGPORT"] == "5433"
    assert env["PGDATABASE"] == "eval"
    assert env["PGUSER"] == "backup"
    assert env["PGPASSWORD"] == "correct-secret"
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/etc/ssl/db-ca.pem"
    assert env["PGCHANNELBINDING"] == "require"


def test_subprocess_env_does_not_inherit_unrelated_pgpassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PGPASSWORD", "stale")
    connection = pg.parse_postgresql_url(
        "postgresql://backup@db.example.test/eval?sslmode=require"
    )
    env = connection.subprocess_env()
    assert "PGPASSWORD" not in env
    assert os.environ["PGPASSWORD"] == "stale"
