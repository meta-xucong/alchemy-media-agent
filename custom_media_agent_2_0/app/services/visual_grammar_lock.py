from __future__ import annotations

import re
from typing import Any

from app.schemas import CreativeOrchestratorDecision, PromptCase
from app.services.ids import new_id
from app.services.visual_signals import build_case_visual_signals


LOCKED_VISUAL_GRAMMAR_ELEMENTS = [
    "composition_framework",
    "main_visual_presence",
    "spatial_hierarchy",
    "layout_rhythm",
    "lighting_logic",
    "mood",
    "background_density",
    "design_language",
    "typography_or_information_treatment",
]

REPLACEABLE_SEMANTIC_ELEMENTS = [
    "subject_identity",
    "product_or_food_content",
    "brand_or_campaign_copy",
    "logo",
    "requested_or_source_qr_code",
    "minor_props",
    "business_offer",
]

INFO_DENSE_MARKERS = [
    "菜单",
    "周卡",
    "套餐",
    "价格",
    "优惠",
    "折扣",
    "购买",
    "加购",
    "配送",
    "赠餐",
    "续卡",
    "卡",
    "文案",
    "二维码",
    "活动",
    "规则",
    "menu",
    "weekly card",
    "price",
    "offer",
    "discount",
    "promotion",
    "coupon",
    "delivery",
    "package",
    "qr",
    "copy",
]

CRITICAL_INFORMATION_FIELDS = [
    "main product or food imagery",
    "item names and descriptive copy",
    "prices, counts, dates, calories, and numeric claims",
    "packages, discounts, purchase rules, delivery rules, gifts, and add-on policies",
    "requested CTA, contact, and purchase instructions",
    "legal or operational notes that affect purchase decisions",
]
QR_CRITICAL_INFORMATION_FIELD = "source QR code or scan instructions explicitly requested or detected in uploaded assets"

QR_INTENT_PATTERN = re.compile(
    "(二维码|二維碼|qr\\s*code|qr-code|qrcode|qr码|qr碼|scan\\s*code|扫码|掃碼|小程序码|小程序碼)",
    re.IGNORECASE,
)
QR_EXCLUSION_PATTERN = re.compile(
    "(不要|不需要|无需|無需|禁止|去掉|移除|不要展示|不要出现|不出现|without|no|do\\s+not\\s+include|do\\s+not\\s+show)"
    ".{0,24}"
    "(二维码|二維碼|qr\\s*code|qr-code|qrcode|scan\\s*code|扫码|掃碼)",
    re.IGNORECASE,
)
TEMPLATE_REPLACEMENT_RELATIONSHIPS = {"replace_template_subject", "replace_template_food_subject"}


