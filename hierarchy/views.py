import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .access import ensure_employee_access, ensure_tenant_manage
from .forms import (
    EmployeePhotoForm,
    EmployeePositionAssignmentForm,
    EmployeeProfileForm,
    EmployeeUserCreationForm,
    EmployeeUserEditForm,
    SignatureImageMetaForm,
    TenantForm,
    MAX_SIGNATURE_IMAGES,
)
from .remote_users import (
    RemoteUserSyncError,
    build_users_list_url,
    extract_user_rows,
    fetch_remote_users_json,
    resolve_tenant_api_base,
    sync_users_for_tenant,
    sync_users_for_tenant_events,
)
from .models import AuditLog, Employee, SignatureImage, Tenant
from .tenant_api_credentials import merge_outbound_api_headers
from .tenant_scope import (
    SESSION_ACTIVE_TENANT_KEY,
    SESSION_TENANT_SCOPE_ALL,
    get_superuser_active_tenant,
)
from .user_tenant import get_user_tenant, get_user_tenant_id


def _employee_scope_queryset(request):
    """Employees visible for the current viewer (employee.tenant or superuser scope)."""
    qs = Employee.objects.select_related(
        "user",
        "tenant",
        "manager",
        "manager__user",
    )
    if not request.user.is_superuser:
        tid = get_user_tenant_id(request.user)
        if tid is None:
            return Employee.objects.none()
        return qs.filter(tenant_id=tid)
    st = get_superuser_active_tenant(request)
    if st is not None:
        return qs.filter(tenant_id=st.pk)
    return qs


def _tenant_id_for_manager_scope(request):
    """Tenant used to filter manager dropdown when creating an employee."""
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        if st:
            return st.pk
        raw = request.POST.get("tenant")
        if raw:
            try:
                return int(raw)
            except (ValueError, TypeError):
                return None
        return None
    return get_user_tenant_id(request.user)


def _tenant_id_for_manager_scope_get(request):
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        if st:
            return st.pk
        return None
    return get_user_tenant_id(request.user)


def index(request):
    return render(request, "hierarchy/index.html")


