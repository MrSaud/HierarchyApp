import json

from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api_auth import authorize_tenant_api
from .models import Employee, Sector, Tenant

User = get_user_model()


def _parse_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


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
    JSON login: POST {"username": "...", "password": "..."}
    On success, creates a session and returns Set-Cookie (sessionid).
    CSRF-exempt so non-browser clients can authenticate without a CSRF token.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=204)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body."}, status=400)

    username = data.get("username")
    password = data.get("password")
    if username is None or password is None:
        return JsonResponse(
            {"detail": "Fields 'username' and 'password' are required."},
            status=400,
        )
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({"detail": "username and password must be strings."}, status=400)

    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials."}, status=401)
    if not user.is_active:
        return JsonResponse({"detail": "Account disabled."}, status=403)

    login(request, user)
    from .user_tenant import get_user_tenant

    t = get_user_tenant(user)
    tenant_payload = (
        {
            "slug": t.slug,
            "name": t.name,
            "apiBaseUrl": t.api_base_url or None,
        }
        if t is not None
        else None
    )
    emp_login = Employee.objects.filter(user=user).only("civil_id", "employee_number").first()
    civil_id_login = (emp_login.civil_id or "") if emp_login else ""
    employee_number_login = (emp_login.employee_number or "") if emp_login else ""
    return JsonResponse(
        {
            "detail": "Logged in.",
            "user": {
                "id": user.pk,
                "username": user.get_username(),
                "email": user.email or "",
                "is_staff": user.is_staff,
                "civil_id": civil_id_login,
                "employee_number": employee_number_login,
                "tenant": tenant_payload,
            },
        },
        status=200,
    )