def build_visual_grammar_contract(
    *,
    mode: str,
    user_prompt: str,
    cases: list[PromptCase],
    asset_context: dict[str, Any] | None = None,
    orchestrator_decision: CreativeOrchestratorDecision | None = None,
) -> dict[str, Any] | None:
    primary = cases[0] if cases else None
    if not primary:
        return None
    explicit_template = mode == "template_customize"
    auxiliary_cases = cases[1:3] if not explicit_template else []
    visual_signals = build_case_visual_signals(primary)
    anchor_directive = _anchor_directive(primary)
    source_layout_risk = _source_layout_risk(user_prompt=user_prompt, asset_context=asset_context)
    task_relationship_model = _task_relationship_model(asset_context)
    information_integrity = _information_integrity_contract(
        user_prompt=user_prompt,
        asset_context=asset_context,
        source_layout_risk=source_layout_risk,
    )
    asset_frame_strategy = _asset_frame_strategy(asset_context)
    uploaded_frame_primary = (not explicit_template) and asset_frame_strategy.get("mode") == "uploaded_frame_primary"
    contract = {
        "contract_id": new_id("vgl"),
        "mode": (
            "template_visual_grammar_lock"
            if explicit_template
            else "uploaded_frame_visual_grammar"
            if uploaded_frame_primary
            else "auto_visual_grammar_lock"
        ),
        "lock_strength": "strong" if explicit_template else "medium" if uploaded_frame_primary else "medium_strong",
        "primary_anchor_case_id": primary.case_id,
        "primary_anchor_title": primary.title,
        "primary_anchor_category": primary.category,
        "auxiliary_case_ids": [item.case_id for item in auxiliary_cases],
        "auxiliary_case_titles": [item.title for item in auxiliary_cases],
        "locked_visual_grammar": LOCKED_VISUAL_GRAMMAR_ELEMENTS,
        "replaceable_semantic_content": REPLACEABLE_SEMANTIC_ELEMENTS,
        "anchor_directive": anchor_directive,
        "visual_signal_brief": visual_signals.brief,
        "task_relationship_model": task_relationship_model,
        "source_layout_risk": source_layout_risk,
        "information_integrity": information_integrity,
        "asset_frame_strategy": asset_frame_strategy,
        "critical_asset_rules": _critical_asset_rules(asset_context),
        "conflict_policy": (
            "Preserve the uploaded layout/composition frame; use retrieved cases only for compatible polish, lighting, materials, and finish. "
            "Do not let the case anchor replace the uploaded frame."
            if uploaded_frame_primary
            else "Preserve the selected visual grammar over Claude drafts and uploaded source layouts. "
            "Replace semantic content, not composition, spatial hierarchy, mood, or design language. "
            "If the user's assets lack a key visual element required by the anchor, synthesize suitable virtual content."
        ),
        "orchestrator_decision_id": orchestrator_decision.decision_id if orchestrator_decision else None,
    }
    return contract


def apply_visual_grammar_lock(prompt: str, *, contract: dict[str, Any] | None, user_prompt: str) -> str:
    if not contract:
        return prompt
    block = visual_grammar_prompt_block(contract, user_prompt=user_prompt)
    if not block:
        return prompt
    guarded = (
        f"{block}\n\n"
        "Downstream adaptation draft: use this only for semantic content and compatible details. "
        "Rewrite or ignore any part that conflicts with the visual grammar lock.\n"
        f"{prompt}"
    )
    return _compact_text(guarded, 5600)


