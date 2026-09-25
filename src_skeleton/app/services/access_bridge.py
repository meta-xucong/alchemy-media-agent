"""V1 gateway signer for the independent V2 access bridge contract."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

HEADER_USER = "X-Alchemy-Access-User"
HEADER_SURFACES = "X-Alchemy-Access-Surfaces"
HEADER_REQUEST = "X-Alchemy-Access-Request"
HEADER_ISSUED = "X-Alchemy-Access-Issued"
HEADER_NONCE = "X-Alchemy-Access-Nonce"
HEADER_SIGNATURE = "X-Alchemy-Access-Signature"


def _canonical(user_id: int, surfaces: tuple[str, ...], request_id: str, issued_at: int, nonce: str, method: str, path: str) -> bytes:
    return "\n".join([str(user_id), ",".join(surfaces), request_id, str(issued_at), nonce, method.upper(), path]).encode("utf-8")


def build_access_headers(*, user_id: int, surfaces: list[str] | tuple[str, ...], method: str, path: str, secret: str, request_id: str | None = None, issued_at: int | None = None, nonce: str | None = None) -> dict[str, str]:
    normalized = tuple(sorted({str(item).strip().lower() for item in surfaces if str(item).strip()}))
    if type(user_id) is not int or user_id <= 0 or not secret or not normalized:
        raise ValueError("access bridge configuration is invalid")
    issued = int(time.time() if issued_at is None else issued_at)
    req_id = request_id or secrets.token_urlsafe(16)
    token = nonce or secrets.token_urlsafe(16)
    signature = hmac.new(secret.encode("utf-8"), _canonical(user_id, normalized, req_id, issued, token, method, path), hashlib.sha256).hexdigest()
    return {HEADER_USER: str(user_id), HEADER_SURFACES: ",".join(normalized), HEADER_REQUEST: req_id, HEADER_ISSUED: str(issued), HEADER_NONCE: token, HEADER_SIGNATURE: signature}
