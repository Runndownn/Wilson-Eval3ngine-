from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from ..config import Settings


@dataclass(frozen=True, slots=True)
class RequestContext:
    project_id: str
    role: str


_ALLOWED_DEV_ROLES = {
    "viewer",
    "evaluation_engineer",
    "reviewer",
    "adjudicator",
    "project_admin",
    "release_authority",
}


def make_context_dependency(settings: Settings):
    def get_context(
        x_we3_project_id: str = Header(..., min_length=1, max_length=128),
        x_we3_role: str = Header("viewer"),
    ) -> RequestContext:
        if settings.auth_mode != "dev":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail={
                    "code": "oidc_backend_not_configured",
                    "retryable": False,
                    "safe_detail": "production OIDC adapter is not included in foundation build",
                },
            )
        if x_we3_role not in _ALLOWED_DEV_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "role_not_allowed",
                    "retryable": False,
                    "safe_detail": "role is not recognized",
                },
            )
        return RequestContext(project_id=x_we3_project_id, role=x_we3_role)

    return get_context
