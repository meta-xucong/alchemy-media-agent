from __future__ import annotations

import re

from app.schemas import CreativeOrchestratorDecision, ImagePromptPlan, PromptCase, PromptCaseSummary
from app.services.intent_integrity import compile_prompt_artifact
from app.services.ids import new_id
from app.services.reference_delivery import build_reference_delivery_contract, reference_delivery_prompt_section
from app.services.visual_signals import build_case_visual_signals
from app.services.visual_grammar_lock import build_visual_grammar_contract


_BASE_NEGATIVE_TERMS = [
    "unlicensed third-party logos",
    "celebrity faces",
    "protected characters",
    "distorted anatomy",
    "unreadable text",
    "low-resolution artifacts",
    "unintended direct copying of unrelated references",
]

A4_PORTRAIT_SIZE = "2400x3392"
A4_LANDSCAPE_SIZE = "3392x2400"
PORTRAIT_SIZE = "1024x1536"
LANDSCAPE_SIZE = "1536x1024"
SQUARE_SIZE = "1024x1024"
MIN_CUSTOM_SIZE_SIDE = 1024
MAX_CUSTOM_SIZE_SIDE = 3840
QR_EXCLUSION_PATTERN = re.compile(
    "(不要|不需要|无需|無需|禁止|去掉|移除|不要展示|不要出现|不出现|without|no|do\\s+not\\s+include|do\\s+not\\s+show)"
    ".{0,24}"
    "(二维码|二維碼|qr\\s*code|qr-code|qrcode|scan\\s*code|扫码|掃碼)",
    re.IGNORECASE,
)
QR_EXCLUSION_TERMS = [
    "invented QR code",
    "unrequested scan code",
    "empty QR placeholder",
    "decorative QR card",
]


def summarize_intent(user_prompt: str) -> str:
    clean = " ".join(user_prompt.strip().split())
    if len(clean) <= 140:
        return clean
    return clean[:137].rstrip() + "..."


def compose_prompt_plan(
    *,
    mode: str,
    user_prompt: str,
    cases: list[PromptCase],
    output: dict,
    requested_output: dict | None = None,
    orchestrator_decision: CreativeOrchestratorDecision | None = None,
    asset_context: dict | None = None,
) -> ImagePromptPlan:
    primary = cases[0] if cases else None
    reference_cases = [primary] if mode == "template_customize" and primary else cases
    reusable = [] if mode == "template_customize" and primary else _reusable_elements(reference_cases)
    visual_grammar_contract = build_visual_grammar_contract(
        mode=mode,
        user_prompt=user_prompt,
        cases=reference_cases if reference_cases else cases,
        asset_context=asset_context,
        orchestrator_decision=orchestrator_decision,
    )
    prompt_source = "local_prompt_composer"
    creative_prompt = ""
    if _should_use_claude_final_prompt(orchestrator_decision):
        creative_prompt = _normalise_prompt_text(orchestrator_decision.final_prompt)
        prompt_source = "claude_final_prompt"
    if not creative_prompt:
        creative_prompt = _build_prompt(user_prompt, primary, reusable, orchestrator_decision=orchestrator_decision)
    template_section = _template_frame_section(primary) if mode == "template_customize" and primary else ""
    asset_sections = _asset_sections_for_compiler(asset_context)
    visual_grammar_section = _visual_grammar_section_for_compiler(visual_grammar_contract)
    qr_excluded = _qr_explicitly_excluded(user_prompt)
    task_intent_payload = _task_intent_payload(orchestrator_decision)
    language_lock = _language_lock_from_task_intent(task_intent_payload)
    information_integrity = (
        visual_grammar_contract.get("information_integrity")
        if isinstance(visual_grammar_contract, dict) and isinstance(visual_grammar_contract.get("information_integrity"), dict)
        else {}
    )
    negative_prompt = _merge_negative_prompt(
        orchestrator_decision.negative_prompt if orchestrator_decision else "",
        _BASE_NEGATIVE_TERMS,
    )
    if orchestrator_decision:
        negative_prompt = _merge_negative_prompt(
            negative_prompt,
            orchestrator_decision.prompt_directives.negative_prompt_additions[:8],
        )
        if orchestrator_decision.task_intent:
            negative_prompt = _merge_negative_prompt(
                negative_prompt,
                orchestrator_decision.task_intent.negative_prompt_additions[:8],
            )
    if mode == "template_customize" and primary and _template_allows_text_elements(primary, user_prompt=user_prompt):
        negative_prompt = _remove_negative_terms(negative_prompt, {"text"})
    if information_integrity.get("active"):
        information_negative_terms = [
            "missing requested source content",
            "missing requested CTA or contact details",
            "copied source menu grid",
            "copied source poster layout",
            "source layout overriding selected template",
        ]
        if information_integrity.get("qr_intent"):
            information_negative_terms.append("missing requested or source QR")
        else:
            information_negative_terms.extend(QR_EXCLUSION_TERMS)
        negative_prompt = _merge_negative_prompt(
            negative_prompt,
            information_negative_terms,
        )
    if qr_excluded:
        negative_prompt = _merge_negative_prompt(negative_prompt, QR_EXCLUSION_TERMS)
    if language_lock.get("locked"):
        negative_prompt = _merge_negative_prompt(
            negative_prompt,
            [
                "English template copy",
                "foreign-language visible text",
                "untranslated template labels",
                "placeholder recipe text",
            ],
        )
    provider_parameters = _build_provider_parameters(
        output,
        orchestrator_decision,
        visual_grammar_contract=visual_grammar_contract,
    )
    requested_output = requested_output or {}
    inferred_prompt_size = _infer_prompt_size_for_parameters(
        provider_parameters,
        user_prompt=user_prompt,
        requested_output=requested_output,
    )
    provider_parameters = _apply_prompt_size_inference(
        provider_parameters,
        user_prompt=user_prompt,
        requested_output=requested_output,
        inferred_size=inferred_prompt_size,
    )
    aspect_lock = _aspect_lock_from_requested_output(requested_output)
    if not aspect_lock.get("locked") and inferred_prompt_size:
        aspect_lock = _aspect_lock_from_value(inferred_prompt_size, source="user_prompt.size")
    prompt_transform_request = _prompt_transform_request_from_output(requested_output or {})
    provider_parameters = _apply_aspect_lock(provider_parameters, aspect_lock)
    control_sections = _prompt_control_sections(
        qr_excluded=qr_excluded,
        language_lock=language_lock,
        aspect_lock=aspect_lock,
    )
    reference_delivery = (
        (asset_context or {}).get("reference_delivery")
        if isinstance((asset_context or {}).get("reference_delivery"), dict)
        else build_reference_delivery_contract(asset_context)
    )
    reference_delivery_section = reference_delivery_prompt_section(reference_delivery)
    if reference_delivery_section:
        control_sections.append(
            {
                "intent_id": "intent_reference_delivery_contract",
                "source": "v2_reference_delivery",
                "priority": "required",
                "title": "REFERENCE DELIVERY CONTRACT",
                "text": reference_delivery_section,
            }
        )
    prompt, prompt_integrity = compile_prompt_artifact(
        user_prompt=user_prompt,
        creative_prompt=creative_prompt,
        creative_source=prompt_source,
        template_section=template_section,
        asset_sections=asset_sections,
        visual_grammar_section=visual_grammar_section,
        control_sections=control_sections,
        semantic_user_compaction=creative_prompt if prompt_source == "claude_final_prompt" else "",
    )
    if prompt_source == "claude_final_prompt":
        prompt_source = "compiled_from_claude_and_manifest"
    count = int(provider_parameters.get("count", 1))
    count = max(1, min(count, 8))
    provider_parameters["count"] = count
    style_basis = [
        {
            "case_id": case.case_id,
            "title": case.title,
            "reused_elements": _case_reuse_notes(case, orchestrator_decision=orchestrator_decision),
            "excluded_elements": ["raw image content", "third-party marks", "protected identities"],
        }
        for case in reference_cases[:4]
    ]
    risk_notes = [
        "Template and retrieved cases are used as visual structure references only.",
        "Final images must not copy raw provider images or protected brand marks.",
    ]
    if mode == "template_customize" and primary:
        risk_notes.insert(0, "The hand-selected template is the highest-priority visual anchor.")
    if reference_delivery.get("acceptance", {}).get("requires_pixel_review"):
        risk_notes.append("Reference delivery requires V2 pixel evidence before automatic delivery.")
    if orchestrator_decision:
        risk_notes.extend(orchestrator_decision.prompt_directives.safety_notes[:6])
    explanation = _build_explanation(mode, reference_cases)
    if orchestrator_decision:
        rationale = orchestrator_decision.prompt_rationale or orchestrator_decision.prompt_directives.case_selection_rationale
        explanation = (
            f"Creative orchestration provider: {orchestrator_decision.provider}. "
            f"{rationale or explanation}"
        )
    return ImagePromptPlan(
        plan_id=new_id("plan"),
        mode=mode,  # type: ignore[arg-type]
        prompt=prompt,
        negative_prompt=negative_prompt,
        style_basis=style_basis,
        user_variables={
            "user_prompt": user_prompt,
            "source_mode": mode,
            "primary_case_id": primary.case_id if primary else None,
            "orchestrator_decision_id": orchestrator_decision.decision_id if orchestrator_decision else None,
            "orchestrator_provider": orchestrator_decision.provider if orchestrator_decision else None,
            "orchestrator_task_intent": task_intent_payload,
            "prompt_source": prompt_source,
            "claude_final_prompt_used": bool(orchestrator_decision and _should_use_claude_final_prompt(orchestrator_decision)),
            "prompt_integrity": prompt_integrity,
            "revision_source": output.get("revision_source"),
            "template_lock_enabled": bool((asset_context or {}).get("template_lock_contract")),
            "template_lock_contract": (asset_context or {}).get("template_lock_contract"),
            "task_relationship_model": (asset_context or {}).get("task_relationship_model"),
            "asset_frame_strategy": (asset_context or {}).get("asset_frame_strategy"),
            "template_visual_grammar_plan": (asset_context or {}).get("template_visual_grammar_plan"),
            "visual_grammar_lock_enabled": bool(visual_grammar_contract),
            "visual_grammar_contract": visual_grammar_contract,
            "information_integrity_lock_enabled": bool(information_integrity.get("active")),
            "information_integrity_contract": information_integrity,
            "aspect_lock": aspect_lock,
            "language_lock": language_lock,
            "prompt_transform_mode": prompt_transform_request.get("transform_mode"),
            "prompt_transform_profile": prompt_transform_request,
            "asset_binding_plan": (asset_context or {}).get("asset_binding_plan"),
            "provider_input_plan": (asset_context or {}).get("provider_input_plan"),
            "reference_delivery": reference_delivery,
            "uploaded_assets": (asset_context or {}).get("uploaded_assets", []),
            "provider_input_asset_ids": [
                item.get("asset_id")
                for item in (asset_context or {}).get("provider_input_images", [])
                if isinstance(item, dict) and item.get("asset_id")
            ],
        },
        provider_parameters=provider_parameters,
        risk_notes=risk_notes,
        explanation=explanation,
    )


