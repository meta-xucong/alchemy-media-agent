"""Small audit helpers for activation plans."""

from __future__ import annotations

from .contracts import CapabilityActivationPlan


def safe_activation_summary(plan: CapabilityActivationPlan) -> dict:
    return plan.summary()


def active_capability_ids(plan: CapabilityActivationPlan | dict | None) -> list[str]:
    if isinstance(plan, CapabilityActivationPlan):
        return list(plan.dependency_order)
    if not isinstance(plan, dict):
        return []
    values = plan.get("active_capability_ids") or plan.get("dependency_order") or []
    return [str(item) for item in values if str(item).strip()]
