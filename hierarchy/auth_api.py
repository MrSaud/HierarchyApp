import json

from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api_auth import authorize_tenant_api
from .employee_api import build_employee_api_payload, employee_detail_queryset
from .models import Employee, Sector, Tenant
from .remote_users import (
    RemoteLoginError,
    RemoteLoginUnavailableError,
    build_external_login_url,
    extract_user_rows,
    link_manager_from_remote_row,
    pick_remote_user_row_for_login,
    resolve_tenant_api_base,
    sam_account_name_from_login,
    tenant_external_api_configured,
    tenant_external_login_active,
    upsert_user_from_remote_row,
    verify_external_login,
)

User = get_user_model()


def _parse_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_login_tenant(data: dict) -> tuple[Tenant | None, JsonResponse | None]:
    raw = data.get("tenant_id")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None, JsonResponse({"detail": "Field 'tenant_id' is required."}, status=400)
    try:
        tid = int(raw)
    except (TypeError, ValueError):
        return None, JsonResponse({"detail": "tenant_id must be an integer."}, status=400)
    tenant = Tenant.objects.filter(pk=tid, is_active=True).first()
    if tenant is None:
        return None, JsonResponse({"detail": "Unknown or inactive tenant."}, status=400)
    return tenant, None


def _external_login_url(tenant: Tenant) -> str | None:
    base = resolve_tenant_api_base(tenant)
    if not base:
        return None
    return build_external_login_url(base)


def _login_auth_payload(
    tenant: Tenant,
    *,
    external_configured: bool,
    external_login_enabled: bool = False,
    external_attempted: bool = False,
    external_success: bool | None = None,
    external_error: str | None = None,
    internal_attempted: bool = False,
    internal_success: bool | None = None,
    internal_method: str | None = None,
    internal_step: str | None = None,
    internal_error: str | None = None,
) -> dict:
    """
    Authentication trace for ``POST /api/auth/login/`` responses.

    ``internal_method``: ``external_session`` (AD verified, local session) or
    ``local_password`` (Django authenticate).
  ``internal_step``: ``local_password`` | ``profile_from_ad`` | ``local_user`` |
    ``employee_profile`` | ``account_disabled`` | ``session``.
    """
    return {
        "tenant_id": tenant.pk,
        "external_api_configured": external_configured,
        "external_login_enabled": external_login_enabled,
        "external_api": {
            "attempted": external_attempted,
            "success": external_success,
            "users_url": _external_login_url(tenant) if external_configured else None,
            "error": external_error,
        },
        "internal": {
            "attempted": internal_attempted,
            "success": internal_success,
            "method": internal_method,
            "step": internal_step,
            "error": internal_error,
        },
    }


def _login_json_response(
    tenant: Tenant,
    *,
    status: int,
    detail: str,
    auth: dict,
    extra: dict | None = None,
) -> JsonResponse:
    body: dict = {"detail": detail, "auth": auth}
    if extra:
        body.update(extra)
    return JsonResponse(body, status=status)


def _resolve_user_for_local_login(tenant: Tenant, username: str, password: str, request):
    user = authenticate(request, username=username, password=password)
    if user is None:
        return None
    emp = Employee.objects.filter(user=user).first()
    if emp is not None and emp.tenant_id != tenant.pk and not user.is_superuser:
        return None
    return user


def _resolve_user_for_external_login(tenant: Tenant, username: str):
    """Find local user after AD accepted credentials (UPN, samAccountName, or email)."""
    uname = username.strip()
    sam = sam_account_name_from_login(uname)
    candidates: list[str] = []
    for value in (uname, sam):
        key = value.lower()
        if key not in {c.lower() for c in candidates}:
            candidates.append(value)

    user = None
    for candidate in candidates:
        user = User.objects.filter(username__iexact=candidate).first()
        if user is not None:
            break
    if user is None and "@" in uname:
        user = User.objects.filter(email__iexact=uname).first()
    return user


