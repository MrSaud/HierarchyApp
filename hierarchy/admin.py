from django.contrib import admin
from django.contrib.auth import get_user_model

from django.db.models import Q

from .models import (
    AuditLog,
    Delegation,
    DelegationTemplate,
    Employee,
    OrgUnitTypeDefinition,
    OrganizationalUnit,
    Position,
    PositionAssignment,
    Tenant,
)
from .tenant_scope import get_superuser_active_tenant
from .user_tenant import get_user_tenant_id

User = get_user_model()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "ip_address", "details_preview")
    list_filter = ("action",)
    search_fields = ("details", "ip_address", "user__username")
    readonly_fields = ("created_at", "action", "details", "user", "ip_address")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Details")
    def details_preview(self, obj):
        text = obj.details or ""
        return text if len(text) <= 120 else text[:117] + "..."


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "api_base_url")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    fieldsets = (
        (None, {"fields": ("name", "slug", "is_active")}),
        (
            "External API (AD)",
            {
                "fields": (
                    "api_base_url",
                    "api_key",
                    "api_key_header",
                    "external_login_enabled",
                ),
            },
        ),
    )


def _staff_tenant_id(request):
    if request.user.is_superuser:
        st = get_superuser_active_tenant(request)
        return st.pk if st is not None else None
    return get_user_tenant_id(request.user)


class PositionAssignmentInline(admin.TabularInline):
    model = PositionAssignment
    extra = 0
    autocomplete_fields = ("employee",)


@admin.register(OrgUnitTypeDefinition)
class OrgUnitTypeDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "tenant", "rank", "allows_root", "sort_order")
    list_filter = ("tenant", "allows_root")
    search_fields = ("label", "slug")
    ordering = ("tenant__name", "sort_order", "rank")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)


@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "unit_type", "parent", "code", "sort_order")
    list_filter = ("tenant", "unit_type")
    search_fields = ("name", "code")
    autocomplete_fields = ("parent",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            kwargs["queryset"] = self._scoped_units_queryset(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _scoped_units_queryset(self, request):
        qs = OrganizationalUnit.objects.all()
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk).order_by("sort_order", "name")
            return OrganizationalUnit.objects.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return OrganizationalUnit.objects.none()
        return qs.filter(tenant_id=tid).order_by("sort_order", "name")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "tenant",
        "organizational_unit",
        "code",
        "is_active",
        "sort_order",
    )
    list_filter = ("tenant", "is_active")
    search_fields = ("title", "code", "description")
    autocomplete_fields = ("organizational_unit",)
    inlines = [PositionAssignmentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organizational_unit":
            ou_qs = OrganizationalUnit.objects.all()
            if request.user.is_superuser:
                st = get_superuser_active_tenant(request)
                if st is not None:
                    kwargs["queryset"] = ou_qs.filter(tenant_id=st.pk).order_by(
                        "sort_order",
                        "name",
                    )
                else:
                    kwargs["queryset"] = OrganizationalUnit.objects.none()
            else:
                tid = _staff_tenant_id(request)
                if tid is None:
                    kwargs["queryset"] = OrganizationalUnit.objects.none()
                else:
                    kwargs["queryset"] = ou_qs.filter(tenant_id=tid).order_by(
                        "sort_order",
                        "name",
                    )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(DelegationTemplate)
class DelegationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "default_duration_days", "default_is_full_substitute", "sort_order")
    list_filter = ("tenant", "default_is_full_substitute")
    search_fields = ("name", "description")
    filter_horizontal = ("eligible_delegatee_positions",)
    ordering = ("tenant__name", "sort_order", "name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    list_display = (
        "delegator",
        "delegatee",
        "tenant",
        "start_date",
        "end_date",
        "is_full_substitute",
        "template",
        "created_at",
    )
    list_filter = ("tenant",)
    search_fields = (
        "delegator__user__username",
        "delegatee__user__username",
        "notes",
    )
    autocomplete_fields = ("delegator", "delegatee")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "tenant",
            "delegator__user",
            "delegatee__user",
        )
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ("delegator", "delegatee"):
            tid = _staff_tenant_id(request)
            if tid is not None:
                kwargs["queryset"] = Employee.objects.filter(tenant_id=tid).select_related(
                    "user",
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PositionAssignment)
class PositionAssignmentAdmin(admin.ModelAdmin):
    list_display = ("position", "employee", "is_primary", "start_date", "end_date")
    list_filter = ("is_primary",)
    search_fields = ("position__title", "employee__user__username", "notes")
    autocomplete_fields = ("position", "employee")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "position__tenant",
            "employee__user",
        )
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(position__tenant_id=st.pk)
            return qs.none()
        tid = _staff_tenant_id(request)
        if tid is None:
            return qs.none()
        return qs.filter(position__tenant_id=tid)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tenant",
        "employee_number",
        "job_title",
        "department",
        "employment_status",
        "employee_type",
        "sector",
        "hire_date",
    )
    list_filter = (
        "tenant",
        "sector",
        "employment_status",
        "employee_type",
        "gender",
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "employee_number",
        "civil_id",
        "department",
        "job_title",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ("manager", "tenant")
    fieldsets = (
        (
            "User",
            {"fields": ("user",)},
        ),
        (
            "Employment",
            {
                "fields": (
                    "tenant",
                    "sector",
                    "employee_number",
                    "job_title",
                    "department",
                    "section_team",
                    "manager",
                    "hire_date",
                    "employment_status",
                    "work_location",
                    "employee_type",
                )
            },
        ),
        (
            "Personal",
            {
                "fields": (
                    "civil_id",
                    "date_of_birth",
                    "gender",
                    "nationality",
                    "marital_status",
                    "personal_photo",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "mobile_number",
                    "home_address",
                    "emergency_contact",
                )
            },
        ),
        (
            "Meta",
            {"fields": ("created_at",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            st = get_superuser_active_tenant(request)
            if st is not None:
                return qs.filter(tenant_id=st.pk)
            return qs.none()
        tid = get_user_tenant_id(request.user)
        if tid is None:
            return qs.none()
        return qs.filter(tenant_id=tid)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tid = _staff_tenant_id(request)
        if request.user.is_superuser and tid is None:
            if db_field.name in ("manager", "tenant", "user"):
                if db_field.name == "manager":
                    kwargs["queryset"] = Employee.objects.none()
                elif db_field.name == "tenant":
                    from .models import Tenant

                    kwargs["queryset"] = Tenant.objects.none()
                elif db_field.name == "user":
                    kwargs["queryset"] = User.objects.none()
            return super().formfield_for_foreignkey(db_field, request, **kwargs)
        if tid is None:
            if db_field.name == "manager":
                kwargs["queryset"] = Employee.objects.none()
            elif db_field.name == "tenant":
                from .models import Tenant

                kwargs["queryset"] = Tenant.objects.none()
            elif db_field.name == "user":
                kwargs["queryset"] = User.objects.none()
            return super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "manager":
            kwargs["queryset"] = Employee.objects.filter(tenant_id=tid)
        elif db_field.name == "tenant":
            from .models import Tenant

            kwargs["queryset"] = Tenant.objects.filter(pk=tid)
        elif db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(
                Q(employee_profile__tenant_id=tid) | Q(employee_profile__isnull=True),
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
