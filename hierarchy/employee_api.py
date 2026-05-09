"""HTTP APIs for employee profiles (machine clients + staff sessions)."""

from __future__ import annotations

import base64
import mimetypes
import os
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Employee, Tenant
from .tenant_api_credentials import (
    effective_tenant_api_key,
    effective_tenant_api_key_header,
)
from .user_tenant import get_user_tenant_id


def _get_http_header(request, name: str) -> str | None:
    v = request.headers.get(name)
    if v is not None:
        return v
    meta_key = "HTTP_" + name.upper().replace("-", "_")
    return request.META.get(meta_key)


def _tenant_api_key_matches(request, tenant: Tenant) -> bool:
    secret = effective_tenant_api_key(tenant)
    if not secret:
        return False
    header_name = effective_tenant_api_key_header(tenant)
    provided = _get_http_header(request, header_name)
    if provided is None:
        return False
    try:
        return secrets.compare_digest(
            provided.strip().encode("utf-8"),
            secret.encode("utf-8"),
        )
    except (UnicodeEncodeError, AttributeError):
        return False


def _token_only_access(request) -> bool:
    token = (getattr(settings, "EMPLOYEE_API_TOKEN", None) or "").strip()
    if not token:
        return False
    auth = (request.headers.get("Authorization") or "").strip()
    return auth == f"Bearer {token}"


def _machine_auth(request, tenant: Tenant) -> bool:
    """Global Bearer token or this tenant's API key header."""
    if _token_only_access(request):
        return True
    return _tenant_api_key_matches(request, tenant)


def _authorized(request, tenant: Tenant) -> bool:
    if _machine_auth(request, tenant):
        return True
    user = request.user
    if user.is_authenticated and (user.is_staff or user.is_superuser):
        return True
    return False


def _can_access_employee(request, emp: Employee) -> bool:
    if _token_only_access(request):
        return True
    if emp.tenant_id and emp.tenant and _tenant_api_key_matches(request, emp.tenant):
        return True
    user = request.user
    if user.is_superuser:
        return True
    if not user.is_authenticated or not user.is_staff:
        return False
    tid = get_user_tenant_id(user)
    if tid is None:
        return False
    return emp.tenant_id == tid


def _serialize_signature(sig) -> dict:
    name = sig.image.name
    mime, _ = mimetypes.guess_type(name)
    if not mime:
        mime = "application/octet-stream"
    with sig.image.open("rb") as f:
        raw = f.read()
    return {
        "id": sig.pk,
        "label": sig.label or "",
        "sort_order": sig.sort_order,
        "mime_type": mime,
        "filename": os.path.basename(name) if name else "",
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def _serialize_employee(emp: Employee) -> dict:
    u = emp.user
    tenant_payload = None
    if emp.tenant_id and emp.tenant:
        t = emp.tenant
        tenant_payload = {"id": t.pk, "slug": t.slug, "name": t.name}
    return {
        "id": emp.pk,
        "user_id": u.pk,
        "username": u.get_username(),
        "email": u.email or "",
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "tenant": tenant_payload,
        "sector": emp.sector,
        "employee_number": emp.employee_number or "",
        "job_title": emp.job_title or "",
        "department": emp.department or "",
        "section_team": emp.section_team or "",
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
        "employment_status": emp.employment_status,
        "work_location": emp.work_location or "",
        "employee_type": emp.employee_type,
        "civil_id": emp.civil_id or "",
        "date_of_birth": emp.date_of_birth.isoformat() if emp.date_of_birth else None,
        "gender": emp.gender or "",
        "nationality": emp.nationality or "",
        "marital_status": emp.marital_status or "",
        "mobile_number": emp.mobile_number or "",
        "home_address": emp.home_address or "",
        "emergency_contact": emp.emergency_contact or "",
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
    }


@require_http_methods(["GET", "OPTIONS"])
def api_employee_get(request):
    """
    GET employee profile + signature images as Base64.

    Required query parameters:

    - ``tenant_id`` (integer)
    - Exactly **one** of: ``user_id`` (Django User pk), ``username``, ``civil_id``

    Authentication (any one):

    - ``Authorization: Bearer <EMPLOYEE_API_TOKEN>`` (global, from env), or
    - Tenant API key: header from tenant ``api_key_header`` (default ``X-Api-Key``)
      with value from ``api_key`` or env ``TENANT_API_KEY_<tenant_pk>``, or
    - Signed-in staff/superuser session.

    Staff (non-superuser) must use ``tenant_id`` equal to their assigned tenant.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({}, status=204)
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-Api-Key"
        )
        return response

    tenant_id_raw = request.GET.get("tenant_id")
    if tenant_id_raw in (None, "") or str(tenant_id_raw).strip() == "":
        return JsonResponse(
            {
                "detail": "tenant_id is required (integer). Also pass exactly one of: "
                "user_id, username, civil_id.",
            },
            status=400,
        )
    try:
        tid_scope = int(str(tenant_id_raw).strip())
    except (TypeError, ValueError):
        return JsonResponse({"detail": "tenant_id must be an integer."}, status=400)

    tenant = Tenant.objects.filter(pk=tid_scope).first()
    if tenant is None:
        return JsonResponse({"detail": "Unknown tenant."}, status=404)

    if not _authorized(request, tenant):
        return JsonResponse({"detail": "Authentication required."}, status=401)

    token_ok = _machine_auth(request, tenant)
    user = request.user

    if (
        user.is_authenticated
        and user.is_staff
        and not user.is_superuser
        and not token_ok
    ):
        stid = get_user_tenant_id(user)
        if stid is None:
            return JsonResponse(
                {"detail": "Your account has no tenant scope."},
                status=403,
            )
        if tid_scope != stid:
            return JsonResponse(
                {"detail": "tenant_id must match your assigned tenant."},
                status=403,
            )

    uid_raw = request.GET.get("user_id")
    username = (request.GET.get("username") or "").strip()
    civil_id = (request.GET.get("civil_id") or "").strip()

    has_uid = uid_raw not in (None, "") and str(uid_raw).strip() != ""
    has_username = bool(username)
    has_civil = bool(civil_id)
    if sum([has_uid, has_username, has_civil]) != 1:
        return JsonResponse(
            {
                "detail": "Provide exactly one of: user_id (Django user pk), username, civil_id.",
            },
            status=400,
        )

    qs = (
        Employee.objects.select_related("user", "tenant")
        .prefetch_related("signatures")
        .filter(tenant_id=tid_scope)
    )

    if has_uid:
        try:
            uid = int(str(uid_raw).strip())
        except (TypeError, ValueError):
            return JsonResponse({"detail": "user_id must be an integer."}, status=400)
        emp = qs.filter(user_id=uid).first()
    elif has_username:
        emp = qs.filter(user__username__iexact=username).first()
    else:
        matches = qs.filter(civil_id=civil_id)
        n = matches.count()
        if n > 1:
            return JsonResponse(
                {"detail": "Multiple employees match this civil_id."},
                status=409,
            )
        emp = matches.first()

    if emp is None:
        return JsonResponse({"detail": "Employee not found."}, status=404)

    if not _can_access_employee(request, emp):
        return JsonResponse({"detail": "You cannot access this employee."}, status=403)

    signatures = [_serialize_signature(s) for s in emp.signatures.all()]
    payload = {
        "employee": _serialize_employee(emp),
        "signatures": signatures,
    }
    return JsonResponse(payload, status=200)