def _complete_login_response(
    request,
    tenant: Tenant,
    user,
    auth: dict,
) -> JsonResponse:
    auth["internal"]["step"] = "account_disabled"
    if not user.is_active:
        auth["internal"]["success"] = False
        auth["internal"]["error"] = "Local user account is disabled."
        return _login_json_response(
            tenant,
            status=403,
            detail="Account disabled.",
            auth=auth,
        )

    auth["internal"]["step"] = "employee_profile"
    emp = employee_detail_queryset().filter(user=user, tenant=tenant).first()
    if emp is None:
        auth["internal"]["success"] = False
        auth["internal"]["error"] = "No employee profile for this tenant."
        return _login_json_response(
            tenant,
            status=403,
            detail="No employee profile for this tenant.",
            auth=auth,
        )

    auth["internal"]["step"] = "session"
    auth["internal"]["success"] = True
    login(request, user)
    payload = build_employee_api_payload(emp)
    payload["detail"] = "Logged in."
    payload["auth"] = auth
    return JsonResponse(payload, status=200)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_users(request):
    """
    Create user: POST JSON with samAccountName, password, givenName, surname, tenant.
    ``tenant`` is the tenant slug (e.g. ``default``). Maps names to Django User fields
    and creates an Employee bound to that tenant.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    required = ("samAccountName", "password", "givenName", "surname", "tenant")
    missing = [k for k in required if k not in data]
    if missing:
        return JsonResponse(
            {"detail": f"Missing required fields: {', '.join(missing)}."},
            status=400,
        )

    sam = data["samAccountName"]
    password = data["password"]
    given = data["givenName"]
    surname = data["surname"]
    tenant_slug = data["tenant"]

    if not all(isinstance(x, str) for x in (sam, password, given, surname, tenant_slug)):
        return JsonResponse({"detail": "samAccountName, password, givenName, surname, and tenant must be strings."}, status=400)

    sam = sam.strip()
    given = given.strip()
    surname = surname.strip()
    tenant_slug = tenant_slug.strip()

    if not tenant_slug:
        return JsonResponse({"detail": "tenant cannot be empty."}, status=400)

    if not sam:
        return JsonResponse({"detail": "samAccountName cannot be empty."}, status=400)
    if not password:
        return JsonResponse({"detail": "password cannot be empty."}, status=400)

    if User.objects.filter(username__iexact=sam).exists():
        return JsonResponse({"detail": "User already exists."}, status=409)

    tenant = Tenant.objects.filter(slug__iexact=tenant_slug, is_active=True).first()
    if tenant is None:
        return JsonResponse({"detail": "Unknown or inactive tenant."}, status=400)

    if not authorize_tenant_api(request, tenant):
        return JsonResponse(
            {
                "detail": "Authentication required. Send this tenant's API key "
                "(default header X-Api-Key) or use a staff session for the same tenant.",
            },
            status=401,
        )

    try:
        validate_password(password, user=None)
    except DjangoValidationError as e:
        return JsonResponse(
            {"detail": "Password validation failed.", "errors": list(e.messages)},
            status=400,
        )

    user = User.objects.create_user(
        username=sam,
        password=password,
        first_name=given,
        last_name=surname,
    )
    Employee.objects.create(
        user=user,
        tenant=tenant,
        sector=Sector.GOVERNMENT,
    )
    return JsonResponse(
        {
            "detail": "User created.",
            "user": {
                "id": user.pk,
                "samAccountName": user.get_username(),
                "givenName": user.first_name,
                "surname": user.last_name,
                "civil_id": "",
                "employee_number": "",
                "tenant": {
                    "slug": tenant.slug,
                    "name": tenant.name,
                    "apiBaseUrl": tenant.api_base_url or None,
                },
            },
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_login(request):
    """
    JSON login: POST ``tenant_id``, ``username``, ``password``.

    When the tenant has an active external API (AD), credentials are verified with
    ``GET {external_base}/api/auth/users`` (JSON body + tenant ApiKey), then a local
    session is created for the matching employee. Otherwise uses Django ``authenticate()``.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    tenant, tenant_err = _parse_login_tenant(data)
    if tenant_err is not None:
        return tenant_err

    username = data.get("username")
    password = data.get("password")
    if username is None or password is None:
        return JsonResponse(
            {"detail": "Fields 'tenant_id', 'username', and 'password' are required."},
            status=400,
        )
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse(
            {"detail": "username and password must be strings."},
            status=400,
        )

    username = username.strip()
    if not username:
        return JsonResponse({"detail": "username cannot be empty."}, status=400)
    if not password:
        return JsonResponse({"detail": "password cannot be empty."}, status=400)

    external_configured = tenant_external_api_configured(tenant)
    login_via_ad = tenant_external_login_active(tenant)
    auth = _login_auth_payload(
        tenant,
        external_configured=external_configured,
        external_login_enabled=login_via_ad,
    )

    if login_via_ad:
        auth["external_api"]["attempted"] = True
        try:
            ad_payload = verify_external_login(tenant, username=username, password=password)
        except RemoteLoginError as exc:
            auth["external_api"]["success"] = False
            auth["external_api"]["error"] = str(exc)
            auth["internal"]["attempted"] = False
            return _login_json_response(
                tenant,
                status=401,
                detail="Invalid credentials.",
                auth=auth,
            )
        except RemoteLoginUnavailableError as exc:
            auth["external_api"]["success"] = False
            auth["external_api"]["error"] = str(exc)
            auth["internal"]["attempted"] = False
            return _login_json_response(
                tenant,
                status=503,
                detail=f"External login unavailable: {exc}",
                auth=auth,
            )

        auth["external_api"]["success"] = True
        auth["internal"]["attempted"] = True
        auth["internal"]["method"] = "external_session"
        auth["internal"]["step"] = "profile_from_ad"

        user = None
        profile_warnings: list[str] = []
        ad_row = pick_remote_user_row_for_login(extract_user_rows(ad_payload), username)
        if ad_row is not None:
            upsert = upsert_user_from_remote_row(tenant, ad_row)
            user = upsert.user
            profile_warnings.extend(upsert.errors)
            profile_warnings.extend(link_manager_from_remote_row(tenant, ad_row))
            auth["internal"]["profile_from_ad"] = True
            if upsert.user_created:
                auth["internal"]["profile_user_created"] = True
            if upsert.user_updated or upsert.employee_updated:
                auth["internal"]["profile_updated"] = True
        else:
            auth["internal"]["profile_from_ad"] = False

        if user is None:
            user = _resolve_user_for_external_login(tenant, username)

        if profile_warnings:
            auth["internal"]["profile_warnings"] = profile_warnings

        if user is None:
            auth["internal"]["success"] = False
            if ad_row is None:
                auth["internal"]["error"] = (
                    "AD credentials accepted but no user profile was returned."
                )
                detail = (
                    "AD login succeeded but no user profile was returned. "
                    "Run Sync users or check the external API response."
                )
            else:
                auth["internal"]["error"] = (
                    "AD credentials accepted but local user could not be created or matched."
                )
                detail = (
                    "Could not create or match a local user from the AD profile. "
                    "Run Sync users or check sync errors."
                )
            return _login_json_response(
                tenant,
                status=403,
                detail=detail,
                auth=auth,
            )

        return _complete_login_response(request, tenant, user, auth)

    auth["internal"]["attempted"] = True
    auth["internal"]["method"] = "local_password"
    auth["internal"]["step"] = "local_password"

    user = _resolve_user_for_local_login(tenant, username, password, request)
    if user is None:
        auth["internal"]["success"] = False
        auth["internal"]["error"] = "Local username/password verification failed."
        return _login_json_response(
            tenant,
            status=401,
            detail="Invalid credentials.",
            auth=auth,
        )

    return _complete_login_response(request, tenant, user, auth)