def summaries_from_cases(cases: list[PromptCase]) -> list[PromptCaseSummary]:
    return [
        PromptCaseSummary(
            case_id=case.case_id,
            title=case.title,
            category=case.category,
            summary=case.summary,
            preview_url=case.preview_url,
            style_tags=case.style_tags,
            use_case_tags=case.use_case_tags,
            risk_tags=case.risk_tags,
            why_selected="Used as prompt composition evidence.",
        )
        for case in cases
    ]


def _should_use_claude_final_prompt(orchestrator_decision: CreativeOrchestratorDecision | None) -> bool:
    if not orchestrator_decision:
        return False
    if orchestrator_decision.provider != "claude-code" or orchestrator_decision.fallback_reason:
        return False
    # This is only an availability check.  Do not crop the Claude decision here:
    # the compiler owns capacity management and will use this decision for
    # semantic compression when the complete provider artifact is too large.
    return bool(_normalise_prompt_text(orchestrator_decision.final_prompt))


def _clean_prompt_text(value: str, *, limit: int) -> str:
    clean = _normalise_prompt_text(value)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _normalise_prompt_text(value: str) -> str:
    clean = " ".join(str(value or "").strip().split())
    return _sanitize_downstream_prompt(clean)


def _template_frame_section(template: PromptCase) -> str:
    anchor = _template_anchor_directive(template)
    if not anchor:
        return ""
    return (
        f"TEMPLATE LOCK: use the hand-selected template '{template.title}' as the visual frame. "
        f"Preserve its composition discipline, spatial hierarchy, lighting logic, background density, layout rhythm, "
        f"mood, and typography treatment. Reusable visual grammar from the anchor: visual skeleton: {anchor}. "
        "The template controls the frame only: user-requested subjects, products, faces, logos, copy, and required "
        "reference assets replace compatible template slots instead of being silently downgraded."
    )


