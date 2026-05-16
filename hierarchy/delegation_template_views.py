"""Staff UI for delegation templates (acting director patterns, etc.)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .access import (
    ensure_structure_staff,
    ensure_structure_tenant_access,
    resolve_active_structure_tenant,
)
from django.db.models import Count

from .forms import DelegationTemplateForm
from .models import DelegationTemplate


def _template_queryset(tenant):
    return (
        DelegationTemplate.objects.filter(tenant=tenant)
        .prefetch_related("eligible_delegatee_positions")
        .annotate(delegation_count=Count("delegations", distinct=True))
        .order_by("sort_order", "name")
    )


@login_required
def delegation_template_list(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.warning(
            request,
            "Choose a tenant in Scope to manage delegation templates.",
        )
        return render(
            request,
            "hierarchy/delegation_template_list.html",
            {"structure_tenant": None, "templates": []},
        )
    ensure_structure_tenant_access(request, tenant)
    return render(
        request,
        "hierarchy/delegation_template_list.html",
        {
            "structure_tenant": tenant,
            "templates": _template_queryset(tenant),
        },
    )


@login_required
def delegation_template_create(request):
    ensure_structure_staff(request)
    tenant = resolve_active_structure_tenant(request)
    if tenant is None:
        messages.error(request, "Choose a tenant in Scope first.")
        return redirect("hierarchy:delegation_template_list")
    ensure_structure_tenant_access(request, tenant)

    if request.method == "POST":
        form = DelegationTemplateForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Delegation template created.")
            return redirect("hierarchy:delegation_template_list")
    else:
        form = DelegationTemplateForm(tenant=tenant)

    return render(
        request,
        "hierarchy/delegation_template_form.html",
        {"form": form, "structure_tenant": tenant, "is_edit": False, "tpl": None},
    )


@login_required
def delegation_template_edit(request, pk):
    ensure_structure_staff(request)
    tpl = get_object_or_404(
        DelegationTemplate.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, tpl.tenant)

    if request.method == "POST":
        form = DelegationTemplateForm(request.POST, instance=tpl, tenant=tpl.tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Template updated.")
            return redirect("hierarchy:delegation_template_list")
    else:
        form = DelegationTemplateForm(instance=tpl, tenant=tpl.tenant)

    return render(
        request,
        "hierarchy/delegation_template_form.html",
        {
            "form": form,
            "structure_tenant": tpl.tenant,
            "is_edit": True,
            "tpl": tpl,
        },
    )


@login_required
@require_POST
def delegation_template_delete(request, pk):
    ensure_structure_staff(request)
    tpl = get_object_or_404(
        DelegationTemplate.objects.select_related("tenant"),
        pk=pk,
    )
    ensure_structure_tenant_access(request, tpl.tenant)
    if tpl.delegations.exists():
        messages.error(
            request,
            f'Cannot delete "{tpl.name}": delegations still reference this template.',
        )
    else:
        tpl.delete()
        messages.success(request, "Template removed.")
    return redirect("hierarchy:delegation_template_list")
