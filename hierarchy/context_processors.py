from .models import Employee, Tenant
from .tenant_scope import get_superuser_active_tenant, prune_stale_session_tenant


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
