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
    # OIDC settings for production
    oidc_issuer: str = ""
    oidc_jwks_uri: str = ""
    oidc_audience: str = "wilson-eval3ngine-api"

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
            oidc_issuer=os.getenv("WE3_OIDC_ISSUER", defaults.oidc_issuer),
            oidc_jwks_uri=os.getenv("WE3_OIDC_JWKS_URI", defaults.oidc_jwks_uri),
            oidc_audience=os.getenv("WE3_OIDC_AUDIENCE", defaults.oidc_audience),
        )

    def validate_for_production(self) -> None:
        failures: list[str] = []
        if self.environment in ("production", "staging"):
            if self.database_url.startswith("sqlite"):
                failures.append("production requires PostgreSQL")
            if self.auth_mode == "dev":
                failures.append("production may not use development header authentication")
            if str(self.artifact_root).startswith("."):
                failures.append("production requires an external immutable object store")
            # OIDC validation for production
            if self.auth_mode == "oidc":
                if not self.oidc_issuer:
                    failures.append("production OIDC mode requires WE3_OIDC_ISSUER")
                if not self.oidc_jwks_uri:
                    failures.append("production OIDC mode requires WE3_OIDC_JWKS_URI")
        if failures:
            raise ValueError("; ".join(failures))