def _visual_grammar_section_for_compiler(contract: dict | None) -> str:
    if not isinstance(contract, dict):
        return ""
    mode = str(contract.get("mode") or "")
    title = str(contract.get("primary_anchor_title") or "selected visual reference")
    anchor = str(contract.get("anchor_directive") or contract.get("visual_signal_brief") or "").strip()
    if not mode and not anchor:
        return ""
    parts = [
        f"V2 visual grammar mode: {mode or 'active'}.",
        "Visual Grammar Lock is active.",
        f"Frame anchor: {title}.",
        "Preserve the frame's composition discipline, spatial hierarchy, lighting logic, background density, mood, layout rhythm, and typography treatment.",
        "User semantic content controls the actual subject, product, face, logo, copy, offer, and business meaning; required uploaded references remain binding evidence. Adapt compatible template slots instead of deleting those facts.",
    ]
    if anchor:
        parts.append(f"Anchor evidence: {anchor}")
    if mode == "template_visual_grammar_lock":
        parts.append(
            "TEMPLATE LOCK is active: the selected template is the highest-priority visual frame; "
            "when a subordinate creative preference conflicts with that frame, let the template win."
        )
    elif mode == "auto_visual_grammar_lock":
        parts.append(
            "AUTO VISUAL GRAMMAR LOCK is active: use one primary curated case as the main visual grammar anchor. "
            "Do not average multiple cases into a vague hybrid."
        )
    elif mode == "uploaded_frame_visual_grammar":
        parts.append(
            "UPLOADED FRAME VISUAL GRAMMAR is active: the requested uploaded frame owns composition and layout. "
            "Retrieved case supplies polish only, is not the frame owner, and the uploaded layout/composition wins."
        )
    relationship = contract.get("task_relationship_model")
    if isinstance(relationship, dict):
        relationship_name = str(relationship.get("primary_relationship") or "").strip()
        directive = str(relationship.get("prompt_directive") or "").strip()
        if relationship_name:
            parts.append(f"Resolved asset relationship: {relationship_name}.")
        if directive:
            parts.append(f"Relationship directive: {directive}")
        uploaded_count = relationship.get("uploaded_asset_count")
        if relationship_name in {"replace_template_subject", "replace_template_food_subject"} and isinstance(uploaded_count, int) and uploaded_count > 1:
            parts.append(
                f"All {uploaded_count} uploaded replacement images must be accounted for as distinct food/product intentions inside the active template hierarchy."
            )
    visual_plan = contract.get("template_visual_grammar_plan")
    if isinstance(visual_plan, dict) and visual_plan:
        transfer_parts = []
        for key, label in (
            ("template_frame_directive", "Template frame"),
            ("visual_hierarchy_directive", "Visual hierarchy"),
            ("asset_distribution_directive", "Asset distribution"),
            ("asset_materialization_directive", "Asset materialization"),
            ("virtual_content_directive", "Virtual content"),
            ("typography_directive", "Typography"),
            ("module_narrative_directive", "Module narrative"),
            ("layout_completion_directive", "Module completion"),
        ):
            value = str(visual_plan.get(key) or "").strip()
            if value:
                transfer_parts.append(f"{label}: {value}")
        if transfer_parts:
            parts.append("TEMPLATE VISUAL GRAMMAR TRANSFER: " + " ".join(transfer_parts))
        fidelity_gates = [str(item).strip() for item in (visual_plan.get("template_fidelity_gates") or []) if str(item).strip()]
        if fidelity_gates:
            parts.append("Template fidelity gates: " + "; ".join(fidelity_gates))
    information_integrity = contract.get("information_integrity")
    source_layout_risk = contract.get("source_layout_risk")
    if isinstance(source_layout_risk, dict) and source_layout_risk.get("detected"):
        correspondence = (
            "Food-to-copy, offer-to-product, and QR/CTA correspondence"
            if isinstance(information_integrity, dict) and information_integrity.get("qr_intent")
            else "Food-to-copy and offer-to-product correspondence"
        )
        parts.append(
            "Source-layout risk detected. CONTENT EXTRACTION LOCK: preserve requested source facts inside the template's own "
            "information hierarchy; do not copy its overall grid, full menu grid, or original information architecture. "
            f"{correspondence} must remain semantic relationships and must not stretch the canvas."
        )
    if isinstance(information_integrity, dict) and information_integrity.get("active"):
        parts.append(
            "Information integrity is active: retain every explicitly requested source fact and relationship. "
            "Food-to-copy and offer-to-product correspondence must remain correct; Do not invent QR codes, scan-code modules, empty scan cards, or placeholders."
        )
    frame_strategy = contract.get("asset_frame_strategy")
    if isinstance(frame_strategy, dict) and frame_strategy.get("continuation_frame"):
        parts.append(
            "STARRED HISTORY CONTINUATION FRAME: preserve the selected history image's composition, lighting, palette, spatial hierarchy, and visual rhythm while applying the current user edit; replace the conflicting reference detail when it conflicts with that edit."
        )
    if isinstance(frame_strategy, dict) and frame_strategy.get("content_extraction"):
        parts.append(
            "CONTENT EXTRACTION LOCK: use the selected template for the new visual frame; never make the uploaded source frame dominant, and uploaded source content must not replace the selected template hierarchy."
        )
    return " ".join(part for part in parts if part)


