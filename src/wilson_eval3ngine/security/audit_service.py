"""Enhanced audit service with signing and API integration.

T6.1.7 - Integrate audit logging into API layer with signed checkpoints.

Security:
- Authorization/audit events can be written to the persistent audit ledger
- Audit events are persisted to the database, not just process logs
- Checkpoints can be signed with Ed25519 for integrity verification
- Events include project scope, actor identity, and correlation IDs
- ``log_event`` is deliberately non-blocking on ledger failure: it logs the
  failure and returns an empty hash. Callers that require audit persistence as
  a precondition must check the returned hash or enforce a fail-closed policy
  at their own service boundary.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..persistence.audit import AuditLedger
from ..persistence.database import Database
from .signing import AuditCheckpoint, SignatureEnvelope, TrustRegistry, sign_bytes
from ..util import new_id, utc_now

logger = logging.getLogger("wilson.security.audit")


class AuditService:
    """Audit convenience layer with signing and API-oriented metadata.

    The service wraps :class:`AuditLedger` with event categorization,
    correlation metadata, signed checkpoints, and helper methods for common
    authentication/authorization/data-access events.

    ``AuditLedger.append`` is the persistence primitive and raises on database
    failure. ``AuditService.log_event`` intentionally catches that exception so
    callers that only need best-effort audit telemetry are not automatically
    failed. Security-sensitive callers that require durable audit evidence
    before continuing must treat an empty returned hash as failure or call an
    explicitly fail-closed policy/service boundary.
    """

    def __init__(
        self,
        database: Database,
        trust_registry: TrustRegistry | None = None,
        signing_key: Any | None = None,
    ):
        self._ledger = AuditLedger(database)
        self._trust_registry = trust_registry
        self._signing_key = signing_key
        self._event_buffer: list[dict[str, Any]] = []
        self._buffer_size = 100

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
        """Log an audit event to the persistent ledger when available.

        Args:
            project_id: Project scope for the event
            event_type: Type of event (e.g., ``auth_success``/``auth_failure``)
            aggregate_type: Type of aggregate (e.g., ``experiment``/``operation``)
            aggregate_id: ID of the aggregate
            actor_id: Identity of the actor
            payload: Sanitized event payload; secrets must not be included
            correlation_id: Request correlation ID
            severity: Event severity (info, warning, error)

        Returns:
            The event hash when persistence succeeded; an empty string when the
            ledger append failed. An empty result is therefore a failure signal,
            not a valid audit identity.
        """
        if correlation_id:
            payload = {**payload, "_correlation_id": correlation_id}
        payload = {**payload, "_severity": severity}

        try:
            event_hash = self._ledger.append(
                project_id=project_id,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                actor_id=actor_id,
                payload=payload,
            )
            logger.info(
                "audit_event_logged",
                extra={
                    "event_type": event_type,
                    "project_id": project_id,
                    "aggregate_type": aggregate_type,
                    "aggregate_id": aggregate_id,
                    "actor_id": actor_id,
                    "event_hash": event_hash[:16],
                    "correlation_id": correlation_id,
                },
            )
            return event_hash
        except Exception as e:
            # This wrapper is intentionally non-blocking. The empty return value
            # is the caller-visible failure signal; callers that require audit
            # persistence must enforce their own fail-closed policy.
            logger.error(
                "audit_event_failed",
                extra={
                    "event_type": event_type,
                    "project_id": project_id,
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )
            return ""

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
        """Log an authentication event and return its audit hash on success."""
        event_type = "auth_success" if success else "auth_failure"
        severity = "info" if success else "warning"
        payload = {"method": method, "success": success}
        if failure_reason:
            payload["failure_reason"] = failure_reason
        return self.log_event(
            project_id=project_id,
            event_type=event_type,
            aggregate_type="auth",
            aggregate_id="auth_session",
            actor_id=actor_id,
            payload=payload,
            correlation_id=correlation_id,
            severity=severity,
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
    ) -> str:
        """Log an authorization decision and return its audit hash on success."""
        event_type = "authz_allowed" if allowed else "authz_denied"
        severity = "info" if allowed else "warning"
        return self.log_event(
            project_id=project_id,
            event_type=event_type,
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
            severity=severity,
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
    ) -> str:
        """Log a data-access event and return its audit hash on success."""
        return self.log_event(
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
        """Create a signed checkpoint over the current audit-chain root.

        Checkpoints are created only when a signing key is configured. When a
        trust registry is supplied, the newly created checkpoint must also
        verify against that registry before it is returned.
        """
        if self._signing_key is None:
            logger.warning(
                "checkpoint_skipped_no_signing_key",
                extra={"project_id": project_id},
            )
            return None

        from sqlalchemy import select  # noqa: PLC0415
        from ..persistence.database import AuditEventRow  # noqa: PLC0415

        event_hash_root = "none"
        try:
            with self._ledger.database.session() as session:
                latest = session.scalar(
                    select(AuditEventRow)
                    .where(AuditEventRow.project_id == project_id)
                    .order_by(AuditEventRow.created_at.desc(), AuditEventRow.id.desc())
                    .limit(1)
                )
                if latest:
                    event_hash_root = latest.event_hash
        except Exception as e:
            logger.error(
                "checkpoint_hash_retrieval_failed",
                extra={"error": str(e)},
            )

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

        if self._trust_registry is not None:
            is_valid = checkpoint.verify(self._trust_registry)
            if not is_valid:
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
        """Verify the canonical hash chain for one project."""
        try:
            return self._ledger.verify(project_id)
        except Exception as e:
            logger.error(
                "audit_verification_failed",
                extra={"error": str(e), "project_id": project_id},
            )
            return False


def get_audit_service(
    database: Database,
    signing_key: Any | None = None,
    trust_registry: TrustRegistry | None = None,
) -> AuditService:
    """Create an AuditService over the supplied database and trust material."""
    return AuditService(
        database=database,
        trust_registry=trust_registry,
        signing_key=signing_key,
    )


__all__ = [
    "AuditService",
    "get_audit_service",
]