@login_required
def employee_photo(request):
    """Upload or replace the employee photo (Employee.personal_photo) for the signed-in user."""
    employee = Employee.objects.filter(user=request.user).select_related("user").first()
    if employee is None:
        return render(
            request,
            "hierarchy/profile_requires_employee.html",
            {},
        )
    if request.method == "POST":
        form = EmployeePhotoForm(
            request.POST,
            request.FILES,
            instance=employee,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Employee photo updated.")
            return redirect("hierarchy:employee_photo")
    else:
        form = EmployeePhotoForm(instance=employee)
    return render(
        request,
        "hierarchy/employee_photo.html",
        {
            "employee": employee,
            "form": form,
        },
    )


@login_required
def tenant_create(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    if request.method == "POST":
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            messages.success(
                request,
                f'Tenant "{tenant.name}" ({tenant.slug}) was created.',
            )
            return redirect("hierarchy:tenant_list")
    else:
        form = TenantForm()
    return render(
        request,
        "hierarchy/tenant_create.html",
        {"form": form},
    )


@login_required
@require_POST
def tenant_switch(request):
    """Superuser only: set session tenant scope (or clear for “all tenants”)."""
    if not request.user.is_superuser:
        raise PermissionDenied
    next_url = request.POST.get("next") or ""
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = reverse("hierarchy:index")
    raw = request.POST.get("tenant", "")
    if raw in ("", "all"):
        request.session[SESSION_TENANT_SCOPE_ALL] = True
        request.session.pop(SESSION_ACTIVE_TENANT_KEY, None)
        messages.success(request, "You are now viewing all tenants.")
    else:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            messages.error(request, "Invalid tenant selection.")
            return redirect(next_url)
        t_obj = Tenant.objects.filter(pk=pk).first()
        if t_obj is None:
            messages.error(request, "Unknown tenant.")
        else:
            request.session[SESSION_TENANT_SCOPE_ALL] = False
            request.session[SESSION_ACTIVE_TENANT_KEY] = pk
            messages.success(
                request,
                f'Active scope: “{t_obj.name}” — employees and API health use this tenant '
                "until you change it.",
            )
    return redirect(next_url)


@login_required
def tenant_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    qs = Tenant.objects.all()
    st = get_superuser_active_tenant(request)
    if st is not None:
        qs = qs.filter(pk=st.pk)
    tenants = qs.order_by("name")
    return render(
        request,
        "hierarchy/tenant_list.html",
        {"tenants": tenants},
    )


@login_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    ensure_tenant_manage(request, tenant)
    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Tenant "{tenant.name}" was updated.',
            )
            return redirect("hierarchy:tenant_list")
    else:
        form = TenantForm(instance=tenant)
    return render(
        request,
        "hierarchy/tenant_edit.html",
        {"form": form, "tenant": tenant},
    )


@login_required
def signature_manage(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    employee = get_object_or_404(
        Employee.objects.select_related("user").prefetch_related("signatures"),
        pk=pk,
    )
    ensure_employee_access(request, employee)

    if request.method == "POST":
        if request.POST.get("delete_signature"):
            sig_pk = request.POST.get("delete_signature")
            deleted, _ = SignatureImage.objects.filter(
                pk=sig_pk,
                employee_id=employee.pk,
            ).delete()
            if deleted:
                messages.success(request, "Signature removed.")
            return redirect("hierarchy:signature_manage", pk=pk)

        if request.POST.get("update_signature"):
            sig_pk = request.POST.get("sig_pk")
            sig = get_object_or_404(SignatureImage, pk=sig_pk, employee=employee)
            form = SignatureImageMetaForm(request.POST, instance=sig)
            if form.is_valid():
                form.save()
                messages.success(request, "Signature details updated.")
            else:
                messages.error(request, "Could not update signature.")
            return redirect("hierarchy:signature_manage", pk=pk)

        files = request.FILES.getlist("signature_images")
        if files:
            existing = employee.signatures.count()
            if existing + len(files) > MAX_SIGNATURE_IMAGES:
                messages.error(
                    request,
                    f"You can have at most {MAX_SIGNATURE_IMAGES} signature images.",
                )
            else:
                max_sort = employee.signatures.aggregate(m=Max("sort_order"))["m"]
                base = (max_sort if max_sort is not None else -1) + 1
                for i, upload in enumerate(files):
                    SignatureImage.objects.create(
                        employee=employee,
                        image=upload,
                        sort_order=base + i,
                    )
                messages.success(
                    request,
                    f"Added {len(files)} signature image(s).",
                )
            return redirect("hierarchy:signature_manage", pk=pk)

    signatures = list(employee.signatures.order_by("sort_order", "pk"))
    signature_rows = [
        {"signature": s, "form": SignatureImageMetaForm(instance=s)}
        for s in signatures
    ]
    return render(
        request,
        "hierarchy/signature_manage.html",
        {
            "employee": employee,
            "signatures": signatures,
            "signature_rows": signature_rows,
            "max_signatures": MAX_SIGNATURE_IMAGES,
        },
    )


def _resolve_employee_from_bulk_key(scope, mapping: str, stem: str):
    """
    Match filename stem to an Employee within the scoped queryset.
    Returns (employee or None, error_message or None).
    """
    stem = (stem or "").strip()
    if not stem:
        return None, "empty key (filename without extension)"

    if mapping == "username":
        emp = scope.filter(user__username__iexact=stem).first()
        if emp:
            return emp, None
        return None, f'no employee with username «{stem}»'

    if mapping == "civil_id":
        qs = scope.filter(civil_id=stem)
        n = qs.count()
        if n == 0:
            return None, f'no employee with civil ID «{stem}»'
        if n > 1:
            return None, f'multiple employees ({n}) with civil ID «{stem}»'
        return qs.first(), None

    if mapping == "user_pk":
        try:
            uid = int(stem)
        except ValueError:
            return None, f'«{stem}» is not a valid user id (integer)'
        emp = scope.filter(user_id=uid).first()
        if emp:
            return emp, None
        return None, f"no employee for user id {uid}"

    return None, "invalid mapping mode"


@login_required
def signature_bulk_upload(request):
    """Staff: upload many signature images; filename (without extension) maps to employee."""
    if not request.user.is_staff:
        raise PermissionDenied

    scope = _employee_scope_queryset(request).select_related("user")

    if request.method == "POST":
        mapping = (request.POST.get("bulk_mapping") or "username").strip()
        valid_modes = frozenset({"username", "civil_id", "user_pk"})
        if mapping not in valid_modes:
            mapping = "username"

        files = request.FILES.getlist("bulk_signature_files")
        if not files:
            messages.error(request, "No files selected.")
            return redirect("hierarchy:signature_bulk_upload")

        sort_next = {}
        added = 0
        errors = []

        for upload in files:
            stem = Path(upload.name).stem
            emp, resolve_err = _resolve_employee_from_bulk_key(scope, mapping, stem)
            if resolve_err:
                errors.append(f"{upload.name}: {resolve_err}")
                continue

            try:
                ensure_employee_access(request, emp)
            except PermissionDenied:
                errors.append(f"{upload.name}: no permission for this employee")
                continue

            pk = emp.pk
            count_sig = SignatureImage.objects.filter(employee_id=pk).count()
            if count_sig >= MAX_SIGNATURE_IMAGES:
                errors.append(
                    f"{upload.name}: employee «{emp.user.get_username()}» already has "
                    f"{MAX_SIGNATURE_IMAGES} signatures",
                )
                continue

            if pk not in sort_next:
                m = SignatureImage.objects.filter(employee_id=pk).aggregate(m=Max("sort_order"))["m"]
                sort_next[pk] = (m if m is not None else -1) + 1
            sort_order = sort_next[pk]
            sort_next[pk] = sort_order + 1

            try:
                sig = SignatureImage(
                    employee=emp,
                    image=upload,
                    sort_order=sort_order,
                )
                sig.full_clean()
                sig.save()
                added += 1
            except ValidationError as exc:
                errors.append(f"{upload.name}: {exc}")
            except Exception as exc:
                errors.append(f"{upload.name}: {exc}")

        if added:
            messages.success(request, f"Added {added} signature image(s).")
        if errors:
            cap = 25
            tail = f" … (+{len(errors) - cap} more)" if len(errors) > cap else ""
            messages.warning(
                request,
                "Skipped files: " + " · ".join(errors[:cap]) + tail,
            )
        if not added and not errors:
            messages.info(request, "Nothing was uploaded.")

        return redirect("hierarchy:signature_bulk_upload")

    return render(
        request,
        "hierarchy/signature_bulk_upload.html",
        {
            "max_signatures": MAX_SIGNATURE_IMAGES,
        },
    )


@login_required
def employee_list(request):
    if not request.user.is_staff:
        raise PermissionDenied
    employees = (
        _employee_scope_queryset(request)
        .annotate(signature_count=Count("signatures"))
        .order_by(
            "user__last_name",
            "user__first_name",
            "user__username",
        )
    )
    return render(
        request,
        "hierarchy/employee_list.html",
        {"employees": employees},
    )


@login_required
def employee_create(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method == "POST":
        tid_scope = _tenant_id_for_manager_scope(request)
        scope_tid = None
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st:
                scope_tid = st.pk
        user_form = EmployeeUserCreationForm(
            request.POST,
            acting_user=request.user,
            scope_tenant_id=scope_tid,
        )
        profile_form = EmployeeProfileForm(
            request.POST,
            request.FILES,
            tenant_id=tid_scope,
        )
        if user_form.is_valid() and profile_form.is_valid():
            tenant_obj = user_form.cleaned_data["tenant"]
            mgr = profile_form.cleaned_data.get("manager")
            if mgr is not None and mgr.tenant_id != tenant_obj.pk:
                profile_form.add_error(
                    "manager",
                    "Manager must belong to the selected tenant.",
                )
            else:
                user = user_form.save()
                employee = profile_form.save(commit=False)
                employee.user = user
                employee.tenant = tenant_obj
                employee.save()
                messages.success(
                    request,
                    f"Employee “{user.get_username()}” was created. Add signature images on the next screen.",
                )
                return redirect("hierarchy:signature_manage", pk=employee.pk)
    else:
        tid_scope = _tenant_id_for_manager_scope_get(request)
        scope_tid = None
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st:
                scope_tid = st.pk
        user_form = EmployeeUserCreationForm(
            acting_user=request.user,
            scope_tenant_id=scope_tid,
        )
        profile_form = EmployeeProfileForm(tenant_id=tid_scope)
    return render(
        request,
        "hierarchy/employee_create.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,
        },
    )


@login_required
def employee_edit(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    employee = get_object_or_404(
        Employee.objects.select_related("user"),
        pk=pk,
    )
    user = employee.user

    ensure_employee_access(request, employee)

    tenant_scope_pk = employee.tenant_id

    action = (request.POST.get("action") or "").strip() if request.method == "POST" else ""

    if request.method == "POST" and action == "add_assignment":
        assign_form = EmployeePositionAssignmentForm(request.POST, employee=employee)
        if assign_form.is_valid():
            assignment = assign_form.save(commit=False)
            assignment.full_clean()
            assignment.save()
            messages.success(request, "Position assignment added.")
            return redirect("hierarchy:employee_edit", pk=employee.pk)
        user_form = EmployeeUserEditForm(instance=user)
        profile_form = EmployeeProfileForm(
            instance=employee,
            employee_instance=employee,
            tenant_id=tenant_scope_pk,
        )
    elif request.method == "POST":
        user_form = EmployeeUserEditForm(request.POST, instance=user)
        profile_form = EmployeeProfileForm(
            request.POST,
            request.FILES,
            instance=employee,
            employee_instance=employee,
            tenant_id=tenant_scope_pk,
        )
        assign_form = EmployeePositionAssignmentForm(employee=employee)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(
                request,
                f"Employee “{user.get_username()}” was updated.",
            )
            return redirect("hierarchy:employee_list")
    else:
        user_form = EmployeeUserEditForm(instance=user)
        profile_form = EmployeeProfileForm(
            instance=employee,
            employee_instance=employee,
            tenant_id=tenant_scope_pk,
        )
        assign_form = EmployeePositionAssignmentForm(employee=employee)

    assignments = employee.position_assignments.select_related(
        "position",
        "position__organizational_unit",
    ).order_by("-is_primary", "-start_date", "pk")

    return render(
        request,
        "hierarchy/employee_edit.html",
        {
            "employee": employee,
            "user_form": user_form,
            "profile_form": profile_form,
            "assign_form": assign_form,
            "position_assignments": assignments,
            "assign_positions_allowed": tenant_scope_pk is not None,
        },
    )


def _tenant_for_remote_sync(request):
    """Tenant whose remote ``/api/auth/users`` endpoint we call."""
    if request.user.is_superuser:
        raw = ""
        if request.method == "POST":
            raw = (request.POST.get("tenant_slug") or "").strip()
        if not raw:
            raw = (request.GET.get("tenant_slug") or "").strip()
        if raw:
            return Tenant.objects.filter(slug__iexact=raw, is_active=True).first()
        return get_superuser_active_tenant(request)
    return get_user_tenant(request.user)


def _user_sync_prepare(request):
    """Parse sync form/query params shared by the HTML page and streaming endpoint."""
    search_q = (request.POST.get("search") if request.method == "POST" else request.GET.get("search")) or ""
    search_q = search_q.strip()
    username_q = (request.POST.get("username") if request.method == "POST" else request.GET.get("username")) or ""
    username_q = username_q.strip()
    take_raw = (request.POST.get("take") if request.method == "POST" else request.GET.get("take")) or "100"
    try:
        take_int = max(1, min(500, int(str(take_raw).strip())))
    except ValueError:
        take_int = 100

    tenant_slug_q = ""
    if request.user.is_superuser:
        tenant_slug_q = (
            (request.POST.get("tenant_slug") if request.method == "POST" else request.GET.get("tenant_slug"))
            or ""
        ).strip()

    sync_tenant = _tenant_for_remote_sync(request)

    base = ""
    request_url = ""
    if sync_tenant is not None:
        base = resolve_tenant_api_base(sync_tenant)
        if base:
            request_url = build_users_list_url(
                base,
                search=search_q or None,
                take=take_int,
                username=username_q or None,
            )

    return {
        "search_q": search_q,
        "username_q": username_q,
        "take_int": take_int,
        "tenant_slug_q": tenant_slug_q,
        "sync_tenant": sync_tenant,
        "base": base,
        "request_url": request_url,
    }


def _sync_ndjson_line(payload: dict) -> str:
    return json.dumps(payload, default=str) + "\n"


@login_required
def user_sync(request):
    """
    Staff: GET remote ``/api/auth/users`` for the selected tenant and create/update Django users
    and employee profiles (including tenant).
    """
    if not request.user.is_staff:
        raise PermissionDenied

    prep = _user_sync_prepare(request)
    sync_tenant = prep["sync_tenant"]
    search_q = prep["search_q"]
    username_q = prep["username_q"]
    take_int = prep["take_int"]
    tenant_slug_q = prep["tenant_slug_q"]
    request_url = prep["request_url"]
    base = prep["base"]

    context = {
        "sync_tenant": sync_tenant,
        "search_q": search_q,
        "username_q": username_q,
        "take_q": str(take_int),
        "tenant_slug_q": tenant_slug_q,
        "tenant_choices": Tenant.objects.filter(is_active=True).order_by("name")
        if request.user.is_superuser
        else [],
        "request_url": request_url,
        "last_stats": None,
        "last_row_count": None,
    }

    if sync_tenant is None:
        messages.warning(
            request,
            "Choose which tenant to sync: use Scope in the app bar, or pick a tenant below (superuser).",
        )
        return render(request, "hierarchy/user_sync.html", context)

    if not base:
        messages.error(
            request,
            "No API base URL: set the tenant's API base URL or configure EXTERNAL_API_HEALTH_URL.",
        )
        return render(request, "hierarchy/user_sync.html", context)

    if request.method != "POST":
        return render(request, "hierarchy/user_sync.html", context)

    try:
        payload = fetch_remote_users_json(request_url, tenant=sync_tenant)
        rows = extract_user_rows(payload)
        stats = sync_users_for_tenant(sync_tenant, rows)
        context["last_stats"] = stats
        context["last_row_count"] = len(rows)
        messages.success(
            request,
            f"Synced {len(rows)} remote row(s): {stats.created} users created, "
            f"{stats.updated} updated, {stats.skipped} rows skipped (no username); "
            f"{stats.tenant_linked} employee tenant link(s) ensured; "
            f"{stats.employees_created} employee profile(s) created; "
            f"{stats.employees_updated} employee profile(s) updated from remote fields; "
            f"{stats.managers_linked} manager link(s) resolved.",
        )
        if stats.errors:
            messages.warning(
                request,
                "Issues: " + " · ".join(stats.errors[:15]),
            )
    except RemoteUserSyncError as exc:
        messages.error(request, str(exc))

    return render(request, "hierarchy/user_sync.html", context)


@login_required
def user_sync_stream(request):
    """POST: NDJSON stream of sync progress (for progress UI)."""
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    prep = _user_sync_prepare(request)
    sync_tenant = prep["sync_tenant"]
    request_url = prep["request_url"]
    base = prep["base"]

    if sync_tenant is None:
        return JsonResponse(
            {"detail": "Choose which tenant to sync: use Scope or tenant slug."},
            status=400,
        )
    if not base:
        return JsonResponse(
            {
                "detail": "No API base URL: set the tenant's API base URL or "
                "configure EXTERNAL_API_HEALTH_URL.",
            },
            status=400,
        )

    def ndjson_iter():
        yield _sync_ndjson_line({"phase": "fetch", "pct": 0, "label": "Fetching remote users…"})
        try:
            payload = fetch_remote_users_json(request_url, tenant=sync_tenant)
            rows = extract_user_rows(payload)
        except RemoteUserSyncError as exc:
            yield _sync_ndjson_line({"phase": "error", "message": str(exc)})
            return

        n = len(rows)
        yield _sync_ndjson_line(
            {"phase": "fetch_done", "pct": 5, "total": n, "label": "Processing rows…"}
        )

        for ev in sync_users_for_tenant_events(sync_tenant, rows):
            if ev["phase"] == "row":
                yield _sync_ndjson_line(ev)
            elif ev["phase"] == "managers":
                yield _sync_ndjson_line(ev)
            elif ev["phase"] == "complete":
                yield _sync_ndjson_line(
                    {
                        "phase": "complete",
                        "stats": asdict(ev["stats"]),
                        "row_count": ev["row_count"],
                        "pct": 100,
                        "label": "Done",
                    }
                )

    response = StreamingHttpResponse(ndjson_iter(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-store"
    return response


@login_required
def api_health_test(request):
    """Staff-only page: GET external /api/health for the effective tenant (or global fallback)."""
    if not request.user.is_staff:
        raise PermissionDenied

    timeout = settings.EXTERNAL_API_HEALTH_TIMEOUT
    tenant = None
    tenant_slug = (request.GET.get("tenant") or "").strip()

    if request.user.is_superuser:
        if tenant_slug:
            tenant = Tenant.objects.filter(slug__iexact=tenant_slug).first()
            if tenant is None:
                messages.warning(
                    request,
                    f'Unknown tenant slug "{tenant_slug}". Using session scope or global fallback.',
                )
        if tenant is None:
            tenant = get_superuser_active_tenant(request)
    else:
        tenant = get_user_tenant(request.user)

    if tenant is not None:
        url = tenant.get_api_health_url()
    else:
        url = settings.EXTERNAL_API_HEALTH_URL

    context = {
        "health_url": url,
        "timeout_seconds": timeout,
        "probe_tenant": tenant,
    }

    if request.user.is_superuser:
        context["tenant_choices"] = Tenant.objects.filter(is_active=True).order_by("name")

    t0 = time.monotonic()
    try:
        headers = merge_outbound_api_headers(
            {"Accept": "application/json"},
            tenant,
        )
        req = urllib.request.Request(
            url,
            method="GET",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body_bytes = resp.read()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            body_text = body_bytes.decode("utf-8", errors="replace")
            context["http_status"] = resp.status
            context["elapsed_ms"] = elapsed_ms
            context["success"] = True
            try:
                parsed = json.loads(body_text)
                context["json_body"] = parsed
                context["json_body_pretty"] = json.dumps(
                    parsed, indent=2, ensure_ascii=False
                )
            except json.JSONDecodeError:
                context["raw_body"] = body_text
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        context["success"] = False
        context["http_status"] = e.code
        context["elapsed_ms"] = elapsed_ms
        context["error"] = e.reason or f"HTTP {e.code}"
        try:
            context["raw_body"] = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    except urllib.error.URLError as e:
        context["success"] = False
        context["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        reason = getattr(e, "reason", e)
        context["error"] = str(reason)
    except TimeoutError:
        context["success"] = False
        context["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        context["error"] = "Request timed out."
    except Exception as e:
        context["success"] = False
        context["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        context["error"] = str(e)

    return render(request, "hierarchy/api_health_test.html", context)


@login_required
def api_guide(request):
    """Staff reference: HTTP JSON APIs implemented by this Django app (machine + browser clients)."""
    if not request.user.is_staff:
        raise PermissionDenied
    site_api_base = request.build_absolute_uri("/").rstrip("/")
    employee_api_token_configured = bool(
        (getattr(settings, "EMPLOYEE_API_TOKEN", None) or "").strip()
    )
    return render(
        request,
        "hierarchy/api_guide.html",
        {
            "site_api_base": site_api_base,
            "employee_api_token_configured": employee_api_token_configured,
        },
    )


def _audit_log_filter_query(request):
    parts = {}
    action = (request.GET.get("action") or "").strip()
    if action:
        parts["action"] = action
    q = (request.GET.get("q") or "").strip()
    if q:
        parts["q"] = q
    return urlencode(parts)


@login_required
def audit_log_list(request):
    """Staff-only: browse persisted audit rows (HTTP + model/auth events)."""
    if not request.user.is_staff:
        raise PermissionDenied

    qs = AuditLog.objects.select_related("user").order_by("-created_at")
    action_filter = (request.GET.get("action") or "").strip()
    if action_filter:
        qs = qs.filter(action=action_filter)
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        qs = qs.filter(details__icontains=search_q)

    paginator = Paginator(qs, 40)
    page_obj = paginator.get_page(request.GET.get("page"))

    action_choices = (
        AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
    )

    filter_query = _audit_log_filter_query(request)

    context = {
        "page_obj": page_obj,
        "action_filter": action_filter,
        "action_choices": action_choices,
        "search_q": search_q,
        "filter_query": filter_query,
    }
    return render(request, "hierarchy/audit_log_list.html", context)
