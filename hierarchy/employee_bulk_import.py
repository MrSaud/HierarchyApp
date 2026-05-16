"""CSV bulk import for employees (staff UI)."""

from __future__ import annotations

import csv
import io
import secrets
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from .models import Employee, EmploymentStatus, EmployeeType, Sector, Tenant

User = get_user_model()

MAX_ROWS = 500

# CSV headers (normalized to lowercase snake_case). Aliases map alternative names → canonical.
HEADER_ALIASES: dict[str, str] = {
    "user_name": "username",
    "userid": "username",
    "email_address": "email",
    "firstname": "first_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "emp_no": "employee_number",
    "employee_id": "employee_number",
    "employee_no": "employee_number",
    "national_id": "civil_id",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "phone": "mobile_number",
    "mobile": "mobile_number",
    "address": "home_address",
    "mgr_username": "manager_username",
    "manager": "manager_username",
    "mgr_employee_number": "manager_employee_number",
}

CANONICAL_FIELDS = frozenset(
    {
        "username",
        "email",
        "first_name",
        "last_name",
        "password",
        "employee_number",
        "sector",
        "civil_id",
        "date_of_birth",
        "gender",
        "nationality",
        "marital_status",
        "mobile_number",
        "home_address",
        "emergency_contact",
        "job_title",
        "department",
        "section_team",
        "hire_date",
        "employment_status",
        "work_location",
        "employee_type",
        "manager_username",
        "manager_employee_number",
    }
)


def _norm_header(h: str) -> str:
    key = (h or "").strip().lstrip("\ufeff").lower().replace(" ", "_")
    return HEADER_ALIASES.get(key, key)


def _cell(row: dict[str, str], key: str) -> str:
    v = row.get(key)
    if v is None:
        return ""
    return str(v).strip()


def _parse_csv_rows(raw: bytes) -> tuple[list[dict[str, str]], str | None]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            return [], "File could not be read as UTF-8 or Latin-1."

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], "CSV has no header row."

    norm_fields = [_norm_header(h) for h in reader.fieldnames]
    if len(norm_fields) != len(set(norm_fields)):
        return [], "Duplicate column names after normalization."

    rows_out: list[dict[str, str]] = []
    for raw_row in reader:
        row: dict[str, str] = {}
        for orig_key, val in raw_row.items():
            nk = _norm_header(orig_key or "")
            if nk in CANONICAL_FIELDS:
                row[nk] = val if val is not None else ""
        rows_out.append(row)

    if len(rows_out) > MAX_ROWS:
        return [], f"Too many rows (max {MAX_ROWS})."

    return rows_out, None


def _sector(val: str) -> str:
    v = (val or "").strip().lower()
    if not v:
        return Sector.GOVERNMENT
    if v in ("government", "gov", Sector.GOVERNMENT):
        return Sector.GOVERNMENT
    if v in ("private", "private_sector", Sector.PRIVATE):
        return Sector.PRIVATE
    raise ValueError(f"Unknown sector «{val}» (use government or private).")


def _choice_or_blank(model_field: str, val: str, allowed: frozenset[str], label: str) -> str:
    v = (val or "").strip().lower()
    if not v:
        return ""
    if v not in allowed:
        raise ValueError(f"Invalid {label} «{val}».")
    return v


