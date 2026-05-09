"""HTTP request audit logging (every view access)."""

import time

from .audit_context import bind_audit_request, clear_audit_request
from .audit_store import record_audit


class AuditMiddleware:
    """Bind request for signal attribution; log each request after response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        bind_audit_request(request)
        start = time.monotonic()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            status = getattr(response, "status_code", 500) if response is not None else 500
            user = getattr(request, "user", None)
            actor = user if user is not None and user.is_authenticated else None
            uname = user.get_username() if actor is not None else "-"
            uid = actor.pk if actor is not None else None
            xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
            if xff:
                remote = xff.split(",")[0].strip()
            else:
                remote = request.META.get("REMOTE_ADDR", "-")

            record_audit(
                "http_request",
                'method=%s path="%s" status=%s ms=%s uid=%s user=%s'
                % (
                    request.method,
                    request.get_full_path(),
                    status,
                    duration_ms,
                    uid,
                    uname,
                ),
                user=actor,
                ip=remote,
            )
            clear_audit_request()
