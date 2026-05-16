"""Shared HTTP helpers for versioned JSON APIs (ETag, canonical JSON, response headers)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from django.http import HttpResponse, JsonResponse

_ETAG_INNER_RE = re.compile(r"(?:W/)?\"([^\"]*)\"")


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def weak_etag_for_payload(data: Any) -> str:
    digest = hashlib.sha256(canonical_json_bytes(data)).hexdigest()
    return f'W/"{digest}"'


def _normalize_etag_candidate(value: str) -> str:
    t = value.strip()
    if t.startswith("W/"):
        t = t[2:].strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    return t


def etag_tokens_from_header(header: str | None) -> list[str]:
    """Return captured ETag *values* (inside quotes), or ``[\"*\"]`` for bare asterisk."""
    if header is None:
        return []
    raw = header.strip()
    if raw == "*":
        return ["*"]
    return _ETAG_INNER_RE.findall(header)


def etag_header_matches(expected_header_value: str, client_header: str | None) -> bool:
    """Weak-compare a single ETag response value to an If-(None-)Match style header."""
    if client_header is None:
        return False
    exp = _normalize_etag_candidate(expected_header_value)
    for token in etag_tokens_from_header(client_header):
        if token == "*":
            return True
        if exp == token:
            return True
    return False


def should_return_not_modified(request, etag: str) -> bool:
    """True when ``If-None-Match`` indicates the representation is still current."""
    inm = request.headers.get("If-None-Match")
    if not inm:
        return False
    if inm.strip() == "*":
        # RFC 7232: * means the precondition is false when a current representation exists.
        return False
    return etag_header_matches(etag, inm)


def evaluate_if_match_for_write(
    request,
    etag: str,
    *,
    allow_missing: bool = False,
) -> tuple[bool, JsonResponse | None]:
    """
    Enforce optimistic concurrency for writes.

    Returns ``(ok, error_response)``. ``ok`` is True when the request may proceed.
    """
    im = request.headers.get("If-Match")
    if im is None or str(im).strip() == "":
        if allow_missing:
            return True, None
        return False, JsonResponse(
            {"detail": "If-Match is required. Send the ETag from the corresponding GET."},
            status=428,
        )
    if im.strip() == "*":
        return False, JsonResponse(
            {"detail": "A specific entity-tag from GET is required (not *)."},
            status=400,
        )
    if not etag_header_matches(etag, im):
        return False, JsonResponse(
            {
                "detail": "If-Match failed; another writer changed the resource. "
                "GET again and retry with the new ETag.",
            },
            status=412,
        )
    return True, None


def not_modified_response(etag: str) -> HttpResponse:
    r = HttpResponse(status=304)
    r["ETag"] = etag
    return r


def attach_v1_read_headers(
    response: HttpResponse,
    *,
    etag: str,
    read_contract: str,
    guide_url: str | None = None,
) -> None:
    response["ETag"] = etag
    response["X-API-Version"] = "1"
    response["X-API-Read-Contract"] = read_contract
    if guide_url:
        response["Link"] = f'<{guide_url}>; rel="service-doc"'


def attach_v1_write_headers(
    response: HttpResponse,
    *,
    etag: str,
    read_contract: str,
    guide_url: str | None = None,
) -> None:
    response["ETag"] = etag
    response["X-API-Version"] = "1"
    response["X-API-Read-Contract"] = read_contract
    if guide_url:
        response["Link"] = f'<{guide_url}>; rel="service-doc"'


def v1_cors_allow_headers() -> str:
    return "Authorization, Content-Type, X-Api-Key, If-Match, If-None-Match"
