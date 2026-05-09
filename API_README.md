# Hierarchy API

HTTP APIs exposed under the app URL prefix (typically site root). Replace `<HOST>` with your server origin (e.g. `http://127.0.0.1:8000`).

All JSON responses use UTF-8. Error bodies usually look like: `{ "detail": "<message>" }`.

---

## Authentication summary

| Mechanism | Header / mechanism | Used by |
|-----------|-------------------|---------|
| **Bearer token** | `Authorization: Bearer <EMPLOYEE_API_TOKEN>` | `GET /api/employees/` (global secret, optional) |
| **Tenant API key** | Header from tenant config (default **`X-Api-Key`**) + secret | `GET /api/employees/` — see below |
| **Session cookie** | `sessionid` after login (staff/superuser) | `GET /api/employees/` |
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

### Per-tenant API key (`Tenant` model)

Each tenant can define:

| Field | Purpose |
|-------|---------|
| **`api_key`** | Shared secret for machine clients calling `GET /api/employees/?tenant_id=<this tenant's pk>&…`. |
| **`api_key_header`** | HTTP header name for that secret; leave blank to use **`X-Api-Key`**. |

**Production:** prefer injecting the secret via environment (does not require storing it in the DB):

| Environment variable | Meaning |
|------------------------|--------|
| `TENANT_API_KEY_<tenant_pk>` | Overrides `Tenant.api_key` for that primary key (e.g. `TENANT_API_KEY_1`). |
| `TENANT_API_KEY_HEADER_<tenant_pk>` | Optional override for header name (e.g. `TENANT_API_KEY_HEADER_1`). |

Example:

```bash
export TENANT_API_KEY_1='your-tenant-secret'
# optional custom header name:
export TENANT_API_KEY_HEADER_1='X-Tenant-Api-Key'
```

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

Authenticates with username/password and establishes a **session** (`Set-Cookie: sessionid`).

| | |
|---|---|
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **CSRF** | Exempt |

### Request body (JSON)

| Field | Type | Required |
|-------|------|----------|
| `username` | string | Yes |
| `password` | string | Yes |

### Responses

| HTTP | When |
|------|------|
| **200** | Logged in. Body: `detail`, `user` (`id`, `username`, `email`, `is_staff`, `tenant` or `null`) |
| **401** | Invalid credentials |
| **403** | Account disabled |

### Example

```bash
curl -sS -c cookies.txt -X POST "<HOST>/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
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
    "created_at": "2025-01-01T12:00:00+00:00"
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

## `OPTIONS` preflight

`POST /api/auth/users/`, `POST /api/auth/login/`, and `GET /api/employees/` respond to **`OPTIONS`** with **204** and minimal CORS-related headers where implemented.

---

## Production notes

- Serve **HTTPS** and restrict **who can reach** `POST /api/auth/users/` if you keep it public.
- Store **`EMPLOYEE_API_TOKEN`** only in secrets / env, never in source control.
- Rotate the Bearer token if it leaks.
