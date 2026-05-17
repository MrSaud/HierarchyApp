"""Daily per-tenant inbound / outbound API usage counters."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from .api_auth import tenant_api_key_matches
from .models import Tenant, TenantApiUsageDaily
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant_id

logger = logging.getLogger(__name__)

INBOUND_SKIP_URL_NAMES = frozenset({"api_login", "api_users"})

OPERATION_LABELS: dict[str, str] = {
    "api_v1_employee_get": "GET /api/v1/employees/",
    "api_employee_get": "GET /api/employees/",
    "api_v1_employee_signatures_get": "GET /api/v1/employees/signatures/",
    "api_employee_signatures_get": "GET /api/employees/signatures/",
    "api_v1_employee_reports_to_get": "GET /api/v1/employees/reports-to/",
    "api_reports_to_get": "GET /api/employees/reports-to/",
    "api_v1_org_units_list": "GET /api/v1/organization/units/",
    "api_org_units_list": "GET /api/organization/units/",
    "api_v1_assignments_list": "GET /api/v1/organization/assignments/",
    "api_v1_org_units_bulk": "PATCH /api/v1/organization/units/bulk/",
    "api_v1_assignments_bulk": "PATCH /api/v1/organization/assignments/bulk/",
    "api_login": "POST /api/auth/login/",
    "api_users": "POST /api/auth/users/",
    "health": "GET /api/health (AD)",
    "ad_sync": "GET /api/auth/users (AD sync)",
    "ad_login": "GET /api/auth/users (AD login)",
}


def operation_label(operation: str) -> str:
    return OPERATION_LABELS.get(operation, operation)


def record_tenant_api_usage(
    tenant: Tenant | None,
    direction: str,
    operation: str,
    *,
    is_error: bool = False,
) -> None:
    """Increment today's counter for tenant + direction + operation."""
    if tenant is None:
        return
    operation = (operation or "unknown")[:128]
    today = timezone.localdate()
    now = timezone.now()
    try:
        with transaction.atomic():
            row, _ = TenantApiUsageDaily.objects.select_for_update().get_or_create(
                tenant=tenant,
                date=today,
                direction=direction,
                operation=operation,
                defaults={
                    "request_count": 0,
                    "error_count": 0,
                    "last_request_at": now,
                },
            )
            row.request_count += 1
            if is_error:
                row.error_count += 1
            row.last_request_at = now
            row.save(
                update_fields=["request_count", "error_count", "last_request_at"],
            )
    except Exception:
        logger.exception(
            "Failed to record API usage tenant=%s direction=%s operation=%s",
            tenant.pk,
            direction,
            operation,
        )


def record_inbound_api_usage(
    tenant: Tenant | None,
    operation: str,
    *,
    is_error: bool = False,
) -> None:
    record_tenant_api_usage(
        tenant,
        TenantApiUsageDaily.Direction.INBOUND,
        operation,
        is_error=is_error,
    )


def record_outbound_api_usage(
    tenant: Tenant | None,
    operation: str,
    *,
    is_error: bool = False,
) -> None:
    record_tenant_api_usage(
        tenant,
        TenantApiUsageDaily.Direction.OUTBOUND,
        operation,
        is_error=is_error,
    )


def resolve_tenant_for_inbound_api(request) -> Tenant | None:
    """Best-effort tenant for inbound /api/ requests (query, ApiKey, staff scope)."""
    raw = request.GET.get("tenant_id")
    if raw not in (None, ""):
        try:
            tid = int(str(raw).strip())
        except (TypeError, ValueError):
            pass
        else:
            tenant = Tenant.objects.filter(pk=tid).first()
            if tenant is not None:
                return tenant

    for tenant in Tenant.objects.filter(is_active=True).exclude(api_key="").only(
        "pk", "api_key", "api_key_header", "slug", "name", "is_active"
    ):
        if tenant_api_key_matches(request, tenant):
            return tenant

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_staff:
        if user.is_superuser:
            return get_superuser_active_tenant(request)
        tid = get_user_tenant_id(user)
        if tid is not None:
            return Tenant.objects.filter(pk=tid).first()
    return None


def inbound_operation_from_request(request) -> str:
    match = getattr(request, "resolver_match", None)
    if match and match.url_name:
        return match.url_name
    return request.path.strip("/") or "unknown"


def maybe_record_inbound_api_request(request, response) -> None:
    if not request.path.startswith("/api/"):
        return
    if request.method == "OPTIONS":
        return
    match = getattr(request, "resolver_match", None)
    if match and match.url_name in INBOUND_SKIP_URL_NAMES:
        return
    tenant = resolve_tenant_for_inbound_api(request)
    if tenant is None:
        return
    is_error = getattr(response, "status_code", 500) >= 400
    record_inbound_api_usage(
        tenant,
        inbound_operation_from_request(request),
        is_error=is_error,
    )


def tenant_api_usage_summary(tenant: Tenant, *, days: int = 30) -> dict[str, Any]:
    """Aggregated inbound/outbound stats for display (today + rolling window)."""
    today = timezone.localdate()
    start = today - timedelta(days=max(days - 1, 0))

    qs = TenantApiUsageDaily.objects.filter(
        tenant=tenant,
        date__gte=start,
        date__lte=today,
    )

    def _aggregate(direction: str) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for row in qs.filter(direction=direction).values(
            "operation",
            "date",
            "request_count",
            "error_count",
            "last_request_at",
        ):
            op = row["operation"]
            bucket = rows.setdefault(
                op,
                {
                    "operation": op,
                    "label": operation_label(op),
                    "today": 0,
                    "period_total": 0,
                    "period_errors": 0,
                    "last_request_at": None,
                },
            )
            count = row["request_count"] or 0
            errors = row["error_count"] or 0
            bucket["period_total"] += count
            bucket["period_errors"] += errors
            if row["date"] == today:
                bucket["today"] += count
            ts = row["last_request_at"]
            if ts is not None and (
                bucket["last_request_at"] is None or ts > bucket["last_request_at"]
            ):
                bucket["last_request_at"] = ts
        return sorted(rows.values(), key=lambda r: (-r["period_total"], r["label"]))

    inbound = _aggregate(TenantApiUsageDaily.Direction.INBOUND)
    outbound = _aggregate(TenantApiUsageDaily.Direction.OUTBOUND)

    period_inbound = sum(r["period_total"] for r in inbound)
    period_outbound = sum(r["period_total"] for r in outbound)
    today_inbound = sum(r["today"] for r in inbound)
    today_outbound = sum(r["today"] for r in outbound)

    def _latest(rows: list[dict[str, Any]]) -> Any:
        latest = None
        for r in rows:
            ts = r.get("last_request_at")
            if ts is not None and (latest is None or ts > latest):
                latest = ts
        return latest

    return {
        "days": days,
        "today": today,
        "inbound": inbound,
        "outbound": outbound,
        "today_inbound": today_inbound,
        "today_outbound": today_outbound,
        "period_inbound": period_inbound,
        "period_outbound": period_outbound,
        "last_inbound_at": _latest(inbound),
        "last_outbound_at": _latest(outbound),
        "has_data": bool(inbound or outbound),
    }
