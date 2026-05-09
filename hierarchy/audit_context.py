"""Per-request context so model signals can attribute changes to the current user."""

import threading

_local = threading.local()


def bind_audit_request(request) -> None:
    _local.request = request


def clear_audit_request() -> None:
    _local.request = None


def get_audit_request():
    return getattr(_local, "request", None)


def get_audit_actor():
    """Return (user_pk_or_None, username_or_dash)."""
    req = get_audit_request()
    if req is None:
        return None, "-"
    user = getattr(req, "user", None)
    if user is not None and user.is_authenticated:
        return user.pk, user.get_username()
    return None, "-"


def get_audit_ip() -> str:
    req = get_audit_request()
    if req is None:
        return "-"
    xff = req.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.META.get("REMOTE_ADDR", "-")