def visual_grammar_prompt_block(contract: dict[str, Any], *, user_prompt: str) -> str:
    mode = str(contract.get("mode") or "")
    title = _safe_title(str(contract.get("primary_anchor_title") or "selected visual reference"))
    anchor = _compact_text(str(contract.get("anchor_directive") or contract.get("visual_signal_brief") or ""), 900)
    source_layout_risk = contract.get("source_layout_risk") if isinstance(contract.get("source_layout_risk"), dict) else {}
    task_relationship_model = contract.get("task_relationship_model") if isinstance(contract.get("task_relationship_model"), dict) else {}
    aux_titles = [
        _safe_title(str(item))
        for item in (contract.get("auxiliary_case_titles") or [])
        if str(item or "").strip()
    ][:2]
    if mode == "template_visual_grammar_lock":
        lead = (
            "TEMPLATE LOCK: the selected case is the highest-priority visual template. "
            f"Visual Grammar Lock: inherit the selected template '{title}' as visual grammar, not literal content."
        )
        strength = (
            "Strong lock: preserve its main visual presence, composition framework, spatial hierarchy, "
            "layout rhythm, lighting logic, background density, mood, typography/information treatment, and design language."
        )
    elif mode == "uploaded_frame_visual_grammar":
        lead = (
            "UPLOADED FRAME VISUAL GRAMMAR: no user-selected template was provided, and the uploaded reference is the requested layout/composition frame. "
            f"Retrieved case '{title}' is a secondary style-polish reference, not the frame owner."
        )
        strength = (
            "Medium lock: preserve the uploaded reference image's composition framework, layout rhythm, major spatial hierarchy, and camera/design structure. "
            "Use retrieved cases only for compatible lighting, material treatment, typography polish, color mood, and commercial finish."
        )
    else:
        lead = (
            "AUTO VISUAL GRAMMAR LOCK: no user-selected template was provided, so use one primary curated case as the main visual grammar anchor. "
            f"Primary anchor: '{title}'."
        )
        strength = (
            "Medium-strong lock: keep this anchor's composition discipline, subject hierarchy, design complexity, "
            "lighting logic, mood, background density, and layout rhythm. Do not average multiple cases into a vague hybrid."
        )
    parts = [
        lead,
        strength,
        (
            "User semantic content controls the actual subject, product, food, brand, copy, offer, requested CTA/contact, and business meaning: "
            + _compact_text(_semantic_prompt_summary(user_prompt), 420)
            + "."
        ),
        (
            "Uploaded assets include the requested frame reference. Hard identity assets must remain reference images when supported, "
            "and the uploaded layout/composition frame stays primary."
            if mode == "uploaded_frame_visual_grammar"
            else "Uploaded assets are evidence and slot variables. Hard identity assets must remain reference images when supported, "
            "but uploaded source layouts must not override the selected visual grammar."
        ),
        (
            "If the visual grammar requires a key element such as a large hero image, product scene, information band, or typography-safe area "
            "and the uploaded assets do not provide it, synthesize suitable virtual content that matches the user's subject."
        ),
        (
            "Conflict policy: uploaded layout/composition wins over retrieved case composition; retrieved cases only polish compatible details; user semantics still control subject, copy, and business meaning."
            if mode == "uploaded_frame_visual_grammar"
            else "Conflict policy: visual grammar wins over Claude draft wording and uploaded source layout; user semantics win over the anchor's original literal subject and copy."
        ),
    ]
    critical_asset_rules = [
        str(item)
        for item in (contract.get("critical_asset_rules") or [])
        if str(item or "").strip()
    ][:3]
    critical_asset_rules = _dedupe(critical_asset_rules)
    insert_index = 2
    if critical_asset_rules:
        parts.insert(insert_index, "Critical uploaded-asset placement rules: " + " ".join(critical_asset_rules))
        insert_index += 1
    if _task_relationship_replaces_template_subject(task_relationship_model):
        target_label = str(task_relationship_model.get("target_label") or "the selected template subject slots")
        try:
            uploaded_count = int(task_relationship_model.get("uploaded_asset_count") or 0)
        except (TypeError, ValueError):
            uploaded_count = 0
        count_rule = (
            f" All {uploaded_count} uploaded replacement images must appear as distinct visible food/photo modules; do not collapse them into one hero dish or ignore later uploads."
            if uploaded_count > 1
            else ""
        )
        parts.insert(
            insert_index,
            "Task relationship lock: uploaded images are concrete replacement subjects for "
            f"{target_label}; keep the visual grammar frame, replace its original slot content, and do not recast the uploads as source-layout evidence."
            + count_rule,
        )
        insert_index += 1
    if anchor:
        parts.insert(insert_index, "Reusable visual grammar from the anchor: " + anchor + ".")
    information_integrity = contract.get("information_integrity") if isinstance(contract.get("information_integrity"), dict) else {}
    if information_integrity.get("active"):
        fields = ", ".join(str(item) for item in (information_integrity.get("critical_fields") or [])[:6])
        qr_intent = bool(information_integrity.get("qr_intent"))
        extracted_details = (
            "extracted copy, food imagery, source QR, and offer facts"
            if qr_intent
            else "extracted copy, food imagery, and offer facts"
        )
        correspondence = (
            "Food-to-copy, offer-to-product, and QR/CTA correspondence must be preserved as semantic pairings inside the template's existing modules; "
            if qr_intent
            else "Food-to-copy and offer-to-product correspondence must be preserved as semantic pairings inside the template's existing modules; "
        )
        qr_policy = (
            "Preserve QR or scan-code content only from a real uploaded/source QR or an explicit user QR request; never invent a replacement QR. "
            if qr_intent
            else "Do not invent QR codes, scan-code modules, QR placeholders, empty scan cards, or decorative square code areas; this overrides any selected-template or reference cue that contains a QR-safe area, scan card, or code block. "
        )
        parts.append(
            "CONTENT EXTRACTION LOCK: this task uses an uploaded poster/menu/flyer as source material. "
            f"Extract the user-requested content categories where present: {fields}. "
            f"Keep the selected visual grammar as the frame owner; condense, curate, and reposition {extracted_details} into the template's own information hierarchy. "
            + correspondence
            + qr_policy
            + "this pairing requirement must not stretch the canvas, add a new menu grid, change the selected template composition, or make the uploaded source frame dominant. "
            "Do not preserve the uploaded source's full menu grid, weekly-card structure, footer policy block, background color field, or original information architecture merely because those facts were visible."
        )
    if aux_titles:
        parts.append("Auxiliary cases may contribute only compatible local cues, not the main composition: " + ", ".join(aux_titles) + ".")
    if source_layout_risk.get("detected") and not _task_relationship_replaces_template_subject(task_relationship_model):
        if mode == "uploaded_frame_visual_grammar":
            parts.append(
                "Uploaded-frame intent confirmed: the uploaded source may be a finished layout, but the user explicitly asked to preserve its frame. "
                "Keep the layout/composition structure while refreshing details and preventing unreadable copied text."
            )
        else:
            parts.append(
                "Source-layout risk detected: the uploaded image or request looks like a finished poster, menu sheet, weekly card, QR/text sheet, or screenshot. "
                "Extract semantic content and hard references only; do not copy its overall grid, background, density, or layout."
            )
    return " ".join(parts)


