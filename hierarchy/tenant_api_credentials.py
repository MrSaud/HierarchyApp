"""Effective tenant API key / header (DB + env) for inbound checks and outbound HTTP."""

from __future__ import annotations

import os

from .models import Tenant


def effective_tenant_api_key(tenant: Tenant) -> str:
    """DB field or env ``TENANT_API_KEY_<pk>`` (env wins when set)."""
    env_val = os.environ.get(f"TENANT_API_KEY_{tenant.pk}")
    if env_val is not None:
        return env_val.strip()
    return (tenant.api_key or "").strip()


def effective_tenant_api_key_header(tenant: Tenant) -> str:
    env_val = os.environ.get(f"TENANT_API_KEY_HEADER_{tenant.pk}")
    if env_val is not None:
        h = env_val.strip()
        return h if h else "X-Api-Key"
    h = (tenant.api_key_header or "").strip()
    return h if h else "X-Api-Key"


def merge_outbound_api_headers(
    base: dict[str, str],
    tenant: Tenant | None,
) -> dict[str, str]:
    """
    Copy ``base`` and add this tenant's API key header when a secret is configured.

    Used for server-side GETs to the tenant's remote ``/api/...`` (health, user list).
    """
    out = dict(base)
    if tenant is None:
        return out
    secret = effective_tenant_api_key(tenant)
    if not secret:
        return out
    out[effective_tenant_api_key_header(tenant)] = secret
    return out
