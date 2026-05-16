"""Reports-to API: manager of subject unit vs parent chief when subject is unit boss."""

from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .employee_api import (
    _serialize_employee_brief,
    _serialize_org_unit_with_parent,
    employee_resolve_from_get,
)
from .models import OrganizationalUnit
from .organization_structure import chief_position_and_holder, primary_org_unit_from_assignments


def _serialize_chief_position(pos) -> dict | None:
    if pos is None:
        return None
    return {"id": pos.pk, "title": pos.title, "code": pos.code or ""}


def reports_to_payload_dict(request):
    emp, err = employee_resolve_from_get(request)
    if err is not None:
        return None, err

    working_ou = primary_org_unit_from_assignments(emp)
    subject_payload = _serialize_employee_brief(emp)

    if working_ou is None:
        return (
            {
                "employee": subject_payload,
                "working_org_unit": None,
                "reports_to": None,
                "detail": "No current assignment linked to an organizational unit.",
            },
            None,
        )

    work_unit_payload = _serialize_org_unit_with_parent(working_ou)
    chief_pos, chief_emp = chief_position_and_holder(working_ou)
    is_subject_chief = chief_emp is not None and chief_emp.pk == emp.pk

    if not is_subject_chief:
        return (
            {
                "employee": subject_payload,
                "working_org_unit": work_unit_payload,
                "reports_to": {
                    "org_unit": work_unit_payload,
                    "chief_position": _serialize_chief_position(chief_pos),
                    "employee": (
                        _serialize_employee_brief(chief_emp) if chief_emp is not None else None
                    ),
                    "escalated": False,
                },
            },
            None,
        )

    parent = None
    if working_ou.parent_id:
        parent = (
            OrganizationalUnit.objects.filter(pk=working_ou.parent_id, tenant_id=working_ou.tenant_id)
            .select_related("parent")
            .first()
        )

    if parent is None:
        return (
            {
                "employee": subject_payload,
                "working_org_unit": work_unit_payload,
                "reports_to": {
                    "org_unit": None,
                    "chief_position": None,
                    "employee": None,
                    "escalated": True,
                    "detail": "Subject holds the chief role for this unit; no parent unit exists.",
                },
            },
            None,
        )

    parent_payload = _serialize_org_unit_with_parent(parent)
    p_pos, p_emp = chief_position_and_holder(parent)
    return (
        {
            "employee": subject_payload,
            "working_org_unit": work_unit_payload,
            "reports_to": {
                "org_unit": parent_payload,
                "chief_position": _serialize_chief_position(p_pos),
                "employee": _serialize_employee_brief(p_emp) if p_emp is not None else None,
                "escalated": True,
            },
        },
        None,
    )


@require_http_methods(["GET", "OPTIONS"])
def api_reports_to_get(request):
    """
    Working org unit + reports-to person.

    Query: ``tenant_id``, exactly one of ``user_id``, ``username``, ``civil_id``.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({}, status=204)
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-Api-Key, If-Match, If-None-Match"
        )
        return response

    payload, err = reports_to_payload_dict(request)
    if err is not None:
        return err
    return JsonResponse(payload, status=200)
