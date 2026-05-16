"""Staff UI for employee authority delegations."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import (
    ensure_structure_staff,
    ensure_structure_tenant_access,
    resolve_active_structure_tenant,
)
from .delegation_utils import delegation_status_label
from .forms import DelegationForm
from .models import Delegation


def _delegation_queryset(tenant):
    return (
        Delegation.objects.filter(tenant=tenant)
        .select_related(
            "delegator__user",
            "delegatee__user",
            "template",
        )
        .order_by("-start_date", "pk")
    )


@login_required
def delegation_list(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(request, "Choose a tenant in Scope to manage delegations.")
        return render(
            request,
            "hierarchy/delegation_list.html",
            {"structure_tenant": None, "delegations": []},
        )
    ensure_structure_tenant_access(request, tenant)
    rows = []
    for d in _delegation_queryset(tenant):
        rows.append(
            {
                "obj": d,
                "status": delegation_status_label(d),
            }
        )
    return render(
        request,
        "hierarchy/delegation_list.html",
        {"structure_tenant": tenant, "delegations": rows},
    )


@login_required
def delegation_create(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:delegation_list")
    ensure_structure_tenant_access(request, tenant)

    if request.method == "POST":
        form = DelegationForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Delegation created.")
            return redirect("hierarchy:delegation_list")
    else:
        form = DelegationForm(tenant=tenant)

    return render(
        request,
        "hierarchy/delegation_form.html",
        {"form": form, "structure_tenant": tenant, "is_edit": False, "delegation": None},
    )


@login_required
def delegation_edit(request, pk):
    ensure_structure_staff(request)
    delegation = get_object_or_404(
        Delegation.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, delegation.tenant)

    if request.method == "POST":
        form = DelegationForm(request.POST, instance=delegation, tenant=delegation.tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Delegation updated.")
            return redirect("hierarchy:delegation_list")
    else:
        form = DelegationForm(instance=delegation, tenant=delegation.tenant)

    return render(
        request,
        "hierarchy/delegation_form.html",
        {
            "form": form,
            "structure_tenant": delegation.tenant,
            "is_edit": True,
            "delegation": delegation,
        },
    )


@login_required
@require_POST
def delegation_delete(request, pk):
    ensure_structure_staff(request)
    delegation = get_object_or_404(
        Delegation.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, delegation.tenant)
    if request.method == "POST":
        delegation.delete()
        messages.success(request, "Delegation removed.")
    return redirect("hierarchy:delegation_list")
