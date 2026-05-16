"""Bulk PATCH APIs (v1) with transactional apply and If-Match preconditions."""

from __future__ import annotations

import json
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api_http import (
    attach_v1_write_headers,
    evaluate_if_match_for_write,
    v1_cors_allow_headers,
    weak_etag_for_payload,
)
from .models import Employee, OrganizationalUnit, Position, PositionAssignment
from .organization_api import (
    _resolve_tenant,
    assignments_build_response_data,
    org_units_snapshot_flat_data,
)

_DATE_ERR = object()


def _guide_url(request) -> str:
    return request.build_absolute_uri(reverse("hierarchy:api_guide"))


def _parse_json(request) -> dict | None:
    try:
        body = request.body.decode("utf-8") or "{}"
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _bulk_patch_options() -> JsonResponse:
    r = JsonResponse({}, status=204)
    r["Access-Control-Allow-Methods"] = "PATCH, OPTIONS"
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r


def _parse_opt_date(
    value: Any,
    *,
    errors: list[dict],
    ctx: dict,
) -> date | None | object:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        d = parse_date(value)
        if d is None:
            errors.append({**ctx, "message": "Expected ISO date (YYYY-MM-DD)."})
            return _DATE_ERR
        return d
    errors.append({**ctx, "message": "Date must be a string or null."})
    return _DATE_ERR


def _apply_cors(resp: JsonResponse) -> JsonResponse:
    resp["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return resp


@csrf_exempt
@require_http_methods(["PATCH", "OPTIONS"])
def api_v1_org_units_bulk_patch(request):
    """
    Apply partial updates to many organizational units in one transaction.

    Preconditions: ``If-Match`` must match
    ``GET /api/v1/organization/units/?tenant_id=&format=flat`` (ETag of flat list).
    """
    if request.method == "OPTIONS":
        return _bulk_patch_options()

    tenant, err = _resolve_tenant(request)
    if err is not None:
        return err

    snapshot = org_units_snapshot_flat_data(tenant)
    etag = weak_etag_for_payload(snapshot)
    ok_im, im_err = evaluate_if_match_for_write(request, etag)
    if not ok_im:
        assert im_err is not None
        return _apply_cors(im_err)

    data = _parse_json(request)
    if data is None:
        return _apply_cors(JsonResponse({"detail": "JSON object body required."}, status=400))

    updates_raw = data.get("updates")
    if updates_raw is None:
        return _apply_cors(JsonResponse({"detail": "Field updates (array) is required."}, status=400))
    if not isinstance(updates_raw, list):
        return _apply_cors(JsonResponse({"detail": "updates must be a JSON array."}, status=400))

    allowed_keys = {"id", "name", "code", "unit_type", "sort_order", "parent_id"}
    errors: list[dict] = []
    unit_ids_in_payload: set[int] = set()

    for i, row in enumerate(updates_raw):
        if not isinstance(row, dict):
            errors.append({"index": i, "message": "Each update must be an object."})
            continue
        extra = set(row.keys()) - allowed_keys
        if extra:
            errors.append(
                {
                    "index": i,
                    "message": f"Unknown keys: {', '.join(sorted(extra))}.",
                }
            )
            continue
        if "id" not in row:
            errors.append({"index": i, "message": "id is required."})
            continue
        try:
            uid = int(row["id"])
        except (TypeError, ValueError):
            errors.append({"index": i, "field": "id", "message": "id must be an integer."})
            continue
        unit_ids_in_payload.add(uid)

    if errors:
        return _apply_cors(JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400))

    by_id = {
        u.pk: u
        for u in OrganizationalUnit.objects.filter(
            tenant=tenant,
            pk__in=unit_ids_in_payload,
        )
    }
    if len(by_id) != len(unit_ids_in_payload):
        missing = sorted(unit_ids_in_payload - set(by_id.keys()))
        return _apply_cors(
            JsonResponse(
                {
                    "detail": "One or more organizational units were not found for this tenant.",
                    "missing_ids": missing,
                },
                status=400,
            )
        )

    for i, row in enumerate(updates_raw):
        uid = int(row["id"])
        unit = by_id[uid]
        if "name" in row:
            v = row["name"]
            if not isinstance(v, str) or not v.strip():
                errors.append({"index": i, "field": "name", "message": "Non-empty string required."})
            else:
                unit.name = v.strip()
        if "code" in row:
            v = row["code"]
            if v is None:
                unit.code = ""
            elif isinstance(v, str):
                unit.code = v.strip()
            else:
                errors.append({"index": i, "field": "code", "message": "Must be string or null."})
        if "unit_type" in row:
            v = row["unit_type"]
            if not isinstance(v, str) or not v.strip():
                errors.append({"index": i, "field": "unit_type", "message": "Non-empty string required."})
            else:
                unit.unit_type = v.strip()
        if "sort_order" in row:
            v = row["sort_order"]
            try:
                unit.sort_order = int(v)
            except (TypeError, ValueError):
                errors.append({"index": i, "field": "sort_order", "message": "Must be an integer."})
        if "parent_id" in row:
            v = row["parent_id"]
            if v is None:
                unit.parent_id = None
            else:
                try:
                    pid = int(v)
                except (TypeError, ValueError):
                    errors.append({"index": i, "field": "parent_id", "message": "Must be integer or null."})
                else:
                    if pid == unit.pk:
                        errors.append(
                            {
                                "index": i,
                                "field": "parent_id",
                                "message": "A unit cannot be its own parent.",
                            }
                        )
                    else:
                        parent = OrganizationalUnit.objects.filter(pk=pid, tenant=tenant).first()
                        if parent is None:
                            errors.append(
                                {
                                    "index": i,
                                    "field": "parent_id",
                                    "message": "Parent not found on this tenant.",
                                }
                            )
                        else:
                            unit.parent_id = pid

    if errors:
        return _apply_cors(JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400))

    for i, row in enumerate(updates_raw):
        uid = int(row["id"])
        unit = by_id[uid]
        try:
            unit.full_clean()
        except ValidationError as e:
            errors.append({"index": i, "message": e.messages[0] if e.messages else str(e)})

    if errors:
        return _apply_cors(JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400))

    with transaction.atomic():
        for unit in by_id.values():
            unit.save()

    new_snapshot = org_units_snapshot_flat_data(tenant)
    new_etag = weak_etag_for_payload(new_snapshot)
    body = {
        "detail": "Bulk unit update applied.",
        "tenant_id": tenant.pk,
        "updated_count": len(by_id),
    }
    r = JsonResponse(body, status=200)
    attach_v1_write_headers(
        r,
        etag=new_etag,
        read_contract="org-units-v1",
        guide_url=_guide_url(request),
    )
    return _apply_cors(r)


