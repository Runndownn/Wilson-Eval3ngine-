"""PostgreSQL-specific primitives for backup and PITR.

The recovery path treats the database URL as a security boundary. Connection
options that affect TLS/authentication are either preserved for libpq or rejected;
they are never silently dropped when invoking PostgreSQL command-line tools.
Secrets are transported through the child environment rather than command-line
arguments, and physical backup refuses ambiguous/non-PostgreSQL targets.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


_WAL_NAME = re.compile(r"^[0-9A-F]{24}$")

# Only options with a direct, documented libpq environment equivalent are
# accepted by the command-line backup path. Rejecting unknown parameters is
# preferable to silently weakening a connection policy present in the URL.
_LIBPQ_QUERY_ENV = {
    "application_name": "PGAPPNAME",
    "channel_binding": "PGCHANNELBINDING",
    "connect_timeout": "PGCONNECT_TIMEOUT",
    "gssencmode": "PGGSSENCMODE",
    "krbsrvname": "PGKRBSRVNAME",
    "options": "PGOPTIONS",
    "passfile": "PGPASSFILE",
    "sslcert": "PGSSLCERT",
    "sslcrl": "PGSSLCRL",
    "sslcrldir": "PGSSLCRLDIR",
    "sslkey": "PGSSLKEY",
    "sslmode": "PGSSLMODE",
    "sslpassword": "PGSSLPASSWORD",
    "sslrootcert": "PGSSLROOTCERT",
    "target_session_attrs": "PGTARGETSESSIONATTRS",
}


class PostgreSQLBackupError(RuntimeError):
    """Raised when PostgreSQL backup or recovery prerequisites are invalid."""


@dataclass(frozen=True, slots=True)
class PostgreSQLConnection:
    host: str
    port: int
    database: str
    user: str
    password: str
    query_parameters: dict[str, str] = field(default_factory=dict)

    def subprocess_env(self) -> dict[str, str]:
        """Return libpq environment preserving the validated connection policy."""
        env = os.environ.copy()
        env.update(
            {
                "PGHOST": self.host,
                "PGPORT": str(self.port),
                "PGDATABASE": self.database,
                "PGUSER": self.user,
            }
        )
        if self.password:
            env["PGPASSWORD"] = self.password
        else:
            # Do not accidentally inherit a credential for a different target.
            env.pop("PGPASSWORD", None)
        for name, value in self.query_parameters.items():
            env[_LIBPQ_QUERY_ENV[name]] = value
        return env


@dataclass(frozen=True, slots=True)
class PostgreSQLIdentity:
    database_name: str
    system_identifier: str
    timeline_id: int
    wal_segment_size_bytes: int
    current_lsn: str
    current_wal_segment: str
    server_version: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_postgresql_url(database_url: str) -> PostgreSQLConnection:
    """Parse a PostgreSQL URL without discarding security-relevant options."""
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres", "postgresql+psycopg"}:
        raise PostgreSQLBackupError(
            "Physical backup/PITR requires a PostgreSQL URL; SQLite and other "
            "database URLs are not supported by this recovery path."
        )
    if parsed.fragment:
        raise PostgreSQLBackupError("PostgreSQL backup URL must not contain a fragment")
    if not parsed.hostname:
        raise PostgreSQLBackupError("PostgreSQL backup URL must include a host")
    if parsed.username is None or not unquote(parsed.username).strip():
        raise PostgreSQLBackupError(
            "PostgreSQL backup URL must include an explicit least-privilege user"
        )
    database = unquote(parsed.path.lstrip("/"))
    if not database or "/" in database:
        raise PostgreSQLBackupError(
            "PostgreSQL backup URL must include exactly one database name"
        )

    query_parameters: dict[str, str] = {}
    for name, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = name.strip().lower()
        if normalized not in _LIBPQ_QUERY_ENV:
            raise PostgreSQLBackupError(
                f"Unsupported PostgreSQL backup connection parameter: {name!r}"
            )
        if normalized in query_parameters:
            raise PostgreSQLBackupError(
                f"Duplicate PostgreSQL backup connection parameter: {name!r}"
            )
        if "\x00" in value:
            raise PostgreSQLBackupError(
                f"Invalid NUL byte in PostgreSQL connection parameter: {name!r}"
            )
        query_parameters[normalized] = value

    return PostgreSQLConnection(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=database,
        user=unquote(parsed.username),
        password=unquote(parsed.password or ""),
        query_parameters=query_parameters,
    )


def sqlalchemy_postgresql_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    raise PostgreSQLBackupError("Expected a PostgreSQL database URL")


def _parse_pg_size(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s*(B|kB|MB|GB|TB)\s*", value, flags=re.IGNORECASE)
    if not match:
        raise PostgreSQLBackupError(f"Unsupported PostgreSQL size value: {value!r}")
    amount = int(match.group(1))
    unit = match.group(2).lower()
    multiplier = {
        "b": 1,
        "kb": 1024,
        "mb": 1024**2,
        "gb": 1024**3,
        "tb": 1024**4,
    }[unit]
    return amount * multiplier


def capture_postgresql_identity(database_url: str) -> PostgreSQLIdentity:
    """Capture the database/system/WAL identity required for recovery lineage."""
    # Parse first so the CLI and SQL paths share the same validation contract.
    parse_postgresql_url(database_url)
    engine = create_engine(
        sqlalchemy_postgresql_url(database_url),
        poolclass=NullPool,
        future=True,
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                      current_database() AS database_name,
                      (SELECT system_identifier::text FROM pg_control_system()) AS system_identifier,
                      (SELECT timeline_id FROM pg_control_checkpoint()) AS timeline_id,
                      current_setting('wal_segment_size') AS wal_segment_size,
                      pg_current_wal_lsn()::text AS current_lsn,
                      pg_walfile_name(pg_current_wal_lsn()) AS current_wal_segment,
                      current_setting('server_version') AS server_version
                    """
                )
            ).mappings().one()
            tablespaces = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM pg_tablespace
                    WHERE spcname NOT IN ('pg_default', 'pg_global')
                    """
                )
            ).scalar_one()
            if tablespaces:
                raise PostgreSQLBackupError(
                    "Native streaming backup currently requires a cluster without "
                    "user-defined tablespaces. Use the deployment platform backup "
                    "service for clusters with external tablespaces."
                )
            return PostgreSQLIdentity(
                database_name=str(row["database_name"]),
                system_identifier=str(row["system_identifier"]),
                timeline_id=int(row["timeline_id"]),
                wal_segment_size_bytes=_parse_pg_size(str(row["wal_segment_size"])),
                current_lsn=str(row["current_lsn"]),
                current_wal_segment=str(row["current_wal_segment"]).upper(),
                server_version=str(row["server_version"]),
            )
    finally:
        engine.dispose()


def require_pg_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    pg_config = shutil.which("pg_config")
    if pg_config:
        result = subprocess.run(
            [pg_config, "--bindir"],
            capture_output=True,
            text=True,
            check=True,
        )
        candidate = Path(result.stdout.strip()) / name
        if candidate.is_file():
            return str(candidate)
    raise PostgreSQLBackupError(
        f"Required PostgreSQL tool {name!r} is not available on PATH or via pg_config"
    )


def tool_version(name: str) -> str:
    executable = require_pg_tool(name)
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() or result.stderr.strip()


def basebackup_command(database_url: str) -> tuple[list[str], dict[str, str]]:
    """Build a credential-safe pg_basebackup command streaming tar to stdout.

    Host/user/password/TLS policy travel through libpq environment variables so
    credentials never appear in argv and URL query security options are not lost.
    """
    connection = parse_postgresql_url(database_url)
    command = [
        require_pg_tool("pg_basebackup"),
        "--pgdata",
        "-",
        "--format",
        "tar",
        "--wal-method",
        "fetch",
        "--checkpoint",
        "fast",
        "--no-password",
        "--progress",
    ]
    return command, connection.subprocess_env()


def wal_segment_index(name: str, wal_segment_size_bytes: int) -> tuple[int, int]:
    """Return ``(timeline, absolute-segment-index)`` for a 24-hex WAL filename."""
    normalized = name.upper()
    if not _WAL_NAME.fullmatch(normalized):
        raise PostgreSQLBackupError(f"Invalid PostgreSQL WAL segment filename: {name!r}")
    if (
        wal_segment_size_bytes <= 0
        or wal_segment_size_bytes > 1024**3
        or (wal_segment_size_bytes & (wal_segment_size_bytes - 1)) != 0
    ):
        raise PostgreSQLBackupError(
            f"Invalid WAL segment size: {wal_segment_size_bytes}"
        )
    timeline = int(normalized[:8], 16)
    log = int(normalized[8:16], 16)
    segment = int(normalized[16:24], 16)
    segments_per_log = 0x100000000 // wal_segment_size_bytes
    if segment >= segments_per_log:
        raise PostgreSQLBackupError(
            f"WAL segment number {segment} is invalid for size {wal_segment_size_bytes}"
        )
    return timeline, log * segments_per_log + segment


def wal_segments_are_contiguous(names: list[str], wal_segment_size_bytes: int) -> bool:
    if not names:
        return True
    parsed = [wal_segment_index(name, wal_segment_size_bytes) for name in names]
    timeline = parsed[0][0]
    previous = parsed[0][1]
    for current_timeline, current in parsed[1:]:
        if current_timeline != timeline or current != previous + 1:
            return False
        previous = current
    return True


def lsn_to_integer(lsn: str) -> int:
    try:
        high, low = lsn.split("/", 1)
        return (int(high, 16) << 32) + int(low, 16)
    except Exception as exc:
        raise PostgreSQLBackupError(f"Invalid PostgreSQL LSN: {lsn!r}") from exc


def wal_segment_for_lsn(lsn: str, timeline_id: int, wal_segment_size_bytes: int) -> str:
    value = lsn_to_integer(lsn)
    absolute_segment = value // wal_segment_size_bytes
    segments_per_log = 0x100000000 // wal_segment_size_bytes
    log, segment = divmod(absolute_segment, segments_per_log)
    return f"{timeline_id:08X}{log:08X}{segment:08X}"


__all__ = [
    "PostgreSQLBackupError",
    "PostgreSQLConnection",
    "PostgreSQLIdentity",
    "basebackup_command",
    "capture_postgresql_identity",
    "lsn_to_integer",
    "parse_postgresql_url",
    "require_pg_tool",
    "sqlalchemy_postgresql_url",
    "tool_version",
    "wal_segment_for_lsn",
    "wal_segment_index",
    "wal_segments_are_contiguous",
]
