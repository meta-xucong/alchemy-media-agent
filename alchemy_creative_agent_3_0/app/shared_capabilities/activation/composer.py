"""Compose only contributions owned by active capabilities."""

from __future__ import annotations

from .catalog import VisualCapabilityRegistry
from .contracts import CapabilityActivationPlan, CapabilityContribution, ComposedVisualContribution


class CapabilityContributionError(ValueError):
    pass


class CapabilityContributionComposer:
    def __init__(self, registry: VisualCapabilityRegistry) -> None:
        self.registry = registry

    def compose(
        self,
        plan: CapabilityActivationPlan,
        contributions: list[CapabilityContribution],
    ) -> ComposedVisualContribution:
        by_id = {item.capability_id: item for item in contributions}
        prompt: list[str] = []
        negative: list[str] = []
        provider_requirements: list[dict] = []
        reviews: list[dict] = []
        retries: list[dict] = []
        memory: list[dict] = []
        provenance: list[dict] = []
        for capability_id in plan.dependency_order:
            contribution = by_id.get(capability_id)
            if contribution is None:
                continue
            active = plan.active(capability_id)
            manifest = self.registry.manifest(capability_id, active.version if active else None)
            if active is None or manifest is None:
                raise CapabilityContributionError(f"inactive or unknown capability contribution: {capability_id}")
            if contribution.activation_plan_id != plan.plan_id or contribution.capability_version != active.version:
                raise CapabilityContributionError(f"contribution does not match frozen plan: {capability_id}")
            undeclared = set(contribution.stages) - set(manifest.contribution_stages)
            if undeclared:
                raise CapabilityContributionError(f"undeclared contribution stages for {capability_id}: {sorted(undeclared)}")
            prompt.extend(contribution.prompt_additions)
            negative.extend(contribution.negative_additions)
            provider_requirements.extend(contribution.provider_input_requirements)
            if contribution.review_contract:
                reviews.append({"capability_id": capability_id, **contribution.review_contract})
            if contribution.retry_contract:
                retries.append({"capability_id": capability_id, **contribution.retry_contract})
            if contribution.project_memory_proposal:
                memory.append({"capability_id": capability_id, **contribution.project_memory_proposal})
            provenance.append({"capability_id": capability_id, "version": active.version, "stages": contribution.stages})
        return ComposedVisualContribution(
            activation_plan_id=plan.plan_id,
            prompt_additions=_dedupe(prompt),
            negative_additions=_dedupe(negative),
            provider_input_requirements=_dedupe_dicts(provider_requirements),
            review_contracts=reviews,
            retry_contracts=retries,
            memory_proposals=memory,
            active_capability_ids=list(plan.dependency_order),
            provenance=provenance,
        )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in items if item and item.strip()))


def _dedupe_dicts(items: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in items:
        key = repr(sorted(item.items()))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
