"""Contracts for V3-native pre-generation thinking."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from ..schemas.models import V3BaseModel
from ..shared_capabilities.activation import (
    CapabilityActivationIntent,
    TemplateCapabilityPolicy,
    VisualTaskProfile,
    general_capability_policy,
)


class BrainIntentSummary(V3BaseModel):
    user_goal: str
    scene: str | None = None
    audience: str | None = None
    output_use: str | None = None
    visual_mood: list[str] = Field(default_factory=list)
    must_keep: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class BrainProjectMemoryDigest(V3BaseModel):
    has_project_context: bool = False
    selected_reference_count: int = 0
    uploaded_reference_count: int = 0
    positive_style_rules: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)
    negative_rules: list[str] = Field(default_factory=list)


class BrainOutputEvidenceContract(V3BaseModel):
    """A Brain-chosen, reviewable evidence purpose for one requested output."""

    output_index: int = Field(ge=1)
    evidence_dimensions: list[str] = Field(default_factory=list)


class BrainImageSetPlan(V3BaseModel):
    set_goal: str
    image_count: int = Field(default=2, ge=1)
    size: str | None = None
    shot_plan: list[str] = Field(default_factory=list)
    evidence_dimensions_by_output: list[BrainOutputEvidenceContract] = Field(default_factory=list)
    composition_rules: list[str] = Field(default_factory=list)
    quality_bar: list[str] = Field(default_factory=list)


class BrainPromptGuidance(V3BaseModel):
    optimized_direction: str
    visual_direction_addons: list[str] = Field(default_factory=list)
    style_notes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    negative_prompt_addons: list[str] = Field(default_factory=list)
    consistency_strategy: str | None = None


class BrainPromptReview(V3BaseModel):
    status: str = "passed"
    checks: list[str] = Field(default_factory=list)
    fixes_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BrainHumanNaturalnessDecision(V3BaseModel):
    """Safe receipt emitted by the existing Human Realism re-signing pass.

    The receipt is deliberately schema-only.  It records that the remote
    Brain kept or rewrote a complete candidate without exposing a rationale,
    a prompt fragment, or any renderer-facing repair instruction.
    """

    contract_version: Literal["v3_human_naturalness_decision_v1"]
    status: Literal["approved", "rewritten"]
    owner: Literal["remote_v3_llm_brain"]


class BrainCanonicalProviderPrompt(V3BaseModel):
    """One Brain-signed, renderer-ready prompt for a frozen output.

    This intentionally contains one complete natural-language instruction, not
    a list of local prompt atoms.  The provider may bind it to the frozen
    operation and reference inputs, but may not append creative, realism,
    scene, or retry wording after the Brain has approved it.
    """

    output_index: int = Field(ge=1)
    prompt: str
    review_status: Literal["approved"] = "approved"
    # This receipt remains optional for historical record readability.  New
    # enforced Human Realism jobs validate that it was explicitly supplied by
    # the remote Brain before they can materialize a renderer operation.
    semantic_preflight_status: Literal["approved"] | None = None
    # Added by Doc142 only on the existing independent Human Realism re-sign.
    # Historical/finalizer records remain readable without this receipt.
    human_naturalness_decision: BrainHumanNaturalnessDecision | None = None

    @field_validator("prompt")
    @classmethod
    def prompt_must_be_complete_text(cls, value: str) -> str:
        cleaned = " ".join(str(value or "").split())
        if len(cleaned) < 24:
            raise ValueError("canonical provider prompt is required")
        return cleaned


class BrainUserVisibleSummary(V3BaseModel):
    headline: str = "V3 已整理好画面方向。"
    done: list[str] = Field(default_factory=list)
    next: list[str] = Field(default_factory=list)
    progress_messages: list[str] = Field(default_factory=list)


class BrainCheckpoint(V3BaseModel):
    checkpoint_id: str
    stage: str
    status: str = "completed"
    summary: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrainRunRequest(V3BaseModel):
    user_input: str
    stage: str = "generate"
    scenario_id: str | None = None
    template_id: str | None = None
    project_id: str | None = None
    project_context: dict[str, Any] = Field(default_factory=dict)
    shared_capabilities: dict[str, Any] = Field(default_factory=dict)
    uploaded_assets: list[dict[str, Any]] = Field(default_factory=list)
    reference_assets: list[dict[str, Any]] = Field(default_factory=list)
    selected_output_assets: list[dict[str, Any]] = Field(default_factory=list)
    product_profile: dict[str, Any] = Field(default_factory=dict)
    requested_image_count: int = Field(default=2, ge=1)
    requested_image_size: str | None = None
    reasoning_depth: str = "balanced"
    metadata: dict[str, Any] = Field(default_factory=dict)
    capability_catalog: dict[str, Any] = Field(default_factory=dict)
    pre_activation_capabilities: dict[str, Any] = Field(default_factory=dict)
    template_capability_policy: TemplateCapabilityPolicy = Field(default_factory=general_capability_policy)

    @field_validator("user_input")
    @classmethod
    def user_input_must_not_be_empty(cls, value: str) -> str:
        cleaned = " ".join(str(value or "").split())
        if not cleaned:
            raise ValueError("user_input is required")
        return cleaned


class BrainRunResult(V3BaseModel):
    enabled: bool = True
    skipped: bool = False
    llm_used: bool = False
    fallback_used: bool = True
    provider: str = "local"
    model: str | None = None
    intent_summary: BrainIntentSummary
    project_memory_digest: BrainProjectMemoryDigest
    image_set_plan: BrainImageSetPlan
    prompt_guidance: BrainPromptGuidance
    prompt_review: BrainPromptReview
    user_visible_summary: BrainUserVisibleSummary
    checkpoints: list[BrainCheckpoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit: dict[str, Any] = Field(default_factory=dict)
    visual_task_profile: VisualTaskProfile | None = None
    capability_activation_intent: CapabilityActivationIntent | None = None
    canonical_provider_prompts: list[BrainCanonicalProviderPrompt] = Field(default_factory=list)

    def safe_metadata(self) -> dict[str, Any]:
        task_profile = self.visual_task_profile.model_dump(mode="json") if self.visual_task_profile is not None else None
        if isinstance(task_profile, dict) and self.visual_task_profile.template_id == "general_template":
            task_profile.pop("commercial_goal_tags", None)
        return {
            "enabled": self.enabled,
            "skipped": self.skipped,
            "llm_used": self.llm_used,
            "fallback_used": self.fallback_used,
            "provider": self.provider,
            "model": self.model,
            "intent_summary": self.intent_summary.model_dump(mode="json"),
            "project_memory_digest": self.project_memory_digest.model_dump(mode="json"),
            "image_set_plan": self.image_set_plan.model_dump(mode="json"),
            "prompt_guidance": self.prompt_guidance.model_dump(mode="json"),
            "prompt_review": self.prompt_review.model_dump(mode="json"),
            "user_visible_summary": self.user_visible_summary.model_dump(mode="json"),
            "checkpoints": [checkpoint.model_dump(mode="json") for checkpoint in self.checkpoints],
            "warnings": list(self.warnings),
            "audit": dict(self.audit),
            "visual_task_profile": task_profile,
            "capability_activation_intent": (
                self.capability_activation_intent.model_dump(mode="json")
                if self.capability_activation_intent is not None
                else None
            ),
            "canonical_provider_prompts": [
                item.model_dump(mode="json") for item in self.canonical_provider_prompts
            ],
        }
