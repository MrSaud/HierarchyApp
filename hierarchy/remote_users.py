"""Fetch users from the tenant external API (AD) GET /api/auth/users and upsert Django users."""

from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterator

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from .models import (
    Employee,
    EmploymentStatus,
    EmployeeType,
    Gender,
    MaritalStatus,
    Sector,
    Tenant,
)
from .api_usage import record_outbound_api_usage
from .tenant_api_credentials import (
    merge_outbound_api_headers,
    tenant_outbound_api_key,
)


class RemoteUserSyncError(Exception):
    """HTTP / JSON / configuration error before local DB writes."""


class RemoteLoginError(Exception):
    """External AD rejected credentials (HTTP 401/403 or ``success: false``)."""


class RemoteLoginUnavailableError(Exception):
    """External AD login could not be attempted (missing config or server error)."""


def default_api_base_from_settings() -> str:
    """Infer API host from EXTERNAL_API_HEALTH_URL (strip ``/api/health``)."""
    health = (getattr(settings, "EXTERNAL_API_HEALTH_URL", "") or "").strip().rstrip("/")
    if health.endswith("/api/health"):
        return health[: -len("/api/health")]
    return ""


def resolve_tenant_api_base(tenant: Tenant) -> str:
    raw = (tenant.api_base_url or "").strip().rstrip("/")
    if raw:
        return raw
    return default_api_base_from_settings()


def tenant_external_api_configured(tenant: Tenant) -> bool:
    """True when sync, health, and other outbound tools may call the external AD API."""
    return bool(tenant.is_active and resolve_tenant_api_base(tenant))


def tenant_external_api_active(tenant: Tenant) -> bool:
    """Alias for :func:`tenant_external_api_configured` (backward-compatible name)."""
    return tenant_external_api_configured(tenant)


def tenant_external_login_active(tenant: Tenant) -> bool:
    """True when ``POST /api/auth/login/`` should verify credentials against AD."""
    return bool(
        tenant_external_api_configured(tenant) and getattr(tenant, "external_login_enabled", True)
    )


def external_health_url(base: str) -> str:
    """``{base}/api/health`` on the tenant external API (AD) server."""
    return f"{base.strip().rstrip('/')}/api/health"


def external_users_url(base: str) -> str:
    """``{base}/api/auth/users`` (external AD user list / login probe)."""
    return f"{base.strip().rstrip('/')}/api/auth/users"


def external_auth_users_url(base: str) -> str:
    """Alias for :func:`external_users_url` (backward-compatible name)."""
    return external_users_url(base)


def build_external_login_url(base: str) -> str:
    """External login probe path without credentials (for display in ``auth`` payloads)."""
    return external_auth_users_url(base)


def sam_account_name_from_login(username: str) -> str:
    """``Test@swap.local`` → ``Test``; otherwise the login name as-is."""
    u = username.strip()
    if "@" in u:
        return u.split("@", 1)[0]
    return u


def build_external_login_request_body(*, username: str, password: str) -> bytes:
    """JSON body for external ``GET /api/auth/users`` credential check (Postman)."""
    return json.dumps({"username": username, "password": password}).encode("utf-8")


def build_users_list_url(
    base: str,
    *,
    search: str | None,
    take: int,
    container: str | None = None,
) -> str:
    """
    ``GET /api/auth/users?take=…&search=…&container=…``

    ``search`` filters name / UPN / email (substring). ``take`` default 100, max 500.
    ``container`` is an optional OU DN scope override.
    """
    url = external_users_url(base)
    params: list[tuple[str, str]] = []
    take_n = max(1, min(500, int(take)))
    params.append(("take", str(take_n)))
    if search:
        params.append(("search", search.strip()))
    if container:
        params.append(("container", container.strip()))
    if not params:
        return url
    return f"{url}?{urllib.parse.urlencode(params)}"


