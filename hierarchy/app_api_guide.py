"""Documentation metadata for JSON APIs implemented by this Django app."""

from __future__ import annotations

import json
from typing import Any


def _format_json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _example_create_user_response() -> str:
    return _format_json(
        {
            "detail": "User created.",
            "user": {
                "id": 42,
                "samAccountName": "jdoe",
                "givenName": "Jane",
                "surname": "Doe",
                "civil_id": "",
                "employee_number": "",
                "tenant": {
                    "slug": "mosa-kuwait",
                    "name": "Ministry of Social Affairs — Kuwait",
                    "apiBaseUrl": "http://63.183.213.237:1113",
                },
            },
        }
    )


def _example_login_response() -> str:
    return _format_json(
        {
            "detail": "Logged in.",
            "user": {
                "id": 42,
                "username": "jdoe",
                "email": "jdoe@example.com",
                "is_staff": True,
                "civil_id": "123456789012",
                "employee_number": "T2-12345",
                "tenant": {
                    "slug": "mosa-kuwait",
                    "name": "Ministry of Social Affairs — Kuwait",
                    "apiBaseUrl": "http://63.183.213.237:1113",
                },
            },
        }
    )


def _example_org_units_flat_response() -> str:
    return _format_json(
        {
            "tenant": {
                "id": 2,
                "slug": "mosa-kuwait",
                "name": "Ministry of Social Affairs — Kuwait",
            },
            "format": "flat",
            "count": 2,
            "units": [
                {
                    "id": 96,
                    "name": "General Administration & Finance",
                    "code": "US-ADM",
                    "unit_type": "general_admin",
                    "unit_type_label": "General administration",
                    "sort_order": 10,
                    "parent_id": None,
                    "parent": None,
                    "path": "General Administration & Finance",
                    "depth": 0,
                },
                {
                    "id": 97,
                    "name": "Finance Department",
                    "code": "US-ADM-FIN",
                    "unit_type": "department",
                    "unit_type_label": "Department",
                    "sort_order": 10,
                    "parent_id": 96,
                    "parent": {
                        "id": 96,
                        "name": "General Administration & Finance",
                        "code": "US-ADM",
                        "unit_type": "general_admin",
                        "unit_type_label": "General administration",
                        "sort_order": 10,
                    },
                    "path": "General Administration & Finance › Finance Department",
                    "depth": 1,
                },
            ],
        }
    )


def _example_org_units_tree_response() -> str:
    return _format_json(
        {
            "tenant": {
                "id": 2,
                "slug": "mosa-kuwait",
                "name": "Ministry of Social Affairs — Kuwait",
            },
            "format": "tree",
            "count": 2,
            "units": [
                {
                    "id": 96,
                    "name": "General Administration & Finance",
                    "code": "US-ADM",
                    "unit_type": "general_admin",
                    "unit_type_label": "General administration",
                    "sort_order": 10,
                    "parent_id": None,
                    "children": [
                        {
                            "id": 97,
                            "name": "Finance Department",
                            "code": "US-ADM-FIN",
                            "unit_type": "department",
                            "unit_type_label": "Department",
                            "sort_order": 10,
                            "parent_id": 96,
                            "children": [],
                        }
                    ],
                }
            ],
        }
    )


