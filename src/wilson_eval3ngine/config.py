from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    The default profile is intentionally local and non-production. Production
    deployments must provide PostgreSQL, an external immutable object store,
    OIDC, and managed signing keys.
    """

    database_url: str = "sqlite:///./var/we3.db"
    artifact_root: Path = Path("./var/artifacts")
    auth_mode: str = "dev"
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            database_url=os.getenv("WE3_DATABASE_URL", defaults.database_url),
            artifact_root=Path(
                os.getenv("WE3_ARTIFACT_ROOT", str(defaults.artifact_root))
            ),
            auth_mode=os.getenv("WE3_AUTH_MODE", defaults.auth_mode),
            environment=os.getenv("WE3_ENVIRONMENT", defaults.environment),
        )

    def validate_for_production(self) -> None:
        failures: list[str] = []
        if self.environment == "production":
            if self.database_url.startswith("sqlite"):
                failures.append("production requires PostgreSQL")
            if self.auth_mode == "dev":
                failures.append("production may not use development header authentication")
            if str(self.artifact_root).startswith("."):
                failures.append("production requires an external immutable object store")
        if failures:
            raise ValueError("; ".join(failures))