@dataclass
class BulkImportResult:
    created: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def import_employees_from_csv(
    file_bytes: bytes,
    tenant: Tenant,
    *,
    generate_passwords: bool,
) -> BulkImportResult:
    """
    Create users + employees from CSV. Two-pass: create rows without manager, then set managers.
    """
    result = BulkImportResult()
    rows, parse_err = _parse_csv_rows(file_bytes)
    if parse_err:
        result.errors.append(parse_err)
        return result

    need_pw_col = not generate_passwords
    required_headers_per_row = {"username", "email", "first_name", "last_name", "employee_number"}

    pending_managers: list[tuple[Employee, str, str]] = []
    created_usernames: list[str] = []

    for idx, row in enumerate(rows, start=2):
        line_label = f"Row {idx}"
        try:
            missing = [k for k in sorted(required_headers_per_row) if not _cell(row, k)]
            if missing:
                raise ValueError(f"missing required values for: {', '.join(missing)}")

            username = _cell(row, "username")
            email = _cell(row, "email")
            fn = _cell(row, "first_name")
            ln = _cell(row, "last_name")
            emp_no = _cell(row, "employee_number")

            if User.objects.filter(username__iexact=username).exists():
                raise ValueError(f"username «{username}» already exists.")

            if Employee.objects.filter(employee_number=emp_no).exclude(employee_number="").exists():
                raise ValueError(f"employee_number «{emp_no}» already in use.")

            pw = _cell(row, "password")
            if generate_passwords:
                pw = secrets.token_urlsafe(14)
            elif not pw:
                raise ValueError("password is empty (use column password or enable generate passwords).")

            validate_password(pw, user=None)

            sec = _sector(_cell(row, "sector"))

            gender_raw = _cell(row, "gender")
            if gender_raw.strip().lower() == "prefer_not_to_say":
                gender_raw = "prefer_not"
            gender = _choice_or_blank(
                "gender",
                gender_raw,
                frozenset({"male", "female", "other", "prefer_not"}),
                "gender",
            )
            marital = _choice_or_blank(
                "marital_status",
                _cell(row, "marital_status"),
                frozenset({"single", "married", "divorced", "widowed", "other"}),
                "marital_status",
            )
            estatus = _choice_or_blank(
                "employment_status",
                _cell(row, "employment_status"),
                frozenset(
                    {
                        "active",
                        "probation",
                        "on_leave",
                        "suspended",
                        "terminated",
                        "retired",
                    }
                ),
                "employment_status",
            )
            etype = _choice_or_blank(
                "employee_type",
                _cell(row, "employee_type"),
                frozenset({"full_time", "part_time", "contractor", "intern"}),
                "employee_type",
            )

            emp_kwargs: dict = {
                "tenant": tenant,
                "sector": sec,
                "civil_id": _cell(row, "civil_id"),
                "nationality": _cell(row, "nationality"),
                "mobile_number": _cell(row, "mobile_number"),
                "home_address": _cell(row, "home_address"),
                "emergency_contact": _cell(row, "emergency_contact"),
                "employee_number": emp_no,
                "job_title": _cell(row, "job_title"),
                "department": _cell(row, "department"),
                "section_team": _cell(row, "section_team"),
                "work_location": _cell(row, "work_location"),
                "gender": gender or "",
                "marital_status": marital or "",
                "employment_status": estatus or EmploymentStatus.ACTIVE,
                "employee_type": etype or EmployeeType.FULL_TIME,
                "manager_id": None,
            }

            dob_s = _cell(row, "date_of_birth")
            if dob_s:
                from django.utils.dateparse import parse_date

                dob = parse_date(dob_s)
                if dob is None:
                    raise ValueError("date_of_birth must be YYYY-MM-DD.")
                emp_kwargs["date_of_birth"] = dob

            hire_s = _cell(row, "hire_date")
            if hire_s:
                from django.utils.dateparse import parse_date

                hd = parse_date(hire_s)
                if hd is None:
                    raise ValueError("hire_date must be YYYY-MM-DD.")
                emp_kwargs["hire_date"] = hd

            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=pw,
                    first_name=fn,
                    last_name=ln,
                )
                employee = Employee(user=user, **emp_kwargs)
                employee.full_clean()
                employee.save()

            mu = _cell(row, "manager_username")
            men = _cell(row, "manager_employee_number")
            if mu or men:
                pending_managers.append((employee, mu, men))

            created_usernames.append(username)
            result.created += 1

        except (ValueError, DjangoValidationError) as e:
            msg = getattr(e, "messages", None)
            if msg:
                detail = msg[0] if isinstance(msg, list) else str(msg)
            else:
                detail = str(e)
            result.errors.append(f"{line_label}: {detail}")
        except Exception as e:
            result.errors.append(f"{line_label}: {e}")

    for emp, mu, men in pending_managers:
        try:
            mgr = None
            if mu:
                mgr = Employee.objects.filter(tenant=tenant, user__username__iexact=mu).first()
                if mgr is None:
                    result.warnings.append(
                        f"Manager username «{mu}» not found for employee «{emp.user.get_username()}» (skipped).",
                    )
            elif men:
                mgr = Employee.objects.filter(tenant=tenant, employee_number=men).first()
                if mgr is None:
                    result.warnings.append(
                        f"Manager employee_number «{men}» not found for employee «{emp.user.get_username()}» (skipped).",
                    )
            if mgr is not None:
                if mgr.pk == emp.pk:
                    result.warnings.append(
                        f"Employee «{emp.user.get_username()}» cannot be their own manager (skipped).",
                    )
                elif mgr.tenant_id != tenant.pk:
                    result.warnings.append(
                        f"Manager for «{emp.user.get_username()}» is not in the same tenant (skipped).",
                    )
                else:
                    emp.manager = mgr
                    emp.save(update_fields=["manager"])
        except Exception as e:
            result.warnings.append(f"Could not set manager for «{emp.user.get_username()}»: {e}")

    if result.created and generate_passwords:
        result.warnings.append(
            "Passwords were generated automatically; share credentials securely or ask users to reset.",
        )

    return result
