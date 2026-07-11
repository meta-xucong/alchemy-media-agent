"""Public activation API for V3 shared capabilities."""

from .audit import active_capability_ids, safe_activation_summary
from .catalog import VisualCapabilityRegistry, default_manifest_inventory
from .composer import CapabilityContributionComposer, CapabilityContributionError
from .contracts import (
    ActivatedCapability,
    ActivationEvidence,
    CapabilityActivationIntent,
    CapabilityActivationPlan,
    CapabilityBudgetDecision,
    CapabilityCatalogEntry,
    CapabilityCatalogSnapshot,
    CapabilityConflictDecision,
    CapabilityContribution,
    CapabilityCost,
    CapabilityGraphAudit,
    CapabilityPlanAmendment,
    ComposedVisualContribution,
    InactiveCapability,
    PreservationTarget,
    RejectedCapability,
    RequestedCapability,
    TemplateCapabilityBinding,
    TemplateCapabilityPolicy,
    VisualCapabilityManifest,
    VisualSubjectEntity,
    VisualTaskProfile,
)
from .fallback import build_task_profile_and_intent
from .planner import CapabilityActivationError, CapabilityActivationPlanner
from .template_policies import compatibility_policy, ecommerce_capability_policy, general_capability_policy

__all__ = [
    "ActivatedCapability",
    "ActivationEvidence",
    "CapabilityActivationError",
    "CapabilityActivationIntent",
    "CapabilityActivationPlan",
    "CapabilityActivationPlanner",
    "CapabilityBudgetDecision",
    "CapabilityCatalogEntry",
    "CapabilityCatalogSnapshot",
    "CapabilityConflictDecision",
    "CapabilityContribution",
    "CapabilityContributionComposer",
    "CapabilityContributionError",
    "CapabilityCost",
    "CapabilityGraphAudit",
    "CapabilityPlanAmendment",
    "ComposedVisualContribution",
    "InactiveCapability",
    "PreservationTarget",
    "RejectedCapability",
    "RequestedCapability",
    "TemplateCapabilityBinding",
    "TemplateCapabilityPolicy",
    "VisualCapabilityManifest",
    "VisualCapabilityRegistry",
    "VisualSubjectEntity",
    "VisualTaskProfile",
    "active_capability_ids",
    "build_task_profile_and_intent",
    "compatibility_policy",
    "default_manifest_inventory",
    "ecommerce_capability_policy",
    "general_capability_policy",
    "safe_activation_summary",
]
