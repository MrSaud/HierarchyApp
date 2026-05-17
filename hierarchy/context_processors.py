from .access import resolve_active_structure_tenant
from .api_terminology import (
    EXTERNAL_API_CREDENTIALS_SECTION,
    EXTERNAL_API_LEAD,
    EXTERNAL_API_SECTION,
    EXTERNAL_LOGIN_LEAD,
    EXTERNAL_LOGIN_SECTION,
    INTERNAL_API_LEAD,
    INTERNAL_API_SECTION,
    ORGANIZATION_LEAD,
    ORGANIZATION_SECTION,
    STATUS_LEAD,
    STATUS_SECTION,
)
from .models import Employee, Tenant
from .tenant_scope import get_superuser_active_tenant, prune_stale_session_tenant
from .user_tenant import get_user_tenant_id


def _user_initials(user):
    name = user.get_full_name().strip()
    if name:
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return parts[0][:2].upper()
    un = user.get_username()
    return (un[:2] if len(un) >= 2 else (un + "?")[:2]).upper()


def employee_photo_bar(request):
    """Employee photo URL and user initials for the app bar (Employee.personal_photo)."""
    out = {"employee_photo_url": None, "avatar_initials": ""}
    if not request.user.is_authenticated:
        return out
    out["avatar_initials"] = _user_initials(request.user)
    emp = Employee.objects.filter(user=request.user).only("personal_photo").first()
    if emp and emp.personal_photo:
        out["employee_photo_url"] = emp.personal_photo.url
    return out


def tenant_switcher(request):
    ctx = {
        "active_tenant": None,
        "tenant_switch_choices": [],
    }
    if not request.user.is_authenticated or not request.user.is_superuser:
        return ctx
    prune_stale_session_tenant(request)
    ctx["active_tenant"] = get_superuser_active_tenant(request)
    # Superusers can scope to any tenant (including inactive) for administration.
    ctx["tenant_switch_choices"] = list(Tenant.objects.order_by("name"))
    return ctx


def tenant_api_types(request):
    """External (AD) vs internal (Hierarchy) API labels for templates."""
    return {
        "api_organization_section": ORGANIZATION_SECTION,
        "api_status_section": STATUS_SECTION,
        "api_external_section": EXTERNAL_API_SECTION,
        "api_internal_section": INTERNAL_API_SECTION,
        "api_external_credentials_section": EXTERNAL_API_CREDENTIALS_SECTION,
        "api_external_login_section": EXTERNAL_LOGIN_SECTION,
        "api_organization_lead": ORGANIZATION_LEAD,
        "api_status_lead": STATUS_LEAD,
        "api_external_lead": EXTERNAL_API_LEAD,
        "api_external_login_lead": EXTERNAL_LOGIN_LEAD,
        "api_internal_lead": INTERNAL_API_LEAD,
    }


def staff_employee_profile_notice(request):
    """Staff (non-superuser) without an Employee row cannot access tenant-scoped data."""
    out = {"staff_needs_employee_profile": False}
    user = request.user
    if not user.is_authenticated or not user.is_staff or user.is_superuser:
        return out
    if get_user_tenant_id(user) is None:
        out["staff_needs_employee_profile"] = True
    return out


def directory_search_bar(request):
    """Show global directory search when staff has a resolved structure tenant."""
    out = {"directory_search_enabled": False, "app_bar_search_q": ""}
    if not request.user.is_authenticated or not request.user.is_staff:
        return out
    tenant = resolve_active_structure_tenant(request)
    out["directory_search_enabled"] = tenant is not None
    rm = getattr(request, "resolver_match", None)
    if tenant is not None and rm and rm.url_name == "hub_search":
        q = (request.GET.get("q") or "").strip()
        if q:
            out["app_bar_search_q"] = q[:200]
    return out
