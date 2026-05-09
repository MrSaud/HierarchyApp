"""Model and auth event audit logging."""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .audit_store import record_audit
from .models import (
    Employee,
    OrganizationalUnit,
    Position,
    PositionAssignment,
    SignatureImage,
    Tenant,
)

User = get_user_model()


def _skip_signal_kwargs(kwargs) -> bool:
    return bool(kwargs.get("raw"))


def _actor_bits():
    from .audit_context import get_audit_actor, get_audit_ip

    uid, uname = get_audit_actor()
    ip = get_audit_ip()
    return "actor_uid=%s actor=%s ip=%s" % (uid, uname, ip)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "-")


@receiver(post_save, sender=Tenant)
def audit_tenant_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "tenant_save",
        "%s tenant id=%s slug=%s created=%s"
        % (_actor_bits(), instance.pk, instance.slug, created),
    )


@receiver(post_delete, sender=Tenant)
def audit_tenant_delete(sender, instance, **kwargs):
    record_audit(
        "tenant_delete",
        "%s tenant_deleted id=%s slug=%s" % (_actor_bits(), instance.pk, instance.slug),
    )


@receiver(post_save, sender=Employee)
def audit_employee_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "employee_save",
        "%s employee id=%s user_id=%s tenant_id=%s created=%s"
        % (
            _actor_bits(),
            instance.pk,
            instance.user_id,
            instance.tenant_id,
            created,
        ),
    )


@receiver(post_delete, sender=Employee)
def audit_employee_delete(sender, instance, **kwargs):
    record_audit(
        "employee_delete",
        "%s employee_deleted id=%s user_id=%s"
        % (_actor_bits(), instance.pk, instance.user_id),
    )


@receiver(post_save, sender=OrganizationalUnit)
def audit_org_unit_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "organizational_unit_save",
        "%s organizational_unit id=%s tenant_id=%s created=%s"
        % (_actor_bits(), instance.pk, instance.tenant_id, created),
    )


@receiver(post_delete, sender=OrganizationalUnit)
def audit_org_unit_delete(sender, instance, **kwargs):
    record_audit(
        "organizational_unit_delete",
        "%s organizational_unit_deleted id=%s tenant_id=%s"
        % (_actor_bits(), instance.pk, instance.tenant_id),
    )


@receiver(post_save, sender=Position)
def audit_position_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "position_save",
        "%s position id=%s tenant_id=%s created=%s"
        % (_actor_bits(), instance.pk, instance.tenant_id, created),
    )


@receiver(post_delete, sender=Position)
def audit_position_delete(sender, instance, **kwargs):
    record_audit(
        "position_delete",
        "%s position_deleted id=%s tenant_id=%s"
        % (_actor_bits(), instance.pk, instance.tenant_id),
    )


@receiver(post_save, sender=PositionAssignment)
def audit_assignment_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "position_assignment_save",
        "%s position_assignment id=%s employee_id=%s position_id=%s created=%s"
        % (
            _actor_bits(),
            instance.pk,
            instance.employee_id,
            instance.position_id,
            created,
        ),
    )


@receiver(post_delete, sender=PositionAssignment)
def audit_assignment_delete(sender, instance, **kwargs):
    record_audit(
        "position_assignment_delete",
        "%s position_assignment_deleted id=%s employee_id=%s position_id=%s"
        % (
            _actor_bits(),
            instance.pk,
            instance.employee_id,
            instance.position_id,
        ),
    )


@receiver(post_save, sender=SignatureImage)
def audit_signature_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "signature_image_save",
        "%s signature_image id=%s employee_id=%s created=%s"
        % (_actor_bits(), instance.pk, instance.employee_id, created),
    )


@receiver(post_delete, sender=SignatureImage)
def audit_signature_delete(sender, instance, **kwargs):
    record_audit(
        "signature_image_delete",
        "%s signature_image_deleted id=%s employee_id=%s"
        % (_actor_bits(), instance.pk, instance.employee_id),
    )


@receiver(post_save, sender=User)
def audit_user_save(sender, instance, created, **kwargs):
    if _skip_signal_kwargs(kwargs):
        return
    record_audit(
        "auth_user_save",
        "%s auth_user id=%s username=%s created=%s"
        % (_actor_bits(), instance.pk, instance.get_username(), created),
    )


@receiver(post_delete, sender=User)
def audit_user_delete(sender, instance, **kwargs):
    record_audit(
        "auth_user_delete",
        "%s auth_user_deleted id=%s username=%s"
        % (_actor_bits(), instance.pk, instance.get_username()),
    )


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    record_audit(
        "login",
        'success username="%s"' % user.get_username(),
        user=user,
        ip=_client_ip(request),
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    ip = _client_ip(request)
    if user is not None and getattr(user, "pk", None):
        record_audit(
            "logout",
            "user_id=%s username=%s" % (user.pk, user.get_username()),
            user=user,
            ip=ip,
        )
    else:
        record_audit("logout", "anonymous", user=None, ip=ip)
