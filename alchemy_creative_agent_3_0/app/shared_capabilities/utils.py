"""Small helpers shared by V3 capability modules."""

from __future__ import annotations

from typing import Any

from .contracts import CapabilityConstraint, CapabilityResult


def dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = " ".join(str(item or "").strip().split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def prior_fact(prior_results: list[CapabilityResult], module_id: str, key: str, default: Any = None) -> Any:
    for result in reversed(prior_results):
        if result.module_id == module_id and key in result.facts:
            return result.facts[key]
    return default


def all_prior_constraints(prior_results: list[CapabilityResult]) -> list[CapabilityConstraint]:
    constraints: list[CapabilityConstraint] = []
    for result in prior_results:
        constraints.extend(result.constraints)
    return constraints


def role_value(value: Any) -> str:
    return str(getattr(value, "value", value or "")).strip()
