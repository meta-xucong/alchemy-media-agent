from __future__ import annotations

import re

from app.schemas import CreativeOrchestratorDecision, ImagePromptPlan, PromptCase, PromptCaseSummary
from app.services.asset_binding import prompt_asset_context_block
from app.services.ids import new_id
from app.services.visual_signals import build_case_visual_signals
from app.services.visual_grammar_lock import apply_visual_grammar_lock, build_visual_grammar_contract


_BASE_NEGATIVE_TERMS = [
    "unlicensed third-party logos",
    "celebrity faces",
    "protected characters",
    "distorted anatomy",
    "unreadable text",
    "low-resolution artifacts",
    "unintended direct copying of unrelated references",
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
    prompt = ""
    if _should_use_claude_final_prompt(orchestrator_decision):
        prompt = _clean_prompt_text(orchestrator_decision.final_prompt, limit=2400)
        prompt_source = "claude_final_prompt"
    if not prompt:
        prompt = _build_prompt(user_prompt, primary, reusable, orchestrator_decision=orchestrator_decision)
    if mode == "template_customize" and primary:
        prompt = _apply_template_anchor(prompt, user_prompt=user_prompt, template=primary)
    prompt = _apply_asset_context_guard(prompt, asset_context=asset_context)
    prompt = apply_visual_grammar_lock(prompt, contract=visual_grammar_contract, user_prompt=user_prompt)
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
    if mode == "template_customize" and primary and _template_allows_text_elements(primary, user_prompt=user_prompt):
        negative_prompt = _remove_negative_terms(negative_prompt, {"text"})
    if information_integrity.get("active"):
        negative_prompt = _merge_negative_prompt(
            negative_prompt,
            [
                "missing business-critical copy",
                "missing purchase offers",
                "missing prices or package rules",
                "missing QR or CTA",
                "over-simplified information layout",
            ],
        )
    provider_parameters = _build_provider_parameters(
        output,
        orchestrator_decision,
        visual_grammar_contract=visual_grammar_contract,
    )
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
            "prompt_source": prompt_source,
            "claude_final_prompt_used": prompt_source == "claude_final_prompt",
            "revision_source": output.get("revision_source"),
            "template_lock_enabled": bool((asset_context or {}).get("template_lock_contract")),
            "template_lock_contract": (asset_context or {}).get("template_lock_contract"),
            "visual_grammar_lock_enabled": bool(visual_grammar_contract),
            "visual_grammar_contract": visual_grammar_contract,
            "information_integrity_lock_enabled": bool(information_integrity.get("active")),
            "information_integrity_contract": information_integrity,
            "asset_binding_plan": (asset_context or {}).get("asset_binding_plan"),
            "provider_input_plan": (asset_context or {}).get("provider_input_plan"),
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
    return bool(_clean_prompt_text(orchestrator_decision.final_prompt, limit=2400))


def _clean_prompt_text(value: str, *, limit: int) -> str:
    clean = " ".join(str(value or "").strip().split())
    clean = _sanitize_downstream_prompt(clean)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


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
    internal_keys = {"prompt", "negative_prompt", "revision_source"}
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
    params["count"] = max(1, min(count, 8))
    params["quality"] = params.get("quality", "high")
    return params


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
