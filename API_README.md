# Hierarchy API

Replace `<HOST>` with your server origin (e.g. `http://127.0.0.1:8000`).

All JSON responses use UTF-8. Error bodies usually look like: `{ "detail": "<message>" }`.

---

## Two API types per tenant

| | **External API (AD)** | **Internal API (Hierarchy)** |
|---|------------------------|--------------------------------|
| **Direction** | Hierarchy → AD / directory server | Other systems → this app |
| **Purpose** | Health checks, user sync from Active Directory | Export employees, org structure; provision users |
| **Configure** | **External API base URL**, **ApiKey**, **ApiKeyHeader** (or env) | This app's public base URL; staff session / global Bearer (see API guide) |
| **Docs in this file** | Not listed (remote host) | Endpoints below |
| **Staff UI** | API health, Sync users | API guide, Internal API (tenant edit / API access) |

This document describes the **internal API** only. The external API lives on each tenant’s AD server (`{external_base}/api/health`, `{external_base}/api/auth/users`).

---

## Authentication summary (internal API)

| Mechanism | Header / mechanism | Used by |
|-----------|-------------------|---------|
| **Bearer token** | `Authorization: Bearer <EMPLOYEE_API_TOKEN>` | `GET /api/employees/` (global secret, optional) |
| **Tenant API key** | Header from tenant config (default **`X-Api-Key`**) + secret | `GET /api/employees/` — see below |
| **Session cookie** | `sessionid` after login (staff/superuser) | `GET /api/employees/`, `GET /api/employees/signatures/` |
| **None** | — | `POST /api/auth/users/` (open registration-style endpoint; secure at network layer in production) |

### Global Bearer (`EMPLOYEE_API_TOKEN`)

```bash
export EMPLOYEE_API_TOKEN='<generate-a-long-random-secret>'
```

Generate locally (examples):

```bash
openssl rand -hex 32
# or
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

If `EMPLOYEE_API_TOKEN` is empty, Bearer authentication for `/api/employees/` is disabled unless you use a **tenant API key** or **staff session**.

### Tenant API credentials (`Tenant` model)

| Field | External API (AD) — outbound | Internal API — inbound |
|-------|------------------------------|-------------------------|
| **`api_key`** | Always used for calls to `{api_base_url}/api/...` | Used unless env override below |
| **`api_key_header`** | Always used (default **`X-Api-Key`**) | Same unless env override below |

Set both on the tenant in **Administration → Tenants** (External API section) or **External API (AD)** page. Outbound login, sync, and health **only** read these DB fields.

**Optional env overrides (inbound only)** — clients calling **this** Hierarchy app:

| Environment variable | Meaning |
|------------------------|--------|
| `TENANT_API_KEY_<tenant_pk>` | Overrides `Tenant.api_key` for machine auth to Hierarchy (e.g. `TENANT_API_KEY_1`). |
| `TENANT_API_KEY_HEADER_<tenant_pk>` | Optional header name override for inbound calls. |

Example inbound:

```bash
curl -sS "<HOST>/api/employees/?tenant_id=1&username=jdoe" \
  -H "X-Api-Key: your-tenant-secret"
```

Configure **`tenant_id`** to match the same tenant whose key you send.

---

## `POST /api/auth/users/`

Creates a Django user and an **Employee** profile on an active tenant.

| | |
|---|---|
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **CSRF** | Exempt (no CSRF token required) |

### Request body (JSON)

| Field | Type | Required |
|-------|------|----------|
| `samAccountName` | string | Yes — becomes Django `username` |
| `password` | string | Yes |
| `givenName` | string | Yes — `first_name` |
| `surname` | string | Yes — `last_name` |
| `tenant` | string | Yes — tenant **slug** (e.g. `default`) |

### Responses

| HTTP | When |
|------|------|
| **201** | User created. Body includes `detail`, `user` (`id`, `samAccountName`, `givenName`, `surname`, `tenant`: `slug`, `name`, `apiBaseUrl`). |
| **400** | Missing/invalid fields, unknown tenant, password validation failure |
| **409** | Username already exists |

### Example

```bash
curl -sS -X POST "<HOST>/api/auth/users/" \
  -H "Content-Type: application/json" \
  -d '{"samAccountName":"jdoe","password":"SecurePass1!","givenName":"Jane","surname":"Doe","tenant":"default"}'
