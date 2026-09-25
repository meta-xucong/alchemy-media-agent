"""Small, dependency-free identity bridge shared by the API gateway and V2.

The bridge carries an already authenticated Alchemy account identity from the
gateway to the separately running V2 process.  It is deliberately not an
account store and never carries a password, API key, cookie, or role.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Mapping


HEADER_USER = "X-Alchemy-Access-User"
HEADER_SURFACES = "X-Alchemy-Access-Surfaces"
HEADER_REQUEST = "X-Alchemy-Access-Request"
HEADER_ISSUED = "X-Alchemy-Access-Issued"
HEADER_NONCE = "X-Alchemy-Access-Nonce"
HEADER_SIGNATURE = "X-Alchemy-Access-Signature"
MAX_CLOCK_SKEW_SECONDS = 90


def _canonical(*, user_id: int, surfaces: tuple[str, ...], request_id: str, issued_at: int, nonce: str, method: str, path: str) -> bytes:
    return "\n".join(
        [
            str(user_id),
            ",".join(surfaces),
            request_id,
            str(issued_at),
            nonce,
            method.upper(),
            path,
        ]
    ).encode("utf-8")


def build_access_headers(*, user_id: int, surfaces: list[str] | tuple[str, ...], method: str, path: str, secret: str, request_id: str | None = None, issued_at: int | None = None, nonce: str | None = None) -> dict[str, str]:
    if type(user_id) is not int or user_id <= 0 or not secret:
        raise ValueError("access bridge configuration is invalid")
    normalized = tuple(sorted({str(item).strip().lower() for item in surfaces if str(item).strip()}))
    if not normalized:
        raise ValueError("access bridge surfaces are required")
    issued = int(time.time() if issued_at is None else issued_at)
    req_id = request_id or secrets.token_urlsafe(16)
    token = nonce or secrets.token_urlsafe(16)
    signature = hmac.new(
        secret.encode("utf-8"),
        _canonical(user_id=user_id, surfaces=normalized, request_id=req_id, issued_at=issued, nonce=token, method=method, path=path),
        hashlib.sha256,
    ).hexdigest()
    return {
        HEADER_USER: str(user_id),
        HEADER_SURFACES: ",".join(normalized),
        HEADER_REQUEST: req_id,
        HEADER_ISSUED: str(issued),
        HEADER_NONCE: token,
        HEADER_SIGNATURE: signature,
    }


def verify_access_headers(headers: Mapping[str, str], *, method: str, path: str, secret: str, now: int | None = None) -> dict[str, object] | None:
    if not secret:
        return None
    try:
        user_id = int(str(headers.get(HEADER_USER) or ""))
        issued_at = int(str(headers.get(HEADER_ISSUED) or ""))
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None
    request_id = str(headers.get(HEADER_REQUEST) or "").strip()
    nonce = str(headers.get(HEADER_NONCE) or "").strip()
    raw_surfaces = str(headers.get(HEADER_SURFACES) or "")
    surfaces = tuple(sorted({item.strip().lower() for item in raw_surfaces.split(",") if item.strip()}))
    supplied = str(headers.get(HEADER_SIGNATURE) or "").strip().lower()
    if not request_id or not nonce or not surfaces or not supplied or len(supplied) != 64:
        return None
    current = int(time.time() if now is None else now)
    if abs(current - issued_at) > MAX_CLOCK_SKEW_SECONDS:
        return None
    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical(user_id=user_id, surfaces=surfaces, request_id=request_id, issued_at=issued_at, nonce=nonce, method=method, path=path),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return None
    return {"user_id": user_id, "surfaces": list(surfaces), "request_id": request_id}