def _anchor_directive(case: PromptCase) -> str:
    raw_text = f"{case.summary} {case.raw_prompt}"
    elements: list[str] = []
    skeleton = _raw_visual_skeleton(raw_text)
    if skeleton:
        elements.append(f"visual skeleton: {skeleton}")
    atoms = case.prompt_atoms or {}
    for key in ["composition", "lighting", "color_palette", "material_texture", "mood", "typography"]:
        value = atoms.get(key)
        if value:
            elements.append(f"{key}: {_compact_anchor_value(value)}")
    features = case.visual_features or {}
    for key in ["composition_type", "background_complexity"]:
        if features.get(key):
            elements.append(f"{key}: {features[key]}")
    signals = build_case_visual_signals(case)
    if signals.brief:
        elements.append(f"visual signal: {signals.brief}")
    elements.extend(signals.reusable_principles[:4])
    if case.style_tags:
        elements.append("style tags: " + ", ".join(case.style_tags[:6]))
    unique = _dedupe(_compact_text(item, 280) for item in elements if item)
    return "; ".join(unique[:12])


def _raw_visual_skeleton(raw_text: str) -> str:
    markers = [
        "hero",
        "main visual",
        "background",
        "floor",
        "reflection",
        "typography",
        "poster",
        "composition",
        "centered",
        "layout",
        "headline",
        "annotation",
        "cards",
        "ingredients",
        "how to make",
        "information",
        "lighting",
        "negative space",
    ]
    sentences = re.split(r"(?<=[.!?。！？])\s+", str(raw_text or ""))
    selected: list[str] = []
    for sentence in sentences:
        clean = _sanitize_case_sentence(sentence)
        if clean and any(marker in clean.lower() for marker in markers):
            selected.append(clean)
        if len(selected) >= 5:
            break
    if not selected:
        selected.append(_sanitize_case_sentence(raw_text))
    return _compact_text(" ".join(selected), 760)


def _source_layout_risk(*, user_prompt: str, asset_context: dict[str, Any] | None) -> dict[str, Any]:
    text_parts = [user_prompt]
    for asset in (asset_context or {}).get("uploaded_assets", []) or []:
        if not isinstance(asset, dict):
            continue
        text_parts.append(str(asset.get("filename") or ""))
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        text_parts.append(str(brief.get("visual_summary") or ""))
        detected_text = brief.get("detected_text") if isinstance(brief.get("detected_text"), list) else []
        if detected_text:
            text_parts.append("detected text")
    text = " ".join(text_parts).lower()
    markers = [
        "菜单",
        "周卡",
        "海报",
        "文案",
        "二维码",
        "整图",
        "截图",
        "版式",
        "摘取",
        "提取",
        "menu",
        "poster",
        "flyer",
        "screenshot",
        "qr",
        "layout",
        "source sheet",
    ]
    hits = [marker for marker in markers if marker in text]
    return {"detected": bool(hits), "markers": hits[:8]}