def _example_employee_get_response() -> str:
    return _format_json(
        {
            "employee": {
                "id": 15,
                "user_id": 42,
                "username": "jdoe",
                "email": "jdoe@example.com",
                "first_name": "Jane",
                "last_name": "Doe",
                "tenant": {
                    "id": 2,
                    "slug": "mosa-kuwait",
                    "name": "Ministry of Social Affairs — Kuwait",
                },
                "sector": "government",
                "employee_number": "T2-12345",
                "job_title": "Social Specialist",
                "department": "Social Care",
                "section_team": "Family Affairs",
                "hire_date": "2020-01-15",
                "employment_status": "active",
                "work_location": "Kuwait City",
                "employee_type": "full_time",
                "civil_id": "123456789012",
                "date_of_birth": "1990-05-20",
                "gender": "female",
                "nationality": "Kuwait",
                "marital_status": "married",
                "mobile_number": "51234567",
                "home_address": "Hawally, Kuwait",
                "emergency_contact": "Ahmad Ali — 50987654",
                "created_at": "2025-01-01T12:00:00+00:00",
                "organizational_units": [
                    {
                        "id": 97,
                        "name": "Finance Department",
                        "code": "US-ADM-FIN",
                        "unit_type": "department",
                        "unit_type_label": "Department",
                        "sort_order": 10,
                        "parent": {
                            "id": 96,
                            "name": "General Administration & Finance",
                            "code": "US-ADM",
                            "unit_type": "general_admin",
                            "unit_type_label": "General administration",
                            "sort_order": 10,
                        },
                        "position": {
                            "id": 10,
                            "title": "Senior Specialist — Finance Department",
                            "code": "P0097",
                        },
                        "is_primary": True,
                    }
                ],
                "organizational_unit": {
                    "id": 97,
                    "name": "Finance Department",
                    "code": "US-ADM-FIN",
                    "sort_order": 10,
                    "parent": {
                        "id": 96,
                        "name": "General Administration & Finance",
                        "code": "US-ADM",
                        "sort_order": 10,
                    },
                },
                "organizational_unit_parent": {
                    "id": 96,
                    "name": "General Administration & Finance",
                    "code": "US-ADM",
                    "sort_order": 10,
                },
                "delegations": {
                    "given": [
                        {
                            "id": 3,
                            "start_date": "2026-01-01",
                            "end_date": "2026-06-30",
                            "notes": "Annual leave coverage",
                            "status": "Active",
                            "is_current": True,
                            "delegator": {
                                "id": 15,
                                "user_id": 42,
                                "username": "jdoe",
                                "civil_id": "123456789012",
                                "employee_number": "T2-12345",
                                "first_name": "Jane",
                                "last_name": "Doe",
                                "name": "Jane Doe",
                            },
                            "delegatee": {
                                "id": 22,
                                "user_id": 55,
                                "username": "aali",
                                "civil_id": "987654321098",
                                "employee_number": "T2-99999",
                                "first_name": "Ahmad",
                                "last_name": "Ali",
                                "name": "Ahmad Ali",
                            },
                        }
                    ],
                    "received": [],
                },
            },
            "signatures": [
                {
                    "id": 1,
                    "label": "Official",
                    "sort_order": 0,
                    "mime_type": "image/png",
                    "filename": "signature.png",
                    "base64": "<base64-encoded file bytes>",
                }
            ],
        }
    )


def _example_assignments_list_response() -> str:
    return _format_json(
        {
            "tenant": {
                "id": 2,
                "slug": "mosa-kuwait",
                "name": "Ministry of Social Affairs — Kuwait",
            },
            "count": 1,
            "assignments": [
                {
                    "id": 501,
                    "employee_id": 15,
                    "position_id": 10,
                    "user_id": 42,
                    "username": "jdoe",
                    "civil_id": "123456789012",
                    "employee_number": "T2-12345",
                    "is_primary": True,
                    "start_date": "2024-01-01",
                    "end_date": None,
                    "notes": "",
                }
            ],
        }
    )