def _asset_sections_for_compiler(asset_context: dict | None) -> list[dict]:
    if not isinstance(asset_context, dict):
        return []
    sections: list[dict] = []
    reference_indexes: dict[str, int] = {}
    for image in asset_context.get("provider_input_images") or []:
        if not isinstance(image, dict):
            continue
        asset_id = str(image.get("asset_id") or "")
        try:
            reference_index = int(image.get("reference_index") or 0)
        except (TypeError, ValueError):
            reference_index = 0
        if asset_id and reference_index > 0:
            reference_indexes[asset_id] = reference_index
    relationship = asset_context.get("task_relationship_model")
    if isinstance(relationship, dict):
        relationship_text = str(relationship.get("prompt_directive") or "").strip()
        uploaded_count = relationship.get("uploaded_asset_count")
        if (
            str(relationship.get("primary_relationship") or "") in {"replace_template_subject", "replace_template_food_subject"}
            and isinstance(uploaded_count, int)
            and uploaded_count > 1
        ):
            relationship_text = (
                relationship_text
                + f" All {uploaded_count} uploaded replacement images must be accounted for as distinct food/product intentions inside the template hierarchy."
            ).strip()
        if reference_indexes:
            relationship_text = (
                relationship_text
                + f" Provider input images required: {len(reference_indexes)} uploaded reference image(s)."
            ).strip()
        if relationship_text:
            if str(relationship.get("primary_relationship") or "") == "extract_composite_content":
                relationship_text = "UPLOADED CONTENT SOURCE: " + relationship_text
            sections.append(
                {
                    "intent_id": "intent_asset_relationship",
                    "title": "TASK RELATIONSHIP",
                    "role": "asset_relationship",
                    "constraint_strength": "strong",
                    "role_source": str(relationship.get("source") or "asset_binding"),
                    "prompt_instruction": relationship_text,
                }
            )
    plan = asset_context.get("asset_binding_plan")
    bindings = plan.get("bindings") if isinstance(plan, dict) else []
    if not isinstance(bindings, list):
        return sections
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        asset_id = str(binding.get("asset_id") or "")
        role = str(binding.get("role") or "uploaded_reference")
        strength = str(binding.get("constraint_strength") or "strong")
        fusion_mode = str(binding.get("fusion_mode") or "reference")
        target = str(binding.get("target_surface") or "").strip()
        placement = binding.get("placement_intent") if isinstance(binding.get("placement_intent"), dict) else {}
        target_label = str(placement.get("target_label") or target or "the compatible template slot").strip()
        reference_index = reference_indexes.get(asset_id)
        reference_label = f"Image {reference_index}" if reference_index else "the uploaded reference"
        role_rule = _asset_role_compiler_rule(role=role, fusion_mode=fusion_mode, target_label=target_label)
        user_note = str(binding.get("asset_notes") or "").strip()
        note_clause = f" User asset note: {user_note}" if user_note else ""
        sections.append(
            {
                "intent_id": f"intent_asset_{asset_id}" if asset_id else f"intent_asset_{len(sections) + 1}",
                "asset_id": asset_id or None,
                "role": role,
                "role_source": str(binding.get("role_source") or "asset_binding"),
                "constraint_strength": strength,
                "provider_input_required": bool(binding.get("provider_input_required")),
                "reference_index": reference_index,
                "prompt_instruction": (
                    f"{reference_label} is an uploaded reference image with role {role}, {strength} constraint, and fusion mode {fusion_mode}. "
                    f"Fusion policy: {fusion_mode}. "
                    f"{role_rule}{note_clause}"
                ),
            }
        )
    return sections


def _asset_role_compiler_rule(*, role: str, fusion_mode: str, target_label: str) -> str:
    if fusion_mode == "template_slot_replacement":
        return (
            f"Use it as a concrete replacement for {target_label}; preserve its visible identity, shape, proportions, "
            "and complete contribution inside the selected template frame. Do not convert it into a generic style cue, "
            "an arbitrary crop, pasted source frames, or a pasted source-photo panel."
        )
    if fusion_mode == "composite_content_source":
        return (
            f"Use it as semantic content evidence for {target_label}; preserve explicitly requested content while rebuilding "
            "it inside the active frame, without copying the source layout."
        )
    if role == "logo_reference" and fusion_mode == "logo_product_surface":
        return (
            f"Use it as the actual logo reference on {target_label}; preserve logo shape, proportions, colors, and readable text. "
            "Do not place it as a poster footer, corner badge, watermark, border decoration, or separate sticker."
        )
    rules = {
        "subject_reference": "Use it as the concrete subject reference; preserve visible identity, shape, and key proportions.",
        "face_reference": "Use it as the face-identity reference; preserve identity cues while the current prompt owns styling and scene.",
        "logo_reference": "Use it as the logo reference; preserve logo shape and place it on the requested target surface.",
        "background_reference": "Use it as the requested background reference when compatible with the active frame.",
        "style_reference": "Use it only for the explicitly requested compatible style, light, material, color, or mood cues.",
        "composition_reference": "Use it for the explicitly requested composition or camera relationship without overriding a selected template frame.",
        "color_reference": "Use it for the requested palette and accent-color relationship.",
        "negative_reference": "Avoid the visual traits represented by this reference.",
    }
    return rules.get(role, "Use it according to the resolved V2 asset intent.")


def _prompt_control_sections(*, qr_excluded: bool, language_lock: dict, aspect_lock: dict) -> list[dict]:
    sections: list[dict] = []
    if qr_excluded:
        sections.append(
            {
                "intent_id": "intent_qr_exclusion",
                "source": "user_request",
                "priority": "required",
                "title": "REQUIRED EXCLUSION",
                "text": (
                    "Do not invent QR codes. Do not include QR codes, scan-code modules, QR placeholders, empty scan cards, or decorative square "
                    "code areas. This overrides any selected-template or reference cue that contains a QR-safe area."
                ),
            }
        )
    language_instruction = str(language_lock.get("prompt_instruction") or "").strip()
    if language_instruction:
        sections.append(
            {
                "intent_id": "intent_visible_text_language",
                "source": str(language_lock.get("source") or "orchestrator_task_intent"),
                "priority": "required",
                "title": "VISIBLE TEXT REQUIREMENT",
                "text": language_instruction,
            }
        )
    aspect_instruction = str(aspect_lock.get("prompt_instruction") or "").strip()
    if aspect_instruction:
        sections.append(
            {
                "intent_id": "intent_aspect_ratio",
                "source": str(aspect_lock.get("source") or "requested_output"),
                "priority": "required",
                "title": "ASPECT RATIO REQUIREMENT",
                "text": aspect_instruction,
            }
        )
    return sections


def _apply_asset_context_guard(prompt: str, *, asset_context: dict | None) -> str:
    block = prompt_asset_context_block(asset_context)
    if not block:
        return prompt
    guarded = f"{block}\n\nDownstream creative prompt:\n{prompt}"
    return _clean_prompt_text(guarded, limit=4200)


