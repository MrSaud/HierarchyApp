"""Resolve tenant from the user's employee profile (no separate membership row)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractBaseUser

from .models import Employee

if TYPE_CHECKING:
    from .models import Tenant


def get_user_tenant_id(user: AbstractBaseUser | None) -> int | None:
    if user is None or not user.is_authenticated:
        return None
    try:
        return user.employee_profile.tenant_id
    except Employee.DoesNotExist:
        return None


def get_user_tenant(user: AbstractBaseUser | None) -> Tenant | None:
    tid = get_user_tenant_id(user)
    if tid is None:
        return None
    from .models import Tenant

    return Tenant.objects.filter(pk=tid).first()
