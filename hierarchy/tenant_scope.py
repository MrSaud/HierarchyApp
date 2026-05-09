"""Session-backed tenant scope for superusers (operate as one tenant at a time)."""

from .models import Tenant

SESSION_ACTIVE_TENANT_KEY = "active_tenant_id"
# True means the user explicitly chose “All tenants” (not merely unset session).
SESSION_TENANT_SCOPE_ALL = "tenant_scope_all"
DEFAULT_SUPERUSER_SCOPE_SLUG = "default"


def get_superuser_active_tenant(request):
    """
    Return the scoped Tenant for the superuser.

    - Explicit “All tenants” (session flag) → None.
    - Session stores a tenant id → that tenant if it exists.
    - Otherwise → implicit default: tenant with slug ``default`` if present, else None.
    """
    if not request.user.is_authenticated or not request.user.is_superuser:
        return None
    if request.session.get(SESSION_TENANT_SCOPE_ALL):
        return None
    tid = request.session.get(SESSION_ACTIVE_TENANT_KEY)
    if tid:
        return Tenant.objects.filter(pk=tid).first()
    return Tenant.objects.filter(slug=DEFAULT_SUPERUSER_SCOPE_SLUG).first()


def prune_stale_session_tenant(request):
    """Clear session if the stored tenant no longer exists."""
    tid = request.session.get(SESSION_ACTIVE_TENANT_KEY)
    if tid and not Tenant.objects.filter(pk=tid).exists():
        request.session.pop(SESSION_ACTIVE_TENANT_KEY, None)