@csrf_exempt
@require_http_methods(["PATCH", "OPTIONS"])
def api_v1_assignments_bulk_patch(request):
    """
    Create, update, or delete many position assignments in one transaction.

    Preconditions: ``If-Match`` must match ``GET /api/v1/organization/assignments/?tenant_id=``.
    """
    if request.method == "OPTIONS":
        return _bulk_patch_options()

    tenant, err = _resolve_tenant(request)
    if err is not None:
        return err

    snapshot = assignments_build_response_data(tenant)
    etag = weak_etag_for_payload(snapshot)
    ok_im, im_err = evaluate_if_match_for_write(request, etag)
    if not ok_im:
        assert im_err is not None
        return _apply_cors(im_err)

    data = _parse_json(request)
    if data is None:
        return _apply_cors(JsonResponse({"detail": "JSON object body required."}, status=400))

    updates_raw = data.get("updates") or []
    creates_raw = data.get("creates") or []
    delete_ids_raw = data.get("delete_ids") or []

    if not isinstance(updates_raw, list):
        return _apply_cors(JsonResponse({"detail": "updates must be an array."}, status=400))
    if not isinstance(creates_raw, list):
        return _apply_cors(JsonResponse({"detail": "creates must be an array."}, status=400))
    if not isinstance(delete_ids_raw, list):
        return _apply_cors(JsonResponse({"detail": "delete_ids must be an array."}, status=400))

    errors: list[dict] = []
    delete_ids: set[int] = set()
    for i, did in enumerate(delete_ids_raw):
        try:
            delete_ids.add(int(did))
        except (TypeError, ValueError):
            errors.append({"section": "delete_ids", "index": i, "message": "Must be integers."})

    update_specs: list[tuple[int, dict]] = []
    for i, row in enumerate(updates_raw):
        if not isinstance(row, dict):
            errors.append({"section": "updates", "index": i, "message": "Must be an object."})
            continue
        keys = set(row.keys())
        allowed = {"id", "is_primary", "start_date", "end_date", "notes"}
        if keys - allowed:
            errors.append(
                {
                    "section": "updates",
                    "index": i,
                    "message": f"Unknown keys: {', '.join(sorted(keys - allowed))}.",
                }
            )
            continue
        if "id" not in row:
            errors.append({"section": "updates", "index": i, "message": "id is required."})
            continue
        try:
            aid = int(row["id"])
        except (TypeError, ValueError):
            errors.append({"section": "updates", "index": i, "field": "id", "message": "Integer required."})
            continue
        if aid in delete_ids:
            errors.append(
                {
                    "section": "updates",
                    "index": i,
                    "message": "Cannot update and delete the same assignment id.",
                }
            )
            continue
        update_specs.append((i, row))

    create_specs: list[tuple[int, dict]] = []
    for i, row in enumerate(creates_raw):
        if not isinstance(row, dict):
            errors.append({"section": "creates", "index": i, "message": "Must be an object."})
            continue
        keys = set(row.keys())
        allowed = {"employee_id", "position_id", "is_primary", "start_date", "end_date", "notes"}
        if keys - allowed:
            errors.append(
                {
                    "section": "creates",
                    "index": i,
                    "message": f"Unknown keys: {', '.join(sorted(keys - allowed))}.",
                }
            )
            continue
        if "employee_id" not in row or "position_id" not in row:
            errors.append(
                {
                    "section": "creates",
                    "index": i,
                    "message": "employee_id and position_id are required.",
                }
            )
            continue
        try:
            int(row["employee_id"])
            int(row["position_id"])
        except (TypeError, ValueError):
            errors.append(
                {
                    "section": "creates",
                    "index": i,
                    "message": "employee_id and position_id must be integers.",
                }
            )
            continue
        create_specs.append((i, row))

    if errors:
        return _apply_cors(JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400))

    all_update_ids = {int(r["id"]) for _, r in update_specs}
    if all_update_ids & delete_ids:
        return _apply_cors(JsonResponse({"detail": "Conflicting update and delete_ids."}, status=400))

    by_assign_id = {
        a.pk: a
        for a in PositionAssignment.objects.filter(
            pk__in=all_update_ids,
            employee__tenant_id=tenant.pk,
        ).select_related("employee", "position")
    }
    if len(by_assign_id) != len(all_update_ids):
        missing = sorted(all_update_ids - set(by_assign_id.keys()))
        return _apply_cors(
            JsonResponse(
                {"detail": "Some assignments were not found for this tenant.", "missing_ids": missing},
                status=400,
            )
        )

    to_delete_qs = PositionAssignment.objects.filter(
        pk__in=delete_ids,
        employee__tenant_id=tenant.pk,
    )
    if to_delete_qs.count() != len(delete_ids):
        found = set(to_delete_qs.values_list("pk", flat=True))
        return _apply_cors(
            JsonResponse(
                {
                    "detail": "Some delete_ids were not found for this tenant.",
                    "missing_ids": sorted(delete_ids - found),
                },
                status=400,
            )
        )

    new_instances: list[PositionAssignment] = []

    for i, row in update_specs:
        aid = int(row["id"])
        a = by_assign_id[aid]
        if "is_primary" in row:
            v = row["is_primary"]
            if not isinstance(v, bool):
                errors.append({"section": "updates", "index": i, "field": "is_primary", "message": "Boolean required."})
            else:
                a.is_primary = v
        if "notes" in row:
            v = row["notes"]
            if v is None:
                a.notes = ""
            elif isinstance(v, str):
                a.notes = v[:500]
            else:
                errors.append({"section": "updates", "index": i, "field": "notes", "message": "String or null."})
        if "start_date" in row:
            d = _parse_opt_date(
                row["start_date"],
                errors=errors,
                ctx={"section": "updates", "index": i, "field": "start_date"},
            )
            if d is not _DATE_ERR:
                a.start_date = d
        if "end_date" in row:
            d = _parse_opt_date(
                row["end_date"],
                errors=errors,
                ctx={"section": "updates", "index": i, "field": "end_date"},
            )
            if d is not _DATE_ERR:
                a.end_date = d

    for i, row in create_specs:
        employee_id = int(row["employee_id"])
        position_id = int(row["position_id"])
        emp = Employee.objects.filter(pk=employee_id, tenant_id=tenant.pk).first()
        if emp is None:
            errors.append({"section": "creates", "index": i, "message": "employee_id not found on tenant."})
            continue
        pos = Position.objects.filter(pk=position_id, tenant_id=tenant.pk).first()
        if pos is None:
            errors.append({"section": "creates", "index": i, "message": "position_id not found on tenant."})
            continue
        is_primary = True
        if "is_primary" in row:
            v = row["is_primary"]
            if not isinstance(v, bool):
                errors.append({"section": "creates", "index": i, "field": "is_primary", "message": "Boolean required."})
                continue
            is_primary = v
        notes = ""
        if "notes" in row:
            v = row["notes"]
            if v is None:
                notes = ""
            elif isinstance(v, str):
                notes = v[:500]
            else:
                errors.append({"section": "creates", "index": i, "field": "notes", "message": "String or null."})
                continue
        start_d: date | None = None
        end_d: date | None = None
        date_bad = False
        if "start_date" in row:
            parsed = _parse_opt_date(
                row["start_date"],
                errors=errors,
                ctx={"section": "creates", "index": i, "field": "start_date"},
            )
            if parsed is _DATE_ERR:
                date_bad = True
            else:
                start_d = parsed
        if "end_date" in row:
            parsed = _parse_opt_date(
                row["end_date"],
                errors=errors,
                ctx={"section": "creates", "index": i, "field": "end_date"},
            )
            if parsed is _DATE_ERR:
                date_bad = True
            else:
                end_d = parsed
        if date_bad:
            continue
        inst = PositionAssignment(
            employee=emp,
            position=pos,
            is_primary=is_primary,
            notes=notes,
            start_date=start_d,
            end_date=end_d,
        )
        try:
            inst.full_clean()
        except ValidationError as e:
            errors.append(
                {
                    "section": "creates",
                    "index": i,
                    "message": e.messages[0] if e.messages else str(e),
                }
            )
            continue
        new_instances.append(inst)

    for i, row in update_specs:
        aid = int(row["id"])
        a = by_assign_id[aid]
        try:
            a.full_clean()
        except ValidationError as e:
            errors.append(
                {
                    "section": "updates",
                    "index": i,
                    "message": e.messages[0] if e.messages else str(e),
                }
            )

    if errors:
        return _apply_cors(JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400))

    with transaction.atomic():
        if delete_ids:
            PositionAssignment.objects.filter(pk__in=delete_ids).delete()
        for a in by_assign_id.values():
            a.save()
        # Per-row save so PositionAssignment.save() enforces one primary per employee.
        for inst in new_instances:
            inst.save()

    new_snapshot = assignments_build_response_data(tenant)
    new_etag = weak_etag_for_payload(new_snapshot)
    body = {
        "detail": "Bulk assignment changes applied.",
        "tenant_id": tenant.pk,
        "updated": len(update_specs),
        "created": len(new_instances),
        "deleted": len(delete_ids),
    }
    r = JsonResponse(body, status=200)
    attach_v1_write_headers(
        r,
        etag=new_etag,
        read_contract="assignments-v1",
        guide_url=_guide_url(request),
    )
    return _apply_cors(r)
