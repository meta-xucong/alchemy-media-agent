from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class VeyraAuthError(RuntimeError):
    code = "veyra_auth_error"


class VeyraAuthDisabled(VeyraAuthError):
    code = "veyra_auth_disabled"


class VeyraAuthMisconfigured(VeyraAuthError):
    code = "veyra_auth_misconfigured"


class VeyraAuthUnauthorized(VeyraAuthError):
    code = "veyra_auth_unauthorized"


class VeyraInsufficientBalance(VeyraAuthError):
    code = "veyra_insufficient_balance"


@dataclass(frozen=True)
class VeyraAccount:
    user_id: int
    email: str = ""
    role: str = ""
    balance: float = 0.0
    status: str = ""
    concurrency: int = 0


@dataclass(frozen=True)
class VeyraDebitResult:
    user_id: int
    amount: float
    balance_after: float
    idempotency_key: str
    replayed: bool = False


class VeyraSub2APIClient:
    def __init__(self, *, base_url: str | None = None, internal_token: str | None = None, timeout_seconds: float | None = None):
        self.base_url = (base_url if base_url is not None else settings.veyra_sub2api_base_url).rstrip("/")
        self.internal_token = internal_token if internal_token is not None else settings.veyra_internal_token
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.veyra_request_timeout_seconds

    def ensure_enabled(self) -> None:
        if not settings.veyra_auth_enabled:
            raise VeyraAuthDisabled("Veyra auth is disabled.")
        if not self.base_url or not self.internal_token:
            raise VeyraAuthMisconfigured("Veyra sub2api bridge is not configured.")

    async def exchange_login_ticket(self, ticket: str) -> dict[str, Any]:
        self.ensure_enabled()
        payload = await self._post_json("/api/veyra/internal/login-ticket/exchange", {"ticket": ticket})
        return _data(payload)

    async def account(self, user_id: int) -> VeyraAccount:
        self.ensure_enabled()
        payload = await self._get_json(f"/api/veyra/internal/users/{int(user_id)}/account")
        data = _data(payload)
        return VeyraAccount(
            user_id=int(data.get("user_id") or 0),
            email=str(data.get("email") or ""),
            role=str(data.get("role") or ""),
            balance=float(data.get("balance") or 0),
            status=str(data.get("status") or ""),
            concurrency=int(data.get("concurrency") or 0),
        )

    async def debit(self, *, user_id: int, amount: float, idempotency_key: str, source: str = "alchemy", reference_id: str = "") -> VeyraDebitResult:
        self.ensure_enabled()
        payload = {
            "user_id": int(user_id),
            "amount": float(amount),
            "idempotency_key": str(idempotency_key),
            "source": source,
            "reference_id": reference_id,
        }
        data = _data(await self._post_json("/api/veyra/internal/billing/debit", payload))
        return VeyraDebitResult(
            user_id=int(data.get("user_id") or 0),
            amount=float(data.get("amount") or 0),
            balance_after=float(data.get("balance_after") or 0),
            idempotency_key=str(data.get("idempotency_key") or ""),
            replayed=bool(data.get("replayed")),
        )

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(self.base_url + path, headers=self._headers())
        except httpx.HTTPError as exc:
            raise VeyraAuthError(str(exc)) from exc
        return _checked_json(response)

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.base_url + path, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise VeyraAuthError(str(exc)) from exc
        return _checked_json(response)

    def _headers(self) -> dict[str, str]:
        return {"X-Veyra-Internal-Token": str(self.internal_token or "")}


def issue_session_token(user_id: int) -> str:
    secret = _session_secret()
    now = int(time.time())
    payload = {"user_id": int(user_id), "iat": now, "exp": now + settings.veyra_session_ttl_seconds}
    raw = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _sign(raw, secret)
    return raw + "." + sig


def verify_session_token(token: str) -> int:
    secret = _session_secret()
    raw, dot, sig = str(token or "").partition(".")
    if not dot or not raw or not sig:
        raise VeyraAuthUnauthorized("Invalid session token.")
    expected = _sign(raw, secret)
    if not hmac.compare_digest(sig, expected):
        raise VeyraAuthUnauthorized("Invalid session signature.")
    try:
        payload = json.loads(base64.urlsafe_b64decode(_pad_b64(raw)).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise VeyraAuthUnauthorized("Invalid session payload.") from exc
    if int(payload.get("exp") or 0) < int(time.time()):
        raise VeyraAuthUnauthorized("Session expired.")
    user_id = int(payload.get("user_id") or 0)
    if user_id <= 0:
        raise VeyraAuthUnauthorized("Invalid session user.")
    return user_id


async def login_with_ticket(ticket: str, client: VeyraSub2APIClient | None = None) -> dict[str, Any]:
    client = client or VeyraSub2APIClient()
    exchanged = await client.exchange_login_ticket(ticket)
    user_id = int(exchanged.get("user_id") or 0)
    if user_id <= 0:
        raise VeyraAuthUnauthorized("Ticket exchange did not return a user.")
    return {
        "user_id": user_id,
        "intent": str(exchanged.get("intent") or ""),
        "access_token": issue_session_token(user_id),
        "token_type": "Bearer",
        "expires_in": settings.veyra_session_ttl_seconds,
    }


def _checked_json(response: httpx.Response) -> dict[str, Any]:
    if response.status_code in {401, 403}:
        raise VeyraAuthUnauthorized("Veyra bridge rejected the request.")
    if response.status_code == 402:
        raise VeyraInsufficientBalance("Insufficient sub2api balance.")
    if response.status_code >= 400:
        raise VeyraAuthError(f"Veyra bridge returned HTTP {response.status_code}.")
    try:
        data = response.json()
    except ValueError as exc:
        raise VeyraAuthError("Veyra bridge returned non-JSON response.") from exc
    if not isinstance(data, dict):
        raise VeyraAuthError("Veyra bridge returned invalid JSON.")
    return data


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise VeyraAuthError("Veyra bridge response is missing data.")
    return data


def _session_secret() -> bytes:
    secret = settings.veyra_session_secret or settings.veyra_internal_token
    if not settings.veyra_auth_enabled:
        raise VeyraAuthDisabled("Veyra auth is disabled.")
    if not secret:
        raise VeyraAuthMisconfigured("Veyra session secret is not configured.")
    return str(secret).encode("utf-8")


def _sign(raw: str, secret: bytes) -> str:
    digest = hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _pad_b64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")