```

---

## `POST /api/auth/login/`

Authenticates with `tenant_id`, `username`, and `password`, then establishes a **session** (`Set-Cookie: sessionid`).

| | |
|---|---|
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **CSRF** | Exempt |

When **AD login** is enabled on the tenant’s **External API (AD)** page and the base URL + **ApiKey** are set, **login** verifies credentials with **`GET {external_base}/api/auth/users`** (JSON body `username` / `password` + ApiKey header), then opens a local session for the synced employee. With AD login **off**, login uses local Django passwords only. **Sync users** and **API health** always use the configured external API (query params + ApiKey for sync; no credentials in the sync body).

### Request body (JSON)

| Field | Type | Required |
|-------|------|----------|
| `tenant_id` | integer | Yes |
| `username` | string | Yes |
| `password` | string | Yes |

### Responses

| HTTP | When |
|------|------|
| **200** | Logged in. Body: `detail`, `auth` (trace), `employee`, `signatures` |
| **400** | Missing/invalid `tenant_id` or credentials |
| **401** | Credentials rejected — check `auth.external_api` / `auth.internal` for which step failed |
| **403** | Disabled account or missing employee — see `auth.internal` |
| **503** | External AD unreachable — `auth.external_api.success` is `false` |

### `auth` object (success and error responses)

| Field | Meaning |
|-------|---------|
| `tenant_id` | Tenant from the request |
| `external_api_configured` | Tenant has a resolvable external API base URL |
| `external_login_enabled` | `true` when AD login is turned on for this tenant |
| `external_api.attempted` | `true` when AD login ran `GET /api/auth/users` with credentials |
| `external_api.success` | `true` / `false` / `null` (AD credential check result) |
| `external_api.users_url` | AD users endpoint when configured |
| `external_api.error` | Message when external step failed |
| `internal.attempted` | Hierarchy ran a local step (user lookup, password, session) |
| `internal.success` | `true` only when login completed |
| `internal.method` | `external_session` (AD path) or `local_password` |
| `internal.step` | Last step: `local_password`, `local_user`, `employee_profile`, `account_disabled`, `session` |
| `internal.error` | Message when an internal step failed |

### Example

```bash
curl -sS -c cookies.txt -X POST "<HOST>/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"username":"jdoe","password":"your-password"}'
```

Use `-b cookies.txt` on later requests to send the session cookie.

---

## `GET /api/employees/`

Returns one employee record (linked **User** + **Employee** fields) and all **signature** images as Base64.

| | |
|---|---|
| **Method** | `GET` |
| **Auth** | Any one of: **`Authorization: Bearer <EMPLOYEE_API_TOKEN>`**, or tenant **`api_key`** in header **`api_key_header`** (default `X-Api-Key`), or signed-in **staff** / **superuser** session |

Machine clients typically use **`tenant_id`** plus either global Bearer or the tenant’s **`X-Api-Key`** (or custom header from **`Tenant.api_key_header`** / env).

### Required query parameters

| Parameter | Description |
|-----------|-------------|
| **`tenant_id`** | Integer primary key of the `Tenant`. Lookup is restricted to employees where `employee.tenant_id = tenant_id`. |
| **Exactly one** of **`user_id`**, **`username`**, **`civil_id`** | |

| Identity parameter | Meaning |
|--------------------|--------|
| `user_id` | Django **User** primary key (`User.pk`). |
| `username` | Login name; match is **case-insensitive**. |
| `civil_id` | Exact string match on `Employee.civil_id` within that tenant. |

Staff who are **not** superusers must use a `tenant_id` equal to their own employee’s tenant (otherwise **403**).

### Responses

| HTTP | When |
|------|------|
| **200** | Success — body shape below |
| **400** | Missing `tenant_id`, invalid integer, or not exactly one identity parameter |
| **401** | Not authenticated |
| **403** | Wrong tenant for staff, or no permission to access that employee |
| **404** | No matching employee in that tenant |
| **409** | More than one employee in that tenant shares the same `civil_id` |

### Success body (`200`)

```json
{
  "employee": {
    "id": 1,
    "user_id": 2,
    "username": "jdoe",
    "email": "",
    "first_name": "Jane",
    "last_name": "Doe",
    "tenant": { "id": 1, "slug": "default", "name": "Default tenant" },
    "sector": "government",
    "employee_number": "",
    "job_title": "",
    "department": "",
    "section_team": "",
    "hire_date": "2020-01-15",
    "employment_status": "active",
    "work_location": "",
    "employee_type": "full_time",
    "civil_id": "",
    "date_of_birth": null,
    "gender": "",
    "nationality": "",
    "marital_status": "",
    "mobile_number": "",
    "home_address": "",
    "emergency_contact": "",
    "created_at": "2025-01-01T12:00:00+00:00",
    "organizational_units": [
      {
        "id": 10,
        "name": "إدارة الشؤون المالية",
        "code": "FIN",
        "sort_order": 0,
        "parent": {
          "id": 5,
          "name": "الإدارة العامة للشؤون الإدارية والمالية",
          "code": "GAF",
          "sort_order": 0
        },
        "position": { "id": 3, "title": "أخصائي", "code": "P0003" },
        "is_primary": true
      }
    ],
    "organizational_unit": {
      "id": 10,
      "name": "إدارة الشؤون المالية",
      "code": "FIN",
      "sort_order": 0,
      "parent": {
        "id": 5,
        "name": "الإدارة العامة للشؤون الإدارية والمالية",
        "code": "GAF",
        "sort_order": 0
      }
    },
    "organizational_unit_parent": {
      "id": 5,
      "name": "الإدارة العامة للشؤون الإدارية والمالية",
      "code": "GAF",
      "sort_order": 0
    }
  },
  "signatures": [
    {
      "id": 1,
      "label": "",
      "sort_order": 0,
      "mime_type": "image/png",
      "filename": "file.png",
      "base64": "<base64-encoded file bytes>"
    }
  ]
}
```

- Dates use ISO `YYYY-MM-DD` where applicable; `created_at` is ISO datetime.
- `organizational_units` lists each **current** position assignment’s unit (via `Position` → `OrganizationalUnit`), each with nested `parent` when set.
- `organizational_unit` / `organizational_unit_parent` are the primary current assignment’s unit and its parent (convenience); both are `null` when the employee has no current assignment under a unit.
- `signatures` may be an empty array.

### Examples

Bearer token:

```bash
export EMPLOYEE_API_TOKEN='your-secret'
curl -sS "<HOST>/api/employees/?tenant_id=1&user_id=2" \
  -H "Authorization: Bearer $EMPLOYEE_API_TOKEN"
