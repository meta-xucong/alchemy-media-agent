"""Small deterministic helpers for the E-Commerce Scenario Pack."""

from __future__ import annotations

from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, dict):
        return [f"{clean_text(key)}: {clean_text(val)}" for key, val in value.items() if clean_text(val)]
    text = clean_text(value)
    if not text:
        return []
    separators = [",", ";", "|", "\n"]
    parts = [text]
    for separator in separators:
        if separator in text:
            parts = [clean_text(item) for item in text.replace("\n", separator).split(separator)]
            break
    return [item for item in parts if item]


def first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return default


def unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = clean_text(item)
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def parameter_value(parameters: dict[str, Any], profile: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in parameters and parameters[name] not in (None, "", []):
            return parameters[name]
        if name in profile and profile[name] not in (None, "", []):
            return profile[name]
    return None
