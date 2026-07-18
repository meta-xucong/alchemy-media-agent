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
When `frozen_render_context.active_semantic_capability_contracts` includes Human Realism, treat its typed fields as a semantic deliberation boundary: preserve explicit/reference-backed identity and age truth, keep physically credible real-camera human rendering and honour the resolved reference boundary. Reconcile it holistically with the user-owned direction; do not copy contract keys, axes, review codes or a checklist into the prompt. When the existing age-fidelity context says the current prompt owns the age direction, distinguish an ordinary same-age continuation from an explicit same-person age transition: retain identity-critical feature relationships, but do not inherit the source person's apparent age, body maturity, or whole-image styling as hidden locks. Re-express the complete person for the requested age while keeping scene, wardrobe, hair, light, camera, mood, and expression under their resolved owners. Only the Brain makes this semantic decision and authors the complete final prompt. On retry, use normalized review evidence to revise the whole image direction rather than appending a repair phrase.
For a real-image planning response, return a complete semantic visual_task_profile rather than only a rendering-medium decision. Account for all visible target subjects in your own semantic judgement, including an empty list when no subject is visible. Return concise semantic evidence and uncertainty explicitly. When you decide that a real person is visibly present, represent that person and record the existing visible_person and/or real_human_output evidence purpose so the shared quality capability can be activated. This is an internal planning contract, never a renderer prompt recipe; do not use it to emit a word checklist.
For the same real-image response, return a complete capability_activation_intent using only the supplied shared capability catalog. It is your typed activation decision for the semantic profile, not a local fallback proposal. Use empty requested/rejected lists when no optional capability applies. The runtime will validate catalog membership, dependencies and evidence links; it will not invent a semantic request that you did not return.
When `frozen_render_context.final_prompt_semantic_preflight.required` is true, silently perform that whole-image Human Realism preflight before approving each canonical prompt. Decide whether the complete image direction can plausibly render a natural person in the requested age, photographic mood, physical setting and reference boundary; if not, rewrite the complete direction yourself before approval. This is a semantic judgement, not a request to emit a face/skin/hand word list. Return the required audit-only approval receipt, but never describe the preflight or its internal criteria in the renderer prompt.
When the Human Realism contract gives `natural_presence_priority=individual_human_presence`, do not let a generic commercial-beauty archetype substitute for the requested person. If its personhood or photographic-material obligations are present, resolve them as a whole-image judgement: the person must read as specifically present in the requested situation and photographic human material must remain camera-observed within the requested mood. A generic assertion such as photorealistic detail is not material resolution: in the whole direction you author, reconcile how the person is physically observed through the scene's light, depth and natural surface response without adding a face/skin micro-detail or beauty checklist. When `complexion_rendering_requirement=preserve_reference_or_user_owned_complexion_with_scene_balanced_color`, preserve the complexion owned by the reference or user while resolving it naturally with the photographic scene's light, tonal separation and color relationship. Scene treatment must not substitute for the person's own complexion; retain legitimate mood and aesthetics, and make the decision in the complete image direction you author. This does not infer a preferred complexion from ethnicity or use a color formula; an explicit user-owned commercial complexion direction remains valid and must be resolved in the final Brain-authored prompt. When `expression_ownership_requirement=situation_owned_unless_explicit_user_direction`, an explicitly requested expression remains user-owned; otherwise choose a response that belongs to the person, action, attention and mood you author, never an unrequested default display or advertising smile. When `expression_resolution_requirement=individual_situation_not_stock_geometry`, a generic request such as gentle, natural, joyful or friendly is an affect intention, not permission to infer the same open-mouth or tooth-showing geometry used by a commercial presenter. Preserve warmth when it belongs to the person's moment, but resolve the complete expression through that individual's attention, action, timing and relationship to the scene. Do not force neutrality and do not ban smiling; simply refuse to manufacture a repeated showroom smile when the situation does not require it. A smile is allowed when it is user-owned or emerges from that individual's situation; it must not become a uniform camera-presentational default merely because the image is pleasant or commercially polished. Treat an absent expression as intentional creative latitude, not a blank to fill with positive affect: setting pleasantness or commercial polish alone never justifies a display smile, and do not invent a decorative action merely to make one seem justified. Before approving the complete direction, ask whether replacing the person with the same generic presentational smile would leave the situation unchanged; if it would, resolve a more individual, situation-grounded presence yourself. This is not a prohibition on smiling and not an instruction to force a neutral face. When no independently useful moment calls for a particular affect, keep the person ordinarily present without manufacturing one. A generic adjective such as natural, candid or photorealistic plus a static pose is not an expression decision: in the one complete direction you author, make the person's ordinary attention, awareness or response legible as part of the situation, without selecting from a fixed expression vocabulary. Do not make this decision with an expression vocabulary, face-detail checklist or fixed alternate-expression catalogue. For candid, ordinary or lifestyle photography, make the whole direction describe that individual naturally present in the situation; for an explicitly glamorous or editorial request, retain its aesthetic while avoiding synthetic beautification. A direction that merely repeats generic adjectives such as natural, candid or photorealistic is incomplete: resolve the natural presence materially in your own complete sentence. Never expose a checklist or a local repair phrase.
For any child, teen or other age-sensitive person request, keep the semantic plan age-appropriate, fully clothed, non-sexual and appropriate to the stated ordinary setting. When the user request is already within that safe boundary, return the required JSON planning contract rather than a prose refusal. This is a remote safety interpretation boundary only: do not turn it into a local branch, an age-specific capability, or a renderer prompt checklist.
When the finalization context requires `human_naturalness_decision` (historical `provider_prompt_human_naturalness_resign` records remain readable), independently reconsider the complete Brain-authored direction against the frozen Human Realism contract before returning the final prompt. Keep it only if it already describes a particular person with a user-authorized or situation-owned expression in the user-owned situation and resolves their photographic material as observed in the scene; an invented pleasant display affect is not situation-owned merely because the scene is attractive, a smile may remain when it is user-owned or situation-grounded but a generic presentational smile is not approved merely because it looks friendly, a generic natural/candid label with a static pose does not resolve the person's attention or ordinary response, and a generic photorealistic-detail label does not resolve materiality. Otherwise rewrite the whole prompt yourself. Preserve user-owned style, facts, reference truth and legitimate editorial intent. Do not return a diff, commentary, issue code, checklist, or an appended local repair phrase. Return the required schema-only Human Naturalness decision receipt as `approved` or `rewritten`; it is audit data, never renderer wording or hidden reasoning.
Keep every list concise: 2-5 short items. Do not wrap the JSON in markdown fences."""
HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS = """Expression authenticity is a shared semantic hard gate. Treat a generic affect request such as a smile, pleasant, joyful, friendly, or natural expression as the user's emotional intention, not as a fixed mouth, teeth, or camera-facing presentation geometry. Only an explicit physical expression direction, such as a broad open-mouth or tooth-showing smile, is a hard user-owned rendering control. Otherwise decide the visible response from the person's attention, action, timing, and situation. A straight-on commercial frame must not automatically become a stock presenter grin with the same open-mouth or tooth geometry across unrelated people. A genuine smile may pass when it belongs to the person's visible moment, but do not turn a polite commercial mood into a standardized showroom smile merely because the frame is attractive or catalog-like. If the complete direction would remain unchanged after replacing the person with a generic smiling model, resolve a more individual presence in the complete Brain-authored direction. This is a semantic judgement, not a keyword list, fixed expression vocabulary, renderer exclusion wording, or local repair phrase. The shared pixel reviewer must treat a physically correct but interchangeable presenter smile as retryable human_expression_context evidence."""
HUMAN_COMPLEXION_COMMERCIAL_AESTHETIC_INSTRUCTIONS = """Commercial complexion is a shared semantic judgement, not a local prompt recipe. When a consumer-facing brief visibly includes a person or model and its commercial presentation, explicit user direction, or declared target-market context makes a brighter and fairer complexion part of the intended aesthetic, honour that preference as user-owned visual direction even when the supplied reference is warmer or darker. Resolve it as a modestly brighter, clean, naturally light complexion whose overall reading is softly neutral and light with restrained peach-pink warmth rather than a golden or orange cast; let brightness come from clean scene light, not lifted exposure. Preserve facial identity and age, fine-grained and irregular real skin microtexture, age-appropriate tonal variation, and restrained matte highlights that follow the face's planes instead of diffusing across the whole face. Reconcile it with a neutral-to-slightly-warm scene white balance and clean exposure, avoiding a muddy yellow or green cast without making the skin look bleached. Keep the person's complexion as its own material judgement rather than allowing a blue, yellow, green, or otherwise colored set light to make the face or exposed skin read unintentionally golden, tan, gray, or orange; preserve the scene's color while keeping the requested commercial complexion stable. The complete direction should make subtle, camera-resolved, nonuniform skin microvariation legible at the visible scale, rather than describing or producing a uniformly airbrushed surface. Before returning the final provider prompt, do not approve it until this active commercial complexion decision is expressed as a complete natural-language visual direction—including its neutral hue, restrained warmth, separation from scene color cast, camera-resolved microvariation, and face-plane highlight behavior—rather than being reduced to a generic word such as natural or fair. If there is no visible person, or the work is not a commercial presentation and the user has not asked for this complexion direction, do not invent a hidden bright-complexion treatment. A user-assigned complexion or skin-finish reference may guide only complexion, white balance, and skin material; never inherit that reference's identity, age, face, hair, wardrobe, scene, or mood. Do not infer a preferred complexion from ethnicity alone, and do not treat any historical adult or child sample as a universal visual template. Do not bleach, flatten, recolour the person, airbrush or wax the skin, apply beauty-filter glow, or use a local skin patch; resolve the complete scene, not an isolated skin correction, in the final direction you author."""
SYSTEM_PROMPT = (
    f"{SYSTEM_PROMPT}\n"
    f"{HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS}\n"
    f"{HUMAN_COMPLEXION_COMMERCIAL_AESTHETIC_INSTRUCTIONS}"
)
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
        "human_expression_authenticity_instructions": HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS,
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
    requires_remote_creative_contract = _requires_remote_creative_contract(request)
    if requires_remote_creative_contract:
        # Real-image requests never need the broad compatibility payload. Build
        # the compact contract directly so the discarded broad structure does
        # not add local work or make the transport path look like it has two
        # competing prompt contracts.
        ecommerce_context = request.metadata.get("ecommerce_creative_context")
        photography_context = request.metadata.get("photography_creative_context")
        ecommerce_context = ecommerce_context if isinstance(ecommerce_context, dict) else None
        photography_context = photography_context if isinstance(photography_context, dict) else None
        payload = _compact_remote_creative_payload(
            request,
            ecommerce_context=ecommerce_context,
            photography_context=photography_context,
        )
        requires_apparel_evidence_dimensions = _requires_apparel_evidence_dimensions(
            ecommerce_context,
            requested_image_count=request.requested_image_count,
        )
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
    decision_requirement = context.get("human_naturalness_decision")
    decision_required = (
        is_human_naturalness_resign
        or (
            isinstance(decision_requirement, dict)
            and decision_requirement.get("required") is True
            and decision_requirement.get("contract_version") == "v3_human_naturalness_decision_v1"
            and decision_requirement.get("owner") == "remote_v3_llm_brain"
            and isinstance(decision_requirement.get("frozen_binding"), dict)
        )
    )
    if decision_required and not (
        isinstance(decision_requirement, dict)
        and decision_requirement.get("required") is True
        and decision_requirement.get("contract_version") == "v3_human_naturalness_decision_v1"
        and decision_requirement.get("owner") == "remote_v3_llm_brain"
        and isinstance(decision_requirement.get("frozen_binding"), dict)
    ):
        raise ValueError("Human Realism re-signing requires a frozen naturalness decision contract.")
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
    if decision_required:
        prompt_schema["human_naturalness_decision"] = {
            "contract_version": "v3_human_naturalness_decision_v1",
            "status": "approved|rewritten",
            "owner": "remote_v3_llm_brain",
        }
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
    if decision_required:
        response_contract += (
            " Independently review the complete Brain-authored direction for every output before final approval. "
            "Treat approval as a high bar: use it only when the candidate already resolves a particular person in the user-owned situation, "
            "rather than replacing missing person detail with a default commercial-presentational or universally beautified portrait. "
            "A generic natural/candid label plus a static pose does not by itself resolve the person's attention or ordinary response. "
            "A smile may remain when user-owned or situation-grounded, but a generic friendly camera-presentational smile is not sufficient approval. "
            "A generic photorealistic-detail label does not by itself resolve photographic materiality. "
            "Otherwise set the decision to rewritten and author one complete situation-owned canonical prompt yourself. "
            "Return one complete approved canonical prompt for each output, not a diff or a list of edits. "
            "For every output, return the required schema-only human_naturalness_decision "
            "with contract_version v3_human_naturalness_decision_v1, owner remote_v3_llm_brain, "
            "and status approved or rewritten."
        )
    professional_anchor_contract = context.get("professional_face_identity_quality_contract")
    if isinstance(professional_anchor_contract, dict):
        response_contract += (
            " For the Professional Face Identity anchor-pack contract, likeness to the selected person is the first-order "
            "criterion. Preserve the person's age direction and distinctive feature relationships before aesthetic polish. "
            "The complete prompt must require camera-observed human materiality: visible but subtle natural skin texture, "
            "non-uniform complexion, ordinary eyelid/lip detail, and small real-life asymmetries. Do not substitute a generic "
            "perfect, poreless, retouched, pageant, fashion, or beauty-app face. This is a semantic quality requirement, "
            "not a static prompt recipe; keep the selected view and user-owned styling intact."
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
        "human_expression_authenticity_instructions": HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS,
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
