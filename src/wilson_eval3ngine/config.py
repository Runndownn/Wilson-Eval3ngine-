from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlsplit


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _is_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == ""
    )


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings and explicit security trust decisions.

    The default profile is intentionally local and non-production. Staging and
    production require PostgreSQL, OIDC, Redis-backed distributed controls, and
    explicit browser/proxy trust configuration. The secure deployment profile
    supplies secrets through an external authority; ordinary environment-backed
    fields remain a compatibility surface rather than a production secret store.
    """

    database_url: str = "sqlite:///./var/we3.db"
    artifact_root: Path = Path("./var/artifacts")
    auth_mode: str = "dev"
    environment: str = "development"

    oidc_issuer: str = ""
    oidc_jwks_uri: str = ""
    oidc_audience: str = "wilson-eval3ngine-api"

    redis_url: str = ""
    encryption_key: str = ""
    csrf_secret: str = ""

    # Browser and reverse-proxy trust are deliberately empty by default. An
    # unset value means cross-origin browser access is not authorized and
    # forwarding headers are not trusted for security decisions.
    cors_allowed_origins: tuple[str, ...] = ()
    trusted_proxy_cidrs: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            database_url=os.getenv("WE3_DATABASE_URL", defaults.database_url),
            artifact_root=Path(
                os.getenv("WE3_ARTIFACT_ROOT", str(defaults.artifact_root))
            ),
            auth_mode=os.getenv("WE3_AUTH_MODE", defaults.auth_mode).strip().lower(),
            environment=os.getenv("WE3_ENVIRONMENT", defaults.environment).strip().lower(),
            oidc_issuer=os.getenv("WE3_OIDC_ISSUER", defaults.oidc_issuer).strip(),
            oidc_jwks_uri=os.getenv("WE3_OIDC_JWKS_URI", defaults.oidc_jwks_uri).strip(),
            oidc_audience=os.getenv("WE3_OIDC_AUDIENCE", defaults.oidc_audience).strip(),
            redis_url=os.getenv("WE3_REDIS_URL", defaults.redis_url).strip(),
            encryption_key=os.getenv("WE3_ENCRYPTION_KEY", defaults.encryption_key),
            csrf_secret=os.getenv("WE3_CSRF_SECRET", defaults.csrf_secret),
            cors_allowed_origins=_csv_tuple(os.getenv("WE3_CORS_ALLOWED_ORIGINS", "")),
            trusted_proxy_cidrs=_csv_tuple(os.getenv("WE3_TRUSTED_PROXY_CIDRS", "")),
        )

    @property
    def is_assurance_environment(self) -> bool:
        return self.environment in {"staging", "production"}

    def validate_for_production(self) -> None:
        """Fail before startup when an assurance environment is underspecified."""
        failures: list[str] = []
        if self.is_assurance_environment:
            if self.database_url.startswith("sqlite"):
                failures.append("staging/production requires PostgreSQL")
            if self.auth_mode != "oidc":
                failures.append("staging/production requires OIDC authentication")
            if str(self.artifact_root).startswith("."):
                failures.append(
                    "staging/production artifact storage must use a deployment-managed path/backend"
                )

            if not _is_https_url(self.oidc_issuer):
                failures.append("WE3_OIDC_ISSUER must be an HTTPS URL without credentials")
            if not _is_https_url(self.oidc_jwks_uri):
                failures.append("WE3_OIDC_JWKS_URI must be an HTTPS URL without credentials")
            if not self.oidc_audience or len(self.oidc_audience) > 256:
                failures.append("WE3_OIDC_AUDIENCE must be a bounded non-empty value")

            # Redis is an authority for both rate-limit and token-revocation
            # state in multi-worker deployments. Startup must prove it is
            # reachable rather than silently degrading to process-local state.
            if not self.redis_url:
                failures.append(
                    "staging/production requires WE3_REDIS_URL for distributed security state"
                )

            # These environment-backed fields are needed by the legacy direct
            # entrypoint. Dockerfile.secure/secure_entrypoint obtains them from
            # the external secret backend before constructing Settings.
            if not self.encryption_key:
                failures.append("staging/production requires WE3_ENCRYPTION_KEY")
            if not self.csrf_secret:
                failures.append("staging/production requires WE3_CSRF_SECRET")

            for origin in self.cors_allowed_origins:
                if not _is_https_url(origin):
                    failures.append(
                        "WE3_CORS_ALLOWED_ORIGINS entries must be credential-free HTTPS origins"
                    )
                    break

        if failures:
            raise ValueError("; ".join(failures))


__all__ = ["Settings"]
