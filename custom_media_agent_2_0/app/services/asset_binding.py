from __future__ import annotations

import re
from typing import Any

from app.repositories import repository
from app.schemas import (
    AssetBinding,
    AssetBindingPlan,
    AssetBrief,
    ConstraintStrength,
    CreateCreativeRunRequest,
    CreativeRunAssetInput,
    ProviderInputImage,
    TemplateLockContract,
    UploadedAsset,
)
from app.services.case_intelligence import get_prompt_case
from app.services.ids import new_id
from app.services.uploaded_assets import get_uploaded_asset


LOCKED_TEMPLATE_ELEMENTS = [
    "composition",
    "spatial_hierarchy",
    "lighting",
    "background_density",
    "color_rhythm",
    "mood",
    "layout_structure",
    "typography_or_annotation_treatment",
]
REPLACEABLE_TEMPLATE_SLOTS = [
    "main_subject",
    "product_identity",
    "logo",
    "face_identity",
    "copy_content",
    "minor_props",
]
HARD_REFERENCE_ROLES = {"subject_reference", "logo_reference", "face_reference", "background_reference"}
ROLE_PRIORITY = {
    "subject_reference": 90,
    "face_reference": 82,
    "logo_reference": 78,
    "background_reference": 68,
    "style_reference": 52,
    "composition_reference": 48,
    "color_reference": 42,
    "negative_reference": 20,
}
STRENGTH_PRIORITY = {"required": 3, "strong": 2, "soft": 1}
ROLE_TO_SLOT = {
    "style_reference": "style_details",
    "subject_reference": "main_subject",
    "logo_reference": "logo",
    "face_reference": "face_identity",
    "background_reference": "background_slot",
    "composition_reference": "composition_notes",
    "color_reference": "color_details",
    "negative_reference": "negative_constraints",
}
ROLE_ALLOWED_OVERRIDES = {
    "subject_reference": ["main subject identity", "product shape", "packaging details", "visible proportions"],
    "logo_reference": ["logo shape", "brand mark placement", "brand mark appearance"],
    "face_reference": ["face identity", "expression cues", "portrait identity"],
    "background_reference": ["background content only when explicitly requested"],
    "composition_reference": ["secondary camera-angle notes only"],
    "style_reference": ["minor texture cues", "compatible accent colors"],
    "color_reference": ["compatible product palette", "compatible accent colors"],
    "negative_reference": ["negative visual exclusions"],
}
TEMPLATE_REPLACEMENT_RELATIONSHIPS = {"replace_template_subject", "replace_template_food_subject"}
TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE = "template_slot_replacement"
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


def build_asset_context(request: CreateCreativeRunRequest) -> dict[str, Any]:
    asset_inputs = _normalize_asset_inputs(request.assets)
    inputs_by_id: dict[str, list[CreativeRunAssetInput]] = {}
    for item in asset_inputs:
        inputs_by_id.setdefault(item.asset_id, []).append(item)
    uploaded_assets = [_resolve_uploaded_asset(asset_id, veyra_user_id=request.veyra_user_id) for asset_id in inputs_by_id]
    uploaded_assets = [item for item in uploaded_assets if item is not None]
    brief_by_id = {item.asset_id: _brief_for(item) for item in uploaded_assets}
    template_lock = _template_lock_contract(request.template_case_id)
    uploaded_asset_contexts = [
        _asset_for_context(asset, brief_by_id.get(asset.asset_id), inputs_by_id.get(asset.asset_id, []))
        for asset in uploaded_assets
    ]
    task_relationship_model = _task_relationship_model(
        user_prompt=request.user_prompt,
        uploaded_assets=uploaded_asset_contexts,
        asset_inputs=asset_inputs,
        template_locked=template_lock is not None,
    )
    binding_plan = _binding_plan(
        asset_inputs,
        brief_by_id,
        template_lock,
        user_prompt=request.user_prompt,
        task_relationship_model=task_relationship_model,
    )
    asset_frame_strategy = _asset_frame_strategy(
        user_prompt=request.user_prompt,
        uploaded_assets=uploaded_asset_contexts,
        binding_plan=binding_plan,
        template_locked=template_lock is not None,
        task_relationship_model=task_relationship_model,
    )
    return {
        "user_prompt": request.user_prompt,
        "uploaded_assets": uploaded_asset_contexts,
        "task_relationship_model": task_relationship_model,
        "template_lock_contract": template_lock.model_dump(mode="json") if template_lock else None,
        "asset_binding_plan": binding_plan.model_dump(mode="json"),
        "asset_frame_strategy": asset_frame_strategy,
        "provider_input_images": [item.model_dump(mode="json") for item in provider_input_images(binding_plan, brief_by_id)],
        "provider_input_plan": binding_plan.provider_input_plan,
        "warnings": _warnings(asset_inputs, uploaded_assets),
    }


def provider_input_images_from_context(asset_context: dict[str, Any] | None) -> list[ProviderInputImage]:
    if not asset_context:
        return []
    images = asset_context.get("provider_input_images")
    if not isinstance(images, list):
        return []
    result: list[ProviderInputImage] = []
    for item in images:
        try:
            result.append(ProviderInputImage.model_validate(item))
        except Exception:
            continue
    return result


def prompt_asset_context_block(asset_context: dict[str, Any] | None) -> str:
    if not asset_context:
        return ""
    parts: list[str] = []
    lock = asset_context.get("template_lock_contract") if isinstance(asset_context.get("template_lock_contract"), dict) else None
    if lock:
        parts.append(
            "TEMPLATE LOCK: the selected case is the highest-priority visual template. "
            "Preserve its composition, spatial hierarchy, lighting, background density, mood, layout structure, and visual rhythm."
        )
    relationship = _relationship_from_context(asset_context)
    if _task_relationship_replaces_template_subject(relationship):
        target_label = _relationship_target_label(relationship)
        parts.append(
            "TASK RELATIONSHIP: uploaded reference images are concrete replacement subjects for "
            f"{target_label} in the selected template. Replace the template's original slot content with the uploaded subjects while preserving the template frame. "
            "Do not treat these uploads as a source poster, layout reference, generic style signal, or composite-content sheet."
        )
    elif _task_relationship_extracts_content(relationship):
        parts.append(
            "TASK RELATIONSHIP: uploaded images are source evidence for semantic content extraction. "
            "Extract only requested content, copy, product/food facts, and explicitly requested source QR details into the selected frame."
        )
    frame_strategy = asset_context.get("asset_frame_strategy") if isinstance(asset_context.get("asset_frame_strategy"), dict) else {}
    if frame_strategy.get("mode") == "uploaded_frame_primary":
        if frame_strategy.get("continuation_frame"):
            parts.append(
                "STARRED HISTORY CONTINUATION FRAME: use the selected starred history image as the primary continuation frame. "
                "Preserve its composition, layout rhythm, major spatial hierarchy, lighting, palette, and visual rhythm. "
                "Apply the current user request as the highest-priority local edit; if it conflicts with an object, prop, text, or surface in the reference image, replace the conflicting reference detail instead of preserving it. "
                "Retrieved cases may add polish, lighting, materials, and commercial finish only; they must not replace the continuation frame."
            )
        else:
            parts.append(
                "UPLOADED FRAME INTENT: no hand-selected template is active, and the user asked the uploaded reference to drive layout or composition. "
                "Preserve the uploaded frame's composition, layout rhythm, major spatial hierarchy, and camera/design structure. "
                "Retrieved cases may add polish, lighting, materials, and commercial finish only; they must not replace the uploaded frame."
            )
    elif (
        frame_strategy.get("content_extraction")
        and frame_strategy.get("mode") in {"template_frame_primary", "case_frame_primary"}
    ):
        frame_source = "the selected template" if frame_strategy.get("mode") == "template_frame_primary" else "retrieved cases"
        qr_intent = _asset_context_qr_intent(asset_context)
        extraction_targets = (
            "Extract semantic content, product/food identity, copy, source QR, and offer details; "
            if qr_intent
            else "Extract semantic content, product/food identity, copy, offer details, and other requested business facts; "
        )
        correspondence = (
            "If the user asks to keep text-food, offer-product, or QR-copy correspondence, preserve those relationships only as semantic pairings inside the frame owner's existing modules; "
            if qr_intent
            else "Preserve requested text-food and offer-product correspondence only as semantic pairings inside the frame owner's existing modules; do not infer a QR or scan-code module from generic CTA/poster structure; "
        )
        parts.append(
            "UPLOADED CONTENT SOURCE: use uploaded poster/menu/screenshot-like assets as content evidence and hard references only. "
            + extraction_targets
            + f"use {frame_source} for the new visual frame. "
            + correspondence
            + "do not expand, re-grid, or recompose the selected frame to mirror the source image."
        )
    provider_plan = asset_context.get("provider_input_plan") if isinstance(asset_context.get("provider_input_plan"), dict) else {}
    if provider_plan.get("reference_image_count"):
        parts.append(
            f"Provider input images required: {provider_plan.get('reference_image_count')} uploaded reference image(s). "
            "The prompt must refer to them as uploaded reference images, not by internal IDs."
        )
    plan = asset_context.get("asset_binding_plan") if isinstance(asset_context.get("asset_binding_plan"), dict) else {}
    bindings = plan.get("bindings") if isinstance(plan, dict) else []
    if isinstance(bindings, list) and bindings:
        parts.append("Uploaded asset binding rules:")
        for item in bindings[:6]:
            if not isinstance(item, dict):
                continue
            instruction = str(item.get("prompt_instruction") or "").strip()
            if instruction:
                parts.append(f"- {instruction}")
            fusion_mode = str(item.get("fusion_mode") or "").strip()
            placement = item.get("placement_intent") if isinstance(item.get("placement_intent"), dict) else {}
            target = placement.get("target_label") or item.get("target_surface")
            if fusion_mode and target:
                parts.append(
                    f"- Fusion policy: {fusion_mode}; target: {target}; this is a hard binding cue for the final prompt."
                )
            if lock:
                blocked = item.get("not_allowed_to_override") or []
                if blocked:
                    parts.append("- Do not let this uploaded image override: " + ", ".join(str(value) for value in blocked[:5]) + ".")
    return "\n".join(parts)


