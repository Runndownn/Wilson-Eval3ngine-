"""Production ASGI entrypoint backed by an external secret authority.

This module is the container entrypoint, not a general import convenience. It
resolves the small fixed set of startup secrets through the configured public
``SecretBackend`` contract before importing the normal application composition.
Private backend implementation, workload identity, endpoints, namespaces, and
policies remain outside this repository.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from typing import Final

from ..security.secrets_backend import SecretLease, build_secret_backend

_BINDINGS: Final[dict[str, str]] = {
    "WE3_DATABASE_URL": "DATABASE_URL",
    "WE3_REDIS_URL": "REDIS_URL",
    "WE3_ENCRYPTION_KEY": "ENCRYPTION_KEY",
    "WE3_CSRF_SECRET": "CSRF_SECRET",
}


def _compose_application():
    environment = os.environ.get("WE3_ENVIRONMENT", "production").strip().lower()
    backend = build_secret_backend(environment=environment)
    previous = {name: os.environ.get(name) for name in _BINDINGS}

    try:
        with ExitStack() as leases:
            for environment_name, secret_name in _BINDINGS.items():
                lease = leases.enter_context(SecretLease.obtain(backend, secret_name))
                os.environ[environment_name] = lease.text()

            # Import only after authoritative startup values have been staged.
            from .main import app as composed_app

            composed_app.state.secret_backend = backend
            composed_app.state.secret_backend_id = backend.backend_id
            composed_app.state.secret_source = "external_authority"
            return composed_app
    finally:
        # Avoid leaving startup credentials in the mutable process environment.
        # The validated Settings object and initialized clients retain only the
        # values they require for operation.
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


app = _compose_application()

__all__ = ["app"]
