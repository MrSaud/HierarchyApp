"""Inbound authentication for the internal API (per-tenant ApiKey + optional global Bearer)."""

from __future__ import annotations

import secrets

from django.conf import settings

from .models import Tenant
from .tenant_api_credentials import (
    effective_tenant_api_key,
    effective_tenant_api_key_header,
)
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant_id


def generate_tenant_api_token() -> str:
    return secrets.token_urlsafe(32)


def get_http_header(request, name: str) -> str | None:
    v = request.headers.get(name)
    if v is not None:
        return v
    meta_key = "HTTP_" + name.upper().replace("-", "_")
    return request.META.get(meta_key)


def tenant_api_key_matches(request, tenant: Tenant) -> bool:
    secret = effective_tenant_api_key(tenant)
    if not secret:
        return False
    header_name = effective_tenant_api_key_header(tenant)
    provided = get_http_header(request, header_name)
    if provided is None:
        return False
    try:
        return secrets.compare_digest(
            provided.strip().encode("utf-8"),
            secret.encode("utf-8"),
        )
    except (UnicodeEncodeError, AttributeError):
        return False


def global_bearer_matches(request) -> bool:
    token = (getattr(settings, "EMPLOYEE_API_TOKEN", None) or "").strip()
    if not token:
        return False
    auth = (request.headers.get("Authorization") or "").strip()
    return auth == f"Bearer {token}"


def authorize_tenant_api(request, tenant: Tenant) -> bool:
    """
  Allow machine clients with this tenant's API key, optional global Bearer,
  or a staff session scoped to the same tenant (superuser: active Scope tenant only).
    """
    if tenant_api_key_matches(request, tenant):
        return True
    if global_bearer_matches(request):
        return True
    user = request.user
    if not user.is_authenticated or not user.is_staff:
        return False
    if user.is_superuser:
        st = get_superuser_active_tenant(request)
        return st is not None and st.pk == tenant.pk
    tid = get_user_tenant_id(user)
    return tid is not None and tid == tenant.pk
