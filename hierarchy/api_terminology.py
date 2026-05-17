"""
Two API surfaces per tenant:

- **External API (AD)** — Hierarchy connects *out* to the tenant's Active Directory /
  Windows Authentication server. Configured via ``Tenant.api_base_url``,
  ``Tenant.api_key``, and ``Tenant.api_key_header`` (tenant settings only).

- **Internal API (Hierarchy)** — Other systems connect *in* to this application
  (employees, org structure, provision users). No separate URL on the tenant record;
  use this app's public base URL and staff session / global Bearer where documented.
"""

from django.utils.translation import gettext_lazy as _

ORGANIZATION_SECTION = _("Organization")
STATUS_SECTION = _("Status")
EXTERNAL_API_SECTION = _("External API (AD)")
INTERNAL_API_SECTION = _("Internal API (Hierarchy)")
EXTERNAL_API_CREDENTIALS_SECTION = _("Credentials")
EXTERNAL_LOGIN_SECTION = _("Login")

ORGANIZATION_LEAD = _(
    "Display name and API slug for this organization. The slug appears in URLs and JSON (e.g. tenant on user provisioning)."
)
STATUS_LEAD = _("Inactive tenants are hidden from most staff workflows; data is kept.")

EXTERNAL_API_LEAD = _(
    "Connections from Hierarchy to the tenant's Active Directory server "
    "(Windows Authentication). Set the base URL and credentials for sync and health. "
    "Use the login toggle to choose whether API login verifies against AD or local passwords only."
)

EXTERNAL_LOGIN_LEAD = _(
    "When AD login is on, POST /api/auth/login/ checks credentials with the external server. "
    "When off, login uses local Django passwords only; sync and health still use the connection above."
)

INTERNAL_API_LEAD = _(
    "APIs this application exposes to other systems (export employees, org structure, provision users). "
    "Use the base URL below; see API guide for staff session and optional global Bearer."
)
