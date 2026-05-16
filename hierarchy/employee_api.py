"""HTTP APIs for employee profiles (machine clients + staff sessions)."""

from __future__ import annotations

import base64
import mimetypes
import os
from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .api_auth import authorize_tenant_api, global_bearer_matches, tenant_api_key_matches
from .delegation_utils import delegation_is_current, delegation_status_label
from .models import Delegation, Employee, OrganizationalUnit, PositionAssignment, Tenant
from .organization_structure import assignment_is_current
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant_id


def _machine_auth(request, tenant: Tenant) -> bool:
    return global_bearer_matches(request) or tenant_api_key_matches(request, tenant)


def _authorized(request, tenant: Tenant) -> bool:
    return authorize_tenant_api(request, tenant)


def _can_access_employee(request, emp: Employee) -> bool:
    if global_bearer_matches(request):
        return True
    if emp.tenant_id and emp.tenant and tenant_api_key_matches(request, emp.tenant):
        return True
    user = request.user
    if user.is_superuser:
        st = get_superuser_active_tenant(request)
        return st is not None and emp.tenant_id == st.pk
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


def _serialize_employee_brief(emp: Employee) -> dict:
    u = emp.user
    full_name = u.get_full_name().strip()
    return {
        "id": emp.pk,
        "user_id": u.pk,
        "username": u.get_username(),
        "civil_id": emp.civil_id or "",
        "employee_number": emp.employee_number or "",
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "name": full_name if full_name else u.get_username(),
    }


def _serialize_delegation(d: Delegation) -> dict:
    return {
        "id": d.pk,
        "start_date": d.start_date.isoformat(),
        "end_date": d.end_date.isoformat() if d.end_date else None,
        "notes": d.notes or "",
        "status": delegation_status_label(d),
        "is_current": delegation_is_current(d),
        "is_full_substitute": d.is_full_substitute,
        "template_name": d.template.name if getattr(d, "template_id", None) else None,
        "delegator": _serialize_employee_brief(d.delegator),
        "delegatee": _serialize_employee_brief(d.delegatee),
    }


def _delegations_payload(emp: Employee) -> dict:
    given = [
        _serialize_delegation(d)
        for d in emp.delegations_given.all()
        if d.tenant_id == emp.tenant_id
    ]
    received = [
        _serialize_delegation(d)
        for d in emp.delegations_received.all()
        if d.tenant_id == emp.tenant_id
    ]
    return {
        "given": given,
        "received": received,
    }


def _serialize_org_unit_brief(ou: OrganizationalUnit | None) -> dict | None:
    if ou is None:
        return None
    return {
        "id": ou.pk,
        "name": ou.name,
        "code": ou.code or "",
        "unit_type": ou.unit_type,
        "unit_type_label": ou.get_unit_type_display(),
        "sort_order": ou.sort_order,
    }


def _serialize_org_unit_with_parent(ou: OrganizationalUnit | None) -> dict | None:
    if ou is None:
        return None
    parent = ou.parent if ou.parent_id else None
    return {
        **_serialize_org_unit_brief(ou),
        "parent": _serialize_org_unit_brief(parent),
    }


def _organizational_units_payload(emp: Employee) -> tuple[list[dict], dict | None, dict | None]:
    """Current position assignments → org units (deduped), plus primary unit + parent."""
    seen_unit_ids: set[int] = set()
    units: list[dict] = []

    for assignment in emp.position_assignments.all():
        if not assignment_is_current(assignment):
            continue
        position = assignment.position
        ou = position.organizational_unit if position else None
        if ou is None or ou.pk in seen_unit_ids:
            continue
        seen_unit_ids.add(ou.pk)
        units.append(
            {
                **_serialize_org_unit_with_parent(ou),
                "position": {
                    "id": position.pk,
                    "title": position.title,
                    "code": position.code or "",
                },
                "is_primary": assignment.is_primary,
            }
        )

    primary_entry = next((u for u in units if u["is_primary"]), units[0] if units else None)
    if primary_entry is None:
        return units, None, None

    primary_unit = {
        "id": primary_entry["id"],
        "name": primary_entry["name"],
        "code": primary_entry["code"],
        "sort_order": primary_entry["sort_order"],
        "parent": primary_entry["parent"],
    }
    return units, primary_unit, primary_entry["parent"]


def _serialize_employee(emp: Employee) -> dict:
    u = emp.user
    tenant_payload = None
    if emp.tenant_id and emp.tenant:
        t = emp.tenant
        tenant_payload = {"id": t.pk, "slug": t.slug, "name": t.name}

    org_units, primary_unit, primary_parent = _organizational_units_payload(emp)

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
        "organizational_units": org_units,
        "organizational_unit": primary_unit,
        "organizational_unit_parent": primary_parent,
        "delegations": _delegations_payload(emp),
    }


