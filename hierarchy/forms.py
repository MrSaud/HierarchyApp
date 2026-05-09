from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import (
    Employee,
    OrganizationalUnit,
    Position,
    PositionAssignment,
    SignatureImage,
    Tenant,
)
from .user_tenant import get_user_tenant_id

MAX_SIGNATURE_IMAGES = 25


class EmployeeUserEditForm(forms.ModelForm):
    """Update account email/name; username read-only; optional password reset."""

    new_password1 = forms.CharField(
        label="New password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "d365-input", "autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "d365-input", "autocomplete": "new-password"}),
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        for name in ("email", "first_name", "last_name"):
            self.fields[name].widget.attrs.setdefault("class", inp)
        self.fields["username"].disabled = True
        self.fields["username"].widget.attrs.setdefault("class", inp)
        self.fields["first_name"].label = "First name"
        self.fields["last_name"].label = "Last name"
        self.order_fields(
            [
                "username",
                "email",
                "first_name",
                "last_name",
                "new_password1",
                "new_password2",
            ]
        )
        self.fields["new_password1"].help_text = (
            "Leave blank to keep the current password."
        )

    def clean(self):
        data = super().clean()
        p1 = data.get("new_password1") or ""
        p2 = data.get("new_password2") or ""
        if p1 or p2:
            if p1 != p2:
                raise ValidationError("The two password fields do not match.")
            validate_password(p1, self.instance)
        return data

    def save(self, commit=True):
        user = super().save(commit=commit)
        pwd = self.cleaned_data.get("new_password1")
        if pwd:
            user.set_password(pwd)
            if commit:
                user.save(update_fields=["password"])
        return user


class EmployeeUserCreationForm(UserCreationForm):
    """Login account: tenant, username, names, email, password."""

    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(is_active=True),
        label="Tenant",
        required=True,
        empty_label=None,
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, acting_user=None, scope_tenant_id=None, **kwargs):
        self._acting_user = acting_user
        self._scope_tenant_id = scope_tenant_id
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "tenant",
                "username",
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
            ]
        )
        inp = "d365-input"
        for name in ("username", "email", "first_name", "last_name", "password1", "password2"):
            self.fields[name].widget.attrs.setdefault("class", inp)
        self.fields["tenant"].widget.attrs.setdefault("class", "d365-select")
        self.fields["first_name"].label = "First name"
        self.fields["last_name"].label = "Last name"

        au = self._acting_user
        if self._scope_tenant_id is not None:
            self.fields["tenant"].queryset = Tenant.objects.filter(
                pk=self._scope_tenant_id,
                is_active=True,
            )
            self.fields["tenant"].initial = self._scope_tenant_id
            self.fields["tenant"].widget = forms.HiddenInput()
        elif au is not None and not au.is_superuser:
            tid = get_user_tenant_id(au)
            if tid is None:
                self.fields["tenant"].queryset = Tenant.objects.none()
            else:
                self.fields["tenant"].queryset = Tenant.objects.filter(
                    pk=tid,
                    is_active=True,
                )
                self.fields["tenant"].initial = tid
                self.fields["tenant"].widget = forms.HiddenInput()

    def clean_tenant(self):
        tenant = self.cleaned_data.get("tenant")
        if self._scope_tenant_id is not None:
            if tenant is None:
                raise ValidationError("Tenant is required.")
            if tenant.pk != self._scope_tenant_id:
                raise ValidationError("Tenant does not match your active scope.")
            return tenant
        au = self._acting_user
        if au is not None and not au.is_superuser:
            if tenant is None:
                raise ValidationError("Tenant is required.")
            expected_id = get_user_tenant_id(au)
            if expected_id is None:
                raise ValidationError(
                    "Your account needs an employee profile with a tenant before creating users.",
                )
            if tenant.pk != expected_id:
                raise ValidationError("You may only create users in your own tenant.")
        return tenant