def provider_input_images(binding_plan: AssetBindingPlan, brief_by_id: dict[str, AssetBrief]) -> list[ProviderInputImage]:
    images_by_asset_id: dict[str, ProviderInputImage] = {}
    for binding in binding_plan.bindings:
        brief = brief_by_id.get(binding.asset_id)
        if not brief or not binding.provider_input_required:
            continue
        asset = get_uploaded_asset(binding.asset_id)
        if not asset:
            continue
        existing = images_by_asset_id.get(binding.asset_id)
        if existing:
            primary_role = _primary_role(existing.role, binding.role)
            update_payload = {
                "role": primary_role,
                "constraint_strength": _stronger_strength(existing.constraint_strength, binding.constraint_strength),
                "prompt_instruction": _merge_prompt_instructions(existing.prompt_instruction, binding.prompt_instruction),
                "review_expectations": _dedupe([*existing.review_expectations, *binding.review_expectations]),
            }
            if primary_role == binding.role:
                update_payload.update(
                    {
                        "fusion_mode": binding.fusion_mode,
                        "placement_intent": binding.placement_intent,
                        "target_surface": binding.target_surface,
                    }
                )
            images_by_asset_id[binding.asset_id] = existing.model_copy(
                update=update_payload
            )
            continue
        images_by_asset_id[binding.asset_id] = (
            ProviderInputImage(
                asset_id=binding.asset_id,
                role=binding.role,
                constraint_strength=binding.constraint_strength,
                source_url=asset.source_url,
                mime_type=asset.mime_type,
                provider_input_required=True,
                prompt_instruction=binding.prompt_instruction,
                fusion_mode=binding.fusion_mode,
                placement_intent=binding.placement_intent,
                target_surface=binding.target_surface,
                review_expectations=binding.review_expectations,
            )
        )
    return list(images_by_asset_id.values())


def _task_relationship_model(
    *,
    user_prompt: str,
    uploaded_assets: list[dict[str, Any]],
    asset_inputs: list[CreativeRunAssetInput],
    template_locked: bool,
) -> dict[str, Any]:
    asset_ids = _strategy_asset_ids(uploaded_assets)
    text = _relationship_source_text(
        user_prompt=user_prompt,
        uploaded_assets=uploaded_assets,
        asset_inputs=asset_inputs,
    )
    has_uploads = bool(asset_ids)
    explicit_extraction = _relationship_explicit_extraction_requested(text) or _relationship_content_evidence_requested(text)
    if explicit_extraction and _hard_single_subject_requested(text) and not _layout_rejection_requested(text):
        explicit_extraction = False
    replacement_requested = _relationship_replacement_requested(text)
    food_requested = _relationship_food_requested(text)
    subject_requested = food_requested or _relationship_subject_requested(text)
    primary_relationship = "no_uploaded_assets"
    target_surface = None
    target_label = None
    uploaded_role = "none"
    if has_uploads and template_locked and replacement_requested and subject_requested and not explicit_extraction:
        primary_relationship = "replace_template_food_subject" if food_requested else "replace_template_subject"
        target_surface = "food_subject_slots" if food_requested else "main_subject_slot"
        target_label = "template food/product image slots" if food_requested else "template main subject slot"
        uploaded_role = "concrete_replacement_subjects"
    elif has_uploads and explicit_extraction:
        primary_relationship = "extract_composite_content"
        target_surface = "semantic_content_slots"
        target_label = "template semantic content slots"
        uploaded_role = "source_evidence"
    elif has_uploads and template_locked:
        primary_relationship = "fill_template_slots"
        target_surface = "replaceable_template_slots"
        target_label = "template replaceable slots"
        uploaded_role = "slot_variables"
    elif has_uploads:
        primary_relationship = "free_reference"
        target_surface = "generated_image"
        target_label = "generated image subject/style slots"
        uploaded_role = "creative_evidence"

    relationship = {
        "primary_relationship": primary_relationship,
        "frame_owner": "selected_template" if template_locked else "selected_or_retrieved_case",
        "uploaded_asset_role": uploaded_role,
        "target_surface": target_surface,
        "target_label": target_label,
        "uploaded_asset_count": len(asset_ids),
        "uploaded_asset_ids": asset_ids,
        "replacement_requested": replacement_requested,
        "explicit_extraction_requested": explicit_extraction,
        "food_or_product_subject_requested": food_requested,
        "subject_requested": subject_requested,
        "content_extraction": primary_relationship == "extract_composite_content",
        "template_slot_replacement": primary_relationship in TEMPLATE_REPLACEMENT_RELATIONSHIPS,
        "provider_input_priority": "hard" if primary_relationship in TEMPLATE_REPLACEMENT_RELATIONSHIPS else "normal",
        "review_expectations": _task_relationship_review_expectations(primary_relationship),
        "prompt_directive": _task_relationship_prompt_directive(primary_relationship, target_label),
    }
    if asset_ids:
        relationship["asset_relationships"] = [
            {
                "asset_id": asset_id,
                "relationship": primary_relationship,
                "target_surface": target_surface,
                "target_label": target_label,
            }
            for asset_id in asset_ids[:8]
        ]
    return relationship


def _relationship_source_text(
    *,
    user_prompt: str,
    uploaded_assets: list[dict[str, Any]],
    asset_inputs: list[CreativeRunAssetInput],
) -> str:
    parts: list[str] = [str(user_prompt or "")]
    for item in asset_inputs:
        parts.extend([str(item.role or ""), str(item.notes or "")])
    for asset in uploaded_assets:
        if not isinstance(asset, dict):
            continue
        parts.extend([str(asset.get("filename") or ""), str(asset.get("role") or ""), str(asset.get("intended_use") or "")])
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        parts.extend(
            [
                str(brief.get("visual_summary") or ""),
                " ".join(str(value) for value in (brief.get("identity_requirements") or [])[:4]),
                " ".join(str(value) for value in (brief.get("style_signals") or [])[:4]),
            ]
        )
    return " ".join(parts).lower()


def _relationship_explicit_extraction_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(提取|摘取|抽取|截取|拆出|只取|只提取|只作为内容|只作内容|内容证据|extract|content\s+only|source\s+content|copy\s+text|take\s+the\s+copy)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _relationship_content_evidence_requested(text: str) -> bool:
    non_subject_content = bool(
        re.search(
            r"(文案|文字|标题|副标题|价格|优惠|套餐|规则|购买|菜单|周卡|copy|text|headline|subtitle|price|offer|promotion|menu|source\s+poster)",
            text,
            flags=re.IGNORECASE,
        )
    )
    qr_content = (not _qr_explicitly_excluded(text)) and _qr_requested_in_text(text)
    return (non_subject_content or qr_content) and _uploaded_content_source_requested(text)


