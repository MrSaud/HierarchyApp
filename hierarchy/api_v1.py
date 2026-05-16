"""Version 1 read API: stable GET payloads with ETag and contract headers."""

from __future__ import annotations

from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .api_http import (
    attach_v1_read_headers,
    not_modified_response,
    should_return_not_modified,
    v1_cors_allow_headers,
    weak_etag_for_payload,
)
from .employee_api import employee_get_payload_dict
from .organization_api import (
    assignments_build_response_data,
    org_units_get_payload_dict,
    _resolve_tenant,
)
from .reports_to_api import reports_to_payload_dict


def _guide_url(request) -> str:
    return request.build_absolute_uri(reverse("hierarchy:api_guide"))


def _v1_read_options() -> JsonResponse:
    r = JsonResponse({}, status=204)
    r["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r


@require_http_methods(["GET", "OPTIONS"])
def api_v1_org_units_list(request):
    if request.method == "OPTIONS":
        return _v1_read_options()

    data, err = org_units_get_payload_dict(request)
    if err is not None:
        return err
    etag = weak_etag_for_payload(data)
    if should_return_not_modified(request, etag):
        r = not_modified_response(etag)
        attach_v1_read_headers(
            r,
            etag=etag,
            read_contract="org-units-v1",
            guide_url=_guide_url(request),
        )
        r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
        return r
    r = JsonResponse(data, status=200)
    attach_v1_read_headers(
        r,
        etag=etag,
        read_contract="org-units-v1",
        guide_url=_guide_url(request),
    )
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r


@require_http_methods(["GET", "OPTIONS"])
def api_v1_employee_get(request):
    if request.method == "OPTIONS":
        return _v1_read_options()

    data, err = employee_get_payload_dict(request)
    if err is not None:
        return err
    etag = weak_etag_for_payload(data)
    if should_return_not_modified(request, etag):
        r = not_modified_response(etag)
        attach_v1_read_headers(
            r,
            etag=etag,
            read_contract="employee-profile-v1",
            guide_url=_guide_url(request),
        )
        r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
        return r
    r = JsonResponse(data, status=200)
    attach_v1_read_headers(
        r,
        etag=etag,
        read_contract="employee-profile-v1",
        guide_url=_guide_url(request),
    )
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r


@require_http_methods(["GET", "OPTIONS"])
def api_v1_assignments_list(request):
    if request.method == "OPTIONS":
        return _v1_read_options()

    tenant, err = _resolve_tenant(request)
    if err is not None:
        return err
    data = assignments_build_response_data(tenant)
    etag = weak_etag_for_payload(data)
    if should_return_not_modified(request, etag):
        r = not_modified_response(etag)
        attach_v1_read_headers(
            r,
            etag=etag,
            read_contract="assignments-v1",
            guide_url=_guide_url(request),
        )
        r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
        return r
    r = JsonResponse(data, status=200)
    attach_v1_read_headers(
        r,
        etag=etag,
        read_contract="assignments-v1",
        guide_url=_guide_url(request),
    )
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r


@require_http_methods(["GET", "OPTIONS"])
def api_v1_employee_reports_to_get(request):
    if request.method == "OPTIONS":
        return _v1_read_options()

    data, err = reports_to_payload_dict(request)
    if err is not None:
        return err
    etag = weak_etag_for_payload(data)
    if should_return_not_modified(request, etag):
        r = not_modified_response(etag)
        attach_v1_read_headers(
            r,
            etag=etag,
            read_contract="employee-reports-to-v1",
            guide_url=_guide_url(request),
        )
        r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
        return r
    r = JsonResponse(data, status=200)
    attach_v1_read_headers(
        r,
        etag=etag,
        read_contract="employee-reports-to-v1",
        guide_url=_guide_url(request),
    )
    r["Access-Control-Allow-Headers"] = v1_cors_allow_headers()
    return r
