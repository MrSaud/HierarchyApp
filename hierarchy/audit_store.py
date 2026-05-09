"""Persist audit events to the database (AuditLog model)."""

import logging

from django.contrib.auth import get_user_model

from .audit_context import get_audit_actor, get_audit_ip
from .models import AuditLog

logger = logging.getLogger(__name__)


def record_audit(action: str, details: str, *, user=None, ip: str | None = None):
    """
    Store one audit row. When ``user`` / ``ip`` are omitted, uses thread-local
    request context from AuditMiddleware when available.
    """
    User = get_user_model()
    if user is None:
        uid, _ = get_audit_actor()
        if uid is not None:
            try:
                user = User.objects.get(pk=uid)
            except User.DoesNotExist:
                user = None
    if ip is None:
        ip = get_audit_ip()
    try:
        AuditLog.objects.create(
            action=action,
            details=details,
            user=user,
            ip_address=(ip or "")[:45],
        )
    except Exception:
        logger.exception("Failed to persist audit log entry")