def employee_resolve_from_get(request) -> tuple[Employee | None, JsonResponse | None]:
    """
    Shared tenant + identity lookup for directory-style GET APIs.
    Returns ``(employee, None)`` or ``(None, error)``.
    """
    tenant_id_raw = request.GET.get("tenant_id")
    if tenant_id_raw in (None, "") or str(tenant_id_raw).strip() == "":
        return None, JsonResponse(
            {
                "detail": "tenant_id is required (integer). Also pass exactly one of: "
                "user_id, username, civil_id.",
            },
            status=400,
        )
    try:
        tid_scope = int(str(tenant_id_raw).strip())
    except (TypeError, ValueError):
        return None, JsonResponse({"detail": "tenant_id must be an integer."}, status=400)

    tenant = Tenant.objects.filter(pk=tid_scope).first()
    if tenant is None:
        return None, JsonResponse({"detail": "Unknown tenant."}, status=404)

    if not _authorized(request, tenant):
        return None, JsonResponse({"detail": "Authentication required."}, status=401)

    token_ok = _machine_auth(request, tenant)
    user = request.user

    if user.is_authenticated and user.is_staff and not token_ok:
        if user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is None or tid_scope != st.pk:
                return None, JsonResponse(
                    {
                        "detail": "Choose a tenant in Scope (superuser) matching tenant_id.",
                    },
                    status=403,
                )
        else:
            stid = get_user_tenant_id(user)
            if stid is None:
                return None, JsonResponse(
                    {"detail": "Your account has no tenant scope."},
                    status=403,
                )
            if tid_scope != stid:
                return None, JsonResponse(
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
        return None, JsonResponse(
            {
                "detail": "Provide exactly one of: user_id (Django user pk), username, civil_id.",
            },
            status=400,
        )

    qs = (
        Employee.objects.select_related("user", "tenant")
        .prefetch_related(
            Prefetch(
                "position_assignments",
                queryset=PositionAssignment.objects.select_related(
                    "position__organizational_unit__parent",
                ).order_by("-is_primary", "-start_date", "pk"),
            ),
        )
        .filter(tenant_id=tid_scope)
    )

    if has_uid:
        try:
            uid = int(str(uid_raw).strip())
        except (TypeError, ValueError):
            return None, JsonResponse({"detail": "user_id must be an integer."}, status=400)
        emp = qs.filter(user_id=uid).first()
    elif has_username:
        emp = qs.filter(user__username__iexact=username).first()
    else:
        matches = qs.filter(civil_id=civil_id)
        n = matches.count()
        if n > 1:
            return None, JsonResponse(
                {"detail": "Multiple employees match this civil_id."},
                status=409,
            )
        emp = matches.first()

    if emp is None:
        return None, JsonResponse({"detail": "Employee not found."}, status=404)

    if not _can_access_employee(request, emp):
        return None, JsonResponse({"detail": "You cannot access this employee."}, status=403)

    return emp, None


@require_http_methods(["GET", "OPTIONS"])
def employee_get_payload_dict(request) -> tuple[dict | None, JsonResponse | None]:
    """
    Validate request and build employee JSON payload (without wrapping).
    Returns ``({"employee": ..., "signatures": ...}, None)`` or ``(None, error)``.
    """
    emp, err = employee_resolve_from_get(request)
    if err is not None:
        return None, err

    qs = (
        Employee.objects.filter(pk=emp.pk)
        .select_related("user", "tenant")
        .prefetch_related(
            "signatures",
            Prefetch(
                "position_assignments",
                queryset=PositionAssignment.objects.select_related(
                    "position__organizational_unit__parent",
                ).order_by("-is_primary", "-start_date", "pk"),
            ),
            Prefetch(
                "delegations_given",
                queryset=Delegation.objects.select_related(
                    "delegatee__user",
                    "delegator__user",
                    "template",
                ).order_by("-start_date", "pk"),
            ),
            Prefetch(
                "delegations_received",
                queryset=Delegation.objects.select_related(
                    "delegator__user",
                    "delegatee__user",
                    "template",
                ).order_by("-start_date", "pk"),
            ),
        )
    )
    emp = qs.first()
    assert emp is not None

    signatures = [_serialize_signature(s) for s in emp.signatures.all()]
    return {
        "employee": _serialize_employee(emp),
        "signatures": signatures,
    }, None


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
            "Authorization, Content-Type, X-Api-Key, If-Match, If-None-Match"
        )
        return response

    payload, err = employee_get_payload_dict(request)
    if err is not None:
        return err
    return JsonResponse(payload, status=200)
