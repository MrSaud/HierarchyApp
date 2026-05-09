from django.urls import path

from . import auth_api, employee_api, organization_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("employee-photo/", views.employee_photo, name="employee_photo"),
    path("tenants/switch/", views.tenant_switch, name="tenant_switch"),
    path("tenants/new/", views.tenant_create, name="tenant_create"),
    path("tenants/<int:pk>/edit/", views.tenant_edit, name="tenant_edit"),
    path("tenants/", views.tenant_list, name="tenant_list"),
    path("api/auth/users/", auth_api.api_users, name="api_users"),
    path("api/auth/login/", auth_api.api_login, name="api_login"),
    path("api/employees/", employee_api.api_employee_get, name="api_employee_get"),
    path("tools/api-health/", views.api_health_test, name="api_health_test"),
    path("tools/api-guide/", views.api_guide, name="api_guide"),
    path("tools/audit-log/", views.audit_log_list, name="audit_log_list"),
    path("tools/user-sync/", views.user_sync, name="user_sync"),
    path("tools/user-sync/stream/", views.user_sync_stream, name="user_sync_stream"),
    path("organization/", organization_views.organization_overview, name="organization_overview"),
    path("organization/units/new/", organization_views.org_unit_create, name="org_unit_create"),
    path("organization/units/<int:pk>/edit/", organization_views.org_unit_edit, name="org_unit_edit"),
    path("organization/units/", organization_views.org_unit_list, name="org_unit_list"),
    path("organization/positions/new/", organization_views.position_create, name="position_create"),
    path("organization/positions/<int:pk>/edit/", organization_views.position_edit, name="position_edit"),
    path(
        "organization/assignments/<int:pk>/remove/",
        organization_views.position_assignment_delete,
        name="position_assignment_delete",
    ),
    path("organization/positions/<int:pk>/", organization_views.position_detail, name="position_detail"),
    path("organization/positions/", organization_views.position_list, name="position_list"),
    path("employees/<int:pk>/signatures/", views.signature_manage, name="signature_manage"),
    path(
        "employees/signatures/bulk/",
        views.signature_bulk_upload,
        name="signature_bulk_upload",
    ),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/", views.employee_list, name="employee_list"),
]

app_name = "hierarchy"
