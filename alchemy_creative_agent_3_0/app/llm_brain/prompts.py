"""Prompt builders for remote V3 LLM Brain runs."""

from __future__ import annotations

import json

from .contracts import BrainRunRequest


SYSTEM_PROMPT = """You are the V3 Creative OS planning brain. Return JSON only.
Do not reveal hidden reasoning. Summarize decisions as user-friendly studio notes.
Use the same language as the user's request; use Simplified Chinese for Chinese requests.
Use only the provided project context. Only selected outputs may become positive style anchors.
Unselected candidates are history only. Keep specialized-template logic out unless its explicit request context is present.
For general_template/general_creative, use subject/scene/style/lighting language by default.
Do not introduce product, packaging, label, CTA, selling-point, offer, or ad-copy concepts unless the user explicitly asks for a product/ecommerce image.
Each returned prompt plan must preserve one complete image per output; do not plan collages, split screens, contact sheets, storyboards, comparison panels, or multi-panel layouts unless the user explicitly asks for that format.
Keep every list concise: 2-5 short items. Do not wrap the JSON in markdown fences."""
CAPABILITY_ACTIVATION_INSTRUCTIONS = """At the task_profile_and_capability_activation checkpoint, classify all simultaneous visible entities.
Request only capability IDs present in capability_catalog. Attach concise reason codes, evidence IDs, and calibrated confidence.
Do not infer a real person from generic photography words alone. Distinguish real humans from illustration/CG intent.
Do not invent a professional deliverable map beyond template_capability_policy. Unknown needs stay unresolved instead of enabling every capability."""
ECOMMERCE_CONTEXT_INSTRUCTIONS = """Treat ecommerce_creative_context only as factual evidence,
user-approved literal copy, and platform constraints. Decide the complete
product-specific output set yourself. Return exactly one natural-language
intent per requested output; do not reuse a stock slot map or prescribe local
camera, crop, coordinate, typography, safe-area, overlay, or post-processing
operation."""
APPAREL_EVIDENCE_DIMENSION_INSTRUCTIONS = """When an active
apparel_on_model_evidence_profile requests more than one output, return exactly
one evidence_dimensions_by_output entry per output. Map only its allowed
evidence dimensions, use enough distinct dimensions to meet its declared
count, and treat each entry as a reviewable evidence purpose--never as a stock role,
scene, camera, crop, pose, or output-order recipe."""
PHOTOGRAPHY_CONTEXT_INSTRUCTIONS = """Treat photography_creative_context as a frozen
non-creative delivery contract. The role IDs only bind output lineage and
cardinality. Invent the complete photographic composition, scene, camera,
lighting, pose, timing, and visual direction from the user request and
reference truth. Return exactly one original whole-image natural-language
direction for every role; never import General suite/cover roles or
E-Commerce roles, slots, copy, or marketplace logic."""


def _compact_required_remote_creative_schema() -> dict:
    """Return the minimum remote contract for LLM-first specialized templates.

    E-Commerce and Photography must fail closed without a remote creative
    answer, but they do not need the provider to re-state project history,
    presentation copy, or deterministic review summaries.  Asking a remote
    model for those redundant sections makes a one-image plan needlessly
    large and can turn a valid remote Brain into a transport timeout.
    """

    # The frozen template plan and shared evidence runtime already own
    # capability gating.  The remote specialist must contribute precisely its
    # irreplaceable work: one creative image direction per frozen output.  Do
    # not make the model restate task-profile or capability bookkeeping; that
    # made compatible providers produce a large, fragile JSON envelope without
    # adding creative evidence.
    return {
        "image_set_plan": {
            "set_goal": "string",
            "image_count": "integer exactly equal to requested_image_count",
            "size": "string|null",
            "shot_plan": ["one original whole-image natural-language direction per requested output"],
            "composition_rules": ["string"],
            "quality_bar": ["string"],
        },
        "prompt_guidance": {
            "optimized_direction": "complete natural-language direction for the requested image set",
            "hard_constraints": ["string"],
            "negative_prompt_addons": ["string"],
            "consistency_strategy": "string|null",
        },
    }


def _requires_apparel_evidence_dimensions(
    ecommerce_context: dict[str, object] | None,
    *,
    requested_image_count: int,
) -> bool:
    if requested_image_count <= 1 or not isinstance(ecommerce_context, dict):
        return False
    profile = ecommerce_context.get("apparel_on_model_evidence_profile")
    return isinstance(profile, dict) and bool(profile.get("applies"))


