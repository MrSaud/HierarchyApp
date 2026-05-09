"""Tenant organization structure: units, positions, assignments."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import (
    ensure_structure_staff,
    ensure_structure_tenant_access,
    resolve_active_structure_tenant,
)
from .forms import OrganizationalUnitForm, PositionAssignmentForm, PositionForm
from .models import OrganizationalUnit, Position, PositionAssignment
from .organization_structure import (
    build_org_structure_branches,
    count_structure_stats,
    partition_assignments_for_positions,
)


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
    units = OrganizationalUnit.objects.filter(tenant=tenant).order_by(
        "sort_order",
        "name",
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
    if request.method == "POST":
        form = OrganizationalUnitForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Organizational unit created.")
            return redirect("hierarchy:org_unit_list")
    else:
        form = OrganizationalUnitForm(tenant=tenant)
    return render(
        request,
        "hierarchy/org_unit_form.html",
        {"form": form, "structure_tenant": tenant, "is_edit": False},
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
            assignment = assign_form.save(commit=False)
            assignment.full_clean()
            assignment.save()
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
