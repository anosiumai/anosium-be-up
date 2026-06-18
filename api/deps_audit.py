"""
HIPAA audit dependency for patient data reads.

Usage — add to any endpoint that returns patient data:

    @router.get("/{patient_id}")
    async def get_patient(
        patient_id: int,
        _: None = Depends(log_patient_read),   # ← add this
        current_user: User = Depends(deps.get_current_user),
        ...
    ):

Or with request context (IP address):

    @router.get("/{patient_id}/history")
    async def get_patient_history(
        patient_id: int,
        audit = Depends(patient_read_auditor),  # factory variant
        ...
    ):
        audit(patient_id)   # call after you know which patient was accessed
"""

from typing import Optional
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user, get_current_tenant
from models.user import User
from models.tenant import Tenant
from repositories.audit import DataAccessLogRepository


def log_patient_read(
    patient_id: int,                                    # path param — FastAPI injects automatically
    request: Request,
    current_user: User   = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session          = Depends(get_db),
) -> None:
    """
    FastAPI dependency: write a DataAccessLog row for every patient GET.

    Drop this into `Depends(...)` on any endpoint that returns patient
    data.  It runs before the endpoint body, so the log is written even
    if the response is later cached or modified by middleware.

    Failures are swallowed so a logging hiccup never blocks a clinical
    read — but are logged at ERROR level for alerting.
    """
    # ponytail: fire-and-forget; clinical reads must never be blocked by audit writes
    try:
        repo = DataAccessLogRepository(db, current_tenant.id, current_user.id)
        repo.log_patient_access(
            patient_id=patient_id,
            user_id=current_user.id,
            access_type="read",
            accessed_fields=None,           # field-level tracking added when needed
            purpose="api_read",
            ip_address=_get_ip(request),
        )
        db.flush()
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "DataAccessLog write failed for patient_id=%s user_id=%s",
            patient_id, current_user.id,
        )


def _get_ip(request: Request) -> Optional[str]:
    """Extract real client IP, honouring proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None