"""Employee signature images API (Base64 payloads)."""

from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .employee_api import (
    build_employee_signatures_payload,
    employee_resolve_from_get,
)
from .models import Employee


def signatures_get_payload_dict(request) -> tuple[dict | None, JsonResponse | None]:
    """
    Validate request and build signatures JSON payload.
    Returns ``({"employee": ..., "signatures": ...}, None)`` or ``(None, error)``.
    """
    emp, err = employee_resolve_from_get(request)
    if err is not None:
        return None, err

    emp = (
        Employee.objects.filter(pk=emp.pk)
        .select_related("user")
        .prefetch_related("signatures")
        .first()
    )
    assert emp is not None
    return build_employee_signatures_payload(emp), None


@require_http_methods(["GET", "OPTIONS"])
def api_employee_signatures_get(request):
    """
    GET signature images for one employee (Base64).

    Query: ``tenant_id``, exactly one of ``user_id``, ``username``, ``civil_id``.
    Same authentication as ``GET /api/employees/``.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({}, status=204)
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-Api-Key, If-Match, If-None-Match"
        )
        return response

    payload, err = signatures_get_payload_dict(request)
    if err is not None:
        return err
    return JsonResponse(payload, status=200)