def _relationship_replacement_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(替换|换成|换掉|替掉|取代|replace|swap|substitute)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _relationship_food_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(食物|菜品|菜图|餐品|餐食|饭|三明治|牛肉|肥牛|虾|三文鱼|意面|碗|food|dish|meal|menu\s+item|product\s+photo|food\s+photo)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _relationship_subject_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(主体|主图|产品|商品|人物|照片|图片|素材|main\s+subject|subject|product|uploaded\s+(image|asset|photo|reference))",
            text,
            flags=re.IGNORECASE,
        )
    )


def _task_relationship_review_expectations(primary_relationship: str) -> list[str]:
    if primary_relationship == "replace_template_food_subject":
        return [
            "uploaded_replacement_subjects_visible",
            "template_food_slots_replaced",
            "selected_template_frame_preserved",
            "no_uploaded_source_layout_copy",
        ]
    if primary_relationship == "replace_template_subject":
        return [
            "uploaded_replacement_subject_visible",
            "template_subject_slot_replaced",
            "selected_template_frame_preserved",
            "no_uploaded_source_layout_copy",
        ]
    if primary_relationship == "extract_composite_content":
        return [
            "uploaded_content_evidence_used",
            "uploaded_source_layout_not_copied",
            "selected_template_frame_preserved",
        ]
    return []


def _task_relationship_prompt_directive(primary_relationship: str, target_label: str | None) -> str:
    target = target_label or "the requested slots"
    if primary_relationship in TEMPLATE_REPLACEMENT_RELATIONSHIPS:
        return (
            f"Use uploaded reference images as concrete replacement subjects for {target}. "
            "Preserve their visible subject identity and complete content while keeping the template composition, hierarchy, lighting, and layout rhythm."
        )
    if primary_relationship == "extract_composite_content":
        return (
            f"Use uploaded images as semantic source evidence for {target}. "
            "Extract requested content only; do not copy the uploaded layout or frame."
        )
    return ""


