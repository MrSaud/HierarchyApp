from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """Organization / tenant boundary for users and data."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    api_base_url = models.URLField(
        "API base URL",
        max_length=500,
        blank=True,
        help_text="This tenant's backend base (e.g. http://63.183.213.237:1113). "
        "Health checks use {base}/api/health.",
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Shared secret for machine API clients (GET /api/employees/). "
        "Optional: override in production with env TENANT_API_KEY_<tenant_pk>.",
    )
    api_key_header = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="HTTP header for api_key (default X-Api-Key if empty). "
        "Optional env: TENANT_API_KEY_HEADER_<tenant_pk>.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_api_health_url(self):
        """GET target for /api/health; falls back to global settings if base URL empty."""
        base = (self.api_base_url or "").strip().rstrip("/")
        if base:
            return f"{base}/api/health"
        from django.conf import settings

        return getattr(settings, "EXTERNAL_API_HEALTH_URL", "")


class OrganizationalUnit(models.Model):
    """Tenant org chart bucket (department, division, team cluster), optionally nested."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="organizational_units",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=64,
        blank=True,
        help_text="Short code for exports (optional).",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "organizational unit"

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "A unit cannot be its own parent."})
        # Skip tenant match until instance has a tenant (ModelForm sets it after field validation).
        if (
            self.tenant_id
            and self.parent_id
            and self.parent.tenant_id != self.tenant_id
        ):
            raise ValidationError({"parent": "Parent must belong to the same tenant."})


class Position(models.Model):
    """Named role/slot within a tenant (optionally placed under an organizational unit)."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    organizational_unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
    )
    title = models.CharField(max_length=200)
    code = models.CharField(
        "Position code",
        max_length=64,
        blank=True,
        help_text="Job code or grade (optional).",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["organizational_unit_id", "sort_order", "title"]

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError

        if (
            self.tenant_id
            and self.organizational_unit_id
            and self.organizational_unit.tenant_id != self.tenant_id
        ):
            raise ValidationError(
                {"organizational_unit": "Organizational unit must belong to the same tenant."}
            )


class PositionAssignment(models.Model):
    """Links an employee to a position for a period (open-ended when end_date is empty)."""

    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="position_assignments",
    )
    is_primary = models.BooleanField(
        default=True,
        help_text="Marks the main role when someone holds several positions.",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-is_primary", "-start_date", "pk"]

    def __str__(self):
        return f"{self.employee} → {self.position.title}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        emp_tid = self.employee.tenant_id
        if emp_tid is None:
            raise ValidationError({"employee": "Employee has no tenant assigned."})
        if emp_tid != self.position.tenant_id:
            raise ValidationError(
                {"employee": "Employee must belong to the same tenant as the position."}
            )


class Sector(models.TextChoices):
    GOVERNMENT = "government", "Government"
    PRIVATE = "private", "Private sector"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"
    PREFER_NOT = "prefer_not", "Prefer not to say"


class MaritalStatus(models.TextChoices):
    SINGLE = "single", "Single"
    MARRIED = "married", "Married"
    DIVORCED = "divorced", "Divorced"
    WIDOWED = "widowed", "Widowed"
    OTHER = "other", "Other"


class EmploymentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PROBATION = "probation", "Probation"
    ON_LEAVE = "on_leave", "On leave"
    SUSPENDED = "suspended", "Suspended"
    TERMINATED = "terminated", "Terminated"
    RETIRED = "retired", "Retired"


class EmployeeType(models.TextChoices):
    FULL_TIME = "full_time", "Full-time"
    PART_TIME = "part_time", "Part-time"
    CONTRACTOR = "contractor", "Contractor"
    INTERN = "intern", "Intern"


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )

    # Employment (sector retained from earlier version)
    sector = models.CharField(max_length=20, choices=Sector.choices)
    employee_number = models.CharField(
        "Employee ID / number",
        max_length=64,
        unique=True,
        blank=True,
        null=True,
    )
    job_title = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    section_team = models.CharField("Section / team", max_length=120, blank=True)
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )
    hire_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
    )
    work_location = models.CharField(max_length=255, blank=True)
    employee_type = models.CharField(
        max_length=20,
        choices=EmployeeType.choices,
        default=EmployeeType.FULL_TIME,
    )

    # Personal / identification
    civil_id = models.CharField("Civil ID / national ID", max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True,
    )
    nationality = models.CharField(max_length=120, blank=True)
    marital_status = models.CharField(
        max_length=20,
        choices=MaritalStatus.choices,
        blank=True,
    )
    personal_photo = models.ImageField(
        "Employee photo",
        upload_to="employee_photos/%Y/%m/",
        blank=True,
        null=True,
    )

    # Contact (email lives on User; mobile & address here)
    mobile_number = models.CharField("Mobile number", max_length=32, blank=True)
    home_address = models.TextField(blank=True)
    emergency_contact = models.TextField(
        "Emergency contact",
        blank=True,
        help_text="Name, relationship, and phone number.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        name = self.user.get_full_name().strip()
        if name:
            return f"{name} ({self.user.get_username()})"
        return self.user.get_username()


class SignatureImage(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="signatures",
    )
    image = models.ImageField(upload_to="employee_signatures/%Y/%m/")
    label = models.CharField(max_length=120, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.label or f"Signature #{self.pk}"


class AuditLog(models.Model):
    """Append-only record of HTTP traffic and notable model/auth actions."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=64, db_index=True)
    details = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    ip_address = models.CharField(max_length=45, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "audit log"
        verbose_name_plural = "audit logs"

    def __str__(self):
        return f"{self.action} @ {self.created_at}"
