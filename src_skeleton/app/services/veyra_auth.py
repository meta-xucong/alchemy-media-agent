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
class VeyraDebitResult:
    user_id: int
    amount: float
    balance_after: float
    idempotency_key: str
    source: str
    replayed: bool = False


@dataclass(frozen=True)
class VeyraAccount:
    user_id: int
    email: str = ""
    role: str = ""
    balance: float = 0.0
    status: str = ""
    concurrency: int = 0


@dataclass(frozen=True)
class VeyraBillingRule:
    key: str
    enabled: bool
    charge_amount: float
    source: str


def verify_session_token(token: str) -> int:
    secret = _session_secret()
    raw, dot, sig = str(token or "").partition(".")
    if not dot or not raw or not sig:
        raise VeyraAuthUnauthorized("Invalid session token.")
    if not hmac.compare_digest(_sign(raw, secret), sig):
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


async def load_billing_rule(rule_key: str | None = None) -> VeyraBillingRule:
    rule_key = str(rule_key or settings.veyra_billing_rule_key_v1 or "alchemy:v1")
    url = str(settings.veyra_billing_settings_url or "").strip()
    if not url:
        return VeyraBillingRule(key=rule_key, enabled=False, charge_amount=0.0, source=rule_key)
    try:
        async with httpx.AsyncClient(timeout=settings.veyra_request_timeout_seconds) as client:
            response = await client.get(url, params={"rule_key": rule_key})
    except httpx.HTTPError as exc:
        raise VeyraAuthError(str(exc)) from exc
    if response.status_code >= 400:
        raise VeyraAuthError(f"Veyra billing settings returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise VeyraAuthError("Veyra billing settings returned non-JSON response.") from exc
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if isinstance(rules, list):
        for item in rules:
            if isinstance(item, dict) and str(item.get("key") or "").lower() == rule_key.lower():
                return _billing_rule_from_payload(item, fallback_key=rule_key)
    if isinstance(payload, dict):
        return _billing_rule_from_payload(payload, fallback_key=rule_key)
    return VeyraBillingRule(key=rule_key, enabled=False, charge_amount=0.0, source=rule_key)


async def load_account(user_id: int) -> VeyraAccount:
    _ensure_bridge_enabled()
    base_url = settings.veyra_sub2api_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.veyra_request_timeout_seconds) as client:
            response = await client.get(
                base_url + f"/api/veyra/internal/users/{int(user_id)}/account",
                headers={"X-Veyra-Internal-Token": str(settings.veyra_internal_token or "")},
            )
    except httpx.HTTPError as exc:
        raise VeyraAuthError(str(exc)) from exc
    data = _checked_data(response)
    return VeyraAccount(
        user_id=int(data.get("user_id") or 0),
        email=str(data.get("email") or ""),
        role=str(data.get("role") or ""),
        balance=float(data.get("balance") or 0),
        status=str(data.get("status") or ""),
        concurrency=int(data.get("concurrency") or 0),
    )


async def ensure_sufficient_balance(*, user_id: int, amount: float) -> VeyraAccount:
    account = await load_account(user_id)
    if float(account.balance) + 1e-9 < float(amount):
        raise VeyraInsufficientBalance("Insufficient sub2api balance.")
    return account


async def debit_balance(*, user_id: int, amount: float, idempotency_key: str, source: str, reference_id: str) -> VeyraDebitResult:
    _ensure_bridge_enabled()
    payload = {
        "user_id": int(user_id),
        "amount": float(amount),
        "idempotency_key": str(idempotency_key),
        "source": str(source or "alchemy:v1"),
        "reference_id": str(reference_id or ""),
    }
    base_url = settings.veyra_sub2api_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.veyra_request_timeout_seconds) as client:
            response = await client.post(
                base_url + "/api/veyra/internal/billing/debit",
                headers={"X-Veyra-Internal-Token": str(settings.veyra_internal_token or "")},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise VeyraAuthError(str(exc)) from exc
    data = _checked_data(response)
    return VeyraDebitResult(
        user_id=int(data.get("user_id") or 0),
        amount=float(data.get("amount") or 0),
        balance_after=float(data.get("balance_after") or 0),
        idempotency_key=str(data.get("idempotency_key") or ""),
        source=str(data.get("source") or source or "alchemy:v1"),
        replayed=bool(data.get("replayed")),
    )


def _billing_rule_from_payload(payload: dict[str, Any], *, fallback_key: str) -> VeyraBillingRule:
    key = str(payload.get("key") or fallback_key)
    return VeyraBillingRule(
        key=key,
        enabled=bool(payload.get("enabled")),
        charge_amount=max(0.0, float(payload.get("charge_amount") or 0.0)),
        source=str(payload.get("source") or key),
    )


def _checked_data(response: httpx.Response) -> dict[str, Any]:
    if response.status_code in {401, 403}:
        raise VeyraAuthUnauthorized("Veyra bridge rejected the request.")
    if response.status_code == 402:
        raise VeyraInsufficientBalance("Insufficient sub2api balance.")
    if response.status_code >= 400:
        raise VeyraAuthError(f"Veyra bridge returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise VeyraAuthError("Veyra bridge returned non-JSON response.") from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise VeyraAuthError("Veyra bridge response is missing data.")
    return data


def _ensure_bridge_enabled() -> None:
    if not settings.veyra_auth_enabled:
        raise VeyraAuthDisabled("Veyra auth is disabled.")
    if not settings.veyra_internal_token or not settings.veyra_sub2api_base_url:
        raise VeyraAuthMisconfigured("Veyra bridge is not configured.")


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
