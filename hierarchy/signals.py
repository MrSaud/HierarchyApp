"""Auth-related audit logging (model ORM events are handled in audit_model_signals)."""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit_store import record_audit


def _client_ip(request):
    if request is None:
        return "-"
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "-")


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


@receiver(user_login_failed)
def audit_login_failed(sender, credentials=None, **kwargs):
    request = kwargs.get("request")
    uname = ""
    if credentials:
        uname = str(credentials.get("username") or credentials.get("email") or "")[:200]
    record_audit(
        "login_failed",
        'username="%s"' % uname.replace('"', "'"),
        user=None,
        ip=_client_ip(request),
    )
