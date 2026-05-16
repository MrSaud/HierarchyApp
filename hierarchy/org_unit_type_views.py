"""Staff UI for tenant organizational unit type catalog."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import (
    ensure_structure_staff,
    ensure_structure_tenant_access,
    resolve_active_structure_tenant,
)
from .forms import OrgUnitTypeDefinitionForm
from .models import OrgUnitTypeDefinition
from .org_unit_types import ensure_default_org_unit_types, unit_type_in_use


def _type_queryset(tenant):
    return OrgUnitTypeDefinition.objects.filter(tenant=tenant).order_by(
        "sort_order",
        "rank",
        "label",
    )


@login_required
def org_unit_type_list(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(request, "Choose a tenant in Scope to manage unit types.")
        return render(
            request,
            "hierarchy/org_unit_type_list.html",
            {"structure_tenant": None, "unit_types": []},
        )
    ensure_structure_tenant_access(request, tenant)
    ensure_default_org_unit_types(tenant)
    rows = []
    for t in _type_queryset(tenant):
        rows.append(
            {
                "obj": t,
                "in_use": unit_type_in_use(tenant.pk, t.slug),
            }
        )
    return render(
        request,
        "hierarchy/org_unit_type_list.html",
        {"structure_tenant": tenant, "unit_types": rows},
    )


@login_required
def org_unit_type_create(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:org_unit_type_list")
    ensure_structure_tenant_access(request, tenant)

    if request.method == "POST":
        form = OrgUnitTypeDefinitionForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Unit type created.")
            return redirect("hierarchy:org_unit_type_list")
    else:
        form = OrgUnitTypeDefinitionForm(tenant=tenant)

    return render(
        request,
        "hierarchy/org_unit_type_form.html",
        {"form": form, "structure_tenant": tenant, "is_edit": False, "unit_type": None},
    )


@login_required
def org_unit_type_edit(request, pk):
    ensure_structure_staff(request)
    unit_type = get_object_or_404(
        OrgUnitTypeDefinition.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, unit_type.tenant)

    if request.method == "POST":
        form = OrgUnitTypeDefinitionForm(
            request.POST,
            instance=unit_type,
            tenant=unit_type.tenant,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Unit type updated.")
            return redirect("hierarchy:org_unit_type_list")
    else:
        form = OrgUnitTypeDefinitionForm(instance=unit_type, tenant=unit_type.tenant)

    return render(
        request,
        "hierarchy/org_unit_type_form.html",
        {
            "form": form,
            "structure_tenant": unit_type.tenant,
            "is_edit": True,
            "unit_type": unit_type,
            "in_use": unit_type_in_use(unit_type.tenant_id, unit_type.slug),
        },
    )


@login_required
@require_POST
def org_unit_type_delete(request, pk):
    ensure_structure_staff(request)
    unit_type = get_object_or_404(
        OrgUnitTypeDefinition.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, unit_type.tenant)
    if unit_type_in_use(unit_type.tenant_id, unit_type.slug):
        messages.error(
            request,
            f'Cannot remove “{unit_type.label}”: organizational units still use this type.',
        )
    else:
        unit_type.delete()
        messages.success(request, "Unit type removed.")
    return redirect("hierarchy:org_unit_type_list")


@login_required
@require_POST
def org_unit_type_restore_defaults(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:org_unit_type_list")
    ensure_structure_tenant_access(request, tenant)
    created = ensure_default_org_unit_types(tenant)
    if created:
        messages.success(request, f"Added {created} missing default unit type(s).")
    else:
        messages.info(request, "All default unit types are already present.")
    return redirect("hierarchy:org_unit_type_list")