def _example_reports_to_response() -> str:
    return _format_json(
        {
            "employee": {
                "id": 15,
                "user_id": 42,
                "username": "jdoe",
                "civil_id": "123456789012",
                "employee_number": "T2-12345",
                "first_name": "Jane",
                "last_name": "Doe",
                "name": "Jane Doe",
            },
            "working_org_unit": {
                "id": 97,
                "name": "Accounting Section",
                "code": "ACC",
                "unit_type": "section",
                "unit_type_label": "Section",
                "sort_order": 10,
                "parent": {
                    "id": 96,
                    "name": "Finance Department",
                    "code": "FIN",
                    "unit_type": "department",
                    "unit_type_label": "Department",
                    "sort_order": 10,
                },
            },
            "reports_to": {
                "org_unit": {
                    "id": 97,
                    "name": "Accounting Section",
                    "code": "ACC",
                    "unit_type": "section",
                    "unit_type_label": "Section",
                    "sort_order": 10,
                    "parent": {
                        "id": 96,
                        "name": "Finance Department",
                        "code": "FIN",
                        "unit_type": "department",
                        "unit_type_label": "Department",
                        "sort_order": 10,
                    },
                },
                "chief_position": {
                    "id": 20,
                    "title": "Accounting Section Head",
                    "code": "ACC-H",
                },
                "employee": {
                    "id": 18,
                    "user_id": 50,
                    "username": "boss1",
                    "civil_id": "111122223333",
                    "employee_number": "T2-00001",
                    "first_name": "Sam",
                    "last_name": "Supervisor",
                    "name": "Sam Supervisor",
                },
                "escalated": False,
            },
        }
    )


def _example_error_response() -> str:
    return _format_json({"detail": "Human-readable error message."})