def _sanitize_downstream_prompt(value: str) -> str:
    clean = str(value or "")
    replacements = [
        (r"\bcase_github_[a-z0-9_.-]+\b", "selected visual reference"),
        (r"\bgithub_evolinkai_[a-z0-9_.-]+\b", "curated visual reference"),
        (r"\basset_[a-z0-9_.-]+\b", "uploaded visual reference"),
        (r"\bprovider_id\b", "source"),
        (r"\bsource_url\b", "source"),
        (r"\bapi[_ -]?key\b", "credential"),
        (r"\bEvoLinkAI\b", "curated reference"),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


def _merge_negative_prompt(base: str, additions: list[str] | tuple[str, ...]) -> str:
    terms: list[str] = []
    for raw in [base, *additions]:
        if not raw:
            continue
        for item in str(raw).replace("，", ",").split(","):
            clean = " ".join(item.strip().split())
            if clean:
                terms.append(clean)
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return ", ".join(unique)


def _build_provider_parameters(
    output: dict,
    orchestrator_decision: CreativeOrchestratorDecision | None,
    *,
    visual_grammar_contract: dict[str, object] | None = None,
) -> dict:
    internal_keys = {
        "prompt",
        "negative_prompt",
        "revision_source",
        "disable_semantic_cache",
        "prompt_transform_mode",
        "prompt_transform_profile",
    }
    params: dict[str, object] = {}
    if orchestrator_decision:
        params.update(
            {
                str(key): value
                for key, value in orchestrator_decision.provider_parameters.items()
                if str(key) not in internal_keys
            }
        )
    params.update({str(key): value for key, value in dict(output).items() if str(key) not in internal_keys})
    information_integrity = (
        visual_grammar_contract.get("information_integrity")
        if isinstance(visual_grammar_contract, dict) and isinstance(visual_grammar_contract.get("information_integrity"), dict)
        else {}
    )
    try:
        count = int(params.get("count", 1))
    except Exception:
        count = 1
    for key in ("aspect_ratio", "size"):
        if params.get(key) in {"", "auto", "default", None}:
            params.pop(key, None)
    output_size = _size_from_width_height(params)
    if output_size and not _has_dimension(params):
        params["size"] = output_size
    params["count"] = max(1, min(count, 8))
    params["quality"] = params.get("quality", "high")
    return params


def _infer_prompt_size_for_parameters(params: dict, *, user_prompt: str, requested_output: dict) -> str | None:
    if _has_manual_dimension(requested_output) or _has_dimension(params):
        return None
    return _infer_size_from_prompt(user_prompt)


def _apply_prompt_size_inference(
    params: dict,
    *,
    user_prompt: str,
    requested_output: dict,
    inferred_size: str | None = None,
) -> dict:
    if _has_manual_dimension(requested_output) or _has_dimension(params):
        return params
    inferred = inferred_size or _infer_size_from_prompt(user_prompt)
    if not inferred:
        return params
    next_params = dict(params)
    next_params["size"] = inferred
    return next_params


def _has_manual_dimension(value: dict) -> bool:
    for key in ("size", "aspect_ratio"):
        raw = value.get(key)
        if _clean_dimension_value(raw):
            return True
    return bool(_size_from_width_height(value))


def _size_from_width_height(value: dict) -> str | None:
    width = _positive_int(value.get("width"))
    height = _positive_int(value.get("height"))
    if width is None or height is None:
        return None
    return _normalize_custom_size(width, height)


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(float(str(value).strip()))
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _has_dimension(params: dict) -> bool:
    return bool(_clean_dimension_value(params.get("size")) or _clean_dimension_value(params.get("aspect_ratio")))


def _infer_size_from_prompt(prompt: str) -> str | None:
    prompt_text = prompt or ""
    explicit_size = _explicit_size_from_prompt(prompt_text)
    if explicit_size:
        return explicit_size
    if _mentions_a4(prompt_text):
        if _mentions_landscape(prompt_text):
            return A4_LANDSCAPE_SIZE
        return A4_PORTRAIT_SIZE
    if _mentions_square(prompt_text):
        return SQUARE_SIZE
    if _mentions_portrait(prompt_text):
        return PORTRAIT_SIZE
    if _mentions_landscape(prompt_text):
        return LANDSCAPE_SIZE
    return None


def _explicit_size_from_prompt(prompt: str) -> str | None:
    dimensions = _explicit_dimensions_from_prompt(prompt)
    if not dimensions:
        return None
    width, height = dimensions
    return _normalize_custom_size(width, height)


def _legacy_explicit_dimensions_from_prompt(prompt: str) -> tuple[int, int] | None:
    text = str(prompt or "")
    if not text:
        return None
    width_words = r"(?:宽度|宽|畫寬|画宽|width|w)"
    height_words = r"(?:高度|高|畫高|画高|height|h)"
    number = r"([1-9]\d{1,4})"
    unit = r"(?:\s*(?:px|像素|cm|厘米|mm|毫米))?"
    separators = r"(?:\s*[*xX×乘,，/\\| ]+\s*)"
    patterns = [
        rf"{width_words}\s*[:：=]?\s*{number}{unit}{separators}{height_words}\s*[:：=]?\s*{number}{unit}",
        rf"{height_words}\s*[:：=]?\s*{number}{unit}{separators}{width_words}\s*[:：=]?\s*{number}{unit}",
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        first = int(match.group(1))
        second = int(match.group(2))
        return (first, second) if index == 0 else (second, first)
    generic = re.search(
        rf"(?:尺寸|画幅|畫幅|size|dimension)\s*[:：=]?\s*{number}{unit}{separators}{number}{unit}",
        text,
        flags=re.IGNORECASE,
    )
    if generic:
        return int(generic.group(1)), int(generic.group(2))
    return None


def _explicit_dimensions_from_prompt(prompt: str) -> tuple[int, int] | None:
    text = str(prompt or "")
    if not text:
        return None
    labeled = _labeled_dimensions_from_text(text)
    if labeled:
        return labeled
    generic = _generic_dimensions_from_text(text)
    if generic:
        return generic
    return _legacy_explicit_dimensions_from_prompt(text)


def _labeled_dimensions_from_text(text: str) -> tuple[int, int] | None:
    number = r"(?P<value>[1-9]\d{1,4})"
    unit = r"(?:\s*(?:px|pixel|pixels|\u50cf\u7d20|cm|\u5398\u7c73|mm|\u6beb\u7c73))?"
    width_labels = (
        r"\u5bbd\u5ea6|\u5bbd|\u756b\u5bbd|\u753b\u5bbd|"
        r"(?<![A-Za-z])width(?![A-Za-z])|(?<![A-Za-z])w(?![A-Za-z])"
    )
    height_labels = (
        r"\u9ad8\u5ea6|\u9ad8|\u756b\u9ad8|\u753b\u9ad8|"
        r"(?<![A-Za-z])height(?![A-Za-z])|(?<![A-Za-z])h(?![A-Za-z])"
    )
    label_before_value = re.compile(
        rf"(?P<label>{width_labels}|{height_labels})\s*[:\uff1a=]?\s*{number}{unit}",
        flags=re.IGNORECASE,
    )
    value_before_label = re.compile(
        rf"{number}{unit}\s*(?P<label>{width_labels}|{height_labels})",
        flags=re.IGNORECASE,
    )
    hits: list[tuple[int, str, int]] = []
    for pattern in (label_before_value, value_before_label):
        for match in pattern.finditer(text):
            label = str(match.group("label") or "").lower()
            kind = "height" if _is_height_label(label) else "width"
            hits.append((match.start(), kind, int(match.group("value"))))
    hits.sort(key=lambda item: item[0])
    best: tuple[int, int] | None = None
    best_span: int | None = None
    for index, first in enumerate(hits):
        for second in hits[index + 1 :]:
            if first[1] == second[1]:
                continue
            span = second[0] - first[0]
            if span > 80:
                continue
            width = first[2] if first[1] == "width" else second[2]
            height = first[2] if first[1] == "height" else second[2]
            if best_span is None or span < best_span:
                best = (width, height)
                best_span = span
            break
    return best


def _is_height_label(label: str) -> bool:
    return label in {
        "\u9ad8",
        "\u9ad8\u5ea6",
        "\u756b\u9ad8",
        "\u753b\u9ad8",
        "height",
        "h",
    }


def _generic_dimensions_from_text(text: str) -> tuple[int, int] | None:
    size_labels = (
        r"\u5c3a\u5bf8|\u753b\u5e45|\u756b\u5e45|\u753b\u5e03|\u756b\u5e03\u5c3a\u5bf8|"
        r"size|dimension|dimensions|canvas"
    )
    number = r"([1-9]\d{1,4})"
    unit = r"(?:\s*(?:px|pixel|pixels|\u50cf\u7d20|cm|\u5398\u7c73|mm|\u6beb\u7c73))?"
    separators = r"(?:\s*(?:[*xX\u00d7\u4e58:/\uff1a\uff0f\\|\-]|by)\s*)"
    generic = re.search(
        rf"(?:{size_labels})\s*[:\uff1a=]?\s*.{{0,16}}?{number}{unit}{separators}{number}{unit}",
        text,
        flags=re.IGNORECASE,
    )
    if generic:
        return int(generic.group(1)), int(generic.group(2))
    return None


def _normalize_custom_size(width: int, height: int) -> str | None:
    if width <= 0 or height <= 0:
        return None
    width_f = float(width)
    height_f = float(height)
    scale = 1.0
    if width_f < MIN_CUSTOM_SIZE_SIDE or height_f < MIN_CUSTOM_SIZE_SIDE:
        scale = max(MIN_CUSTOM_SIZE_SIDE / width_f, MIN_CUSTOM_SIZE_SIDE / height_f)
    if max(width_f * scale, height_f * scale) > MAX_CUSTOM_SIZE_SIDE:
        scale = MAX_CUSTOM_SIZE_SIDE / max(width_f, height_f)
    normalized_width = max(1, int(round(width_f * scale)))
    normalized_height = max(1, int(round(height_f * scale)))
    return f"{normalized_width}x{normalized_height}"


def _mentions_a4(prompt: str) -> bool:
    return bool(
        re.search(
            r"(?<![A-Za-z0-9])A\s*4(?![A-Za-z0-9])|A4\s*(?:大小|尺寸|画幅|比例|版式|纸|图|海报)?",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _mentions_square(prompt: str) -> bool:
    return bool(re.search(r"(方图|正方形|方形|1\s*[:：]\s*1|\bsquare\b)", prompt, flags=re.IGNORECASE))


def _mentions_portrait(prompt: str) -> bool:
    return bool(
        re.search(
            r"(竖版|竖向|纵向|竖图|竖幅|海报竖版|9\s*[:：]\s*16|3\s*[:：]\s*4|\bportrait\b)",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _mentions_landscape(prompt: str) -> bool:
    return bool(
        re.search(
            r"(横版|横向|横图|横幅|宽幅|16\s*[:：]\s*9|4\s*[:：]\s*3|\blandscape\b)",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _aspect_lock_from_requested_output(requested_output: dict) -> dict[str, object]:
    raw_size = requested_output.get("size")
    raw_aspect = requested_output.get("aspect_ratio")
    size = _clean_dimension_value(raw_size)
    aspect = _clean_dimension_value(raw_aspect)
    locked_value = size or aspect
    if not locked_value:
        inferred_size = _size_from_width_height(requested_output)
        if inferred_size:
            return _aspect_lock_from_value(inferred_size, source="output.size")
    if not locked_value:
        return {
            "mode": "auto",
            "locked": False,
            "source": "auto",
            "value": "",
            "aspect_ratio": "",
            "prompt_instruction": "",
        }
    return _aspect_lock_from_value(locked_value, source="output.size" if size else "output.aspect_ratio")


def _aspect_lock_from_value(locked_value: str, *, source: str) -> dict[str, object]:
    ratio = _ratio_from_dimension_or_ratio(locked_value)
    return {
        "mode": "manual",
        "locked": True,
        "source": source,
        "value": locked_value,
        "aspect_ratio": ratio,
        "prompt_instruction": f"Required output aspect ratio: {ratio}." if ratio else "",
    }


def _prompt_transform_request_from_output(requested_output: dict) -> dict[str, str]:
    requested = str(requested_output.get("prompt_transform_mode") or "").strip().lower()
    alias_map = {
        "original": "stable",
        "strict": "enhanced",
        "off": "exploration",
    }
    transform_mode = alias_map.get(requested, requested)
    if transform_mode not in {"stable", "enhanced", "exploration"}:
        transform_mode = ""
    fidelity_mode = {
        "stable": "original",
        "enhanced": "strict",
        "exploration": "off",
    }.get(transform_mode, "")
    return {
        "source": "output.prompt_transform_mode" if transform_mode else "v2_mode_fallback",
        "requested_mode": requested,
        "transform_mode": transform_mode,
        "fidelity_mode": fidelity_mode,
    }


def _apply_aspect_lock(params: dict, aspect_lock: dict[str, object]) -> dict:
    if not aspect_lock.get("locked"):
        return params
    next_params = dict(params)
    value = str(aspect_lock.get("value") or "").strip()
    source = str(aspect_lock.get("source") or "")
    if value:
        if source.endswith(".size"):
            next_params["size"] = value
        else:
            next_params["aspect_ratio"] = value
    return next_params


def _append_aspect_lock_instruction(prompt: str, aspect_lock: dict[str, object]) -> str:
    instruction = str(aspect_lock.get("prompt_instruction") or "").strip()
    if not instruction:
        return prompt
    prompt_text = str(prompt or "").rstrip()
    if instruction in prompt_text:
        return prompt_text
    return f"{prompt_text}\n\n{instruction}" if prompt_text else instruction


def _append_qr_exclusion_instruction(prompt: str, *, qr_excluded: bool) -> str:
    if not qr_excluded:
        return prompt
    instruction = (
        "Hard QR exclusion: do not include QR codes, scan-code modules, QR placeholders, empty scan cards, "
        "or decorative square code areas. This overrides any selected-template or reference cue that contains a QR-safe area, scan card, or code block."
    )
    prompt_text = str(prompt or "").rstrip()
    if instruction in prompt_text:
        return prompt_text
    return f"{prompt_text}\n\n{instruction}" if prompt_text else instruction


def _task_intent_payload(orchestrator_decision: CreativeOrchestratorDecision | None) -> dict[str, object]:
    if not orchestrator_decision or not orchestrator_decision.task_intent:
        return {}
    return orchestrator_decision.task_intent.model_dump(mode="json", exclude_none=True)


def _language_lock_from_task_intent(task_intent: dict[str, object]) -> dict[str, object]:
    language = str(task_intent.get("visible_text_language") or "").strip()
    policy = str(task_intent.get("visible_text_policy") or "").strip()
    if not language and not policy:
        return {"locked": False, "language": "", "source": "auto", "prompt_instruction": ""}
    instruction = policy or f"Visible text language lock: use {language} for all visible copy requested by the user."
    return {
        "locked": True,
        "language": language,
        "source": "orchestrator_task_intent",
        "prompt_instruction": f"Visible text language lock: {policy}" if policy else instruction,
    }


def _append_language_lock_instruction(prompt: str, *, language_lock: dict[str, object]) -> str:
    instruction = str(language_lock.get("prompt_instruction") or "").strip()
    if not instruction:
        return prompt
    prompt_text = str(prompt or "").rstrip()
    if instruction in prompt_text:
        return prompt_text
    return f"{prompt_text}\n\n{instruction}" if prompt_text else instruction


def _clean_dimension_value(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"auto", "default", "none", "null"}:
        return ""
    return text


def _qr_explicitly_excluded(value: str) -> bool:
    return bool(QR_EXCLUSION_PATTERN.search(str(value or "")))


def _ratio_from_dimension_or_ratio(value: str) -> str:
    text = str(value or "").strip().lower()
    if ":" in text:
        parts = text.split(":", 1)
    elif "x" in text:
        parts = text.split("x", 1)
    else:
        return ""
    try:
        width = int(parts[0].strip())
        height = int(parts[1].strip())
    except (ValueError, IndexError):
        return ""
    if width <= 0 or height <= 0:
        return ""
    divisor = _gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _gcd(left: int, right: int) -> int:
    a = abs(left)
    b = abs(right)
    while b:
        a, b = b, a % b
    return a or 1


def _build_prompt(
    user_prompt: str,
    primary: PromptCase | None,
    reusable: list[str],
    *,
    orchestrator_decision: CreativeOrchestratorDecision | None = None,
) -> str:
    base = f"Create a high-quality custom image for this client request: {user_prompt.strip()}."
    directive_parts: list[str] = []
    if orchestrator_decision:
        directives = orchestrator_decision.prompt_directives
        for label, value in [
            ("creative strategy", directives.visual_strategy),
            ("composition", directives.composition),
            ("lighting", directives.lighting),
            ("color palette", directives.color_palette),
        ]:
            if value:
                directive_parts.append(f"{label}: {value}")
        directive_parts.extend(directives.reusable_prompt_atoms[:8])
    directive_text = ""
    if directive_parts:
        directive_text = " Follow these central-orchestrator directives: " + "; ".join(directive_parts) + "."
    if not primary:
        return (
            base
            + directive_text
            + " Use clear subject hierarchy, intentional lighting, coherent color, commercially usable composition, "
            "and a polished modern finish."
        )
    if orchestrator_decision:
        return (
            base
            + directive_text
            + " Use the selected cases only as abstract evidence for composition, lighting, material handling, "
            "distinctive accent colors, and commercial polish; do not carry over their original product category, brand text, props, or scene-specific content. "
            "Keep the client's subject and intent primary. Leave appropriate negative space when the use case needs copy. "
            "Use refined lighting, controlled background detail, accurate materials, and a commercially polished finish."
        )
    additions = "; ".join(reusable[:8])
    if not additions:
        return (
            base
            + directive_text
            + " Use the locked selected-template structure from the Template Lock instructions, then replace only the client-specific subject, product, logo, copy, or minor props requested by the user."
        )
    return (
        f"{base} Build a new composition inspired by reusable visual principles from curated cases: {additions}. "
        f"{directive_text} "
        "Keep the client's subject and intent primary. Leave appropriate negative space when the use case needs copy. "
        "Use refined lighting, controlled background detail, accurate materials, and a commercially polished finish."
    )


def _apply_template_anchor(prompt: str, *, user_prompt: str, template: PromptCase) -> str:
    anchor = _template_anchor_directive(template)
    if not anchor:
        return prompt
    anchored = (
        f"TEMPLATE LOCK: use the hand-selected template '{template.title}' as the non-negotiable highest-priority visual base. "
        f"Preserve its visual DNA before applying any other style: {anchor}. "
        "Keep the template's composition type, spatial hierarchy, background density, color palette, typography or annotation treatment, and subject placement when present. "
        "Only replace the original subject/products with the user's requested subject. "
        "If the subordinate draft conflicts with the template by asking for a standalone portrait, minimal plain background, or no text while the template uses poster/cards/annotations, ignore that conflicting part and let the template win. "
        f"Client request to adapt into the template: {user_prompt.strip()}. "
        f"Subordinate draft for subject details only: {prompt}"
    )
    return _clean_prompt_text(anchored, limit=2800)


def _template_anchor_directive(template: PromptCase) -> str:
    elements: list[str] = []
    raw_text = f"{template.summary} {template.raw_prompt}"
    visual_skeleton = _template_raw_visual_skeleton(template)
    if visual_skeleton:
        elements.append(f"template_visual_skeleton: {visual_skeleton}")
    atoms = template.prompt_atoms or {}
    for key in ["scene", "composition", "lighting", "color_palette", "material_texture", "mood", "typography"]:
        value = atoms.get(key)
        if value:
            clean_value = _sanitize_template_visual_sentence(_compact_anchor_value(value))
            if visual_skeleton and key in {"scene", "composition", "mood"} and len(clean_value) > 180:
                continue
            elements.append(f"{key}: {clean_value}")
    for field, value in _template_string_fields(raw_text):
        elements.append(f"{field}: {value}")
    features = template.visual_features or {}
    if features.get("composition_type"):
        elements.append(f"composition_type: {features['composition_type']}")
    if features.get("background_complexity"):
        elements.append(f"background_complexity: {features['background_complexity']}")
    visual_signals = build_case_visual_signals(template)
    if visual_signals.brief:
        elements.append(f"visual_signal_brief: {visual_signals.brief}")
    elements.extend(f"visual_principle: {item}" for item in visual_signals.reusable_principles[:4])
    if template.style_tags:
        elements.append(f"style_tags: {', '.join(template.style_tags[:6])}")
    unique = _dedupe_anchor_elements(elements)
    return "; ".join(unique[:14])


def _template_raw_visual_skeleton(template: PromptCase) -> str:
    raw_text = str(template.raw_prompt or template.summary or "")
    if not raw_text.strip():
        return ""
    markers = [
        "background",
        "floor",
        "reflection",
        "reflective",
        "typography",
        "letter",
        "poster",
        "composition",
        "centered",
        "oversized",
        "giant",
        "scale",
        "model",
        "leaning",
        "pose",
        "studio",
        "lighting",
        "annotation",
        "cards",
        "copy text",
    ]
    sentences = re.split(r"(?<=[.!?。！？])\s+", raw_text)
    selected: list[str] = []
    for sentence in sentences:
        clean = _sanitize_template_visual_sentence(sentence)
        lowered = clean.lower()
        if clean and any(marker in lowered for marker in markers):
            selected.append(clean)
        if len(selected) >= 5:
            break
    if not selected:
        selected.append(_sanitize_template_visual_sentence(raw_text))
    return _clean_prompt_text(" ".join(selected), limit=760)


def _sanitize_template_visual_sentence(sentence: str) -> str:
    clean = " ".join(str(sentence or "").strip().split())
    if not clean:
        return ""
    clean = re.sub(r"[\"“”][^\"“”]{1,90}[\"“”]", "campaign copy", clean)
    clean = re.sub(r"\b[A-Z][A-Z0-9]{3,}(?:\s+[A-Z0-9]{2,}){0,4}\b", "campaign text", clean)
    clean = re.sub(r"\bARTTEESHOW\b", "brand mark", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\{argument[^{}]*\}", "the requested variant", clean)
    return _clean_prompt_text(clean, limit=260)


def _template_allows_text_elements(template: PromptCase, *, user_prompt: str) -> bool:
    if _user_disallows_text(user_prompt):
        return False
    searchable = " ".join(
        [
            template.title,
            template.summary,
            template.raw_prompt,
            " ".join(template.style_tags),
            " ".join(str(value) for value in (template.prompt_atoms or {}).values()),
        ]
    ).lower()
    markers = [
        "typography",
        "handwritten",
        "annotation",
        "annotations",
        "notes",
        "label",
        "caption",
        "poster",
        "card",
        "cards",
        "feature sheet",
        "infographic",
        "text",
    ]
    return any(marker in searchable for marker in markers)


def _user_disallows_text(user_prompt: str) -> bool:
    lowered = str(user_prompt or "").lower()
    markers = [
        "no text",
        "without text",
        "不要文字",
        "不要出现文字",
        "不要有文字",
        "无文字",
        "不出现文字",
    ]
    return any(marker in lowered for marker in markers)


def _remove_negative_terms(prompt: str, blocked_terms: set[str]) -> str:
    blocked = {item.lower() for item in blocked_terms}
    kept: list[str] = []
    for item in str(prompt or "").replace("，", ",").split(","):
        clean = " ".join(item.strip().split())
        if clean and clean.lower() not in blocked:
            kept.append(clean)
    return ", ".join(kept)


def _template_string_fields(raw_text: str) -> list[tuple[str, str]]:
    fields = [
        "type",
        "theme",
        "style",
        "background",
        "orientation",
        "mood",
        "composition",
        "color_palette",
        "palette",
        "typography",
    ]
    found: list[tuple[str, str]] = []
    for field in fields:
        pattern = re.compile(rf'"{re.escape(field)}"\s*:\s*"([^"]+)"', re.IGNORECASE)
        match = pattern.search(raw_text)
        if match:
            found.append((field, _clean_prompt_text(match.group(1), limit=180)))
    return found


def _compact_anchor_value(value) -> str:
    if isinstance(value, dict):
        parts = [f"{key}: {_compact_anchor_value(child)}" for key, child in list(value.items())[:6]]
        return _clean_prompt_text(", ".join(parts), limit=220)
    if isinstance(value, list):
        return _clean_prompt_text(", ".join(_compact_anchor_value(item) for item in value[:8]), limit=220)
    return _clean_prompt_text(str(value), limit=220)


def _dedupe_anchor_elements(elements: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for element in elements:
        limit = 900 if element.startswith("template_visual_skeleton:") else 260
        clean = _clean_prompt_text(element, limit=limit)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique


def _reusable_elements(cases: list[PromptCase]) -> list[str]:
    elements: list[str] = []
    for case in cases:
        atoms = case.prompt_atoms
        for key in ["composition", "lighting", "color_palette", "material_texture", "mood", "typography"]:
            value = atoms.get(key)
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if value:
                elements.append(f"{key}: {value}")
        visual_signals = build_case_visual_signals(case)
        if visual_signals.brief:
            elements.append(f"visual_signal: {visual_signals.brief}")
        elements.extend(f"visual_principle: {item}" for item in visual_signals.reusable_principles[:4])
    seen: set[str] = set()
    unique: list[str] = []
    for item in elements:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _case_reuse_notes(
    case: PromptCase,
    *,
    orchestrator_decision: CreativeOrchestratorDecision | None = None,
) -> list[str]:
    if orchestrator_decision:
        directives = orchestrator_decision.prompt_directives
        notes: list[str] = []
        if directives.composition:
            notes.append(f"composition: {directives.composition}")
        if directives.lighting:
            notes.append(f"lighting: {directives.lighting}")
        if directives.color_palette:
            notes.append(f"color_palette: {directives.color_palette}")
        notes.extend(f"prompt_atom: {item}" for item in directives.reusable_prompt_atoms[:4])
        notes.extend(_visual_signal_notes(case, limit=4))
        return notes or ["central-orchestrator selected this case as abstract prompt evidence"]
    notes: list[str] = []
    for key in ["composition", "lighting", "color_palette", "mood"]:
        value = case.prompt_atoms.get(key)
        if value:
            notes.append(f"{key}: {value}")
    notes.extend(_visual_signal_notes(case, limit=4))
    return notes or ["overall visual structure"]


def _visual_signal_notes(case: PromptCase, *, limit: int) -> list[str]:
    signals = build_case_visual_signals(case)
    notes: list[str] = []
    if signals.brief:
        notes.append(f"visual_signal: {signals.brief}")
    notes.extend(f"visual_principle: {item}" for item in signals.reusable_principles[: max(0, limit - 1)])
    return notes[:limit]


def _build_explanation(mode: str, cases: list[PromptCase]) -> str:
    if not cases:
        return "No template case was required; the prompt uses general high-quality commercial image principles."
    if mode == "template_customize":
        return (
            f"The selected template case {cases[0].case_id} is treated as the primary visual structure. "
            "The generated prompt replaces subject-specific elements with the user's request."
        )
    return (
        f"The prompt combines reusable composition, lighting, color, and mood cues from {len(cases)} relevant cases "
        "while avoiding direct copying of protected or provider-specific content."
    )
