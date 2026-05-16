"""Tenant organization structure: units, positions, assignments."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .access import (
    ensure_structure_staff,
    ensure_structure_tenant_access,
    resolve_active_structure_tenant,
)
from .forms import OrganizationalUnitForm, PositionAssignmentForm, PositionForm
from .models import Employee, OrganizationalUnit, Position, PositionAssignment
from .organization_structure import (
    assignment_is_current,
    build_org_structure_branches,
    build_position_groups_for_board,
    count_structure_stats,
    flatten_org_units_for_search,
    employee_display_label,
    partition_assignments_for_positions,
)


def _resolve_org_unit_parent(tenant, parent_id: str | None) -> OrganizationalUnit | None:
    if not parent_id:
        return None
    try:
        pk = int(parent_id)
    except (TypeError, ValueError):
        return None
    return OrganizationalUnit.objects.filter(pk=pk, tenant=tenant).first()


def _org_unit_after_save_redirect(request, *, parent: OrganizationalUnit | None = None):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt == "overview":
        url = reverse("hierarchy:organization_overview")
        if parent is not None:
            return redirect(f"{url}#org-unit-{parent.pk}")
        return redirect(url)
    return redirect("hierarchy:org_unit_list")


def _parse_json_body(request) -> dict | None:
    try:
        raw = request.body.decode("utf-8") or "{}"
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _assignment_payload(assignment: PositionAssignment) -> dict:
    emp = assignment.employee
    u = emp.user
    return {
        "id": assignment.pk,
        "employee_id": assignment.employee_id,
        "position_id": assignment.position_id,
        "user_id": u.pk,
        "username": u.get_username(),
        "civil_id": emp.civil_id or "",
        "employee_number": emp.employee_number or "",
        "label": employee_display_label(assignment.employee),
        "is_primary": assignment.is_primary,
    }


def _get_board_position(request, pk: int) -> Position:
    position = get_object_or_404(
        Position.objects.select_related("tenant", "organizational_unit"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, position.tenant)
    return position


@login_required
def organization_overview(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(
            request,
            "Choose a tenant in Scope (superuser) to view organization structure.",
        )
        return render(
            request,
            "hierarchy/organization_overview.html",
            {
                "structure_tenant": None,
                "branches": [],
                "loose_positions": [],
                "stats": {},
                "unit_search_list": [],
            },
        )
    ensure_structure_tenant_access(request, tenant)
    branches, loose = build_org_structure_branches(tenant)
    stats = count_structure_stats(tenant)
    return render(
        request,
        "hierarchy/organization_overview.html",
        {
            "structure_tenant": tenant,
            "branches": branches,
            "loose_positions": loose,
            "stats": stats,
            "unit_search_list": flatten_org_units_for_search(tenant),
        },
    )


@login_required
def org_unit_list(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(request, "Choose a tenant in Scope to manage organizational units.")
        return render(
            request,
            "hierarchy/org_unit_list.html",
            {"structure_tenant": None, "units": []},
        )
    ensure_structure_tenant_access(request, tenant)
    units = (
        OrganizationalUnit.objects.filter(tenant=tenant)
        .select_related("parent")
        .order_by("sort_order", "name")
    )
    return render(
        request,
        "hierarchy/org_unit_list.html",
        {"structure_tenant": tenant, "units": units},
    )


@login_required
def org_unit_create(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:organization_overview")
    ensure_structure_tenant_access(request, tenant)

    parent_id = request.POST.get("parent") if request.method == "POST" else request.GET.get("parent")
    preset_parent = _resolve_org_unit_parent(tenant, parent_id)
    if parent_id and preset_parent is None:
        messages.warning(request, "That parent unit was not found; pick a parent on the form.")

    return_to_overview = (request.POST.get("next") or request.GET.get("next")) == "overview"

    if request.method == "POST":
        form = OrganizationalUnitForm(request.POST, tenant=tenant)
        if form.is_valid():
            unit = form.save()
            messages.success(request, "Organizational unit created.")
            anchor_parent = unit.parent or preset_parent
            return _org_unit_after_save_redirect(request, parent=anchor_parent)
    else:
        initial = {}
        if preset_parent is not None:
            initial["parent"] = preset_parent.pk
        form = OrganizationalUnitForm(tenant=tenant, initial=initial)

    cancel_url = (
        reverse("hierarchy:organization_overview")
        if return_to_overview
        else reverse("hierarchy:org_unit_list")
    )
    return render(
        request,
        "hierarchy/org_unit_form.html",
        {
            "form": form,
            "structure_tenant": tenant,
            "is_edit": False,
            "preset_parent": preset_parent,
            "return_to_overview": return_to_overview,
            "cancel_url": cancel_url,
        },
    )


@login_required
def org_unit_edit(request, pk):
    ensure_structure_staff(request)
    unit = get_object_or_404(OrganizationalUnit.objects.select_related("tenant"), pk=pk)
    ensure_structure_tenant_access(request, unit.tenant)
    if request.method == "POST":
        form = OrganizationalUnitForm(request.POST, tenant=unit.tenant, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, "Organizational unit updated.")
            return redirect("hierarchy:org_unit_list")
    else:
        form = OrganizationalUnitForm(tenant=unit.tenant, instance=unit)
    return render(
        request,
        "hierarchy/org_unit_form.html",
        {"form": form, "structure_tenant": unit.tenant, "is_edit": True, "unit": unit},
    )


@login_required
def position_list(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(request, "Choose a tenant in Scope to manage positions.")
        return render(
            request,
            "hierarchy/position_list.html",
            {"structure_tenant": None, "positions": []},
        )
    ensure_structure_tenant_access(request, tenant)
    positions = (
        Position.objects.filter(tenant=tenant)
        .select_related("organizational_unit")
        .order_by("organizational_unit_id", "sort_order", "title")
    )
    return render(
        request,
        "hierarchy/position_list.html",
        {"structure_tenant": tenant, "positions": positions},
    )


@login_required
def position_create(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:organization_overview")
    ensure_structure_tenant_access(request, tenant)
    if request.method == "POST":
        form = PositionForm(request.POST, tenant=tenant)
        if form.is_valid():
            pos = form.save()
            messages.success(request, "Position created. Add people on the position page.")
            return redirect("hierarchy:position_detail", pk=pos.pk)
    else:
        form = PositionForm(tenant=tenant)
    return render(
        request,
        "hierarchy/position_form.html",
        {"form": form, "structure_tenant": tenant, "is_edit": False},
    )


@login_required
def position_edit(request, pk):
    ensure_structure_staff(request)
    position = get_object_or_404(
        Position.objects.select_related("tenant", "organizational_unit"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, position.tenant)
    if request.method == "POST":
        form = PositionForm(
            request.POST,
            tenant=position.tenant,
            instance=position,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Position updated.")
            return redirect("hierarchy:position_detail", pk=position.pk)
    else:
        form = PositionForm(tenant=position.tenant, instance=position)
    return render(
        request,
        "hierarchy/position_form.html",
        {
            "form": form,
            "structure_tenant": position.tenant,
            "is_edit": True,
            "position": position,
        },
    )


@login_required
def position_detail(request, pk):
    ensure_structure_staff(request)
    position = get_object_or_404(
        Position.objects.select_related("tenant", "organizational_unit").prefetch_related(
            Prefetch(
                "assignments",
                queryset=PositionAssignment.objects.select_related(
                    "employee__user",
                ).order_by("-is_primary", "-start_date", "pk"),
            ),
        ),
        pk=pk,
    )
    ensure_structure_tenant_access(request, position.tenant)
    partition_assignments_for_positions([position])

    if request.method == "POST":
        assign_form = PositionAssignmentForm(request.POST, position=position)
        if assign_form.is_valid():
            assign_form.save()
            messages.success(request, "Person assigned to this position.")
            return redirect("hierarchy:position_detail", pk=position.pk)
    else:
        assign_form = PositionAssignmentForm(position=position)

    return render(
        request,
        "hierarchy/position_detail.html",
        {
            "position": position,
            "assign_form": assign_form,
            "structure_tenant": position.tenant,
        },
    )


@login_required
def position_assign_board(request):
    """Drag-and-drop UI: assign employees to a selected position."""
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(
            request,
            "Choose a tenant in Scope (superuser) to manage position assignments.",
        )
        return render(
            request,
            "hierarchy/position_assign_board.html",
            {
                "structure_tenant": None,
                "position_groups": [],
                "board_employees": [],
                "selected_position_id": None,
            },
        )
    ensure_structure_tenant_access(request, tenant)

    selected_position_id = None
    raw_pos = (request.GET.get("position") or "").strip()
    if raw_pos:
        try:
            selected_position_id = int(raw_pos)
        except ValueError:
            selected_position_id = None

    employees = list(
        Employee.objects.filter(tenant_id=tenant.pk)
        .select_related("user")
        .order_by("user__last_name", "user__first_name", "user__username"),
    )
    board_employees = [
        {
            "id": e.pk,
            "label": employee_display_label(e),
            "user_id": e.user_id,
            "username": e.user.username,
            "civil_id": e.civil_id or "",
            "employee_number": e.employee_number or "",
        }
        for e in employees
    ]

    return render(
        request,
        "hierarchy/position_assign_board.html",
        {
            "structure_tenant": tenant,
            "position_groups": build_position_groups_for_board(tenant),
            "board_employees": board_employees,
            "selected_position_id": selected_position_id,
            "position_data_url_template": reverse(
                "hierarchy:position_assign_board_position",
                kwargs={"pk": 0},
            ).replace("/0/", "/__ID__/"),
            "assign_url": reverse("hierarchy:position_assign_board_assign"),
            "unassign_url": reverse("hierarchy:position_assign_board_unassign"),
        },
    )


@login_required
@require_GET
def position_assign_board_position(request, pk):
    """JSON: current assignees for one position (assignment board)."""
    ensure_structure_staff(request)
    position = _get_board_position(request, pk)
    partition_assignments_for_positions([position])
    ou = position.organizational_unit
    return JsonResponse(
        {
            "position": {
                "id": position.pk,
                "title": position.title,
                "code": position.code or "",
                "ou_name": ou.name if ou else "",
                "is_active": position.is_active,
            },
            "assignments": [
                _assignment_payload(a) for a in position.org_current_assignments
            ],
        },
    )


@login_required
@require_POST
def position_assign_board_assign(request):
    """JSON: create a current assignment (drag employee onto position)."""
    ensure_structure_staff(request)
    data = _parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    try:
        position_id = int(data.get("position_id"))
        employee_id = int(data.get("employee_id"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"detail": "position_id and employee_id are required integers."},
            status=400,
        )

    position = _get_board_position(request, position_id)
    employee = get_object_or_404(
        Employee.objects.select_related("user"),
        pk=employee_id,
    )
    if employee.tenant_id != position.tenant_id:
        return JsonResponse(
            {"detail": "Employee must belong to the same tenant as the position."},
            status=400,
        )

    for existing in position.assignments.filter(employee=employee).select_related(
        "employee__user",
    ):
        if assignment_is_current(existing):
            return JsonResponse(
                {
                    "detail": "Employee is already assigned to this position.",
                    "assignment": _assignment_payload(existing),
                },
                status=409,
            )

    raw_primary = data.get("is_primary", True)
    if isinstance(raw_primary, str):
        is_primary = raw_primary.strip().lower() in ("1", "true", "yes", "on")
    else:
        is_primary = bool(raw_primary)

    assignment = PositionAssignment(
        position=position,
        employee=employee,
        is_primary=is_primary,
    )
    try:
        assignment.full_clean()
        assignment.save()
    except ValidationError as exc:
        return JsonResponse(
            {"detail": "Validation failed.", "errors": exc.message_dict},
            status=400,
        )

    assignment.employee = employee
    return JsonResponse(
        {"detail": "Assigned.", "assignment": _assignment_payload(assignment)},
        status=201,
    )


@login_required
@require_POST
def position_assign_board_unassign(request):
    """JSON: remove an assignment (drag employee back to the pool)."""
    ensure_structure_staff(request)
    data = _parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    assignment_id = data.get("assignment_id")
    try:
        assignment_id = int(assignment_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "assignment_id is required."}, status=400)

    assignment = get_object_or_404(
        PositionAssignment.objects.select_related("position__tenant", "employee__user"),
        pk=assignment_id,
    )
    ensure_structure_tenant_access(request, assignment.position.tenant)
    assignment.delete()
    return JsonResponse({"detail": "Removed."})


@login_required
@require_POST
def position_assignment_delete(request, pk):
    ensure_structure_staff(request)
    assignment = get_object_or_404(
        PositionAssignment.objects.select_related("position__tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, assignment.position.tenant)
    pos_pk = assignment.position_id
    assignment.delete()
    messages.success(request, "Assignment removed.")
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("hierarchy:position_detail", pk=pos_pk)