def hierarchy_app_api_endpoints(site_base: str) -> list[dict[str, Any]]:
    """
    Public HTTP JSON endpoints defined in ``hierarchy.urls`` under ``/api/``.

    Includes stable **v1** read paths (ETag + contract headers), bulk PATCH for
    integrations, and legacy ``/api/...`` aliases. Does not document external
    tenant backends or staff-only HTML under ``/organization/``.
    """
    base = site_base.rstrip("/")
    error_json = _example_error_response()

    return [
        {
            "id": "org-units-list",
            "method": "GET",
            "path": "/api/organization/units/",
            "url": f"{base}/api/organization/units/",
            "title": "List organizational units",
            "auth_label": "Tenant API key",
            "summary": (
                "Legacy path (unchanged across releases). "
                "List all organizational units for a tenant. "
                "Query: <code class=\"d365-code\">tenant_id</code> (required); "
                "<code class=\"d365-code\">format=flat</code> (default) returns a sorted "
                "flat list with <code class=\"d365-code\">unit_type</code>, "
                "<code class=\"d365-code\">path</code>, and "
                "<code class=\"d365-code\">depth</code>; "
                "<code class=\"d365-code\">format=tree</code> returns nested "
                "<code class=\"d365-code\">children</code>. "
                "Prefer <code class=\"d365-code\">/api/v1/organization/units/</code> for ETags and contract headers."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — tenant primary key"),
                ("format", "string", "No — flat (default) or tree"),
            ],
            "responses": [
                ("200", "tenant summary + units — see JSON below"),
                ("400", "Bad tenant_id or format"),
                ("401", "Not authenticated"),
                ("403", "Staff tenant scope mismatch"),
                ("404", "Unknown tenant"),
            ],
            "response_examples": [
                ("200 OK (flat)", _example_org_units_flat_response()),
                ("200 OK (tree)", _example_org_units_tree_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS "{base}/api/organization/units/?tenant_id=2&format=flat" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "api-v1-org-units",
            "method": "GET",
            "path": "/api/v1/organization/units/",
            "url": f"{base}/api/v1/organization/units/",
            "title": "List organizational units (v1, stable read)",
            "auth_label": "Tenant API key",
            "summary": (
                "Same query parameters and JSON body as the legacy list endpoint, "
                "with a <strong>versioned read contract</strong>: responses include "
                "<code class=\"d365-code\">ETag</code> (weak), "
                "<code class=\"d365-code\">X-API-Version: 1</code>, and "
                "<code class=\"d365-code\">X-API-Read-Contract: org-units-v1</code>. "
                "Send <code class=\"d365-code\">If-None-Match</code> with the prior "
                "ETag to receive <strong>304 Not Modified</strong> when unchanged. "
                "Bulk unit PATCH requires an ETag from "
                "<code class=\"d365-code\">format=flat</code> on this URL."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — tenant primary key"),
                ("format", "string", "No — flat (default) or tree"),
                ("If-None-Match", "header", "No — optional conditional GET"),
            ],
            "responses": [
                ("200", "Payload + version headers"),
                ("304", "Not modified (body empty)"),
                ("400", "Bad tenant_id or format"),
                ("401", "Not authenticated"),
                ("403", "Staff tenant scope mismatch"),
                ("404", "Unknown tenant"),
            ],
            "response_examples": [
                ("200 OK (flat)", _example_org_units_flat_response()),
                ("200 OK (tree)", _example_org_units_tree_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS -D- "{base}/api/v1/organization/units/?tenant_id=2&format=flat" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "api-v1-org-units-bulk",
            "method": "PATCH",
            "path": "/api/v1/organization/units/bulk/",
            "url": f"{base}/api/v1/organization/units/bulk/",
            "title": "Bulk patch organizational units (v1)",
            "auth_label": "Tenant API key",
            "summary": (
                "Apply partial updates to many units in <strong>one transaction</strong>. "
                "Requires <code class=\"d365-code\">If-Match</code> equal to the "
                "<code class=\"d365-code\">ETag</code> from "
                "<code class=\"d365-code\">GET /api/v1/organization/units/?tenant_id=…&format=flat</code>. "
                "On mismatch returns <strong>412 Precondition Failed</strong> (another writer won). "
                "Missing <code class=\"d365-code\">If-Match</code> returns <strong>428</strong>."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — query string"),
                ("If-Match", "header", "Yes — ETag from flat units GET"),
                ("updates", "array", "Yes — objects with id + optional name, code, unit_type, sort_order, parent_id"),
            ],
            "responses": [
                ("200", "Applied — response includes new ETag for the flat snapshot"),
                ("400", "Invalid JSON or validation errors"),
                ("401", "Not authenticated"),
                ("403", "Staff tenant scope mismatch"),
                ("404", "Unknown tenant"),
                ("412", "If-Match stale"),
                ("428", "If-Match missing"),
            ],
            "response_examples": [
                ("200 OK", _format_json({"detail": "Bulk unit update applied.", "tenant_id": 2, "updated_count": 3})),
                ("412 / 428 / 4xx Error", error_json),
            ],
            "curl": f'''curl -sS -X PATCH "{base}/api/v1/organization/units/bulk/?tenant_id=2" \\
  -H "Content-Type: application/json" \\
  -H "X-Api-Key: <tenant-token>" \\
  -H 'If-Match: W/"<etag-from-get>"' \\
  -d '{{"updates":[{{"id":97,"sort_order":5}}]}}' ''',
            "auth_required": True,
        },
        {
            "id": "employee-get",
            "method": "GET",
            "path": "/api/employees/",
            "url": f"{base}/api/employees/",
            "title": "Get employee",
            "auth_label": "Tenant API key",
            "summary": (
                "Return one employee profile, current organizational units "
                "(with <code class=\"d365-code\">unit_type</code> / "
                "<code class=\"d365-code\">unit_type_label</code> and parent), delegations "
                "(<code class=\"d365-code\">given</code> / "
                "<code class=\"d365-code\">received</code> — each party includes "
                "<code class=\"d365-code\">civil_id</code> and "
                "<code class=\"d365-code\">employee_number</code>), and signature images (Base64). "
                "Query string only."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — tenant primary key"),
                ("user_id", "integer", "One of — Django user pk"),
                ("username", "string", "One of — case-insensitive"),
                ("civil_id", "string", "One of — exactly one identifier required"),
            ],
            "responses": [
                ("200", "Full employee object + signatures — see JSON below"),
                ("400", "Bad query / tenant_id / multiple identifiers"),
                ("401", "Not authenticated"),
                ("403", "Wrong tenant scope or access denied"),
                ("404", "Unknown tenant or employee not found"),
                ("409", "Multiple employees match civil_id"),
            ],
            "response_examples": [
                ("200 OK", _example_employee_get_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS "{base}/api/employees/?tenant_id=2&username=jdoe" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
            "note": (
                "Unversioned response (no ETag). For conditional GET use "
                "<code class=\"d365-code\">/api/v1/employees/</code>."
            ),
        },
        {
            "id": "api-v1-employee-get",
            "method": "GET",
            "path": "/api/v1/employees/",
            "url": f"{base}/api/v1/employees/",
            "title": "Get employee (v1, stable read)",
            "auth_label": "Tenant API key",
            "summary": (
                "Same semantics as legacy <code class=\"d365-code\">/api/employees/</code> with "
                "<code class=\"d365-code\">ETag</code>, "
                "<code class=\"d365-code\">X-API-Version: 1</code>, and "
                "<code class=\"d365-code\">X-API-Read-Contract: employee-profile-v1</code>. "
                "Supports <code class=\"d365-code\">If-None-Match</code> → 304."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes"),
                ("user_id / username / civil_id", "query", "Exactly one required"),
                ("If-None-Match", "header", "No — optional conditional GET"),
            ],
            "responses": [
                ("200", "Employee + signatures"),
                ("304", "Not modified"),
                ("400", "Bad query"),
                ("401", "Not authenticated"),
                ("403", "Access denied"),
                ("404", "Not found"),
                ("409", "Multiple civil_id matches"),
            ],
            "response_examples": [
                ("200 OK", _example_employee_get_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS -D- "{base}/api/v1/employees/?tenant_id=2&username=jdoe" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "employee-reports-to",
            "method": "GET",
            "path": "/api/employees/reports-to/",
            "url": f"{base}/api/employees/reports-to/",
            "title": "Employee reports-to (manager chain)",
            "auth_label": "Tenant API key",
            "summary": (
                "Resolve who the subject <strong>reports to</strong>. Uses their "
                "<strong>primary-first</strong> current assignment’s organizational unit. "
                "The unit’s <strong>chief slot</strong> is the first active position "
                "(lowest <code class=\"d365-code\">sort_order</code>) under that unit; "
                "its primary holder is the section/department boss. "
                "If the subject <em>is</em> that holder, the response escalates to the "
                "<strong>parent unit</strong> and its chief holder instead "
                "(<code class=\"d365-code\">escalated: true</code>). "
                "Place managerial positions first under each unit via sort order."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes"),
                ("user_id / username / civil_id", "query", "Exactly one required"),
            ],
            "responses": [
                ("200", "employee + working_org_unit + reports_to"),
                ("400", "Bad query"),
                ("401", "Not authenticated"),
                ("403", "Access denied"),
                ("404", "Unknown tenant or employee not found"),
                ("409", "Multiple civil_id matches"),
            ],
            "response_examples": [
                ("200 OK", _example_reports_to_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS "{base}/api/employees/reports-to/?tenant_id=2&username=jdoe" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "api-v1-employee-reports-to",
            "method": "GET",
            "path": "/api/v1/employees/reports-to/",
            "url": f"{base}/api/v1/employees/reports-to/",
            "title": "Employee reports-to (v1)",
            "auth_label": "Tenant API key",
            "summary": (
                "Same body as <code class=\"d365-code\">/api/employees/reports-to/</code> "
                "with <code class=\"d365-code\">ETag</code>, "
                "<code class=\"d365-code\">X-API-Read-Contract: employee-reports-to-v1</code>, "
                "and optional <code class=\"d365-code\">If-None-Match</code>."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes"),
                ("user_id / username / civil_id", "query", "Exactly one required"),
                ("If-None-Match", "header", "No"),
            ],
            "responses": [
                ("200", "reports-to payload"),
                ("304", "Not modified"),
                ("400", "Bad query"),
                ("401", "Not authenticated"),
                ("403", "Access denied"),
                ("404", "Not found"),
                ("409", "Multiple civil_id matches"),
            ],
            "response_examples": [
                ("200 OK", _example_reports_to_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS -D- "{base}/api/v1/employees/reports-to/?tenant_id=2&username=jdoe" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "api-v1-assignments-list",
            "method": "GET",
            "path": "/api/v1/organization/assignments/",
            "url": f"{base}/api/v1/organization/assignments/",
            "title": "List position assignments (v1 snapshot)",
            "auth_label": "Tenant API key",
            "summary": (
                "Ordered snapshot of all <code class=\"d365-code\">PositionAssignment</code> rows "
                "for the tenant (integration-friendly). Each assignment includes "
                "<code class=\"d365-code\">employee_id</code>, "
                "<code class=\"d365-code\">user_id</code>, "
                "<code class=\"d365-code\">username</code>, "
                "<code class=\"d365-code\">civil_id</code>, "
                "<code class=\"d365-code\">employee_number</code>, "
                "<code class=\"d365-code\">position_id</code>, dates, and "
                "<code class=\"d365-code\">is_primary</code>. Weak "
                "<code class=\"d365-code\">ETag</code>; contract "
                "<code class=\"d365-code\">assignments-v1</code>. "
                "Bulk assignment PATCH requires this ETag in "
                "<code class=\"d365-code\">If-Match</code>."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — query string"),
                ("If-None-Match", "header", "No — optional conditional GET"),
            ],
            "responses": [
                ("200", "tenant + assignments[]"),
                ("304", "Not modified"),
                ("400", "Bad tenant_id"),
                ("401", "Not authenticated"),
                ("403", "Staff scope mismatch"),
                ("404", "Unknown tenant"),
            ],
            "response_examples": [
                ("200 OK", _example_assignments_list_response()),
                ("4xx Error", error_json),
            ],
            "curl": f'''curl -sS -D- "{base}/api/v1/organization/assignments/?tenant_id=2" \\
  -H "X-Api-Key: <tenant-token>"''',
            "auth_required": True,
        },
        {
            "id": "api-v1-assignments-bulk",
            "method": "PATCH",
            "path": "/api/v1/organization/assignments/bulk/",
            "url": f"{base}/api/v1/organization/assignments/bulk/",
            "title": "Bulk patch position assignments (v1)",
            "auth_label": "Tenant API key",
            "summary": (
                "Create, update, and delete assignments in <strong>one transaction</strong>. "
                "<code class=\"d365-code\">If-Match</code> must match the ETag from "
                "<code class=\"d365-code\">GET /api/v1/organization/assignments/?tenant_id=…</code>. "
                "Body: optional arrays <code class=\"d365-code\">updates</code>, "
                "<code class=\"d365-code\">creates</code>, "
                "<code class=\"d365-code\">delete_ids</code>."
            ),
            "request_fields": [
                ("tenant_id", "integer", "Yes — query"),
                ("If-Match", "header", "Yes — assignments snapshot ETag"),
                ("updates", "array", "No — {id, is_primary?, start_date?, end_date?, notes?}"),
                ("creates", "array", "No — {employee_id, position_id, …}"),
                ("delete_ids", "array", "No — assignment primary keys"),
            ],
            "responses": [
                ("200", "Summary counts + new ETag"),
                ("400", "Invalid JSON or validation"),
                ("401", "Not authenticated"),
                ("403", "Staff scope mismatch"),
                ("404", "Unknown tenant"),
                ("412", "If-Match stale"),
                ("428", "If-Match missing"),
            ],
            "response_examples": [
                (
                    "200 OK",
                    _format_json(
                        {
                            "detail": "Bulk assignment changes applied.",
                            "tenant_id": 2,
                            "updated": 1,
                            "created": 0,
                            "deleted": 0,
                        }
                    ),
                ),
                ("412 / 428 / 4xx Error", error_json),
            ],
            "curl": f'''curl -sS -X PATCH "{base}/api/v1/organization/assignments/bulk/?tenant_id=2" \\
  -H "Content-Type: application/json" \\
  -H "X-Api-Key: <tenant-token>" \\
  -H 'If-Match: W/"<etag-from-assignments-get>"' \\
  -d '{{"delete_ids":[],"updates":[],"creates":[]}}' ''',
            "auth_required": True,
        },
        {
            "id": "create-user",
            "method": "POST",
            "path": "/api/auth/users/",
            "url": f"{base}/api/auth/users/",
            "title": "Create user",
            "auth_label": "Tenant API key",
            "summary": (
                "Create a Django user and an employee profile on an active tenant. "
                "Requires authentication for the target tenant (API key or staff session). "
                "JSON body; CSRF exempt. Response <code class=\"d365-code\">user</code> includes "
                "<code class=\"d365-code\">civil_id</code> and "
                "<code class=\"d365-code\">employee_number</code> (usually empty until updated in UI or admin)."
            ),
            "request_fields": [
                ("samAccountName", "string", "Yes — Django username"),
                ("password", "string", "Yes"),
                ("givenName", "string", "Yes — first name"),
                ("surname", "string", "Yes — last name"),
                ("tenant", "string", "Yes — tenant slug (e.g. mosa-kuwait)"),
            ],
            "responses": [
                ("201", "Created — user includes samAccountName, civil_id, employee_number, tenant"),
                ("400", "Invalid JSON, missing fields, unknown tenant, password rules"),
                ("409", "Username already exists"),
            ],
            "response_examples": [
                ("201 Created", _example_create_user_response()),
                ("400 / 409 Error", error_json),
            ],
            "curl": f'''curl -sS -X POST "{base}/api/auth/users/" \\
  -H "Content-Type: application/json" \\
  -H "X-Api-Key: <tenant-token>" \\
  -d '{{"samAccountName":"jdoe","password":"SecurePass1!","givenName":"Jane","surname":"Doe","tenant":"mosa-kuwait"}}' ''',
            "note": (
                "Not the same as Sync users: that tool calls "
                "<code class=\"d365-code\">GET /api/auth/users</code> on each tenant’s "
                "<strong>external</strong> API base URL."
            ),
            "auth_required": True,
        },
        {
            "id": "login",
            "method": "POST",
            "path": "/api/auth/login/",
            "url": f"{base}/api/auth/login/",
            "title": "Login",
            "auth_label": "None",
            "summary": (
                "Authenticate with JSON; on success sets a session cookie "
                "(<code class=\"d365-code\">sessionid</code>) usable on other "
                "tenant-scoped endpoints when logged in as staff. CSRF exempt. "
                "Response <code class=\"d365-code\">user</code> includes "
                "<code class=\"d365-code\">civil_id</code> and "
                "<code class=\"d365-code\">employee_number</code> when an employee row exists."
            ),
            "request_fields": [
                ("username", "string", "Yes"),
                ("password", "string", "Yes"),
            ],
            "responses": [
                ("200", "Logged in — user includes id, username, email, is_staff, civil_id, employee_number, tenant"),
                ("401", "Invalid credentials"),
                ("403", "Account disabled"),
            ],
            "response_examples": [
                ("200 OK", _example_login_response()),
                ("401 / 403 Error", error_json),
            ],
            "curl": f'''curl -sS -c cookies.txt -X POST "{base}/api/auth/login/" \\
  -H "Content-Type: application/json" \\
  -d '{{"username":"jdoe","password":"SecurePass1!"}}' ''',
            "auth_required": False,
        },
    ]


def api_guide_context(
    site_base: str,
    *,
    employee_api_token_configured: bool,
) -> dict[str, Any]:
    """Template context for the staff API guide page."""
    endpoints = hierarchy_app_api_endpoints(site_base)
    return {
        "site_api_base": site_base.rstrip("/"),
        "employee_api_token_configured": employee_api_token_configured,
        "app_api_endpoints": endpoints,
        "app_api_endpoint_index": [
            {
                "id": ep["id"],
                "method": ep["method"],
                "path": ep["path"],
                "title": ep["title"],
                "auth_label": ep.get("auth_label", ""),
            }
            for ep in endpoints
        ],
    }
