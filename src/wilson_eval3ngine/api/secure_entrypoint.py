"""Production ASGI entrypoint backed by an external secret authority.

Private backend implementation, workload identity, endpoints, namespaces, and
policies remain outside this repository. Startup values are resolved before the
normal app imports, redacted from logs, and removed from the mutable environment
once the validated application composition owns them.
"""

from __future__ import annotations

import logging
import os
from contextlib import ExitStack
from typing import Final

from ..security.log_redaction import install_sensitive_log_filter
from ..security.secrets_backend import SecretLease, build_secret_backend

_BINDINGS: Final[dict[str, str]] = {
    "WE3_DATABASE_URL": "DATABASE_URL",
    "WE3_REDIS_URL": "REDIS_URL",
    "WE3_ENCRYPTION_KEY": "ENCRYPTION_KEY",
    "WE3_CSRF_SECRET": "CSRF_SECRET",
}


def _compose_application():
    install_sensitive_log_filter(logging.getLogger())
    install_sensitive_log_filter(logging.getLogger("wilson"))

    environment = os.environ.get("WE3_ENVIRONMENT", "production").strip().lower()
    backend = build_secret_backend(environment=environment)
    previous = {name: os.environ.get(name) for name in _BINDINGS}

    try:
        with ExitStack() as leases:
            for environment_name, secret_name in _BINDINGS.items():
                lease = leases.enter_context(SecretLease.obtain(backend, secret_name))
                os.environ[environment_name] = lease.text()

            from .main import app as composed_app

            composed_app.state.secret_backend = backend
            composed_app.state.secret_backend_id = backend.backend_id
            composed_app.state.secret_source = "external_authority"
            return composed_app
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


app = _compose_application()

__all__ = ["app"]