class EmployeePhotoForm(forms.ModelForm):
    """Self-service upload for Employee.personal_photo."""

    class Meta:
        model = Employee
        fields = ("personal_photo",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["personal_photo"].widget.attrs.setdefault("class", "d365-file-input")
class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "sector",
            "civil_id",
            "date_of_birth",
            "gender",
            "nationality",
            "marital_status",
            "personal_photo",
            "mobile_number",
            "home_address",
            "emergency_contact",
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

    def __init__(self, *args, employee_instance=None, tenant_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        self.fields["sector"].widget = forms.RadioSelect()
        self.fields["sector"].widget.attrs.setdefault("class", "d365-sector-widget")
        for name in (
            "civil_id",
            "nationality",
            "mobile_number",
            "employee_number",
            "job_title",
            "department",
            "section_team",
            "work_location",
        ):
            self.fields[name].widget.attrs.setdefault("class", inp)
        for name in ("gender", "marital_status", "employment_status", "employee_type", "manager"):
            self.fields[name].widget.attrs.setdefault("class", "d365-select")
        self.fields["home_address"].widget = forms.Textarea(
            attrs={"class": "d365-textarea", "rows": 3}
        )
        self.fields["emergency_contact"].widget = forms.Textarea(
            attrs={"class": "d365-textarea", "rows": 3}
        )
        self.fields["date_of_birth"].widget = forms.DateInput(
            attrs={"type": "date", "class": inp}
        )
        self.fields["hire_date"].widget = forms.DateInput(
            attrs={"type": "date", "class": inp}
        )
        self.fields["personal_photo"].widget.attrs.setdefault("class", "d365-file-input")
        qs = Employee.objects.select_related("user").order_by(
            "user__last_name",
            "user__first_name",
        )
        if employee_instance is not None:
            qs = qs.exclude(pk=employee_instance.pk)
            tid = employee_instance.tenant_id
            if tid is None:
                tid = tenant_id
        else:
            tid = tenant_id
        if tid is not None:
            qs = qs.filter(tenant_id=tid)
        self.fields["manager"].queryset = qs
        self.fields["manager"].label_from_instance = self._manager_label
        self.fields["employee_number"].required = True

    @staticmethod
    def _manager_label(obj):
        name = obj.user.get_full_name().strip()
        if name:
            return f"{name} ({obj.user.get_username()})"
        return obj.user.get_username()


class TenantForm(forms.ModelForm):
    """Create or edit a tenant (slug optional on create — generated from name)."""

    class Meta:
        model = Tenant
        fields = ("name", "slug", "api_base_url", "api_key", "api_key_header", "is_active")
        help_texts = {
            "slug": "URL-safe identifier for APIs (e.g. acme-corp). Leave blank to auto-generate from name.",
            "api_base_url": "Tenant-specific API host (scheme + host + port). Example: http://63.183.213.237:1113",
            "api_key": "Shared secret for API clients (optional if you use env TENANT_API_KEY_<pk> or global Bearer token only).",
            "api_key_header": "Header name for the key (leave blank for X-Api-Key).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        self.fields["name"].widget.attrs.setdefault("class", inp)
        self.fields["slug"].widget.attrs.setdefault("class", inp)
        self.fields["slug"].required = False
        self.fields["api_base_url"].widget.attrs.setdefault("class", inp)
        self.fields["api_base_url"].required = False
        self.fields["api_key"].widget.attrs.setdefault("class", inp)
        self.fields["api_key"].required = False
        self.fields["api_key_header"].widget.attrs.setdefault("class", inp)
        self.fields["api_key_header"].required = False

    def clean(self):
        from django.utils.text import slugify

        cleaned = super().clean()
        name = (cleaned.get("name") or "").strip()
        slug_in = (cleaned.get("slug") or "").strip()
        if not name:
            return cleaned
        if slug_in:
            cleaned["slug"] = slug_in
            return cleaned
        if self.instance.pk:
            if not slug_in:
                cleaned["slug"] = self.instance.slug
            return cleaned
        base = slugify(name)
        if not base:
            raise ValidationError(
                {
                    "name": "Use letters or numbers so a slug can be generated, or enter Slug manually.",
                }
            )
        candidate = base
        n = 2
        qs = Tenant.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        while qs.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        cleaned["slug"] = candidate
        return cleaned


class SignatureImageMetaForm(forms.ModelForm):
    class Meta:
        model = SignatureImage
        fields = ("label", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        self.fields["label"].widget.attrs.setdefault("class", inp)
        self.fields["sort_order"].widget.attrs.setdefault("class", inp)
        self.fields["label"].required = False


class OrganizationalUnitForm(forms.ModelForm):
    """Department / division tree node inside one tenant."""

    class Meta:
        model = OrganizationalUnit
        fields = ("parent", "name", "code", "sort_order")

    def __init__(self, *args, tenant=None, **kwargs):
        self._tenant = tenant
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        for name in ("name", "code", "sort_order"):
            self.fields[name].widget.attrs.setdefault("class", inp)
        self.fields["parent"].widget.attrs.setdefault("class", "d365-select")
        self.fields["sort_order"].required = False
        if tenant is not None:
            qs = OrganizationalUnit.objects.filter(tenant=tenant).order_by(
                "sort_order",
                "name",
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = qs
        else:
            self.fields["parent"].queryset = OrganizationalUnit.objects.none()

    def clean(self):
        # Ensure tenant is on the instance before model validation (tenant not in Meta.fields).
        if self._tenant is not None:
            self.instance.tenant = self._tenant
        cleaned = super().clean()
        parent = cleaned.get("parent")
        if parent is not None and self._tenant is not None:
            if parent.tenant_id != self._tenant.pk:
                raise ValidationError({"parent": "Parent must belong to this tenant."})
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._tenant is not None:
            obj.tenant = self._tenant
        if commit:
            obj.save()
        return obj


class PositionForm(forms.ModelForm):
    """Named role within a tenant."""

    class Meta:
        model = Position
        fields = (
            "organizational_unit",
            "title",
            "code",
            "description",
            "is_active",
            "sort_order",
        )

    def __init__(self, *args, tenant=None, **kwargs):
        self._tenant = tenant
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        for name in ("title", "code", "sort_order"):
            self.fields[name].widget.attrs.setdefault("class", inp)
        self.fields["description"].widget = forms.Textarea(
            attrs={"class": "d365-textarea", "rows": 3},
        )
        self.fields["organizational_unit"].widget.attrs.setdefault("class", "d365-select")
        self.fields["sort_order"].required = False
        if tenant is not None:
            self.fields["organizational_unit"].queryset = OrganizationalUnit.objects.filter(
                tenant=tenant,
            ).order_by("sort_order", "name")
            self.fields["organizational_unit"].required = False
        else:
            self.fields["organizational_unit"].queryset = OrganizationalUnit.objects.none()

    def clean(self):
        if self._tenant is not None:
            self.instance.tenant = self._tenant
        cleaned = super().clean()
        ou = cleaned.get("organizational_unit")
        if ou is not None and self._tenant is not None and ou.tenant_id != self._tenant.pk:
            raise ValidationError({"organizational_unit": "Invalid unit for this tenant."})
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._tenant is not None:
            obj.tenant = self._tenant
        if commit:
            obj.save()
        return obj


class PositionAssignmentForm(forms.ModelForm):
    """Put someone in a position."""

    class Meta:
        model = PositionAssignment
        fields = ("employee", "is_primary", "start_date", "end_date", "notes")

    def __init__(self, *args, position=None, **kwargs):
        self._position = position
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        self.fields["employee"].widget.attrs.setdefault("class", "d365-select")
        self.fields["notes"].widget.attrs.setdefault("class", inp)
        for name in ("start_date", "end_date"):
            self.fields[name].widget = forms.DateInput(attrs={"type": "date", "class": inp})
        self.fields["notes"].required = False
        if position is not None:
            tid = position.tenant_id
            self.fields["employee"].queryset = Employee.objects.filter(
                tenant_id=tid,
            ).select_related("user").order_by(
                "user__last_name",
                "user__first_name",
                "user__username",
            )

            def label_from_instance(e):
                name = e.user.get_full_name().strip()
                if name:
                    return f"{name} ({e.user.username})"
                return e.user.username

            self.fields["employee"].label_from_instance = label_from_instance
        else:
            self.fields["employee"].queryset = Employee.objects.none()

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._position is not None:
            obj.position = self._position
        if commit:
            obj.save()
        return obj


class EmployeePositionAssignmentForm(forms.ModelForm):
    """Assign this employee to a position (from the employee edit screen)."""

    class Meta:
        model = PositionAssignment
        fields = ("position", "is_primary", "start_date", "end_date", "notes")

    def __init__(self, *args, employee=None, **kwargs):
        self._employee = employee
        super().__init__(*args, **kwargs)
        inp = "d365-input"
        self.fields["position"].widget.attrs.setdefault("class", "d365-select")
        self.fields["notes"].widget.attrs.setdefault("class", inp)
        for name in ("start_date", "end_date"):
            self.fields[name].widget = forms.DateInput(attrs={"type": "date", "class": inp})
        self.fields["notes"].required = False
        if employee is not None:
            tid = employee.tenant_id
            if tid:
                self.fields["position"].queryset = Position.objects.filter(
                    tenant_id=tid,
                ).select_related("organizational_unit").order_by(
                    "organizational_unit_id",
                    "sort_order",
                    "title",
                )

                def label_from_instance(p):
                    ou = p.organizational_unit
                    prefix = f"{ou.name} · " if ou else ""
                    code = f" ({p.code})" if p.code else ""
                    return f"{prefix}{p.title}{code}"

                self.fields["position"].label_from_instance = label_from_instance
            else:
                self.fields["position"].queryset = Position.objects.none()
        else:
            self.fields["position"].queryset = Position.objects.none()

    def clean(self):
        if self._employee is not None:
            self.instance.employee = self._employee
        return super().clean()

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._employee is not None:
            obj.employee = self._employee
        if commit:
            obj.save()
        return obj