def _asset_frame_strategy(asset_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(asset_context, dict):
        return {}
    strategy = asset_context.get("asset_frame_strategy")
    return strategy if isinstance(strategy, dict) else {}


def _information_integrity_contract(
    *,
    user_prompt: str,
    asset_context: dict[str, Any] | None,
    source_layout_risk: dict[str, Any],
) -> dict[str, Any]:
    text_parts = [user_prompt]
    plan = (asset_context or {}).get("asset_binding_plan")
    bindings = plan.get("bindings") if isinstance(plan, dict) else []
    fusion_modes = [
        str(item.get("fusion_mode") or "")
        for item in bindings or []
        if isinstance(item, dict)
    ]
    for asset in (asset_context or {}).get("uploaded_assets", []) or []:
        if not isinstance(asset, dict):
            continue
        text_parts.extend([str(asset.get("filename") or ""), str(asset.get("intended_use") or "")])
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        text_parts.append(str(brief.get("visual_summary") or ""))
        detected_text = brief.get("detected_text") if isinstance(brief.get("detected_text"), list) else []
        text_parts.extend(str(item) for item in detected_text[:8])
    text = " ".join(text_parts).lower()
    hits = [marker for marker in INFO_DENSE_MARKERS if marker in text]
    qr_intent = _qr_intent_detected(user_prompt=user_prompt, asset_context=asset_context)
    uploaded_frame_primary = _asset_frame_strategy(asset_context).get("mode") == "uploaded_frame_primary"
    composite_source = "composite_content_source" in fusion_modes
    task_relationship_model = _task_relationship_model(asset_context)
    replacement_relationship = _task_relationship_replaces_template_subject(task_relationship_model)
    explicit_retention = bool(
        re.search(
            r"(完整保留|全部保留|信息.*完整|不要丢|不要省略|保留.*文案|保留.*优惠|保留.*价格|保留.*政策|complete information|preserve all|do not omit)",
            text,
            flags=re.IGNORECASE,
        )
    )
    active = False if replacement_relationship else bool(composite_source or explicit_retention or (source_layout_risk.get("detected") and len(hits) >= 2))
    return {
        "active": active,
        "priority": "hard" if explicit_retention else "strong",
        "scope": "commercial_poster_information_integrity",
        "triggers": hits[:10],
        "critical_fields": _critical_information_fields(qr_intent=qr_intent),
        "qr_intent": qr_intent,
        "qr_policy": "preserve_real_source_qr_only" if qr_intent else "do_not_invent_qr_or_scan_placeholder",
        "layout_policy": (
            "Preserve facts and commercial meaning inside the uploaded layout/composition frame; refresh only incompatible visual details."
            if uploaded_frame_primary
            else "Preserve facts and commercial meaning while adapting them into the locked visual grammar; "
            "do not preserve the old source layout."
        ),
        "canvas_policy": (
            "Prefer concise template-native content modules over copying the source poster's complete information architecture."
        ),
        "correspondence_policy": (
            "Preserve requested food/copy and offer/product relationships as semantic pairings inside the selected template modules; "
            + (
                "preserve QR relationships only when a real source QR or explicit QR request exists; "
                if qr_intent
                else "do not add QR/scan placeholders for generic CTA needs; "
            )
            + "do not let correspondence or completeness requests change the locked frame."
        ),
    }


def _critical_asset_rules(asset_context: dict[str, Any] | None) -> list[str]:
    plan = (asset_context or {}).get("asset_binding_plan")
    bindings = plan.get("bindings") if isinstance(plan, dict) else []
    rules: list[str] = []
    for item in bindings or []:
        if not isinstance(item, dict):
            continue
        fusion = str(item.get("fusion_mode") or "")
        placement = item.get("placement_intent") if isinstance(item.get("placement_intent"), dict) else {}
        label = placement.get("target_label") or item.get("target_surface") or "the requested slot"
        if fusion == "logo_product_surface":
            rules.append(f"Uploaded logo must appear on {label} as a real scene-surface mark, never as a footer, corner badge, watermark, or sticker.")
        elif fusion == "template_slot_replacement":
            rules.append(
                f"Uploaded subject image is a concrete replacement for {label}; preserve its visible subject and fit it into the existing template slot without adding a new source-layout frame."
            )
        elif fusion == "composite_content_source":
            rules.append(
                "Uploaded composite/menu/poster image supplies content evidence only; extract requested food/product, copy, offer facts, and other user-requested business details without inheriting the source layout."
            )
        elif item.get("provider_input_required") and item.get("role") in {"subject_reference", "face_reference", "background_reference"}:
            rules.append(f"Uploaded {item.get('role')} remains a hard reference for {label}, adapted inside the visual grammar.")
    return rules[:4]


def _task_relationship_model(asset_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(asset_context, dict):
        return {}
    relationship = asset_context.get("task_relationship_model")
    return relationship if isinstance(relationship, dict) else {}


def _task_relationship_replaces_template_subject(task_relationship_model: dict[str, Any] | None) -> bool:
    if not isinstance(task_relationship_model, dict):
        return False
    return str(task_relationship_model.get("primary_relationship") or "") in TEMPLATE_REPLACEMENT_RELATIONSHIPS


def _compact_anchor_value(value: Any) -> str:
    if isinstance(value, dict):
        return _compact_text(", ".join(f"{key}: {_compact_anchor_value(child)}" for key, child in list(value.items())[:6]), 220)
    if isinstance(value, list):
        return _compact_text(", ".join(_compact_anchor_value(item) for item in value[:8]), 220)
    return _compact_text(_sanitize_case_sentence(str(value)), 220)


def _sanitize_case_sentence(value: str) -> str:
    clean = " ".join(str(value or "").strip().split())
    if not clean:
        return ""
    clean = re.sub(r"[\"“”][^\"“”]{1,90}[\"“”]", "campaign copy", clean)
    clean = re.sub(r"\b[A-Z][A-Z0-9]{3,}(?:\s+[A-Z0-9]{2,}){0,4}\b", "campaign text", clean)
    clean = re.sub(r"\{argument[^{}]*\}", "the requested variant", clean)
    return _compact_text(clean, 260)


def _safe_title(value: str) -> str:
    clean = re.sub(r"\bcase_[a-z0-9_.-]+\b", "selected reference", value, flags=re.IGNORECASE)
    clean = re.sub(r"\basset_[a-z0-9_.-]+\b", "uploaded reference", clean, flags=re.IGNORECASE)
    return _compact_text(clean, 90)


def _semantic_prompt_summary(value: str) -> str:
    clean = _compact_text(value, 420)
    return re.sub(r"[\s.!?。！？]+$", "", clean)


def _compact_text(value: str, limit: int) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def _dedupe(items) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        unique.append(clean)
    return unique


def _critical_information_fields(*, qr_intent: bool) -> list[str]:
    fields = list(CRITICAL_INFORMATION_FIELDS)
    if qr_intent:
        fields.insert(4, QR_CRITICAL_INFORMATION_FIELD)
    return fields


def _qr_intent_detected(*, user_prompt: str, asset_context: dict[str, Any] | None) -> bool:
    if _qr_explicitly_excluded(user_prompt):
        return False
    if _qr_text_requested(user_prompt):
        return True
    for asset in (asset_context or {}).get("uploaded_assets", []) or []:
        if not isinstance(asset, dict):
            continue
        parts = [
            asset.get("filename"),
            asset.get("intended_use"),
        ]
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        parts.extend(
            [
                brief.get("visual_summary"),
                brief.get("identity_requirements"),
                brief.get("detected_text"),
            ]
        )
        if _qr_text_requested(" ".join(str(item or "") for item in parts)):
            return True
    return False


def _qr_explicitly_excluded(value: str) -> bool:
    return bool(QR_EXCLUSION_PATTERN.search(str(value or "")))


def _qr_text_requested(value: Any) -> bool:
    text = str(value or "")
    if not text:
        return False
    if _qr_explicitly_excluded(text):
        return False
    return bool(QR_INTENT_PATTERN.search(text))
