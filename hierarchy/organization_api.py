"""HTTP APIs for organizational units (machine clients + staff sessions)."""

from __future__ import annotations

from collections import defaultdict

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .api_auth import authorize_tenant_api, global_bearer_matches, tenant_api_key_matches
from .models import OrganizationalUnit, PositionAssignment, Tenant
from .organization_structure import flatten_org_units_for_search
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant_id


def _machine_auth(request, tenant: Tenant) -> bool:
    return global_bearer_matches(request) or tenant_api_key_matches(request, tenant)


def _resolve_tenant(request) -> tuple[Tenant | None, JsonResponse | None]:
    tenant_id_raw = request.GET.get("tenant_id")
    if tenant_id_raw in (None, "") or str(tenant_id_raw).strip() == "":
        return None, JsonResponse(
            {"detail": "tenant_id is required (integer)."},
            status=400,
        )
    try:
        tid = int(str(tenant_id_raw).strip())
    except (TypeError, ValueError):
        return None, JsonResponse({"detail": "tenant_id must be an integer."}, status=400)

    tenant = Tenant.objects.filter(pk=tid).first()
    if tenant is None:
        return None, JsonResponse({"detail": "Unknown tenant."}, status=404)

    if not authorize_tenant_api(request, tenant):
        return None, JsonResponse({"detail": "Authentication required."}, status=401)

    if not _machine_auth(request, tenant):
        user = request.user
        if user.is_authenticated and user.is_staff:
            if user.is_superuser:
                st = get_superuser_active_tenant(request)
                if st is None or tid != st.pk:
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
                if tid != stid:
                    return None, JsonResponse(
                        {"detail": "tenant_id must match your assigned tenant."},
                        status=403,
                    )

    return tenant, None


def _serialize_unit_parent(parent: OrganizationalUnit | None) -> dict | None:
    if parent is None:
        return None
    return {
        "id": parent.pk,
        "name": parent.name,
        "code": parent.code or "",
        "unit_type": parent.unit_type,
        "unit_type_label": parent.get_unit_type_display(),
        "sort_order": parent.sort_order,
    }


def _serialize_unit(u: OrganizationalUnit) -> dict:
    return {
        "id": u.pk,
        "name": u.name,
        "code": u.code or "",
        "unit_type": u.unit_type,
        "unit_type_label": u.get_unit_type_display(),
        "sort_order": u.sort_order,
        "parent_id": u.parent_id,
    }


def _list_units_flat(tenant: Tenant) -> list[dict]:
    rows = flatten_org_units_for_search(tenant)
    by_id = {
        u.pk: u
        for u in OrganizationalUnit.objects.filter(tenant=tenant).select_related("parent")
    }
    out: list[dict] = []
    for row in rows:
        u = by_id[row["id"]]
        parent = u.parent if u.parent_id else None
        out.append(
            {
                **_serialize_unit(u),
                "parent": _serialize_unit_parent(parent),
                "path": row["path"],
                "depth": row["depth"],
            }
        )
    return out


def _unit_tree_node(u: OrganizationalUnit, children_map: dict[int, list[OrganizationalUnit]]) -> dict:
    kids = children_map.get(u.pk, [])
    return {
        **_serialize_unit(u),
        "children": [_unit_tree_node(c, children_map) for c in kids],
    }


def _list_units_tree(tenant: Tenant) -> list[dict]:
    units = list(
        OrganizationalUnit.objects.filter(tenant=tenant).order_by("sort_order", "name"),
    )
    unit_ids = {u.pk for u in units}
    children_map: defaultdict[int, list[OrganizationalUnit]] = defaultdict(list)
    for u in units:
        if u.parent_id and u.parent_id in unit_ids:
            children_map[u.parent_id].append(u)

    roots = [
        u for u in units if u.parent_id is None or u.parent_id not in unit_ids
    ]
    roots.sort(key=lambda x: (x.sort_order, x.name))
    return [_unit_tree_node(u, children_map) for u in roots]


def org_units_build_response_data(tenant: Tenant, fmt: str) -> dict | None:
    """Build JSON-serializable org units list. ``fmt`` is ``flat`` or ``tree``."""
    if fmt == "tree":
        units_payload = _list_units_tree(tenant)
    else:
        units_payload = _list_units_flat(tenant)
    return {
        "tenant": {
            "id": tenant.pk,
            "slug": tenant.slug,
            "name": tenant.name,
        },
        "format": fmt,
        "count": (
            _count_tree_nodes(units_payload)
            if fmt == "tree"
            else len(units_payload)
        ),
        "units": units_payload,
    }


def _serialize_assignment(a: PositionAssignment) -> dict:
    emp = a.employee
    u = emp.user
    return {
        "id": a.pk,
        "employee_id": a.employee_id,
        "position_id": a.position_id,
        "user_id": u.pk,
        "username": u.get_username(),
        "civil_id": emp.civil_id or "",
        "employee_number": emp.employee_number or "",
        "is_primary": a.is_primary,
        "start_date": a.start_date.isoformat() if a.start_date else None,
        "end_date": a.end_date.isoformat() if a.end_date else None,
        "notes": a.notes or "",
    }


def assignments_build_response_data(tenant: Tenant) -> dict:
    """
    Stable, flat list of all position assignments for a tenant (integration snapshot).
    Ordering: employee, position, primary key.
    """
    rows = list(
        PositionAssignment.objects.filter(
            employee__tenant_id=tenant.pk,
        )
        .select_related("employee__user", "position")
        .order_by("employee_id", "position_id", "pk"),
    )
    return {
        "tenant": {
            "id": tenant.pk,
            "slug": tenant.slug,
            "name": tenant.name,
        },
        "count": len(rows),
        "assignments": [_serialize_assignment(a) for a in rows],
    }


def org_units_snapshot_flat_data(tenant: Tenant) -> dict:
    """Org units payload used for bulk PATCH preconditions (always ``format=flat``)."""
    return org_units_build_response_data(tenant, "flat")


def org_units_get_payload_dict(request) -> tuple[dict | None, JsonResponse | None]:
    """
    Shared GET handler body: validate request, return payload dict or error response.
    Used by legacy ``/api/organization/units/`` and versioned read API.
    """
    tenant, err = _resolve_tenant(request)
    if err is not None:
        return None, err

    fmt = (request.GET.get("format") or "flat").strip().lower()
    if fmt not in ("flat", "tree"):
        return None, JsonResponse(
            {"detail": "format must be flat or tree."},
            status=400,
        )

    data = org_units_build_response_data(tenant, fmt)
    assert data is not None
    return data, None


@require_http_methods(["GET", "OPTIONS"])
def api_org_units_list(request):
    """
    List organizational units for a tenant.

    Query parameters:

    - ``tenant_id`` (integer, required)
    - ``format`` — ``flat`` (default) or ``tree``
    """
    if request.method == "OPTIONS":
        response = JsonResponse({}, status=204)
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, X-Api-Key, If-Match, If-None-Match"
        )
        return response

    data, err = org_units_get_payload_dict(request)
    if err is not None:
        return err
    return JsonResponse(data, status=200)


def _count_tree_nodes(nodes: list[dict]) -> int:
    total = 0
    for n in nodes:
        total += 1
        total += _count_tree_nodes(n.get("children") or [])
    return total