def probe_external_api_health(tenant: Tenant) -> dict[str, Any]:
    """
    GET ``{external_base}/api/health`` using the tenant outbound ApiKey.

    Uses :func:`resolve_tenant_api_base` (same base as sync and login).
    """
    timeout = getattr(settings, "EXTERNAL_API_HEALTH_TIMEOUT", 10)
    base = resolve_tenant_api_base(tenant)
    if not base:
        return {
            "configured": False,
            "health_url": "",
            "timeout_seconds": timeout,
            "success": False,
            "error": "External API base URL is not configured for this tenant.",
        }

    url = external_health_url(base)
    result: dict[str, Any] = {
        "configured": True,
        "health_url": url,
        "timeout_seconds": timeout,
    }
    t0 = time.monotonic()
    try:
        headers = merge_outbound_api_headers({"Accept": "application/json"}, tenant)
        req = urllib.request.Request(url, method="GET", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body_bytes = resp.read()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            body_text = body_bytes.decode("utf-8", errors="replace")
            result["http_status"] = resp.status
            result["elapsed_ms"] = elapsed_ms
            result["success"] = True
            try:
                parsed = json.loads(body_text)
                result["json_body"] = parsed
                result["json_body_pretty"] = json.dumps(
                    parsed, indent=2, ensure_ascii=False
                )
            except json.JSONDecodeError:
                result["raw_body"] = body_text
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        result["success"] = False
        result["http_status"] = e.code
        result["elapsed_ms"] = elapsed_ms
        result["error"] = e.reason or f"HTTP {e.code}"
        try:
            result["raw_body"] = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    except urllib.error.URLError as e:
        result["success"] = False
        result["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        reason = getattr(e, "reason", e)
        result["error"] = str(reason)
    except TimeoutError:
        result["success"] = False
        result["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        result["error"] = "Request timed out."
    except Exception as e:
        result["success"] = False
        result["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        result["error"] = str(e)
    record_outbound_api_usage(
        tenant,
        "health",
        is_error=not result.get("success"),
    )
    return result


def fetch_remote_users_json(
    url: str,
    *,
    tenant: Tenant | None = None,
    json_body: bytes | None = None,
    timeout: int | None = None,
    usage_operation: str | None = None,
) -> object:
    """
    ``GET`` remote URL with tenant ApiKey / ApiKeyHeader.

  When ``json_body`` is set, sends it as the request body (external login probe).
    """
    to = timeout if timeout is not None else getattr(
        settings,
        "EXTERNAL_API_HEALTH_TIMEOUT",
        10,
    )
    headers = merge_outbound_api_headers({"Accept": "application/json"}, tenant)
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method="GET", headers=headers, data=json_body)
    op = usage_operation

    def _record(*, is_error: bool) -> None:
        if op and tenant is not None:
            record_outbound_api_usage(tenant, op, is_error=is_error)

    try:
        with urllib.request.urlopen(req, timeout=to) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if not body.strip():
                _record(is_error=False)
                return []
            _record(is_error=False)
            return json.loads(body)
    except urllib.error.HTTPError as e:
        _record(is_error=True)
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RemoteUserSyncError(
            f"Remote API returned HTTP {e.code}. {detail or e.reason}"
        ) from e
    except urllib.error.URLError as e:
        _record(is_error=True)
        raise RemoteUserSyncError(f"Network error: {e}") from e
    except json.JSONDecodeError as e:
        _record(is_error=True)
        raise RemoteUserSyncError(f"Invalid JSON from remote API: {e}") from e


def verify_external_login(
    tenant: Tenant,
    *,
    username: str,
    password: str,
) -> object:
    """
    Verify credentials against the tenant external AD API.

    ``GET {base}/api/auth/users`` with JSON body ``username`` / ``password`` and
    outbound tenant ApiKey (same path as sync; credentials in body for login only).
    """
    base = resolve_tenant_api_base(tenant)
    if not base:
        raise RemoteLoginUnavailableError("No external API base URL configured.")
    if not tenant_outbound_api_key(tenant):
        raise RemoteLoginUnavailableError(
            "Tenant ApiKey is not configured for external API calls."
        )

    url = external_users_url(base)
    body = build_external_login_request_body(username=username, password=password)
    try:
        payload = fetch_remote_users_json(
            url,
            tenant=tenant,
            json_body=body,
            usage_operation="ad_login",
        )
    except RemoteUserSyncError as exc:
        msg = str(exc)
        if "HTTP 401" in msg or "HTTP 403" in msg:
            raise RemoteLoginError(msg) from exc
        raise RemoteLoginUnavailableError(msg) from exc

    if isinstance(payload, dict):
        if payload.get("success") is False:
            detail = payload.get("message") or payload.get("detail") or "External authentication failed."
            raise RemoteLoginError(str(detail))
        if payload.get("authenticated") is False:
            detail = payload.get("message") or "External authentication failed."
            raise RemoteLoginError(str(detail))
    return payload


def extract_user_rows(payload: object) -> list[dict]:
    """Normalize JSON body to a list of user dicts (wrapped ``users`` array supported)."""
    rows: list[dict] = []
    if isinstance(payload, list):
        rows = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("users", "items", "value", "data", "results", "records"):
            inner = payload.get(key)
            if isinstance(inner, list):
                rows = [x for x in inner if isinstance(x, dict)]
                break
    return [normalize_remote_user_row(row) for row in rows]


_JUNK_AD_PREFIXES = ("System.", "System.__")


def _is_junk_ad_scalar(value: str) -> bool:
    s = value.strip()
    if not s:
        return True
    return any(s.startswith(prefix) for prefix in _JUNK_AD_PREFIXES)


def _flatten_ad_value(val: Any) -> str | None:
    """LDAP/API values are often ``[\"single\"]``; drop COM-object placeholders."""
    if val is None:
        return None
    if isinstance(val, list):
        for item in val:
            flat = _flatten_ad_value(item)
            if flat:
                return flat
        return None
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, (int, float)):
        s = str(val).strip()
        return s if s and not _is_junk_ad_scalar(s) else None
    s = str(val).strip()
    if _is_junk_ad_scalar(s):
        return None
    return s


def normalize_remote_user_row(raw: dict) -> dict:
    """
    Flatten ``properties`` (AD attribute bags) into one dict for extractors.

    Top-level API fields (``samAccountName``, ``givenName``, ``enabled``, …) win
    over ``properties`` when both are present.
    """
    merged: dict[str, Any] = {}
    props = raw.get("properties")
    if isinstance(props, dict):
        for key, val in props.items():
            flat = _flatten_ad_value(val)
            if flat is not None:
                merged[key] = flat

    for key, val in raw.items():
        if key in ("properties", "groups"):
            continue
        if key == "enabled" and isinstance(val, bool):
            merged["enabled"] = val
            continue
        flat = _flatten_ad_value(val)
        if flat is not None:
            merged[key] = flat

    return merged


def _first_present(raw: dict, keys: tuple[str, ...]) -> Any | None:
    """Return first key's value if the key exists in ``raw`` (including JSON ``null``)."""
    for k in keys:
        if k in raw:
            return raw.get(k)
    return None


def _first_str(raw: dict, *keys: str) -> str | None:
    v = _first_present(raw, keys)
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v).lower()
    s = str(v).strip()
    return s if s else None


def _parse_date(val: Any) -> date | None:
    if val is None or val == "":
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10].replace("T", " ")[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _norm_sector(raw: dict) -> str:
    v = _first_str(
        raw,
        "sector",
        "businessSector",
        "organizationType",
        "companyType",
    )
    if not v:
        return Sector.GOVERNMENT
    sl = v.lower()
    if "private" in sl or sl in ("private", "commercial", "corp"):
        return Sector.PRIVATE
    return Sector.GOVERNMENT


def _norm_gender(val: str | None) -> str:
    if not val:
        return ""
    s = str(val).strip().lower()
    if s in ("m", "male", "1", "man"):
        return Gender.MALE
    if s in ("f", "female", "2", "woman"):
        return Gender.FEMALE
    if s in ("other", "o", "3"):
        return Gender.OTHER
    if "prefer" in s or s in ("u", "unknown"):
        return Gender.PREFER_NOT
    return ""


def _norm_marital(val: str | None) -> str:
    if not val:
        return ""
    s = str(val).strip().lower()
    mapping = {
        "single": MaritalStatus.SINGLE,
        "married": MaritalStatus.MARRIED,
        "divorced": MaritalStatus.DIVORCED,
        "widowed": MaritalStatus.WIDOWED,
        "other": MaritalStatus.OTHER,
    }
    return mapping.get(s, "")


def _norm_employment_status(raw: dict) -> str:
    if raw.get("enabled") is False:
        return EmploymentStatus.TERMINATED
    if raw.get("accountDisabled") is True:
        return EmploymentStatus.TERMINATED
    v = _first_str(
        raw,
        "employmentStatus",
        "employment_status",
        "userAccountControl",
        "status",
    )
    if not v:
        return EmploymentStatus.ACTIVE
    s = v.lower().replace(" ", "_").replace("-", "_")
    fixes = {
        "active": EmploymentStatus.ACTIVE,
        "probation": EmploymentStatus.PROBATION,
        "on_leave": EmploymentStatus.ON_LEAVE,
        "onleave": EmploymentStatus.ON_LEAVE,
        "suspended": EmploymentStatus.SUSPENDED,
        "terminated": EmploymentStatus.TERMINATED,
        "retired": EmploymentStatus.RETIRED,
        "inactive": EmploymentStatus.TERMINATED,
        "disabled": EmploymentStatus.TERMINATED,
    }
    return fixes.get(s, EmploymentStatus.ACTIVE)


def _norm_employee_type(val: str | None) -> str:
    if not val:
        return EmployeeType.FULL_TIME
    s = str(val).lower()
    if "part" in s:
        return EmployeeType.PART_TIME
    if "contract" in s:
        return EmployeeType.CONTRACTOR
    if "intern" in s:
        return EmployeeType.INTERN
    return EmployeeType.FULL_TIME


def extract_username(raw: dict) -> str | None:
    uname = (
        raw.get("samAccountName")
        or raw.get("sAMAccountName")
        or raw.get("username")
        or raw.get("userName")
        or raw.get("login")
        or raw.get("accountName")
    )
    if uname is None:
        return None
    u = str(uname).strip()
    return u[:150] if u else None


def extract_user_defaults(raw: dict) -> dict[str, str]:
    """Fields for Django ``User`` (non-empty strings)."""
    given = (
        raw.get("givenName")
        or raw.get("firstName")
        or raw.get("first_name")
        or raw.get("given_name")
        or ""
    )
    surname = (
        raw.get("surname")
        or raw.get("lastName")
        or raw.get("last_name")
        or raw.get("family_name")
        or ""
    )
    email = (
        raw.get("mail")
        or raw.get("email")
        or raw.get("emailAddress")
        or raw.get("userPrincipalName")
        or ""
    )
    return {
        "first_name": str(given).strip()[:150],
        "last_name": str(surname).strip()[:150],
        "email": str(email).strip()[:254],
    }


def _ou_from_distinguished_name(raw: dict) -> str | None:
    """Parse ``OU=…`` from AD ``distinguishedName`` (e.g. ``OU=Employees,DC=…``)."""
    dn = _first_str(raw, "distinguishedName", "distinguished_name")
    if not dn:
        return None
    match = re.search(r"OU=([^,]+)", dn, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip() or None


def extract_nationality(raw: dict) -> str | None:
    """
    Map nationality / country for ``Employee.nationality``.

    AD (in ``properties``): ``co`` = country name (e.g. Algeria), ``c`` = ISO alpha-2
    (e.g. DZ). Numeric ``countryCode`` is a phone dialling code — not used here.
    """
    for key in (
        "country",
        "nationality",
        "citizenship",
        "countryOfBirth",
        "country_of_birth",
    ):
        inner = raw.get(key)
        if isinstance(inner, dict):
            name = (
                inner.get("name")
                or inner.get("displayName")
                or inner.get("countryName")
                or inner.get("label")
                or inner.get("englishName")
            )
            if name is not None:
                s = str(name).strip()
                if s:
                    return s[:120]
            code = (
                inner.get("iso3166Alpha2")
                or inner.get("alpha2")
                or inner.get("code")
                or inner.get("value")
            )
            if code is not None:
                s = str(code).strip()
                if len(s) == 2 and s.isalpha():
                    return s.upper()[:120]
        elif isinstance(inner, str):
            s = inner.strip()
            if s:
                return s[:120]

    # Prefer human-readable country (AD ``co``) before ISO code (AD ``c``).
    name = _first_str(
        raw,
        "co",
        "countryName",
        "country_name",
        "nationality",
        "nationalityName",
        "nationality_name",
        "countryOfCitizenship",
        "country_of_citizenship",
        "citizenship",
        "citizenshipCountry",
        "birthCountry",
        "birth_country",
    )
    if name is not None:
        return name[:120]

    code = _first_str(raw, "c", "isoCountryCode", "nationalityCode")
    if code is not None and len(code) == 2 and code.isalpha():
        return code.upper()[:120]

    return None


def extract_employee_updates(raw: dict) -> dict[str, Any]:
    """
    Map API / AD-style keys to ``Employee`` field names.
    Only includes keys we could derive from the payload (omitted = leave DB unchanged).
    """
    out: dict[str, Any] = {}

    v = _first_str(
        raw,
        "employeeNumber",
        "employeeId",
        "employeeID",
        "employee_id",
        "badgeNumber",
        "badge",
    )
    if v is not None:
        out["employee_number"] = v[:64] if v else None

    v = _first_str(raw, "title", "jobTitle", "job_title")
    if v is not None:
        out["job_title"] = v[:120]

    v = _first_str(raw, "department", "organizationalUnit", "division", "company")
    if v is not None:
        out["department"] = v[:120]
    else:
        ou_name = _ou_from_distinguished_name(raw)
        if ou_name:
            out["department"] = ou_name[:120]

    v = _first_str(raw, "sectionTeam", "section_team", "section", "team", "businessUnit")
    if v is not None:
        out["section_team"] = v[:120]

    v = _first_present(raw, ("hireDate", "employeeHireDate", "startDate", "hire_date"))
    if v is not None:
        d = _parse_date(v)
        if d:
            out["hire_date"] = d

    out["employment_status"] = _norm_employment_status(raw)

    v = _first_str(
        raw,
        "office",
        "officeLocation",
        "physicalDeliveryOfficeName",
        "workLocation",
        "work_location",
        "location",
    )
    if v is not None:
        out["work_location"] = v[:255]

    out["employee_type"] = _norm_employee_type(
        _first_str(raw, "employeeType", "employmentType", "employee_type")
    )

    v = _first_str(
        raw,
        "civilId",
        "civil_id",
        "nationalId",
        "nationalID",
        "governmentId",
        "idNumber",
    )
    if v is not None:
        out["civil_id"] = v[:80]

    vb = _first_present(raw, ("birthDate", "dateOfBirth", "date_of_birth", "birthday"))
    if vb is not None:
        bd = _parse_date(vb)
        if bd:
            out["date_of_birth"] = bd

    vg = _first_str(raw, "gender", "sex")
    if vg is not None:
        ng = _norm_gender(vg)
        if ng:
            out["gender"] = ng

    nat = extract_nationality(raw)
    if nat is not None:
        out["nationality"] = nat

    vm = _first_str(raw, "maritalStatus", "marital_status")
    if vm is not None:
        nm = _norm_marital(vm)
        if nm:
            out["marital_status"] = nm

    v = _first_str(
        raw,
        "mobile",
        "mobilePhone",
        "telephoneNumber",
        "phone",
        "businessPhones",
    )
    if v is not None:
        out["mobile_number"] = v[:32]

    street = _first_str(raw, "streetAddress", "street")
    city = _first_str(raw, "city", "l")
    postal = _first_str(raw, "postalCode", "zip")
    region = _first_str(raw, "state", "st", "region")
    if any(x is not None for x in (street, city, postal, region)):
        parts = [p for p in (street, city, region, postal) if p]
        out["home_address"] = ", ".join(parts)[:2000] if parts else ""

    v = _first_str(raw, "emergencyContact", "emergency_contact", "iceContact")
    if v is not None:
        out["emergency_contact"] = v[:2000]

    out["sector"] = _norm_sector(raw)

    return out


def extract_manager_username(raw: dict) -> str | None:
    v = _first_present(
        raw,
        ("managerSamAccountName", "managerUsername", "managerLogin", "manager"),
    )
    if isinstance(v, dict):
        return extract_username(v)
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def extract_photo_url(raw: dict) -> str | None:
    return _first_str(
        raw,
        "thumbnailPhotoUrl",
        "photoUrl",
        "picture",
        "personalPhotoUrl",
        "avatarUrl",
    )


def try_download_photo(url: str, *, timeout: int = 8) -> ContentFile | None:
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) > 6 * 1024 * 1024:
                return None
            ct = (resp.headers.get("Content-Type") or "").lower()
            ext = ".jpg"
            if "png" in ct:
                ext = ".png"
            elif "gif" in ct:
                ext = ".gif"
            elif "webp" in ct:
                ext = ".webp"
            return ContentFile(data, name=f"sync_{secrets.token_hex(8)}{ext}")
    except Exception:
        return None


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    skipped_existing: int = 0
    tenant_linked: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    managers_linked: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class RemoteUserUpsertResult:
    user: object | None = None
    employee: Employee | None = None
    user_created: bool = False
    user_updated: bool = False
    employee_created: bool = False
    employee_updated: bool = False
    skipped_no_username: bool = False
    skipped_existing: bool = False
    errors: list[str] = field(default_factory=list)


def pick_remote_user_row_for_login(rows: list[dict], username: str) -> dict | None:
    """Choose the AD row that matches the login id when the payload has multiple users."""
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    login = username.strip()
    sam = sam_account_name_from_login(login)
    keys: list[str] = []
    for value in (login, sam):
        key = value.lower()
        if key not in {k.lower() for k in keys}:
            keys.append(value)

    for row in rows:
        uname = (extract_username(row) or "").strip()
        ud = extract_user_defaults(row)
        email = (ud.get("email") or "").strip()
        for key in keys:
            if uname and uname.lower() == key.lower():
                return row
            if email and email.lower() == key.lower():
                return row
            if "@" in key and email and email.lower() == login.lower():
                return row
    return rows[0]


def upsert_user_from_remote_row(
    tenant: Tenant,
    raw: dict,
    *,
    only_new: bool = False,
) -> RemoteUserUpsertResult:
    """Create or update one Django ``User`` and ``Employee`` from a remote AD user dict."""
    User = get_user_model()
    result = RemoteUserUpsertResult()
    uname = extract_username(raw)
    if not uname:
        result.skipped_no_username = True
        return result

    if only_new and User.objects.filter(username__iexact=uname).exists():
        result.skipped_existing = True
        return result

    try:
        ud = extract_user_defaults(raw)
        emp_updates = extract_employee_updates(raw)

        user = User.objects.filter(username__iexact=uname).first()
        if user is None:
            user = User(
                username=uname,
                email=ud["email"],
                first_name=ud["first_name"],
                last_name=ud["last_name"],
            )
            user.set_unusable_password()
            user.save()
            result.user_created = True
        else:
            changed = False
            if ud["email"] and user.email != ud["email"]:
                user.email = ud["email"]
                changed = True
            if user.first_name != ud["first_name"]:
                user.first_name = ud["first_name"]
                changed = True
            if user.last_name != ud["last_name"]:
                user.last_name = ud["last_name"]
                changed = True
            if changed:
                user.save(update_fields=["email", "first_name", "last_name"])
                result.user_updated = True

        emp, emp_created = Employee.objects.get_or_create(
            user=user,
            defaults={
                "sector": emp_updates.get("sector", Sector.GOVERNMENT),
                "tenant": tenant,
            },
        )
        result.employee = emp
        if emp_created:
            result.employee_created = True

        changed_fields: list[str] = []
        if emp.tenant_id != tenant.pk:
            emp.tenant = tenant
            changed_fields.append("tenant")

        for fname, val in emp_updates.items():
            current = getattr(emp, fname)
            if current != val:
                setattr(emp, fname, val)
                changed_fields.append(fname)

        photo_added = False
        photo_url = extract_photo_url(raw)
        if photo_url and not emp.personal_photo:
            cf = try_download_photo(photo_url)
            if cf:
                emp.personal_photo.save(cf.name, cf, save=False)
                photo_added = True

        if changed_fields or photo_added:
            update_fields = changed_fields.copy()
            if photo_added:
                update_fields.append("personal_photo")
            try:
                emp.save(update_fields=update_fields)
            except Exception as exc:
                result.errors.append(f"{uname} (employee save): {exc}")
            else:
                if not emp_created:
                    result.employee_updated = True

        result.user = user
    except Exception as exc:
        result.errors.append(f"{uname}: {exc}")

    return result


def link_employee_manager_for_tenant(
    tenant: Tenant,
    *,
    user_username_lower: str,
    manager_username: str,
) -> bool:
    """Set ``employee.manager`` when both employees exist in the tenant."""
    mgr_uname = manager_username.strip()
    if not mgr_uname:
        return False
    emp = Employee.objects.filter(
        user__username__iexact=user_username_lower,
        tenant=tenant,
    ).first()
    mgr_emp = Employee.objects.filter(
        user__username__iexact=mgr_uname,
        tenant=tenant,
    ).first()
    if emp and mgr_emp and emp.pk != mgr_emp.pk:
        if emp.manager_id != mgr_emp.pk:
            emp.manager = mgr_emp
            emp.save(update_fields=["manager"])
            return True
    return False


def link_manager_from_remote_row(tenant: Tenant, raw: dict) -> list[str]:
    uname = extract_username(raw)
    mgr_u = extract_manager_username(raw)
    if not uname or not mgr_u:
        return []
    try:
        link_employee_manager_for_tenant(
            tenant,
            user_username_lower=uname.lower(),
            manager_username=mgr_u,
        )
    except Exception as exc:
        return [f"manager {mgr_u}: {exc}"]
    return []


def sync_users_for_tenant_events(
    tenant: Tenant,
    rows: list[dict],
    *,
    only_new: bool = False,
) -> Iterator[dict[str, Any]]:
    """
    Create/update Django ``User`` and ``Employee`` from API rows.

    When ``only_new`` is true, skip rows whose username already exists locally
    (no user or employee updates for existing accounts).

    Yields ``phase: row`` after each remote row (percentage ~5–90%), then
    ``phase: managers``, then ``phase: complete`` with ``SyncStats``.
    """
    stats = SyncStats()
    pending_managers: list[tuple[str, str]] = []
    total = len(rows)

    for i, raw in enumerate(rows):
        upsert = upsert_user_from_remote_row(tenant, raw, only_new=only_new)
        uname = extract_username(raw)
        if upsert.skipped_no_username:
            stats.skipped += 1
        elif upsert.skipped_existing:
            stats.skipped_existing += 1
        else:
            if uname:
                mgr_u = extract_manager_username(raw)
                if mgr_u:
                    pending_managers.append((uname.lower(), mgr_u.strip()))
            if upsert.user_created:
                stats.created += 1
            elif upsert.user_updated:
                stats.updated += 1
            if upsert.user is not None:
                stats.tenant_linked += 1
            if upsert.employee_created:
                stats.employees_created += 1
            elif upsert.employee_updated:
                stats.employees_updated += 1
            stats.errors.extend(upsert.errors)

        pct = 5 + int((i + 1) / max(total, 1) * 90)
        yield {"phase": "row", "done": i + 1, "total": total, "pct": pct}

    yield {"phase": "managers", "pct": 96, "label": "Resolving managers…"}

    seen_pairs = set()
    for user_lower, mgr_uname in pending_managers:
        if not mgr_uname or (user_lower, mgr_uname.lower()) in seen_pairs:
            continue
        seen_pairs.add((user_lower, mgr_uname.lower()))
        try:
            if link_employee_manager_for_tenant(
                tenant,
                user_username_lower=user_lower,
                manager_username=mgr_uname,
            ):
                stats.managers_linked += 1
        except Exception as exc:
            stats.errors.append(f"manager {mgr_uname}: {exc}")

    yield {
        "phase": "complete",
        "stats": stats,
        "row_count": total,
        "pct": 100,
        "label": "Done",
    }


def sync_users_for_tenant(
    tenant: Tenant,
    rows: list[dict],
    *,
    only_new: bool = False,
) -> SyncStats:
    """Create/update Django ``User`` and ``Employee`` from API rows (employee carries tenant)."""
    for ev in sync_users_for_tenant_events(tenant, rows, only_new=only_new):
        if ev["phase"] == "complete":
            return ev["stats"]
    raise RuntimeError("sync incomplete")
