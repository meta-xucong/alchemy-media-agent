"""Plugin boundary for active Visual Cluster contributions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...activation import ActivatedCapability, CapabilityActivationPlan, CapabilityContribution


@dataclass(frozen=True)
class VisualPluginContext:
    plan: CapabilityActivationPlan
    active: ActivatedCapability
    cluster: dict[str, Any]


class VisualCapabilityPlugin(Protocol):
    capability_id: str

    def contribute(self, context: VisualPluginContext) -> CapabilityContribution:
        ...


class BaseVisualCapabilityPlugin:
    capability_id = "visual_capability"

    def contribution(
        self,
        context: VisualPluginContext,
        *,
        prompt: list[str] | None = None,
        negative: list[str] | None = None,
        provider_requirements: list[dict[str, Any]] | None = None,
        review: dict[str, Any] | None = None,
        retry: dict[str, Any] | None = None,
        stages: list[str] | None = None,
    ) -> CapabilityContribution:
        prompt_additions = string_list(prompt or [])
        negative_additions = string_list(negative or [])
        retry_contract = dict(retry or {})
        # Retry is a capability-owned projection of already accepted guidance.
        # Do not leave Product API to reconstruct a prompt from issue names.
        # Specialized plugins may provide a narrower template themselves; the
        # default keeps the same active capability's safe prompt/negative
        # contribution bounded and auditable.
        if retry_contract and not isinstance(retry_contract.get("templates"), dict):
            retry_contract["templates"] = {
                "prompt_additions": list(prompt_additions),
                "negative_additions": list(negative_additions),
            }
        return CapabilityContribution(
            capability_id=context.active.capability_id,
            capability_version=context.active.version,
            activation_plan_id=context.plan.plan_id,
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            provider_input_requirements=list(provider_requirements or []),
            review_contract=dict(review or {}),
            retry_contract=retry_contract,
            stages=list(stages or []),
            metadata={"selected_profile": context.active.selected_profile},
        )


class MetadataCapabilityPlugin(BaseVisualCapabilityPlugin):
    def __init__(self, capability_id: str, stages: list[str]) -> None:
        self.capability_id = capability_id
        self.stages = stages

    def contribute(self, context: VisualPluginContext) -> CapabilityContribution:
        return self.contribution(context, stages=self.stages)


def as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
