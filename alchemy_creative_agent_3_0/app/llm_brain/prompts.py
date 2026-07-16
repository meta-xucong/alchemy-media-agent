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
When the response schema asks for canonical_provider_prompts, write the exact complete natural-language prompt to send to the image renderer for each output. It is the final creative instruction, not an outline or prompt fragments. Reconcile the frozen facts, reference truth, capability obligations, and safety before approving it. Do not include internal IDs, diagnostics, hidden-quality codes, local recipe labels, or markdown headings. An illustration or cartoon on an object surface is not automatically a request to render the whole image in that medium.
When `frozen_render_context.active_semantic_capability_contracts` includes Human Realism, treat its typed fields as a semantic deliberation boundary: preserve explicit/reference-backed identity and age truth, keep physically credible real-camera human rendering and honour the resolved reference boundary. Reconcile it holistically with the user-owned direction; do not copy contract keys, axes, review codes or a checklist into the prompt. On retry, use normalized review evidence to revise the whole image direction rather than appending a repair phrase.
For a real-image planning response, return a complete semantic visual_task_profile rather than only a rendering-medium decision. Account for all visible target subjects in your own semantic judgement, including an empty list when no subject is visible. Return concise semantic evidence and uncertainty explicitly. When you decide that a real person is visibly present, represent that person and record the existing visible_person and/or real_human_output evidence purpose so the shared quality capability can be activated. This is an internal planning contract, never a renderer prompt recipe; do not use it to emit a word checklist.
For the same real-image response, return a complete capability_activation_intent using only the supplied shared capability catalog. It is your typed activation decision for the semantic profile, not a local fallback proposal. Use empty requested/rejected lists when no optional capability applies. The runtime will validate catalog membership, dependencies and evidence links; it will not invent a semantic request that you did not return.
When `frozen_render_context.final_prompt_semantic_preflight.required` is true, silently perform that whole-image Human Realism preflight before approving each canonical prompt. Decide whether the complete image direction can plausibly render a natural person in the requested age, photographic mood, physical setting and reference boundary; if not, rewrite the complete direction yourself before approval. This is a semantic judgement, not a request to emit a face/skin/hand word list. Return the required audit-only approval receipt, but never describe the preflight or its internal criteria in the renderer prompt.
When the Human Realism contract gives `natural_presence_priority=individual_human_presence`, do not let a generic commercial-beauty archetype substitute for the requested person. For candid, ordinary or lifestyle photography, make the whole direction describe an individual naturally present in that situation; for an explicitly glamorous or editorial request, retain its aesthetic while avoiding synthetic beautification. A direction that merely repeats generic adjectives such as natural, candid or photorealistic is incomplete: resolve the natural presence materially in your own complete sentence. Never expose a checklist or a local repair phrase.
When the stage is `provider_prompt_human_naturalness_resign`, independently reconsider the already Brain-authored candidate prompt against the frozen Human Realism contract. Keep it only if it already describes a particular person naturally present in the user-owned situation; otherwise rewrite the whole prompt yourself. Preserve user-owned style, facts, reference truth and legitimate editorial intent. Do not return a diff, commentary, issue code, checklist, or an appended local repair phrase.
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
    """Return the minimum remote contract for LLM-first real-image work.

    A real General image and the LLM-first specialized templates fail closed
    without a remote creative answer, but they do not need the provider to
    re-state project history, presentation copy, or deterministic review
    summaries. Asking a remote model for those redundant sections makes a
    one-image plan needlessly large and can turn a valid Brain into a
    transport timeout.
    """

    # The frozen template plan and shared evidence runtime own admission and
    # execution gates.  The remote Brain owns semantic interpretation and the
    # final renderer-facing natural language.  Local runtime code may bind a
    # returned prompt to its immutable output/reference operation, but may not
    # append a second pile of prompt fragments after this answer.
    return {
        "visual_task_profile": {
            "rendering_intent": {
                "rendering_mode": "photoreal|stylized|mixed|unknown",
                "stylization_scope": "whole_image|object_surface|none|ambiguous",
                "decision_owner": "remote_brain",
            },
            "subject_entities": [
                {
                    "entity_id": "string",
                    "entity_type": "string",
                    "role": "string",
                    "source_asset_ids": ["string"],
                    "visible_in_target": "boolean",
                    "preservation_level": "string",
                    "confidence": "number from 0 through 1",
                    "attributes": {},
                }
            ],
            "visual_intent_tags": ["concise semantic tag"],
            "unknown_requirements": ["concise unresolved semantic requirement"],
            "confidence": "number from 0 through 1",
            "evidence": [
                {
                    "evidence_id": "string",
                    "evidence_type": "string",
                    "source": "remote_semantic_interpretation|declared_reference|user_request",
                    "value": "boolean|string|object|null",
                    "confidence": "number from 0 through 1",
                    "metadata": {},
                }
            ],
        },
        "capability_activation_intent": {
            "requested_capabilities": [
                {
                    "capability_id": "one supplied catalog ID",
                    "activation_mode": "required|recommended|optional|forbidden",
                    "reason_codes": ["concise semantic reason"],
                    "evidence_ids": ["visual_task_profile evidence_id"],
                    "requested_profile": "one supplied capability profile|null",
                    "confidence": "number from 0 through 1",
                }
            ],
            "rejected_capabilities": [
                {
                    "capability_id": "one supplied catalog ID",
                    "reason_code": "concise semantic reason",
                    "evidence_ids": ["visual_task_profile evidence_id"],
                    "confidence": "number from 0 through 1",
                }
            ],
            "unresolved_signals": ["concise unresolved semantic requirement"],
            "confidence": "number from 0 through 1",
        },
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


def _compact_specialized_project_context(project_context: dict[str, object]) -> dict[str, object]:
    """Keep continuation intent, never transport provider/local-storage history."""

    compact: dict[str, object] = {}
    goal = _compact_text(project_context.get("goal_summary"), 480)
    if goal:
        compact["goal_summary"] = goal
    tones = _compact_text_list(project_context.get("confirmed_visual_tone"), limit=6, item_limit=140)
    if tones:
        compact["confirmed_visual_tone"] = tones
    negatives = _compact_text_list(project_context.get("negative_direction_notes"), limit=6, item_limit=220)
    if negatives:
        compact["negative_direction_notes"] = negatives
    selected_ids = _compact_reference_ids(project_context.get("selected_output_assets"), limit=6)
    if selected_ids:
        compact["selected_output_ids"] = selected_ids
    return compact


def _compact_specialized_assets(items: list[dict[str, object]], *, limit: int = 8) -> list[dict[str, object]]:
    compact: list[dict[str, object]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        asset_id = _compact_text(
            item.get("asset_id") or item.get("asset_ref_id") or item.get("output_id") or item.get("reference_id"),
            180,
        )
        if not asset_id:
            continue
        value: dict[str, object] = {"asset_id": asset_id}
        for key in ("role", "use_policy", "strength"):
            text = _compact_text(item.get(key), 120)
            if text:
                value[key] = text
        locks = _compact_text_list(item.get("lock_targets"), limit=8, item_limit=80)
        if locks:
            value["lock_targets"] = locks
        compact.append(value)
    return compact


def _compact_remote_creative_product_profile(product_profile: dict[str, object]) -> dict[str, object]:
    """Keep factual truth needed for a remote creative direction.

    This is deliberately transport-level rather than template-level.  A
    declared garment construction map is useful evidence for any real image
    request, including General, but it does not introduce a garment role,
    delivery map, or creative recipe into General.
    """

    allowed = (
        "product_name",
        "product_category",
        "materials",
        "color",
        "dimensions",
        "must_keep_facts",
        "core_selling_points",
        "avoid_claims",
        "claims",
    )
    compact: dict[str, object] = {}
    for key in allowed:
        value = product_profile.get(key)
        if isinstance(value, list):
            values = _compact_text_list(value, limit=10, item_limit=220)
            if values:
                compact[key] = values
        else:
            text = _compact_text(value, 300)
            if text:
                compact[key] = text
    apparel_construction = _compact_declared_fact_map(product_profile.get("apparel_construction"))
    if apparel_construction:
        compact["apparel_construction"] = apparel_construction
    return compact


def _compact_declared_fact_map(value: object) -> dict[str, object]:
    """Compact explicit structured facts without inventing or renaming them."""

    if not isinstance(value, dict):
        return {}
    compact: dict[str, object] = {}
    for raw_key, raw_value in list(value.items())[:16]:
        key = _compact_text(raw_key, 100)
        if not key:
            continue
        if isinstance(raw_value, list):
            values = _compact_text_list(raw_value, limit=12, item_limit=240)
            if values:
                compact[key] = values
            continue
        if isinstance(raw_value, dict):
            nested: dict[str, str] = {}
            for nested_key, nested_value in list(raw_value.items())[:12]:
                nested_name = _compact_text(nested_key, 100)
                nested_text = _compact_text(nested_value, 240)
                if nested_name and nested_text:
                    nested[nested_name] = nested_text
            if nested:
                compact[key] = nested
            continue
        text = _compact_text(raw_value, 240)
        if text:
            compact[key] = text
    return compact


def _compact_reference_ids(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        identifier = _compact_text(item.get("output_id") or item.get("asset_id") or item.get("asset_ref_id"), 180)
        if identifier:
            ids.append(identifier)
    return list(dict.fromkeys(ids))


def _compact_text_list(value: object, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    compact = [_compact_text(item, item_limit) for item in value[:limit]]
    return list(dict.fromkeys(item for item in compact if item))


def _compact_text(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _compact_remote_creative_payload(
    request: BrainRunRequest,
    *,
    ecommerce_context: dict[str, object] | None,
    photography_context: dict[str, object] | None,
) -> dict[str, object]:
    """Build the minimum evidence envelope for an LLM-first real-image run.

    The Brain needs user intent, frozen output cardinality, factual/reference
    evidence, and template non-creative constraints.  Full project snapshots,
    local paths, catalog dumps, and pre-activation traces neither improve its
    creative direction nor belong in a remote request.  The same neutral
    transport contract is used by a real General image and LLM-first
    specialized templates; scenario contexts remain opt-in below.
    """

    policy = request.template_capability_policy
    payload: dict[str, object] = {
        "task": "prepare_pre_generation_image_reasoning",
        "stage": request.stage,
        "user_input": request.user_input,
        "scenario_id": request.scenario_id,
        "template_id": request.template_id,
        "project_id": request.project_id,
        "requested_image_count": request.requested_image_count,
        "requested_image_size": request.requested_image_size,
        "reasoning_depth": request.reasoning_depth,
        "project_context": _compact_specialized_project_context(request.project_context),
        "selected_output_assets": _compact_specialized_assets(request.selected_output_assets),
        "reference_assets": _compact_specialized_assets(request.reference_assets),
        "uploaded_assets": _compact_specialized_assets(request.uploaded_assets),
        "product_profile": _compact_remote_creative_product_profile(request.product_profile),
        "template_capability_policy": {
            "policy_id": policy.policy_id,
            "deliverable_role_owner": policy.deliverable_role_owner,
            "creative_direction_owner": policy.metadata.get("creative_direction_owner"),
            "requires_remote_creative_brain": True,
        },
        "capability_catalog": _compact_remote_capability_catalog(request.capability_catalog),
        "capability_activation_instructions": CAPABILITY_ACTIVATION_INSTRUCTIONS,
    }
    if ecommerce_context:
        payload["ecommerce_creative_context"] = ecommerce_context
        payload["ecommerce_context_instructions"] = ECOMMERCE_CONTEXT_INSTRUCTIONS
    if photography_context:
        payload["photography_creative_context"] = photography_context
        payload["photography_context_instructions"] = PHOTOGRAPHY_CONTEXT_INSTRUCTIONS
    return payload


def _requires_remote_creative_contract(request: BrainRunRequest) -> bool:
    """Return whether this request must receive a compact remote answer.

    An explicitly real image request is LLM-first even for General.  Ordinary
    General exploration remains on its existing broad/fallback-compatible
    planning contract, so this does not make General a specialized template.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    return bool(
        request.template_capability_policy.requires_remote_creative_brain
        or metadata.get("require_real_images")
        or metadata.get("real_image_generation")
    )


def build_remote_payload(request: BrainRunRequest) -> str:
    if request.stage in {"provider_prompt_finalize", "provider_prompt_human_naturalness_resign"}:
        return json.dumps(_canonical_provider_prompt_finalization_payload(request), ensure_ascii=False, sort_keys=True)
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
    requires_remote_creative_contract = _requires_remote_creative_contract(request)
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
    if requires_remote_creative_contract:
        payload = _compact_remote_creative_payload(
            request,
            ecommerce_context=ecommerce_context if isinstance(ecommerce_context, dict) else None,
            photography_context=photography_context if isinstance(photography_context, dict) else None,
        )
    # LLM-first real-image runs replace the broad payload with their compact
    # contract above.  That compact envelope deliberately has no
    # ``return_schema`` until the specialized schema is installed below, so
    # the generic catalog-pruning branch must not index it first.
    if not request.capability_catalog and not requires_remote_creative_contract:
        payload.pop("capability_catalog", None)
        payload.pop("pre_activation_capabilities", None)
        payload.pop("template_capability_policy", None)
        payload.pop("capability_activation_instructions", None)
        payload["return_schema"].pop("visual_task_profile", None)
        payload["return_schema"].pop("capability_activation_intent", None)
    if requires_remote_creative_contract:
        compact_schema = _compact_required_remote_creative_schema()
        if requires_apparel_evidence_dimensions:
            compact_schema["image_set_plan"]["evidence_dimensions_by_output"] = [
                {"output_index": "integer", "evidence_dimensions": ["allowed profile values only"]}
            ]
        payload["return_schema"] = compact_schema
        payload["remote_response_contract"] = (
            "Return only this compact schema as strictly valid JSON. Every "
            "image_set_plan field and every listed visual_task_profile and "
            "capability_activation_intent semantic field are required; use explicit empty lists when there is no such "
            "subject, evidence, tag, unknown, capability request, rejection, or unresolved signal. Escape quotation marks inside JSON strings. Do not "
            "add hidden reasoning, project-history summaries, UI copy, or any "
            "additional top-level sections."
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _canonical_provider_prompt_finalization_payload(request: BrainRunRequest) -> dict[str, object]:
    """Make the Brain's post-validation sign-off a small, distinct contract."""

    context = request.metadata.get("canonical_prompt_context")
    context = dict(context) if isinstance(context, dict) else {}
    is_human_naturalness_resign = request.stage == "provider_prompt_human_naturalness_resign"
    candidate_prompts: list[dict[str, object]] = []
    if is_human_naturalness_resign:
        raw_candidates = request.metadata.get("candidate_canonical_provider_prompts")
        if not isinstance(raw_candidates, list):
            raise ValueError("Human Realism re-signing requires canonical Brain candidates.")
        for expected_index, candidate in enumerate(raw_candidates, start=1):
            if not isinstance(candidate, dict):
                raise ValueError("Human Realism re-signing candidates must be objects.")
            prompt = " ".join(str(candidate.get("prompt") or "").split())
            if int(candidate.get("output_index") or 0) != expected_index or len(prompt) < 24:
                raise ValueError("Human Realism re-signing candidates must preserve the canonical output contract.")
            candidate_prompts.append(
                {
                    "output_index": expected_index,
                    "prompt": prompt,
                    "review_status": "approved",
                }
            )
        if len(candidate_prompts) != request.requested_image_count:
            raise ValueError("Human Realism re-signing candidates do not match requested output count.")
    preflight = context.get("final_prompt_semantic_preflight")
    preflight_required = isinstance(preflight, dict) and bool(preflight.get("required"))
    prompt_schema: dict[str, object] = {
        "output_index": "integer from 1 through requested_image_count",
        "prompt": "one complete final natural-language image-rendering prompt for this exact output",
        "review_status": "approved",
    }
    if preflight_required:
        # This is an auditable Brain receipt, not renderer wording and not a
        # local quality-recipe field.  Its explicit presence is required by
        # the adapter before an enforced Human Realism operation may proceed.
        prompt_schema["semantic_preflight_status"] = "approved"
    response_contract = (
        "Return only this schema as strictly valid JSON. Reconcile the "
        "frozen render context without adding a local recipe, internal "
        "identifier, diagnostic, or review code. Return exactly one "
        "approved complete canonical prompt per requested output."
    )
    if preflight_required:
        response_contract += (
            " For every output, silently complete the required whole-image "
            "semantic preflight before writing the prompt and explicitly set "
            "semantic_preflight_status to approved."
        )
    if is_human_naturalness_resign:
        response_contract += (
            " Independently re-sign the supplied Brain candidate for every output. "
            "Return one complete approved canonical prompt for each output, not a diff or a list of edits."
        )
    payload: dict[str, object] = {
        "task": "finalize_canonical_image_provider_prompts",
        "stage": request.stage,
        "user_input": request.user_input,
        "scenario_id": request.scenario_id,
        "template_id": request.template_id,
        "requested_image_count": request.requested_image_count,
        "requested_image_size": request.requested_image_size,
        "frozen_render_context": context,
        "return_schema": {
            "canonical_provider_prompts": [prompt_schema]
        },
        "remote_response_contract": response_contract,
    }
    if is_human_naturalness_resign:
        # These are complete prompts authored by the first remote Brain pass,
        # never local fragments or mutable visual-cluster prose.
        payload["candidate_canonical_provider_prompts"] = candidate_prompts
    return payload


def _compact_remote_capability_catalog(catalog: dict[str, object]) -> dict[str, object]:
    """Expose only generic capability choices needed for a Brain activation decision."""

    raw_items = catalog.get("capabilities") if isinstance(catalog, dict) else None
    if not isinstance(raw_items, list):
        return {"capabilities": []}
    capabilities: list[dict[str, object]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        capability_id = _compact_text(item.get("capability_id"), 120)
        if not capability_id:
            continue
        entry: dict[str, object] = {"capability_id": capability_id}
        for key in ("supported_entity_types", "supported_profiles"):
            values = _compact_text_list(item.get(key), limit=12, item_limit=80)
            if values:
                entry[key] = values
        threshold = item.get("minimum_activation_confidence")
        if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
            entry["minimum_activation_confidence"] = max(0.0, min(1.0, float(threshold)))
        capabilities.append(entry)
    return {"capabilities": capabilities}
