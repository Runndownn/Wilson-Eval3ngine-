"""Persistent audit convenience service and signed checkpoint support.

The hash-linked ``AuditLedger`` is the durable security primitive. ``AuditService``
keeps a compatibility best-effort logging API for non-critical telemetry and an
explicit required API for security boundaries that must fail closed when audit
persistence is unavailable. Callers must choose that policy deliberately; a
failure must never be described as fail-closed when it is actually swallowed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..persistence.audit import AuditLedger
from ..persistence.database import Database
from ..util import new_id, utc_now
from .signing import AuditCheckpoint, TrustRegistry, sign_bytes

logger = logging.getLogger("wilson.security.audit")


class AuditPersistenceError(RuntimeError):
    """Raised when a required audit event cannot be durably persisted."""


class AuditService:
    """Audit convenience layer with explicit best-effort/required semantics.

    ``log_event`` is retained as a compatibility best-effort method and returns
    an empty string on failure. Security-sensitive API composition should use
    ``log_event_required`` (or ``AuditLedger.append`` directly), which raises
    ``AuditPersistenceError`` before the caller proceeds with its side effect.
    """

    def __init__(
        self,
        database: Database,
        trust_registry: TrustRegistry | None = None,
        signing_key: Any | None = None,
    ) -> None:
        self._ledger = AuditLedger(database)
        self._trust_registry = trust_registry
        self._signing_key = signing_key

    @staticmethod
    def _event_payload(
        payload: dict[str, Any],
        *,
        correlation_id: str,
        severity: str,
    ) -> dict[str, Any]:
        bounded = {**payload, "_severity": severity}
        if correlation_id:
            bounded["_correlation_id"] = correlation_id
        return bounded

    def _append(
        self,
        *,
        project_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor_id: str,
        payload: dict[str, Any],
        correlation_id: str,
        severity: str,
    ) -> str:
        event_hash = self._ledger.append(
            project_id=project_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_id=actor_id,
            payload=self._event_payload(
                payload,
                correlation_id=correlation_id,
                severity=severity,
            ),
        )
        logger.info(
            "audit_event_logged",
            extra={
                "event_type": event_type,
                "project_id": project_id,
                "aggregate_type": aggregate_type,
                "event_hash": event_hash[:16],
                "correlation_id": correlation_id,
            },
        )
        return event_hash

    def log_event(
        self,
        *,
        project_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor_id: str,
        payload: dict[str, Any],
        correlation_id: str = "",
        severity: str = "info",
    ) -> str:
        """Best-effort compatibility API; returns ``""`` if persistence fails."""
        try:
            return self._append(
                project_id=project_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                actor_id=actor_id,
                payload=payload,
                correlation_id=correlation_id,
                severity=severity,
            )
        except Exception as exc:
            logger.error(
                "audit_event_failed",
                extra={
                    "event_type": event_type,
                    "project_id": project_id,
                    "error_class": type(exc).__name__,
                    "correlation_id": correlation_id,
                },
            )
            return ""

    def log_event_required(
        self,
        *,
        project_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor_id: str,
        payload: dict[str, Any],
        correlation_id: str = "",
        severity: str = "info",
    ) -> str:
        """Persist an audit event or raise a bounded fail-closed error."""
        try:
            return self._append(
                project_id=project_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                actor_id=actor_id,
                payload=payload,
                correlation_id=correlation_id,
                severity=severity,
            )
        except Exception as exc:
            logger.error(
                "required_audit_event_failed",
                extra={
                    "event_type": event_type,
                    "project_id": project_id,
                    "error_class": type(exc).__name__,
                    "correlation_id": correlation_id,
                },
            )
            raise AuditPersistenceError(
                "required audit persistence is unavailable"
            ) from exc

    def log_auth_event(
        self,
        *,
        project_id: str,
        success: bool,
        actor_id: str,
        method: str = "oidc",
        failure_reason: str = "",
        correlation_id: str = "",
    ) -> str:
        """Best-effort authentication event helper."""
        payload: dict[str, Any] = {"method": method, "success": success}
        if failure_reason:
            payload["failure_reason"] = failure_reason
        return self.log_event(
            project_id=project_id,
            event_type="auth_success" if success else "auth_failure",
            aggregate_type="auth",
            aggregate_id="auth_session",
            actor_id=actor_id,
            payload=payload,
            correlation_id=correlation_id,
            severity="info" if success else "warning",
        )

    def log_authorization_event(
        self,
        *,
        project_id: str,
        actor_id: str,
        role: str,
        resource: str,
        action: str,
        allowed: bool,
        correlation_id: str = "",
        required: bool = False,
    ) -> str:
        """Persist an authorization decision with caller-selected failure policy."""
        method = self.log_event_required if required else self.log_event
        return method(
            project_id=project_id,
            event_type="authz_allowed" if allowed else "authz_denied",
            aggregate_type=resource,
            aggregate_id=resource,
            actor_id=actor_id,
            payload={
                "role": role,
                "resource": resource,
                "action": action,
                "allowed": allowed,
            },
            correlation_id=correlation_id,
            severity="info" if allowed else "warning",
        )

    def log_data_access_event(
        self,
        *,
        project_id: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        operation: str,
        correlation_id: str = "",
        required: bool = False,
    ) -> str:
        """Persist a data-access event with caller-selected failure policy."""
        method = self.log_event_required if required else self.log_event
        return method(
            project_id=project_id,
            event_type=f"data_access_{operation}",
            aggregate_type=resource_type,
            aggregate_id=resource_id,
            actor_id=actor_id,
            payload={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "operation": operation,
            },
            correlation_id=correlation_id,
            severity="info",
        )

    def create_signed_checkpoint(
        self,
        *,
        project_id: str,
        event_count: int,
        event_window_start: datetime | str,
        event_window_end: datetime | str,
    ) -> AuditCheckpoint | None:
        """Create and optionally trust-verify a checkpoint over the current tail."""
        if self._signing_key is None:
            logger.warning(
                "checkpoint_skipped_no_signing_key",
                extra={"project_id": project_id},
            )
            return None

        from sqlalchemy import select  # noqa: PLC0415

        from ..persistence.database import AuditEventRow  # noqa: PLC0415

        try:
            with self._ledger.database.session() as session:
                latest = session.scalar(
                    select(AuditEventRow)
                    .where(AuditEventRow.project_id == project_id)
                    .order_by(AuditEventRow.created_at.desc(), AuditEventRow.id.desc())
                    .limit(1)
                )
        except Exception as exc:
            logger.error(
                "checkpoint_hash_retrieval_failed",
                extra={
                    "project_id": project_id,
                    "error_class": type(exc).__name__,
                },
            )
            return None

        event_hash_root = latest.event_hash if latest else "none"
        if isinstance(event_window_start, datetime):
            event_window_start = event_window_start.isoformat()
        if isinstance(event_window_end, datetime):
            event_window_end = event_window_end.isoformat()

        now_iso = utc_now().isoformat()
        checkpoint_payload = f"{now_iso}:{event_count}:{event_hash_root}"
        envelope = sign_bytes(checkpoint_payload.encode(), self._signing_key)
        checkpoint = AuditCheckpoint(
            checkpoint_id=new_id("chk"),
            timestamp=now_iso,
            event_window_start=event_window_start,
            event_window_end=event_window_end,
            event_count=event_count,
            event_hash_chain_root=event_hash_root,
            signature=envelope,
            signer_key_id="primary",
        )

        if self._trust_registry is not None and not checkpoint.verify(
            self._trust_registry
        ):
            logger.error(
                "checkpoint_verification_failed",
                extra={"checkpoint_id": checkpoint.checkpoint_id},
            )
            return None

        logger.info(
            "checkpoint_created",
            extra={
                "project_id": project_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "event_count": event_count,
            },
        )
        return checkpoint

    def verify_audit_trail(self, project_id: str) -> bool:
        """Return whether the project audit hash chain is internally consistent."""
        try:
            return self._ledger.verify(project_id)
        except Exception as exc:
            logger.error(
                "audit_verification_failed",
                extra={
                    "error_class": type(exc).__name__,
                    "project_id": project_id,
                },
            )
            return False


def get_audit_service(
    database: Database,
    signing_key: Any | None = None,
    trust_registry: TrustRegistry | None = None,
) -> AuditService:
    return AuditService(
        database=database,
        trust_registry=trust_registry,
        signing_key=signing_key,
    )


__all__ = [
    "AuditPersistenceError",
    "AuditService",
    "get_audit_service",
]