def build_remote_payload(request: BrainRunRequest) -> str:
    payload = {
        "task": "prepare_pre_generation_image_reasoning",
        "stage": request.stage,
        "user_input": request.user_input,
        "scenario_id": request.scenario_id,
        "template_id": request.template_id,
        "project_id": request.project_id,
        "requested_image_count": request.requested_image_count,
        "requested_image_size": request.requested_image_size,
        "reasoning_depth": request.reasoning_depth,
        "project_context": request.project_context,
        "selected_output_assets": request.selected_output_assets,
        "reference_assets": request.reference_assets,
        "uploaded_assets": request.uploaded_assets,
        "shared_capabilities": request.shared_capabilities,
        "product_profile": request.product_profile,
        "capability_catalog": request.capability_catalog,
        "pre_activation_capabilities": request.pre_activation_capabilities,
        "template_capability_policy": request.template_capability_policy.model_dump(mode="json"),
        "capability_activation_instructions": CAPABILITY_ACTIVATION_INSTRUCTIONS,
        "return_schema": {
            "visual_task_profile": {
                "profile_id": "string",
                "project_id": "string|null",
                "job_id": "string",
                "template_id": "string",
                "scenario_id": "string",
                "output_medium": "image",
                "subject_entities": [
                    {
                        "entity_id": "string",
                        "entity_type": "open string",
                        "role": "string",
                        "source_asset_ids": ["string"],
                        "visible_in_target": "boolean",
                        "preservation_level": "string",
                        "confidence": "number 0-1",
                        "attributes": {},
                    }
                ],
                "preservation_targets": [],
                "allowed_changes": ["string"],
                "visual_intent_tags": ["string"],
                "commercial_goal_tags": ["string"],
                "requested_deliverable_roles": ["string"],
                "explicit_user_controls": {},
                "unknown_requirements": ["string"],
                "confidence": "number 0-1",
                "evidence": [],
            },
            "capability_activation_intent": {
                "intent_id": "string",
                "task_profile_id": "string",
                "requested_capabilities": [
                    {
                        "capability_id": "catalog ID only",
                        "activation_mode": "required|recommended|optional|forbidden",
                        "reason_codes": ["string"],
                        "evidence_ids": ["string"],
                        "requested_profile": "string|null",
                        "confidence": "number 0-1",
                    }
                ],
                "rejected_capabilities": [],
                "unresolved_signals": ["string"],
                "confidence": "number 0-1",
            },
            "intent_summary": {
                "user_goal": "string",
                "scene": "string",
                "audience": "string|null",
                "output_use": "string",
                "visual_mood": ["string"],
                "must_keep": ["string"],
                "avoid": ["string"],
            },
            "project_memory_digest": {
                "has_project_context": "boolean",
                "selected_reference_count": "integer",
                "uploaded_reference_count": "integer",
                "positive_style_rules": ["string"],
                "continuity_rules": ["string"],
                "negative_rules": ["string"],
            },
            "image_set_plan": {
                "set_goal": "string",
                "image_count": "integer exactly equal to requested_image_count",
                "size": "string|null",
                "shot_plan": ["string"],
                "evidence_dimensions_by_output": [
                    {"output_index": "integer", "evidence_dimensions": ["string"]}
                ],
                "composition_rules": ["string"],
                "quality_bar": ["string"],
            },
            "prompt_guidance": {
                "optimized_direction": "string",
                "visual_direction_addons": ["string"],
                "style_notes": ["string"],
                "layout_notes": ["string"],
                "hard_constraints": ["string"],
                "negative_prompt_addons": ["string"],
                "consistency_strategy": "string|null",
            },
            "prompt_review": {
                "status": "passed|warning",
                "checks": ["string"],
                "fixes_applied": ["string"],
                "warnings": ["string"],
            },
            "user_visible_summary": {
                "headline": "short user-facing sentence",
                "done": ["short user-facing phrases"],
                "next": ["short user-facing phrases"],
                "progress_messages": ["short progress messages"],
            },
            "checkpoints": [
                {
                    "checkpoint_id": "task_profile_and_capability_activation|intent|context|visual_strategy|prompt_guidance|pre_generation_review|post_generation_review",
                    "stage": "string",
                    "status": "completed|warning",
                    "summary": "short user-friendly planning note",
                    "inputs": ["short input facts"],
                    "outputs": ["short output decisions"],
                    "warnings": ["short warnings"],
                    "metadata": {},
                }
            ],
        },
    }
    ecommerce_context = request.metadata.get("ecommerce_creative_context")
    requires_apparel_evidence_dimensions = _requires_apparel_evidence_dimensions(
        ecommerce_context if isinstance(ecommerce_context, dict) else None,
        requested_image_count=request.requested_image_count,
    )
    if isinstance(ecommerce_context, dict) and ecommerce_context:
        payload["ecommerce_creative_context"] = ecommerce_context
        payload["ecommerce_context_instructions"] = ECOMMERCE_CONTEXT_INSTRUCTIONS
        if requires_apparel_evidence_dimensions:
            payload["ecommerce_context_instructions"] += "\n" + APPAREL_EVIDENCE_DIMENSION_INSTRUCTIONS
            payload["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"] = [
                {"output_index": "integer", "evidence_dimensions": ["allowed profile values only"]}
            ]
    photography_context = request.metadata.get("photography_creative_context")
    if isinstance(photography_context, dict) and photography_context:
        payload["photography_creative_context"] = photography_context
        payload["photography_context_instructions"] = PHOTOGRAPHY_CONTEXT_INSTRUCTIONS
    if not request.capability_catalog:
        payload.pop("capability_catalog", None)
        payload.pop("pre_activation_capabilities", None)
        payload.pop("template_capability_policy", None)
        payload.pop("capability_activation_instructions", None)
        payload["return_schema"].pop("visual_task_profile", None)
        payload["return_schema"].pop("capability_activation_intent", None)
    if request.template_capability_policy.requires_remote_creative_brain:
        compact_schema = _compact_required_remote_creative_schema()
        if requires_apparel_evidence_dimensions:
            compact_schema["image_set_plan"]["evidence_dimensions_by_output"] = [
                {"output_index": "integer", "evidence_dimensions": ["allowed profile values only"]}
            ]
        payload["return_schema"] = compact_schema
        payload["remote_response_contract"] = (
            "Return only this compact schema as strictly valid JSON. Every "
            "image_set_plan field and prompt_guidance.optimized_direction is "
            "required. Escape quotation marks inside JSON strings. Do not add "
            "hidden reasoning, project-history summaries, UI copy, or any "
            "additional top-level sections."
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
