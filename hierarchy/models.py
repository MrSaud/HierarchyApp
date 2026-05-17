from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """Organization / tenant boundary for users and data."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    api_base_url = models.URLField(
        "External API (AD) base URL",
        max_length=500,
        blank=True,
        help_text="External API: AD / Windows Authentication server this tenant uses. "
        "Scheme + host + port, e.g. http://63.183.213.237:1113. "
        "Hierarchy calls {base}/api/health and {base}/api/auth/users for sync and login.",
    )
    api_key = models.CharField(
        "ApiKey",
        max_length=255,
        blank=True,
        help_text="External API: secret sent to the AD server on outbound calls "
        "(stored on this tenant; not overridden by env).",
    )
    api_key_header = models.CharField(
        "ApiKeyHeader",
        max_length=64,
        blank=True,
        default="",
        help_text="External API: HTTP header name for ApiKey on AD requests; "
        "optional, defaults to X-Api-Key (tenant settings only).",
    )
    external_login_enabled = models.BooleanField(
        "AD login enabled",
        default=True,
        help_text="When on, POST /api/auth/login/ verifies credentials against the external AD API. "
        "When off, login uses local Django passwords only (sync and health still use the external API above).",
    )
    external_sync_username = models.CharField(
        "AD sync username",
        max_length=255,
        blank=True,
        help_text="Service account for Sync users (GET /api/auth/users with JSON body).",
    )
    external_sync_password = models.CharField(
        "AD sync password",
        max_length=255,
        blank=True,
        help_text="Password for the AD sync account (stored on tenant).",
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


class OrgUnitType(models.TextChoices):
    """Built-in slug constants for seeds and default catalog rows."""

    MINISTER = "minister", "Minister (DG)"
    DEPUTY_DG = "deputy_dg", "Deputy DG"
    SECTOR = "sector", "Sector (Program)"
    GENERAL_ADMIN = "general_admin", "General administration"
    DEPARTMENT = "department", "Department"
    CONTROLLER = "controller", "Controller"
    SECTION = "section", "Section"
    REGIONAL_DIRECTORATE = "regional_directorate", "Regional directorate"


class OrgUnitTypeDefinition(models.Model):
    """Per-tenant organizational unit type (label, hierarchy rank, root rules)."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="org_unit_type_definitions",
    )
    slug = models.SlugField(
        max_length=64,
        help_text="Stable code stored on units (e.g. department). Letters, numbers, underscores.",
    )
    label = models.CharField(max_length=120)
    rank = models.PositiveSmallIntegerField(
        default=50,
        help_text="Lower = higher in hierarchy. Parent must have a lower rank than child.",
    )
    allows_root = models.BooleanField(
        default=False,
        help_text="May exist without a parent unit (top-level).",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "rank", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="hierarchy_orgunittype_tenant_slug_uniq",
            ),
        ]
        verbose_name = "organizational unit type"

    def __str__(self):
        return self.label

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.slug and self.slug != self.slug.lower():
            raise ValidationError({"slug": "Use lowercase letters, numbers, and underscores only."})


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
    unit_type = models.CharField(
        max_length=64,
        default=OrgUnitType.DEPARTMENT,
        db_index=True,
        help_text="Slug of an organizational unit type defined for this tenant.",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "organizational unit"

    def __str__(self):
        return self.name

    def get_unit_type_display(self):
        from .org_unit_types import resolve_unit_type_label

        return resolve_unit_type_label(self.tenant_id, self.unit_type)

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

        from .org_unit_types import validate_org_unit_parent_type, validate_unit_type_slug

        validate_unit_type_slug(self.tenant_id, self.unit_type)
        parent = self.parent if self.parent_id else None
        validate_org_unit_parent_type(self, parent)


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
        help_text="Main role when someone holds several positions; at most one assignment per employee may be primary.",
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
        if not self.position_id:
            raise ValidationError({"position": "Position is required."})
        if not self.employee_id:
            raise ValidationError({"employee": "Employee is required."})
        emp_tid = self.employee.tenant_id
        if emp_tid is None:
            raise ValidationError({"employee": "Employee has no tenant assigned."})
        pos_tid = self.position.tenant_id
        if emp_tid != pos_tid:
            raise ValidationError(
                {"employee": "Employee must belong to the same tenant as the position."}
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary and self.employee_id:
            type(self).objects.filter(
                employee_id=self.employee_id,
                is_primary=True,
            ).exclude(pk=self.pk).update(is_primary=False)


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


class DelegationTemplate(models.Model):
    """
    Reusable pattern for delegations (e.g. acting director): default duration,
    full vs partial substitute, and which positions qualify as delegatee.
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="delegation_templates",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(
        blank=True,
        help_text="Internal notes on when to use this pattern (e.g. acting director leave).",
    )
    default_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="If set, applying this template fills end date as start + N days when end is left blank.",
    )
    default_is_full_substitute = models.BooleanField(
        default=True,
        help_text="Default for “full substitute” (overlapping full delegations per delegator are blocked).",
    )
    eligible_delegatee_positions = models.ManyToManyField(
        "Position",
        blank=True,
        related_name="delegation_templates_eligible",
        help_text="If any are selected, the delegatee must currently hold one of these positions. "
        "Leave empty to allow any employee in the tenant.",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in the “start from template” dropdown.",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "delegation template"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="hierarchy_delegationtemplate_tenant_name_uniq",
            ),
        ]

    def __str__(self):
        return self.name


class Delegation(models.Model):
    """
    Temporary authority: one employee (delegatee) acts on behalf of another (delegator).
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="delegations",
    )
    delegator = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="delegations_given",
    )
    delegatee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="delegations_received",
    )
    start_date = models.DateField()
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Leave empty for an open-ended delegation.",
    )
    notes = models.CharField(max_length=500, blank=True)
    is_full_substitute = models.BooleanField(
        default=True,
        help_text="Full substitute: this person fully acts for the delegator. "
        "Only one overlapping full delegation per delegator is allowed.",
    )
    template = models.ForeignKey(
        DelegationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegations",
        help_text="Pattern used when this delegation was created (optional).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "pk"]
        verbose_name = "delegation"

    def __str__(self):
        return f"{self.delegator} → {self.delegatee}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        if self.delegator_id and self.delegatee_id and self.delegator_id == self.delegatee_id:
            raise ValidationError({"delegatee": "Delegator and delegatee must be different people."})
        if not self.delegator_id or not self.delegatee_id:
            return
        if self.delegator.tenant_id != self.delegatee.tenant_id:
            raise ValidationError(
                {"delegatee": "Delegator and delegatee must belong to the same tenant."}
            )
        tid = self.tenant_id
        if tid is None:
            return
        for label, emp in (("delegator", self.delegator), ("delegatee", self.delegatee)):
            if emp.tenant_id != tid:
                raise ValidationError({label: "Employee must belong to this tenant."})
        from .delegation_policy import validate_delegation_conflicts

        validate_delegation_conflicts(self)


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
