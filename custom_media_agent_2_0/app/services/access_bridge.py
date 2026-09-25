"""Independent V2 verifier for the gateway's signed Alchemy identity bridge."""
from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping

HEADER_USER = "X-Alchemy-Access-User"
HEADER_SURFACES = "X-Alchemy-Access-Surfaces"
HEADER_REQUEST = "X-Alchemy-Access-Request"
HEADER_ISSUED = "X-Alchemy-Access-Issued"
HEADER_NONCE = "X-Alchemy-Access-Nonce"
HEADER_SIGNATURE = "X-Alchemy-Access-Signature"
MAX_CLOCK_SKEW_SECONDS = 90


def _canonical(user_id: int, surfaces: tuple[str, ...], request_id: str, issued_at: int, nonce: str, method: str, path: str) -> bytes:
    return "\n".join([str(user_id), ",".join(surfaces), request_id, str(issued_at), nonce, method.upper(), path]).encode("utf-8")


def verify_access_headers(headers: Mapping[str, str], *, method: str, path: str, secret: str, now: int | None = None) -> dict[str, object] | None:
    if not secret:
        return None
    try:
        user_id = int(str(headers.get(HEADER_USER) or ""))
        issued_at = int(str(headers.get(HEADER_ISSUED) or ""))
    except (TypeError, ValueError):
        return None
    request_id = str(headers.get(HEADER_REQUEST) or "").strip()
    nonce = str(headers.get(HEADER_NONCE) or "").strip()
    surfaces = tuple(sorted({item.strip().lower() for item in str(headers.get(HEADER_SURFACES) or "").split(",") if item.strip()}))
    supplied = str(headers.get(HEADER_SIGNATURE) or "").strip().lower()
    if user_id <= 0 or not request_id or not nonce or not surfaces or len(supplied) != 64:
        return None
    current = int(time.time() if now is None else now)
    if abs(current - issued_at) > MAX_CLOCK_SKEW_SECONDS:
        return None
    expected = hmac.new(secret.encode("utf-8"), _canonical(user_id, surfaces, request_id, issued_at, nonce, method, path), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return None
    return {"user_id": user_id, "surfaces": list(surfaces), "request_id": request_id}
