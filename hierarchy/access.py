"""Shared permission checks for tenant-scoped views."""

from django.core.exceptions import PermissionDenied

from .models import Employee, Tenant
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant, get_user_tenant_id


def ensure_employee_access(request, employee: Employee) -> None:
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        if st is None:
            raise PermissionDenied
        try:
            emp_tid = employee.tenant_id
        except AttributeError:
            emp_tid = None
        if emp_tid is None:
            raise PermissionDenied
        if emp_tid != st.pk:
            raise PermissionDenied
        return
    viewer_tid = get_user_tenant_id(request.user)
    emp_tid = employee.tenant_id
    if viewer_tid is None or emp_tid is None:
        raise PermissionDenied
    if viewer_tid != emp_tid:
        raise PermissionDenied


def ensure_tenant_manage(request, tenant) -> None:
    if not request.user.is_superuser:
        raise PermissionDenied
    st = get_superuser_active_tenant(request)
    if st is not None and tenant.pk != st.pk:
        raise PermissionDenied


def ensure_tenant_api_manage(request, tenant: Tenant) -> None:
    """Staff on this tenant, or superuser with matching active Scope tenant."""
    if not request.user.is_staff:
        raise PermissionDenied
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        if st is None or tenant.pk != st.pk:
            raise PermissionDenied
        return
    tid = get_user_tenant_id(request.user)
    if tid is None or tenant.pk != tid:
        raise PermissionDenied


def resolve_active_structure_tenant(request):
    """Tenant for org-structure UI; ``None`` when superuser has not scoped a tenant."""
    if request.user.is_superuser:
        return get_superuser_active_tenant(request)
    return get_user_tenant(request.user)


def ensure_structure_staff(request) -> None:
    if not request.user.is_staff:
        raise PermissionDenied


def ensure_structure_tenant_access(request, tenant: Tenant) -> None:
    """Staff may only manage structure for their tenant; superuser only within active scope."""
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        if st is None:
            raise PermissionDenied
        if tenant.pk != st.pk:
            raise PermissionDenied
        return
    tid = get_user_tenant_id(request.user)
    if tid is None:
        raise PermissionDenied
    if tenant.pk != tid:
        raise PermissionDenied