```

Tenant API key (header default `X-Api-Key` unless configured on the tenant):

```bash
curl -sS "<HOST>/api/employees/?tenant_id=1&user_id=2" \
  -H "X-Api-Key: your-tenant-secret"
```

By username:

```bash
curl -sS "<HOST>/api/employees/?tenant_id=1&username=jdoe" \
  -H "Authorization: Bearer $EMPLOYEE_API_TOKEN"
```

By civil ID:

```bash
curl -sS "<HOST>/api/employees/?tenant_id=1&civil_id=123456789" \
  -H "Authorization: Bearer $EMPLOYEE_API_TOKEN"
```

With session cookie (after `POST /api/auth/login/`):

```bash
curl -sS -b cookies.txt "<HOST>/api/employees/?tenant_id=1&username=jdoe"
```

---

## `GET /api/employees/signatures/`

Returns **only** signature images for one employee (lighter than full profile GET).

| | |
|---|---|
| **Method** | `GET` |
| **Auth** | Same as `GET /api/employees/` (Bearer, tenant API key, or staff session) |

### Query parameters

Same as `GET /api/employees/`: **`tenant_id`** (required) and exactly one of **`user_id`**, **`username`**, **`civil_id`**.

### Success body (`200`)

```json
{
  "employee": {
    "id": 15,
    "user_id": 42,
    "username": "jdoe",
    "civil_id": "123456789012",
    "employee_number": "T2-12345",
    "first_name": "Jane",
    "last_name": "Doe",
    "name": "Jane Doe"
  },
  "signatures": [
    {
      "id": 1,
      "label": "Official",
      "sort_order": 0,
      "mime_type": "image/png",
      "filename": "signature.png",
      "base64": "<base64-encoded file bytes>"
    }
  ]
}
```

Each item in `signatures` matches the `signatures` array on `GET /api/employees/`. Use **`GET /api/v1/employees/signatures/`** for the same payload with **ETag** / **304** support (`X-API-Read-Contract: employee-signatures-v1`).

### Example

```bash
curl -sS "<HOST>/api/employees/signatures/?tenant_id=1&username=jdoe" \
  -H "X-Api-Key: your-tenant-secret"
```

---

## `OPTIONS` preflight

`POST /api/auth/users/`, `POST /api/auth/login/`, `GET /api/employees/`, and `GET /api/employees/signatures/` respond to **`OPTIONS`** with **204** and minimal CORS-related headers where implemented.

---

## Production notes

- Serve **HTTPS** and restrict **who can reach** `POST /api/auth/users/` if you keep it public.
- Store **`EMPLOYEE_API_TOKEN`** only in secrets / env, never in source control.
- Rotate the Bearer token if it leaks.
