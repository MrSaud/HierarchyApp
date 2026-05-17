"""
Tenant ApiKey / ApiKeyHeader.

- **Outbound (external AD API):** always ``Tenant.api_key`` and ``Tenant.api_key_header``
  from the database (tenant settings only).
- **Inbound (internal API):** ``effective_tenant_api_key*`` also allows env overrides
  ``TENANT_API_KEY_<pk>`` / ``TENANT_API_KEY_HEADER_<pk>``.
"""

from __future__ import annotations

import os

from .models import Tenant


def tenant_outbound_api_key(tenant: Tenant) -> str:
    """Secret stored on the tenant record (external API calls only)."""
    return (tenant.api_key or "").strip()


def mask_api_key_preview(secret: str, *, prefix: int = 4, suffix: int = 4) -> str:
    """
    Short masked label for UI (never the full secret).

    Examples: ``a1b2…9z0w`` (long keys), ``••••••••`` (short keys).
    """
    s = (secret or "").strip()
    if not s:
        return ""
    min_visible = prefix + suffix + 1
    if len(s) <= min_visible:
        return "•" * min(8, len(s))
    return f"{s[:prefix]}…{s[-suffix:]}"


def tenant_outbound_api_key_header(tenant: Tenant) -> str:
    """Header name stored on the tenant record; default ``X-Api-Key`` when empty."""
    h = (tenant.api_key_header or "").strip()
    return h if h else "X-Api-Key"


def effective_tenant_api_key(tenant: Tenant) -> str:
    """Inbound auth: env ``TENANT_API_KEY_<pk>`` wins when set, else DB ``api_key``."""
    env_val = os.environ.get(f"TENANT_API_KEY_{tenant.pk}")
    if env_val is not None:
        return env_val.strip()
    return tenant_outbound_api_key(tenant)


def effective_tenant_api_key_header(tenant: Tenant) -> str:
    """Inbound auth: env ``TENANT_API_KEY_HEADER_<pk>`` wins when set, else DB header."""
    env_val = os.environ.get(f"TENANT_API_KEY_HEADER_{tenant.pk}")
    if env_val is not None:
        h = env_val.strip()
        return h if h else "X-Api-Key"
    return tenant_outbound_api_key_header(tenant)


def merge_outbound_api_headers(
    base: dict[str, str],
    tenant: Tenant | None,
) -> dict[str, str]:
    """
    Copy ``base`` and add the tenant's stored API key header for external AD requests.

    Uses only ``Tenant.api_key`` / ``Tenant.api_key_header`` (never env overrides).
    """
    out = dict(base)
    if tenant is None:
        return out
    secret = tenant_outbound_api_key(tenant)
    if not secret:
        return out
    out[tenant_outbound_api_key_header(tenant)] = secret
    return out