def _asset_frame_strategy(
    *,
    user_prompt: str,
    uploaded_assets: list[dict[str, Any]],
    binding_plan: AssetBindingPlan,
    template_locked: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bindings = [item.model_dump(mode="json") for item in binding_plan.bindings]
    text = _frame_strategy_text(user_prompt=user_prompt, uploaded_assets=uploaded_assets, bindings=bindings)
    layout_rejected = _layout_rejection_requested(text)
    replacement_relationship = _task_relationship_replaces_template_subject(task_relationship_model)
    content_extraction = False if replacement_relationship else _content_extraction_requested(text, bindings)
    continuation_frame_requested = _continuation_frame_requested(text, bindings) and not layout_rejected
    uploaded_frame_requested = (
        _uploaded_frame_requested(text, bindings) or continuation_frame_requested
    ) and not layout_rejected
    retrieval_hints = _asset_retrieval_hints(
        text=text,
        uploaded_assets=uploaded_assets,
        bindings=bindings,
        content_extraction=content_extraction,
        uploaded_frame_requested=uploaded_frame_requested,
        task_relationship_model=task_relationship_model,
    )
    if template_locked:
        return {
            "mode": "template_frame_primary",
            "frame_source": "selected_template",
            "case_anchor_policy": "selected template controls the visual frame; uploads fill replaceable slots",
            "uploaded_layout_may_override_case": False,
            "content_extraction": content_extraction,
            "asset_ids": _strategy_asset_ids(uploaded_assets),
            "retrieval_hints": retrieval_hints,
            "reason": "A hand-selected template is active.",
        }
    if uploaded_frame_requested:
        return {
            "mode": "uploaded_frame_primary",
            "frame_source": "uploaded_asset",
            "case_anchor_policy": "retrieved cases support style, lighting, material, and finish only",
            "uploaded_layout_may_override_case": True,
            "content_extraction": False,
            "asset_ids": _strategy_asset_ids(uploaded_assets),
            "retrieval_hints": retrieval_hints,
            "continuation_frame": continuation_frame_requested,
            "reason": (
                "The user selected a starred history image as the continuation frame."
                if continuation_frame_requested
                else "The user explicitly asked to preserve or follow the uploaded layout/composition frame."
            ),
        }
    return {
        "mode": "case_frame_primary",
        "frame_source": "retrieved_case",
        "case_anchor_policy": "one retrieved case controls the main visual grammar; uploads fill semantic or identity slots",
        "uploaded_layout_may_override_case": False,
        "content_extraction": content_extraction,
        "asset_ids": _strategy_asset_ids(uploaded_assets),
        "retrieval_hints": retrieval_hints,
        "reason": (
            "Uploaded source looks like content evidence; extract content into a new case frame."
            if content_extraction
            else "No explicit uploaded-layout override was requested."
        ),
    }


def _relationship_from_context(asset_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(asset_context, dict):
        return {}
    relationship = asset_context.get("task_relationship_model")
    return relationship if isinstance(relationship, dict) else {}


def _task_relationship_replaces_template_subject(task_relationship_model: dict[str, Any] | None) -> bool:
    if not isinstance(task_relationship_model, dict):
        return False
    return str(task_relationship_model.get("primary_relationship") or "") in TEMPLATE_REPLACEMENT_RELATIONSHIPS


def _task_relationship_extracts_content(task_relationship_model: dict[str, Any] | None) -> bool:
    if not isinstance(task_relationship_model, dict):
        return False
    return str(task_relationship_model.get("primary_relationship") or "") == "extract_composite_content"


def _relationship_target_label(task_relationship_model: dict[str, Any] | None) -> str:
    if not isinstance(task_relationship_model, dict):
        return "the requested template slots"
    return str(task_relationship_model.get("target_label") or "the requested template slots")


def _compact_task_relationship_model(task_relationship_model: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(task_relationship_model, dict):
        return {}
    return {
        "primary_relationship": task_relationship_model.get("primary_relationship"),
        "frame_owner": task_relationship_model.get("frame_owner"),
        "uploaded_asset_role": task_relationship_model.get("uploaded_asset_role"),
        "target_surface": task_relationship_model.get("target_surface"),
        "target_label": task_relationship_model.get("target_label"),
        "uploaded_asset_count": task_relationship_model.get("uploaded_asset_count"),
        "content_extraction": bool(task_relationship_model.get("content_extraction")),
        "template_slot_replacement": bool(task_relationship_model.get("template_slot_replacement")),
        "provider_input_priority": task_relationship_model.get("provider_input_priority"),
        "review_expectations": (task_relationship_model.get("review_expectations") or [])[:4],
        "prompt_directive": _compact_strategy_text(str(task_relationship_model.get("prompt_directive") or ""), 260),
    }


def _frame_strategy_text(
    *,
    user_prompt: str,
    uploaded_assets: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> str:
    parts = [str(user_prompt or "")]
    for asset in uploaded_assets:
        if not isinstance(asset, dict):
            continue
        parts.extend([str(asset.get("filename") or ""), str(asset.get("role") or ""), str(asset.get("intended_use") or "")])
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        parts.extend(
            [
                str(brief.get("visual_summary") or ""),
                " ".join(str(item) for item in (brief.get("identity_requirements") or [])[:4]),
                " ".join(str(item) for item in (brief.get("style_signals") or [])[:5]),
            ]
        )
    for item in bindings:
        if not isinstance(item, dict):
            continue
        placement = item.get("placement_intent") if isinstance(item.get("placement_intent"), dict) else {}
        parts.extend(
            [
                str(item.get("role") or ""),
                str(item.get("constraint_strength") or ""),
                str(item.get("fusion_mode") or ""),
                str(item.get("binding_slot") or ""),
                str(placement.get("instruction") or ""),
                str(placement.get("target_label") or ""),
            ]
        )
    return " ".join(parts).lower()


def _asset_context_qr_intent(asset_context: dict[str, Any]) -> bool:
    if _qr_explicitly_excluded(asset_context.get("user_prompt")):
        return False
    parts: list[Any] = [asset_context.get("user_prompt")]
    for asset in asset_context.get("uploaded_assets", []) or []:
        if not isinstance(asset, dict):
            continue
        parts.extend([asset.get("filename"), asset.get("intended_use")])
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        parts.extend(
            [
                brief.get("visual_summary"),
                brief.get("identity_requirements"),
                brief.get("detected_text"),
            ]
        )
    return _qr_requested_in_text(" ".join(str(item or "") for item in parts))


def _qr_explicitly_excluded(value: Any) -> bool:
    return bool(QR_EXCLUSION_PATTERN.search(str(value or "")))


def _qr_requested_in_text(value: Any) -> bool:
    text = str(value or "")
    if not text:
        return False
    if _qr_explicitly_excluded(text):
        return False
    return bool(QR_INTENT_PATTERN.search(text))


def _uploaded_frame_requested(text: str, bindings: list[dict[str, Any]]) -> bool:
    return bool(
        re.search(
            r"(按.*(版式|布局|构图|排版|画面结构)|参考.*(版式|布局|构图|排版|画面结构)|沿用.*(版式|布局|构图|排版)|保持.*(版式|布局|构图|排版)|"
            r"以.*(上传|原图|参考图).*(底版|基础|基底)|基于.*(上传|原图|参考图).*(设计|修改|改造)|"
            r"same\s+(layout|composition|framing)|follow\s+(the\s+)?(layout|composition|framing)|use\s+.*(layout|composition|framing)\s+as\s+(the\s+)?(frame|reference))",
            text,
            flags=re.IGNORECASE,
        )
    )


def _continuation_frame_requested(text: str, bindings: list[dict[str, Any]]) -> bool:
    if re.search(
        r"(continue[_\s-]?modifying[_\s-]?selected[_\s-]?favorite[_\s-]?image|continuation\s+frame|"
        r"selected\s+starred.*history\s+image|starred.*history\s+image.*continuation|"
        r"星标.*(继续修改|继续编辑|延续|基底|底版|参考)|历史图.*(继续修改|继续编辑|延续|基底|底版))",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    for item in bindings:
        if not isinstance(item, dict) or item.get("role") != "composition_reference":
            continue
        placement = item.get("placement_intent") if isinstance(item.get("placement_intent"), dict) else {}
        joined = " ".join(
            str(value or "")
            for value in [
                item.get("fusion_mode"),
                item.get("binding_slot"),
                item.get("prompt_instruction"),
                placement.get("instruction"),
            ]
        )
        if re.search(r"(continuation\s+frame|continue[_\s-]?modifying|继续修改|继续编辑)", joined, flags=re.IGNORECASE):
            return True
    return False


def _layout_rejection_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(不要.*(沿用|复制|照搬).*(版式|布局|构图|排版)|不.*(沿用|复制|照搬).*(版式|布局|构图|排版)|只提取|仅提取|提取.*内容|摘取.*内容|"
            r"do\s+not\s+(copy|reuse|follow).*(layout|composition)|content\s+only|extract\s+content)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _content_extraction_requested(text: str, bindings: list[dict[str, Any]]) -> bool:
    if any(isinstance(item, dict) and item.get("fusion_mode") == "composite_content_source" for item in bindings):
        return True
    if _uploaded_content_source_requested(text):
        return True
    return bool(
        re.search(
            r"(菜单|周卡|整图|旧图|旧海报|截图|二维码|优惠|价格|套餐|配送|加购|文案|提取|摘取|内容|"
            r"menu|weekly card|poster source|screenshot|qr|offer|price|package|copy|extract)",
            text,
            flags=re.IGNORECASE,
        )
        and _layout_rejection_requested(text)
    )


def _asset_retrieval_hints(
    *,
    text: str,
    uploaded_assets: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    content_extraction: bool,
    uploaded_frame_requested: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user_intent_text = _user_intent_text(text)
    category_hints: list[str] = []
    use_case_hints: list[str] = []
    style_hints: list[str] = []
    if re.search(r"(海报|菜单|周卡|活动|poster|menu|flyer|campaign)", text, flags=re.IGNORECASE):
        category_hints.append("poster")
        use_case_hints.append("poster")
    if re.search(r"(商品|产品|电商|包装|product|ecommerce|marketplace|listing|package)", text, flags=re.IGNORECASE):
        use_case_hints.extend(["ecommerce", "product-listing"])
    if re.search(r"(食物|食品|美食|菜品|餐饮|咖啡|饮料|food|meal|dish|restaurant|coffee|beverage)", text, flags=re.IGNORECASE):
        use_case_hints.append("poster")
    if re.search(r"(高级|高端|奢华|质感|premium|luxury|high-end)", user_intent_text, flags=re.IGNORECASE):
        style_hints.extend(["premium", "luxury"])
    if re.search(r"(极简|干净|留白|minimal|clean)", user_intent_text, flags=re.IGNORECASE):
        style_hints.extend(["minimal", "clean"])
    role_terms = _dedupe(str(item.get("role") or "") for item in bindings if isinstance(item, dict))
    fusion_terms = _dedupe(str(item.get("fusion_mode") or "") for item in bindings if isinstance(item, dict))
    asset_terms: list[str] = []
    for asset in uploaded_assets[:4]:
        if not isinstance(asset, dict):
            continue
        brief = asset.get("brief") if isinstance(asset.get("brief"), dict) else {}
        asset_terms.extend(
            [
                str(asset.get("filename") or ""),
                str(asset.get("role") or ""),
                str(brief.get("visual_summary") or ""),
                " ".join(str(item) for item in (brief.get("style_signals") or [])[:4]),
            ]
        )
    if _task_relationship_replaces_template_subject(task_relationship_model):
        intent = "uploaded assets supply concrete replacement subjects for selected template slots; keep one template-compatible visual frame"
    else:
        intent = (
            "uploaded frame/layout reference should drive composition; find cases for compatible style polish"
            if uploaded_frame_requested
            else "uploaded source supplies content/identity slots; find one fresh visual frame"
            if content_extraction
            else "uploaded assets fill identity or style slots; find one compatible visual frame"
        )
    return {
        "query_terms": _compact_strategy_text(" ".join([intent, *asset_terms, *role_terms, *fusion_terms]), 760),
        "category_filters": _dedupe(category_hints),
        "use_case_filters": _dedupe(use_case_hints),
        "style_filters": _dedupe(style_hints),
    }


def _user_intent_text(text: str) -> str:
    marker = " uploaded asset intent:"
    if marker in text:
        return text.split(marker, 1)[0]
    return text


def _strategy_asset_ids(uploaded_assets: list[dict[str, Any]]) -> list[str]:
    return [
        str(item.get("asset_id"))
        for item in uploaded_assets
        if isinstance(item, dict) and item.get("asset_id")
    ][:8]


def _compact_strategy_text(value: str, limit: int) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."


def _normalize_asset_inputs(raw_assets: list[str | CreativeRunAssetInput]) -> list[CreativeRunAssetInput]:
    inputs: list[CreativeRunAssetInput] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_assets or []:
        if isinstance(raw, str):
            item = CreativeRunAssetInput(asset_id=raw)
        else:
            item = raw
        key = (item.asset_id, item.role or "")
        if not item.asset_id or key in seen:
            continue
        seen.add(key)
        inputs.append(item)
    return inputs


def _resolve_uploaded_asset(asset_id: str, *, veyra_user_id: int | None = None) -> UploadedAsset | None:
    asset = get_uploaded_asset(asset_id)
    if not asset:
        return None
    if veyra_user_id is None:
        return asset
    try:
        owner_id = int(asset.veyra_user_id or 0)
    except (TypeError, ValueError):
        owner_id = 0
    if owner_id and owner_id != int(veyra_user_id):
        return None
    return asset


def _brief_for(asset: UploadedAsset) -> AssetBrief:
    if asset.brief:
        return asset.brief
    role = asset.role or "subject_reference"
    return AssetBrief(
        asset_id=asset.asset_id,
        role=role,
        constraint_strength=asset.constraint_strength,
        visual_summary=f"Uploaded image `{asset.filename}`.",
        identity_requirements=["use as uploaded visual reference"],
        usable_as_input_image=asset.status == "ready",
        provider_input_required=role in HARD_REFERENCE_ROLES,
        warnings=["asset_brief_missing"],
    )


def _template_lock_contract(template_case_id: str | None) -> TemplateLockContract | None:
    if not template_case_id:
        return None
    template = get_prompt_case(template_case_id)
    title = template.title if template else template_case_id
    return TemplateLockContract(
        contract_id=new_id("tlc"),
        locked_case_id=template_case_id,
        locked_elements=LOCKED_TEMPLATE_ELEMENTS,
        replaceable_slots=REPLACEABLE_TEMPLATE_SLOTS,
        summary=(
            f"Selected template `{title}` controls the frame. Uploaded assets fill replaceable slots and must not "
            "override the selected template's composition, lighting, layout, background density, mood, or visual rhythm."
        ),
    )


def _binding_plan(
    asset_inputs: list[CreativeRunAssetInput],
    brief_by_id: dict[str, AssetBrief],
    template_lock: TemplateLockContract | None,
    *,
    user_prompt: str = "",
    task_relationship_model: dict[str, Any] | None = None,
) -> AssetBindingPlan:
    bindings: list[AssetBinding] = []
    conflicts: list[dict[str, Any]] = []
    for item in asset_inputs:
        brief = brief_by_id.get(item.asset_id)
        if not brief:
            conflicts.append({"type": "asset_missing", "asset_id": item.asset_id, "resolution": "ignore_missing_asset"})
            continue
        requested_role = item.role or brief.role
        strength: ConstraintStrength = item.constraint_strength or brief.constraint_strength
        role, strength, intent_upgrade = _role_for_prompt_intent(
            role=requested_role,
            strength=strength,
            user_prompt=user_prompt,
            notes=item.notes,
            brief=brief,
            template_locked=template_lock is not None,
            task_relationship_model=task_relationship_model,
        )
        binding_input = item.model_copy(update={"role": role, "constraint_strength": strength})
        brief = _brief_for_binding(brief, binding_input)
        fusion_policy = _fusion_policy(
            role=role,
            strength=strength,
            brief=brief,
            user_prompt=user_prompt,
            notes=item.notes,
            template_locked=template_lock is not None,
            task_relationship_model=task_relationship_model,
        )
        provider_required = _provider_input_required_for_binding(
            role=role,
            strength=strength,
            brief=brief,
            fusion_policy=fusion_policy,
            user_prompt=user_prompt,
            notes=item.notes,
        )
        blocked = LOCKED_TEMPLATE_ELEMENTS if template_lock else []
        conflict_resolution = intent_upgrade
        if template_lock and role in {"style_reference", "composition_reference", "color_reference", "background_reference"}:
            conflict_resolution = "keep selected template as frame; use uploaded asset only as compatible slot evidence"
            conflicts.append(
                {
                    "type": "template_asset_priority",
                    "asset_id": item.asset_id,
                    "role": role,
                    "resolution": conflict_resolution,
                }
            )
        if intent_upgrade:
            conflicts.append(
                {
                    "type": "asset_intent_auto_upgrade",
                    "asset_id": item.asset_id,
                    "from_role": requested_role,
                    "to_role": role,
                    "resolution": intent_upgrade,
                }
            )
        bindings.append(
            AssetBinding(
                asset_id=item.asset_id,
                role=role,
                constraint_strength=strength,
                binding_slot=str(fusion_policy.get("binding_slot") or ROLE_TO_SLOT.get(role, "minor_props")),
                fusion_mode=str(fusion_policy.get("fusion_mode") or "reference"),
                placement_intent=fusion_policy.get("placement_intent") or {},
                target_surface=fusion_policy.get("target_surface"),
                allowed_to_override=ROLE_ALLOWED_OVERRIDES.get(role, ["compatible details"]),
                not_allowed_to_override=blocked,
                provider_input_required=provider_required,
                prompt_instruction=_prompt_instruction(
                    role=role,
                    strength=strength,
                    brief=brief,
                    template_locked=template_lock is not None,
                    notes=item.notes,
                    fusion_policy=fusion_policy,
                ),
                conflict_resolution=conflict_resolution,
                review_expectations=list(fusion_policy.get("review_expectations") or []),
            )
        )
    provider_plan = _provider_input_plan(bindings, task_relationship_model=task_relationship_model)
    return AssetBindingPlan(
        plan_id=new_id("abp"),
        template_lock_contract_id=template_lock.contract_id if template_lock else None,
        mode="template_lock" if template_lock else "free_agent",
        bindings=bindings,
        conflicts=conflicts,
        provider_input_plan=provider_plan,
    )


def _prompt_instruction(
    *,
    role: str,
    strength: ConstraintStrength,
    brief: AssetBrief,
    template_locked: bool,
    notes: str | None,
    fusion_policy: dict[str, Any] | None = None,
) -> str:
    base = brief.visual_summary or f"Use uploaded {role.replace('_', ' ')} image."
    identity = "; ".join(brief.identity_requirements[:4])
    style = "; ".join(brief.style_signals[:4])
    if template_locked:
        prefix = "Bind this uploaded reference image into the selected template slot without changing the template frame."
    else:
        prefix = "Use this uploaded reference image as creative evidence for the free-agent plan."
    fusion_policy = fusion_policy or {}
    fusion_mode = str(fusion_policy.get("fusion_mode") or "reference")
    placement = fusion_policy.get("placement_intent") if isinstance(fusion_policy.get("placement_intent"), dict) else {}
    target_label = placement.get("target_label") or fusion_policy.get("target_surface")
    subject_rule = "Replace the template's original subject with the uploaded subject while preserving the selected template's visual frame."
    if role == "subject_reference" and fusion_mode == TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE:
        target = target_label or "the selected template subject slot"
        subject_rule = (
            f"Use the uploaded image as a concrete replacement subject for {target}. "
            "Preserve the uploaded subject's visible identity, proportions, and complete content; map it into the template's existing slot geometry. "
            "Do not crop it into arbitrary fragments, add new container frames, treat it as a style reference, or copy the uploaded image's source layout."
        )
    if role == "subject_reference" and fusion_mode == "composite_content_source":
        qr_intent = bool(fusion_policy.get("qr_intent"))
        content_targets = (
            "the user-requested food/product evidence, copy, source QR, logo, or business facts"
            if qr_intent
            else "the user-requested food/product evidence, copy, logo, or business facts"
        )
        qr_policy = (
            "Preserve QR or scan-code details only from a real uploaded/source QR or explicit user QR request. "
            if qr_intent
            else "Do not add QR codes, scan-code blocks, blank QR placeholders, or decorative code areas. "
        )
        subject_rule = (
            "Treat the uploaded image as a source of extractable content, not as the visual frame. "
            f"Extract only {content_targets}, then rebuild those elements inside the selected visual grammar. "
            + qr_policy
            + "Do not copy its whole poster/menu/screenshot layout, grid, background, density, original information architecture, or visual rhythm."
        )
    role_rule = {
        "subject_reference": subject_rule,
        "logo_reference": _logo_prompt_rule(fusion_mode=fusion_mode, target_label=target_label),
        "face_reference": "Preserve uploaded face identity cues while adapting pose, lighting, and scene to the selected template.",
        "background_reference": "Use background content only if compatible with the template lock or explicitly requested by the user.",
        "style_reference": "Use only compatible color, light, material, and mood cues; do not override the selected template style.",
        "composition_reference": (
            "Use this uploaded reference image as the selected continuation frame. "
            "Preserve its composition, lighting, palette, spatial hierarchy, and visual rhythm; apply the current user request as the highest-priority local edit. "
            "When the requested edit conflicts with a visible object, prop, text, or surface in the reference, replace that conflicting detail instead of preserving it."
            if fusion_mode == "continuation_frame"
            else "Use only secondary camera-angle or spacing hints; do not override the selected template composition."
        ),
        "color_reference": "Use compatible palette/accent cues without replacing the selected template color rhythm.",
        "negative_reference": "Avoid the visual traits represented by this uploaded reference.",
    }.get(role, "Use the uploaded asset as compatible visual evidence.")
    fusion_text = _fusion_prompt_suffix(fusion_policy)
    extra = f" User notes: {notes}" if notes else ""
    return f"{prefix} {role_rule}{fusion_text} Reference strength: {strength}. Asset brief: {base} Identity requirements: {identity}. Style signals: {style}.{extra}"


def _provider_input_plan(
    bindings: list[AssetBinding],
    *,
    task_relationship_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reference_ids = _dedupe([item.asset_id for item in bindings if item.provider_input_required])
    operation = "image_edit_with_reference_images" if reference_ids else "generate"
    placement_targets = [
        {
            "asset_id": item.asset_id,
            "role": item.role,
            "fusion_mode": item.fusion_mode,
            "mode": (item.placement_intent or {}).get("mode"),
            "target_surface": item.target_surface,
            "target_label": (item.placement_intent or {}).get("target_label"),
            "source": (item.placement_intent or {}).get("source"),
        }
        for item in bindings
        if item.placement_intent or item.target_surface or item.fusion_mode not in {"reference", ""}
    ]
    return {
        "operation": operation,
        "reference_image_asset_ids": reference_ids,
        "reference_image_count": len(reference_ids),
        "requires_image_reference": bool(reference_ids),
        "fusion_modes": _dedupe([item.fusion_mode for item in bindings if item.fusion_mode]),
        "placement_targets": placement_targets,
        "review_expectations": _dedupe([expectation for item in bindings for expectation in item.review_expectations]),
        "task_relationship_model": _compact_task_relationship_model(task_relationship_model),
        "provider_contract": (
            "Uploaded references that the user expects to influence the result must be sent to capable providers as input images. "
            "Provider visibility does not make the uploaded image the frame owner; template and asset-frame strategy still control visual priority."
        ),
    }


def _provider_input_required_for_binding(
    *,
    role: str,
    strength: ConstraintStrength,
    brief: AssetBrief,
    fusion_policy: dict[str, Any],
    user_prompt: str,
    notes: str | None,
) -> bool:
    if role == "negative_reference":
        return False
    if brief.provider_input_required or role in HARD_REFERENCE_ROLES or fusion_policy.get("provider_input_required"):
        return True
    if strength == "required":
        return True
    source_text, _ = _intent_source_text(user_prompt=user_prompt, notes=notes, brief=brief)
    if strength == "strong" and role in {"style_reference", "composition_reference", "color_reference"}:
        return True
    return _uploaded_reference_visibility_requested(source_text)


def _brief_for_binding(brief: AssetBrief, requested: CreativeRunAssetInput) -> AssetBrief:
    role = requested.role or brief.role
    strength = requested.constraint_strength or brief.constraint_strength
    if role == "logo_reference":
        return brief.model_copy(
            update={
                "role": role,
                "constraint_strength": strength,
                "visual_summary": _role_adjusted_summary(brief.visual_summary, previous_role=brief.role, role=role),
                "identity_requirements": [
                    "preserve the uploaded logo shape, proportions, colors, and readable brand text",
                    "place the uploaded logo at the user-specified target surface",
                ],
                "style_signals": [],
                "provider_input_required": True,
            }
        )
    if role == brief.role and strength == brief.constraint_strength:
        return brief
    return brief.model_copy(
        update={
            "role": role,
            "constraint_strength": strength,
            "visual_summary": _role_adjusted_summary(brief.visual_summary, previous_role=brief.role, role=role),
            "provider_input_required": bool(
                brief.provider_input_required
                or role in HARD_REFERENCE_ROLES
                or (strength == "required" and role in {"style_reference", "composition_reference", "color_reference"})
            ),
        }
    )


def _role_adjusted_summary(summary: str, *, previous_role: str, role: str) -> str:
    if role == previous_role:
        return summary
    clean = (summary or "").strip()
    previous_label = previous_role.replace("_", " ")
    role_label = role.replace("_", " ")
    if clean.lower().startswith(f"{previous_label} image"):
        return f"{role_label} image" + clean[len(f"{previous_label} image"):]
    if clean:
        return f"{role_label} image requested for this run. Visual analysis: {clean}"
    return f"{role_label} image requested for this run."


def _asset_for_context(asset: UploadedAsset, brief: AssetBrief | None, requested_inputs: list[CreativeRunAssetInput] | None = None) -> dict[str, Any]:
    requested_inputs = requested_inputs or []
    primary_input = _primary_asset_input(requested_inputs)
    role = primary_input.role if primary_input and primary_input.role else asset.role or (brief.role if brief else None)
    strength = _strongest_requested_strength(requested_inputs) or asset.constraint_strength
    display_brief = _brief_for_binding(brief, primary_input) if brief and primary_input else brief
    return {
        "asset_id": asset.asset_id,
        "filename": asset.filename,
        "mime_type": asset.mime_type,
        "status": asset.status,
        "role": role,
        "roles": _dedupe([item.role for item in requested_inputs if item.role] or ([role] if role else [])),
        "constraint_strength": strength,
        "intended_use": asset.intended_use,
        "source_url": asset.source_url,
        "brief": display_brief.model_dump(mode="json") if display_brief else None,
    }


def _role_for_prompt_intent(
    *,
    role: str,
    strength: ConstraintStrength,
    user_prompt: str,
    notes: str | None,
    brief: AssetBrief,
    template_locked: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> tuple[str, ConstraintStrength, str | None]:
    source_text, _ = _intent_source_text(user_prompt=user_prompt, notes=notes, brief=brief)
    if _task_relationship_replaces_template_subject(task_relationship_model):
        if role in {"logo_reference", "face_reference", "background_reference", "negative_reference"}:
            return role, strength, None
        upgraded_strength: ConstraintStrength = "required" if strength == "soft" else strength
        target_label = _relationship_target_label(task_relationship_model)
        reason = (
            "user prompt asks uploaded images to replace selected-template subject slots; "
            f"treat the uploaded asset as a concrete replacement subject for {target_label}, not as style or composite content evidence"
        )
        if role != "subject_reference":
            return "subject_reference", upgraded_strength, reason
        return role, upgraded_strength, reason
    if not _uploaded_content_source_requested(source_text):
        return role, strength, None
    if role in {"logo_reference", "face_reference", "background_reference", "negative_reference"}:
        return role, strength, None
    upgraded_strength: ConstraintStrength = "required" if strength == "soft" else strength
    qr_intent = _qr_requested_in_text(source_text)
    content_label = "content/copy/QR" if qr_intent else "content/copy"
    reason = (
        f"user prompt asks to migrate uploaded image {content_label} into the selected template frame; "
        "treat the uploaded asset as semantic content evidence, not as the frame"
        if template_locked
        else f"user prompt asks to extract uploaded image {content_label} into a new visual frame"
    )
    if role != "subject_reference":
        return "subject_reference", upgraded_strength, reason
    return role, upgraded_strength, reason


def _fusion_policy(
    *,
    role: str,
    strength: ConstraintStrength,
    brief: AssetBrief,
    user_prompt: str,
    notes: str | None,
    template_locked: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_text, source = _intent_source_text(user_prompt=user_prompt, notes=notes, brief=brief)
    placement = _placement_intent(
        role=role,
        text=source_text,
        source=source,
        template_locked=template_locked,
        task_relationship_model=task_relationship_model,
    )
    fusion_mode = _fusion_mode(
        role=role,
        placement=placement,
        text=source_text,
        template_locked=template_locked,
        task_relationship_model=task_relationship_model,
    )
    qr_intent = _qr_requested_in_text(source_text)
    provider_input_required = role in HARD_REFERENCE_ROLES or strength == "required"
    if fusion_mode in {
        "logo_product_surface",
        "logo_canvas_brand_mark",
        "logo_template_slot",
        "subject_identity",
        TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE,
        "composite_content_source",
        "face_identity",
        "background_identity",
    }:
        provider_input_required = True
    review_expectations = _review_expectations(
        role=role,
        fusion_mode=fusion_mode,
        placement=placement,
        template_locked=template_locked,
    )
    return {
        "fusion_mode": fusion_mode,
        "binding_slot": (
            "semantic_content"
            if fusion_mode == "composite_content_source"
            else placement.get("target_surface")
            if fusion_mode == TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE
            else None
        ),
        "placement_intent": placement,
        "target_surface": placement.get("target_surface"),
        "provider_input_required": provider_input_required,
        "review_expectations": review_expectations,
        "qr_intent": qr_intent,
    }


def _intent_source_text(*, user_prompt: str, notes: str | None, brief: AssetBrief) -> tuple[str, str]:
    note_text = " ".join(str(notes or "").split())
    if note_text:
        return f"{note_text} {user_prompt or ''} {brief.visual_summary or ''}".strip().lower(), "notes"
    prompt_text = " ".join(str(user_prompt or "").split())
    if prompt_text:
        return f"{prompt_text} {brief.visual_summary or ''}".strip().lower(), "user_prompt"
    return (brief.visual_summary or "").lower(), "asset_brief"


def _placement_intent(
    *,
    role: str,
    text: str,
    source: str,
    template_locked: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if role == "subject_reference" and _task_relationship_replaces_template_subject(task_relationship_model):
        target_surface = str(task_relationship_model.get("target_surface") or "main_subject_slot") if isinstance(task_relationship_model, dict) else "main_subject_slot"
        target_label = _relationship_target_label(task_relationship_model)
        return {
            "mode": TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE,
            "target_surface": target_surface,
            "target_label": target_label,
            "source": "task_relationship_model",
            "relationship": str(task_relationship_model.get("primary_relationship") or "") if isinstance(task_relationship_model, dict) else "",
            "asset_count": task_relationship_model.get("uploaded_asset_count") if isinstance(task_relationship_model, dict) else None,
            "instruction": (
                f"Use uploaded reference images as concrete replacement subjects for {target_label}; "
                "replace the template's original slot content without inheriting uploaded image layout."
            ),
        }
    if role == "subject_reference" and _composite_source_requested(text):
        qr_intent = _qr_requested_in_text(text)
        return {
            "mode": "content_evidence",
            "target_surface": "semantic_content_slots",
            "qr_intent": qr_intent,
            "target_label": (
                "content, copy, source QR, food, or business information slots"
                if qr_intent
                else "content, copy, food, or business information slots"
            ),
            "source": source,
            "instruction": (
                "Use the uploaded image as source evidence for replaceable content slots, not as the composition or layout frame."
            ),
        }
    scene = _scene_surface_target(text)
    canvas = _canvas_overlay_target(text)
    if scene:
        return {
            "mode": "scene_surface",
            "target_surface": scene["id"],
            "target_label": scene["label"],
            "source": source,
            "instruction": f"Fuse the uploaded asset into {scene['label']} as a real element inside the generated scene.",
        }
    if canvas:
        return {
            "mode": "canvas_overlay",
            "target_surface": canvas["id"],
            "target_label": canvas["label"],
            "source": source,
            "instruction": f"Use the uploaded asset as a brand/layout element at {canvas['label']}.",
        }
    if role == "logo_reference":
        return {
            "mode": "template_slot" if template_locked else "brand_area",
            "target_surface": "logo_brand_slot",
            "target_label": "模板 Logo/品牌标识槽" if template_locked else "合适的品牌标识区域",
            "source": "role_default",
            "instruction": "Bind the uploaded logo to the appropriate brand slot; do not invent a replacement logo.",
        }
    if role == "subject_reference":
        return {
            "mode": "template_slot" if template_locked else "main_subject",
            "target_surface": "main_subject_slot",
            "target_label": "主商品/主体位置",
            "source": "role_default",
            "instruction": "Use the uploaded asset as the main subject identity inside the image.",
        }
    if role == "face_reference":
        return {
            "mode": "identity_reference",
            "target_surface": "face_identity",
            "target_label": "人物脸部身份",
            "source": "role_default",
            "instruction": "Preserve face identity cues while adapting pose and lighting.",
        }
    if role == "background_reference":
        return {
            "mode": "background_slot",
            "target_surface": "background_slot",
            "target_label": "背景/场景槽位",
            "source": "role_default",
            "instruction": "Use background content only when compatible with the user request and template lock.",
        }
    if role == "composition_reference" and _continuation_frame_requested(text, []):
        return {
            "mode": "continuation_frame",
            "target_surface": "selected_history_frame",
            "target_label": "星标历史图继续修改基底",
            "source": source,
            "instruction": (
                "Use the uploaded starred history image as the continuation frame while applying the current user edits over conflicting reference details."
            ),
        }
    return {
        "mode": "reference",
        "target_surface": None,
        "target_label": None,
        "source": "role_default",
        "instruction": "",
    }


def _fusion_mode(
    *,
    role: str,
    placement: dict[str, Any],
    text: str,
    template_locked: bool,
    task_relationship_model: dict[str, Any] | None = None,
) -> str:
    mode = placement.get("mode")
    if role == "logo_reference":
        if _typographic_brand_text_only(text):
            return "typographic_brand_text"
        if mode == "scene_surface":
            return "logo_product_surface"
        if mode == "canvas_overlay":
            return "logo_canvas_brand_mark"
        return "logo_template_slot" if template_locked else "logo_brand_mark"
    if role == "subject_reference":
        if mode == TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE or _task_relationship_replaces_template_subject(task_relationship_model):
            return TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE
        if mode == "content_evidence" or _composite_source_requested(text):
            return "composite_content_source"
        return "subject_identity"
    if role == "face_reference":
        return "face_identity"
    if role == "background_reference":
        return "background_identity" if _background_replace_requested(text) else "background_mood"
    if role == "style_reference":
        return "style_signal"
    if role == "composition_reference":
        if mode == "continuation_frame":
            return "continuation_frame"
        return "composition_signal"
    if role == "color_reference":
        return "color_signal"
    if role == "negative_reference":
        return "negative_visual_exclusion"
    return "reference"


def _scene_surface_target(text: str) -> dict[str, str] | None:
    checks = [
        (
            r"(右胸|右胸口|右胸前|右侧胸口|right chest|right breast|right pectoral)",
            "apparel_right_chest",
            "衣服右胸位置",
        ),
        (
            r"(左胸|左胸口|左胸前|左侧胸口|left chest|left breast|left pectoral)",
            "apparel_left_chest",
            "衣服左胸位置",
        ),
        (
            r"(领子|领口|衣领|collar|neckline)",
            "apparel_collar",
            "衣领或领口位置",
        ),
        (
            r"(胸口|左胸|右胸|衣服上|衣服表面|衣服胸前|polo|polo衫|t恤|t-shirt|shirt|hoodie|sweatshirt|chest|apparel|clothing|fabric)",
            "apparel_chest_or_surface",
            "衣服胸口或服装表面",
        ),
        (
            r"(商品上|产品上|产品表面|商品表面|包装上|包装正面|盒子上|盒身|盒面|package|packaging|box front|product surface)",
            "product_or_package_surface",
            "商品或包装表面",
        ),
        (
            r"(瓶身|瓶子上|罐身|杯身|杯子上|bottle|jar|can|cup|mug)",
            "container_surface",
            "瓶身、杯身或容器表面",
        ),
        (r"(鞋面|鞋侧|鞋舌|鞋上|sneaker|shoe|footwear)", "footwear_surface", "鞋面或鞋侧表面"),
        (
            r"(设备上|机身|外壳|手机背面|电脑外壳|device|phone back|case|laptop lid)",
            "device_surface",
            "设备外壳或机身表面",
        ),
        (
            r"(墙面|门头|招牌|店招|店铺外立面|wall|signboard|storefront)",
            "signage_or_wall_surface",
            "墙面、招牌或门头表面",
        ),
        (
            r"(贴在|印在|绣在|烫印|压印|刻在|附着|贴附|融合到|apply to|printed on|embroidered on|attached to)",
            "explicit_scene_surface",
            "用户指定的物体表面",
        ),
    ]
    for pattern, target_id, label in checks:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {"id": target_id, "label": label}
    return None


def _canvas_overlay_target(text: str) -> dict[str, str] | None:
    checks = [
        (r"(右下|右下角|bottom right)", "canvas_bottom_right", "画布右下角"),
        (r"(左下|左下角|bottom left)", "canvas_bottom_left", "画布左下角"),
        (r"(右上|右上角|top right)", "canvas_top_right", "画布右上角"),
        (r"(左上|左上角|top left)", "canvas_top_left", "画布左上角"),
        (r"(底部居中|下方居中|bottom center)", "canvas_bottom_center", "画布底部居中"),
        (r"(顶部居中|top center)", "canvas_top_center", "画布顶部居中"),
        (
            r"(角标|水印|边角|海报下方|海报底部|页脚|页眉|poster corner|watermark|corner badge|footer|header)",
            "poster_brand_area",
            "海报品牌区、角标或页眉页脚",
        ),
    ]
    for pattern, target_id, label in checks:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {"id": target_id, "label": label}
    return None


def _typographic_brand_text_only(text: str) -> bool:
    return bool(re.search(r"(只要文字|品牌名文字|文字logo|纯文字|wordmark only|text-only logo)", text, flags=re.IGNORECASE))


def _background_replace_requested(text: str) -> bool:
    return bool(re.search(r"(替换背景|换背景|用上传.*背景|背景必须|background replacement|use uploaded background)", text, flags=re.IGNORECASE))


def _composite_source_requested(text: str) -> bool:
    extraction_markers = [
        "摘取",
        "提取",
        "抽取",
        "拆出",
        "拆成",
        "只取",
        "只提取",
        "只作为内容",
        "copy text",
        "extract",
        "source content",
    ]
    source_layout_markers = [
        "菜单",
        "周卡",
        "旧海报",
        "成品海报",
        "整页",
        "信息表",
        "整图",
        "旧图",
        "上次的图片",
        "原图里面",
        "图片里面",
        "版式",
        "截图",
        "menu",
        "weekly card",
        "finished poster",
        "source poster",
        "flyer",
        "screenshot",
        "layout",
        "source sheet",
    ]
    content_only_markers = [
        "不要沿用原版式",
        "不要沿用.*布局",
        "不要复制.*布局",
        "不要复制.*版式",
        "只提取内容",
        "只作为内容",
        "只取内容",
        "content only",
        "do not copy.*layout",
        "do not inherit.*layout",
    ]
    has_extraction = any(re.search(marker, text, flags=re.IGNORECASE) for marker in extraction_markers)
    has_source_layout = any(re.search(marker, text, flags=re.IGNORECASE) for marker in source_layout_markers)
    explicit_content_only = any(re.search(marker, text, flags=re.IGNORECASE) for marker in content_only_markers)
    hard_single_subject = _hard_single_subject_requested(text)
    if explicit_content_only:
        return True
    return (has_extraction and has_source_layout and not hard_single_subject) or _uploaded_content_source_requested(text)


def _uploaded_content_source_requested(text: str) -> bool:
    if not text:
        return False
    if _hard_single_subject_requested(text) and not re.search(
        r"(文案|文字|标题|菜品|菜名|菜单|套餐|价格|优惠|配送|加购|页脚|购买|规则|食物内容|食物部分|copy|text|menu|offer|price)",
        text,
        flags=re.IGNORECASE,
    ):
        return False
    uploaded_source = bool(
        re.search(
            r"(上传(的)?(图片|图|素材|参考图)|参考图|上次(的)?图片|原图|图里|图中|图片里|图片中|uploaded\s+(image|asset|reference)|source\s+(image|poster|asset))",
            text,
            flags=re.IGNORECASE,
        )
    )
    content_markers = bool(
        re.search(
            r"(食物内容|食物部分|菜品|菜名|食品|美食|餐食|商品内容|产品内容|文案|文字|标题|价格|优惠|套餐|配送|加购|页脚|购买|规则|二维码|qr|copy|text|menu|food|dish|product|offer|price)",
            text,
            flags=re.IGNORECASE,
        )
    )
    transfer_markers = bool(
        re.search(
            r"(摘取|提取|抽取|取出|保留|完整保留|体现|放到|匹配到|迁移|转移|套到|套进|设计成|改成|替换|replace|extract|migrate|transfer|preserve|fit\s+into|adapt\s+into)",
            text,
            flags=re.IGNORECASE,
        )
    )
    template_markers = bool(
        re.search(
            r"(模板|案例|海报|poster|template|case|layout)",
            text,
            flags=re.IGNORECASE,
        )
    )
    return uploaded_source and content_markers and (transfer_markers or template_markers)


def _uploaded_reference_visibility_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(上传(的)?(图片|图|素材|参考图)|参考图|上次(的)?图片|原图|图里|图中|图片里|图片中|"
            r"uploaded\s+(image|asset|reference)|source\s+(image|poster|asset))",
            text,
            flags=re.IGNORECASE,
        )
    )


def _hard_single_subject_requested(text: str) -> bool:
    return bool(
        re.search(
            r"(产品作为主体|商品作为主体|主体必须|保留.*产品|保留.*商品|产品.*保留|商品.*保留|保留.*包装|保留.*logo|保留.*人脸|preserve.*product identity|preserve.*product|use.*as main subject)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _logo_prompt_rule(*, fusion_mode: str, target_label: str | None) -> str:
    target = target_label or "the requested brand placement"
    collar_exclusion = ""
    if "胸" in target or "chest" in target.lower():
        collar_exclusion = " Do not move it to the collar, neckline, hang tag, sleeve, footer, or poster corner."
    if fusion_mode == "logo_product_surface":
        return (
            f"Use the uploaded logo image as the actual logo reference and naturally print, embroider, attach, or integrate it on {target}. "
            "Preserve the uploaded logo shape, proportions, colors, and readable brand text. Do not place it as a poster footer, corner badge, watermark, border decoration, or separate sticker."
            f"{collar_exclusion}"
        )
    if fusion_mode == "logo_canvas_brand_mark":
        return (
            f"Use the uploaded logo image as the brand mark at {target}. Preserve its shape and readable text. "
            "Do not invent a different logo and do not move it onto the product surface unless the user asks for that."
        )
    if fusion_mode == "typographic_brand_text":
        return "Use the requested brand name as clean typography only; do not invent decorative logo marks beyond the user's text request."
    return (
        "Reserve or apply the uploaded logo/brand mark in the correct template brand slot without inventing new unreadable logo text. "
        "If the user names a target surface, that target overrides any generic poster badge placement."
    )


def _fusion_prompt_suffix(fusion_policy: dict[str, Any]) -> str:
    placement = fusion_policy.get("placement_intent") if isinstance(fusion_policy.get("placement_intent"), dict) else {}
    instruction = str(placement.get("instruction") or "").strip()
    expectations = fusion_policy.get("review_expectations") or []
    suffix_parts: list[str] = []
    if instruction:
        suffix_parts.append(f" Placement intent: {instruction}")
    if expectations:
        suffix_parts.append(" Review expectation: " + ", ".join(str(item) for item in expectations[:4]) + ".")
    return "".join(suffix_parts)


def _review_expectations(*, role: str, fusion_mode: str, placement: dict[str, Any], template_locked: bool) -> list[str]:
    expectations: list[str] = []
    if template_locked:
        expectations.append("selected_template_frame_preserved")
    if fusion_mode == "logo_product_surface":
        expectations.extend(
            [
                "uploaded_logo_visible_on_scene_surface",
                "no_canvas_corner_logo_unless_requested",
                "no_invented_logo_text",
            ]
        )
    elif fusion_mode in {"logo_canvas_brand_mark", "logo_template_slot", "logo_brand_mark"}:
        expectations.extend(["uploaded_logo_used_as_brand_mark", "no_invented_logo_text"])
    elif fusion_mode == "composite_content_source":
        expectations.extend(
            [
                "uploaded_content_evidence_used",
                "uploaded_source_layout_not_copied",
                "uploaded_information_complete",
                "business_offer_policy_preserved",
            ]
        )
    elif fusion_mode == TEMPLATE_SLOT_REPLACEMENT_FUSION_MODE:
        expectations.extend(
            [
                "uploaded_replacement_subject_visible",
                "template_subject_slot_replaced",
                "complete_uploaded_subject_preserved",
                "no_uploaded_source_layout_copy",
            ]
        )
    elif fusion_mode == "continuation_frame":
        expectations.extend(
            [
                "selected_history_frame_preserved",
                "current_user_edit_applied",
                "conflicting_reference_details_replaced",
            ]
        )
    elif role == "subject_reference":
        expectations.append("uploaded_subject_identity_preserved")
    elif role == "face_reference":
        expectations.append("uploaded_face_identity_preserved")
    elif role == "background_reference":
        expectations.append("uploaded_background_or_mood_respected")
    if placement.get("target_label"):
        expectations.append(f"target:{placement['target_label']}")
    return _dedupe(expectations)


def _primary_asset_input(inputs: list[CreativeRunAssetInput]) -> CreativeRunAssetInput | None:
    if not inputs:
        return None
    return sorted(inputs, key=lambda item: ROLE_PRIORITY.get(item.role or "", 0), reverse=True)[0]


def _strongest_requested_strength(inputs: list[CreativeRunAssetInput]) -> ConstraintStrength | None:
    values = [item.constraint_strength for item in inputs if item.constraint_strength]
    if not values:
        return None
    return sorted(values, key=lambda value: STRENGTH_PRIORITY.get(value, 0), reverse=True)[0]


def _primary_role(left: str, right: str) -> str:
    return left if ROLE_PRIORITY.get(left, 0) >= ROLE_PRIORITY.get(right, 0) else right


def _stronger_strength(left: ConstraintStrength, right: ConstraintStrength) -> ConstraintStrength:
    return left if STRENGTH_PRIORITY.get(left, 0) >= STRENGTH_PRIORITY.get(right, 0) else right


def _merge_prompt_instructions(left: str, right: str) -> str:
    if not left:
        return right
    if not right or right in left:
        return left
    return f"{left} Also use the same uploaded reference image for this additional binding: {right}"


def _dedupe(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[Any] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _warnings(inputs: list[CreativeRunAssetInput], assets: list[UploadedAsset]) -> list[dict[str, Any]]:
    found = {item.asset_id for item in assets}
    warnings: list[dict[str, Any]] = []
    for item in inputs:
        if item.asset_id not in found:
            warnings.append({"code": "asset_not_found", "asset_id": item.asset_id})
    for asset in assets:
        if asset.status != "ready":
            warnings.append({"code": "asset_not_ready", "asset_id": asset.asset_id, "status": asset.status})
    return warnings
