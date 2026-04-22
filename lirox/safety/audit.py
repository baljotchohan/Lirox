"""Centralized audit trail persistence."""
from __future__ import annotations

import logging
from functools import lru_cache

_logger = logging.getLogger("lirox.safety.audit")


@lru_cache(maxsize=1)
def _db():
    from lirox.database.store import DatabaseStore
    return DatabaseStore()


def log_audit_event(
    action: str,
    target: str,
    *,
    status: str = "ok",
    detail: str = "",
    user_approved: bool = False,
) -> None:
    """Persist an autonomous action audit event (best-effort)."""
    try:
        from lirox.database.models import AuditEvent

        _db().audit(
            AuditEvent(
                action=action,
                target=target[:1000],
                status=status,
                detail=detail[:4000],
                user_approved=user_approved,
            )
        )
    except Exception as exc:
        _logger.debug("Audit persist failed: %s", exc)

