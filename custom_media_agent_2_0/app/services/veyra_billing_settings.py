from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.schemas import (
    VeyraBillingRule,
    VeyraBillingRuleUpdate,
    VeyraBillingSettingsRequest,
    VeyraBillingSettingsResponse,
)


DEFAULT_RULES: dict[str, dict[str, Any]] = {
    "alchemy:v1": {
        "key": "alchemy:v1",
        "label": "Alchemy V1 生图",
        "agent": "alchemy",
        "version": "v1",
        "enabled": True,
        "charge_amount": 0.25,
        "source": "alchemy:v1",
    },
    "alchemy:v2": {
        "key": "alchemy:v2",
        "label": "Alchemy V2 生图",
        "agent": "alchemy",
        "version": "v2",
        "enabled": True,
        "charge_amount": 0.25,
        "source": "alchemy:v2",
    },
}

_runtime_rules: dict[str, VeyraBillingRule] | None = None


def billing_settings_path():
    return settings.data_dir / "veyra_billing_settings.json"


def apply_persisted_billing_settings() -> None:
    _load_rules(force=True)
    v2_rule = get_billing_rule("alchemy:v2")
    object.__setattr__(settings, "veyra_billing_enabled", v2_rule.enabled)
    object.__setattr__(settings, "veyra_generation_charge_amount", v2_rule.charge_amount)


def get_billing_rule(rule_key: str | None = None) -> VeyraBillingRule:
    rules = _load_rules()
    key = _normalize_rule_key(rule_key or "alchemy:v2")
    if key not in rules:
        rules[key] = _rule_from_raw({"key": key})
    return rules[key]


def reset_billing_settings_cache() -> None:
    global _runtime_rules
    _runtime_rules = None


def get_billing_settings(rule_key: str | None = None) -> VeyraBillingSettingsResponse:
    rules = _load_rules()
    active = get_billing_rule(rule_key or "alchemy:v2")
    return VeyraBillingSettingsResponse(
        enabled=active.enabled,
        charge_amount=active.charge_amount,
        rules=sorted(rules.values(), key=lambda item: item.key),
        persisted=billing_settings_path().exists(),
    )


def update_billing_settings(body: VeyraBillingSettingsRequest) -> VeyraBillingSettingsResponse:
    rules = _load_rules()
    updates = list(body.rules or [])
    if body.enabled is not None or body.charge_amount is not None:
        updates.append(
            VeyraBillingRuleUpdate(
                key=body.rule_key or "alchemy:v2",
                enabled=body.enabled,
                charge_amount=body.charge_amount,
            )
        )
    for update in updates:
        key = _normalize_rule_key(update.key)
        current = rules.get(key, _rule_from_raw({"key": key, "label": update.label or ""}))
        raw = current.model_dump()
        if update.label is not None:
            raw["label"] = update.label
        if update.enabled is not None:
            raw["enabled"] = bool(update.enabled)
        if update.charge_amount is not None:
            raw["charge_amount"] = max(0.0, float(update.charge_amount))
        rules[key] = _rule_from_raw(raw)
    _persist_rules(rules)
    v2_rule = rules.get("alchemy:v2")
    if v2_rule:
        object.__setattr__(settings, "veyra_billing_enabled", v2_rule.enabled)
        object.__setattr__(settings, "veyra_generation_charge_amount", v2_rule.charge_amount)
    return get_billing_settings(body.rule_key or "alchemy:v2")


def _load_rules(*, force: bool = False) -> dict[str, VeyraBillingRule]:
    global _runtime_rules
    if _runtime_rules is not None and not force:
        return _runtime_rules
    raw_rules = _default_rules()
    path = billing_settings_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        raw_rules.update(_rules_from_payload(payload))
    _runtime_rules = {key: _rule_from_raw(value) for key, value in raw_rules.items()}
    return _runtime_rules


def _default_rules() -> dict[str, dict[str, Any]]:
    amount = float(settings.veyra_generation_charge_amount or 0.25)
    enabled = bool(settings.veyra_billing_enabled)
    return {
        key: {
            **value,
            "enabled": enabled,
            "charge_amount": amount,
        }
        for key, value in DEFAULT_RULES.items()
    }


def _rules_from_payload(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("rules"), list):
        return {
            _normalize_rule_key(item.get("key")): dict(item)
            for item in payload["rules"]
            if isinstance(item, dict) and item.get("key")
        }
    if "enabled" in payload or "charge_amount" in payload:
        enabled = bool(payload.get("enabled", True))
        amount = float(payload.get("charge_amount") or settings.veyra_generation_charge_amount or 0.25)
        return {
            key: {
                **value,
                "enabled": enabled,
                "charge_amount": amount,
            }
            for key, value in DEFAULT_RULES.items()
        }
    return {
        _normalize_rule_key(key): dict(value)
        for key, value in payload.items()
        if isinstance(value, dict)
    }


def _rule_from_raw(raw: dict[str, Any]) -> VeyraBillingRule:
    key = _normalize_rule_key(raw.get("key"))
    defaults = DEFAULT_RULES.get(key, {})
    agent, version = _split_key(key)
    return VeyraBillingRule(
        key=key,
        label=str(raw.get("label") or defaults.get("label") or key),
        agent=str(raw.get("agent") or defaults.get("agent") or agent),
        version=str(raw.get("version") or defaults.get("version") or version),
        enabled=bool(raw.get("enabled", defaults.get("enabled", True))),
        charge_amount=max(0.0, float(raw.get("charge_amount", defaults.get("charge_amount", 0.0)) or 0.0)),
        source=str(raw.get("source") or defaults.get("source") or key),
    )


def _normalize_rule_key(value: Any) -> str:
    key = str(value or "").strip().lower().replace("\\", ":").replace("/", ":")
    return key or "alchemy:v2"


def _split_key(key: str) -> tuple[str, str]:
    agent, _, version = key.partition(":")
    return agent or "alchemy", version or ""


def _persist_rules(rules: dict[str, VeyraBillingRule]) -> None:
    path = billing_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "currency_label": "sub2api_balance",
        "rules": [rule.model_dump() for rule in sorted(rules.values(), key=lambda item: item.key)],
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
