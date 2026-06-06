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


def build_asset_context(request: CreateCreativeRunRequest) -> dict[str, Any]:
    asset_inputs = _normalize_asset_inputs(request.assets)
    inputs_by_id: dict[str, list[CreativeRunAssetInput]] = {}
    for item in asset_inputs:
        inputs_by_id.setdefault(item.asset_id, []).append(item)
    uploaded_assets = [_resolve_uploaded_asset(asset_id) for asset_id in inputs_by_id]
    uploaded_assets = [item for item in uploaded_assets if item is not None]
    brief_by_id = {item.asset_id: _brief_for(item) for item in uploaded_assets}
    template_lock = _template_lock_contract(request.template_case_id)
    binding_plan = _binding_plan(asset_inputs, brief_by_id, template_lock, user_prompt=request.user_prompt)
    return {
        "uploaded_assets": [
            _asset_for_context(asset, brief_by_id.get(asset.asset_id), inputs_by_id.get(asset.asset_id, []))
            for asset in uploaded_assets
        ],
        "template_lock_contract": template_lock.model_dump(mode="json") if template_lock else None,
        "asset_binding_plan": binding_plan.model_dump(mode="json"),
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
    provider_plan = asset_context.get("provider_input_plan") if isinstance(asset_context.get("provider_input_plan"), dict) else {}
    if provider_plan.get("reference_image_count"):
        parts.append(
            f"Provider input images required: {provider_plan.get('reference_image_count')} uploaded reference image(s). "
            "The prompt must refer to them as uploaded reference images, not by internal IDs."
        )
    return "\n".join(parts)


def provider_input_images(binding_plan: AssetBindingPlan, brief_by_id: dict[str, AssetBrief]) -> list[ProviderInputImage]:
    images_by_asset_id: dict[str, ProviderInputImage] = {}
    for binding in binding_plan.bindings:
        brief = brief_by_id.get(binding.asset_id)
        if not brief or not binding.provider_input_required:
            continue
        asset = repository.get_uploaded_asset(binding.asset_id)
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


def _resolve_uploaded_asset(asset_id: str) -> UploadedAsset | None:
    return repository.get_uploaded_asset(asset_id)


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
) -> AssetBindingPlan:
    bindings: list[AssetBinding] = []
    conflicts: list[dict[str, Any]] = []
    for item in asset_inputs:
        brief = brief_by_id.get(item.asset_id)
        if not brief:
            conflicts.append({"type": "asset_missing", "asset_id": item.asset_id, "resolution": "ignore_missing_asset"})
            continue
        role = item.role or brief.role
        strength: ConstraintStrength = item.constraint_strength or brief.constraint_strength
        brief = _brief_for_binding(brief, item)
        fusion_policy = _fusion_policy(
            role=role,
            strength=strength,
            brief=brief,
            user_prompt=user_prompt,
            notes=item.notes,
            template_locked=template_lock is not None,
        )
        provider_required = bool(
            brief.provider_input_required
            or role in HARD_REFERENCE_ROLES
            or fusion_policy.get("provider_input_required")
        )
        if strength == "required" and role in {"style_reference", "composition_reference", "color_reference"}:
            provider_required = True
        blocked = LOCKED_TEMPLATE_ELEMENTS if template_lock else []
        conflict_resolution = None
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
        bindings.append(
            AssetBinding(
                asset_id=item.asset_id,
                role=role,
                constraint_strength=strength,
                binding_slot=ROLE_TO_SLOT.get(role, "minor_props"),
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
    provider_plan = _provider_input_plan(bindings)
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
    role_rule = {
        "subject_reference": "Replace the template's original subject with the uploaded subject while preserving the selected template's visual frame.",
        "logo_reference": _logo_prompt_rule(fusion_mode=fusion_mode, target_label=target_label),
        "face_reference": "Preserve uploaded face identity cues while adapting pose, lighting, and scene to the selected template.",
        "background_reference": "Use background content only if compatible with the template lock or explicitly requested by the user.",
        "style_reference": "Use only compatible color, light, material, and mood cues; do not override the selected template style.",
        "composition_reference": "Use only secondary camera-angle or spacing hints; do not override the selected template composition.",
        "color_reference": "Use compatible palette/accent cues without replacing the selected template color rhythm.",
        "negative_reference": "Avoid the visual traits represented by this uploaded reference.",
    }.get(role, "Use the uploaded asset as compatible visual evidence.")
    fusion_text = _fusion_prompt_suffix(fusion_policy)
    extra = f" User notes: {notes}" if notes else ""
    return f"{prefix} {role_rule}{fusion_text} Reference strength: {strength}. Asset brief: {base} Identity requirements: {identity}. Style signals: {style}.{extra}"


def _provider_input_plan(bindings: list[AssetBinding]) -> dict[str, Any]:
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
        "provider_contract": (
            "Hard visual constraints such as product, logo, face, or required background must be sent to capable providers "
            "as input images. Do not silently reduce them to text-only prompts."
        ),
    }


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


def _fusion_policy(
    *,
    role: str,
    strength: ConstraintStrength,
    brief: AssetBrief,
    user_prompt: str,
    notes: str | None,
    template_locked: bool,
) -> dict[str, Any]:
    source_text, source = _intent_source_text(user_prompt=user_prompt, notes=notes, brief=brief)
    placement = _placement_intent(role=role, text=source_text, source=source, template_locked=template_locked)
    fusion_mode = _fusion_mode(role=role, placement=placement, text=source_text, template_locked=template_locked)
    provider_input_required = role in HARD_REFERENCE_ROLES or strength == "required"
    if fusion_mode in {
        "logo_product_surface",
        "logo_canvas_brand_mark",
        "logo_template_slot",
        "subject_identity",
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
        "placement_intent": placement,
        "target_surface": placement.get("target_surface"),
        "provider_input_required": provider_input_required,
        "review_expectations": review_expectations,
    }


def _intent_source_text(*, user_prompt: str, notes: str | None, brief: AssetBrief) -> tuple[str, str]:
    note_text = " ".join(str(notes or "").split())
    if note_text:
        return f"{note_text} {user_prompt or ''} {brief.visual_summary or ''}".strip().lower(), "notes"
    prompt_text = " ".join(str(user_prompt or "").split())
    if prompt_text:
        return f"{prompt_text} {brief.visual_summary or ''}".strip().lower(), "user_prompt"
    return (brief.visual_summary or "").lower(), "asset_brief"


def _placement_intent(*, role: str, text: str, source: str, template_locked: bool) -> dict[str, Any]:
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
    return {
        "mode": "reference",
        "target_surface": None,
        "target_label": None,
        "source": "role_default",
        "instruction": "",
    }


def _fusion_mode(*, role: str, placement: dict[str, Any], text: str, template_locked: bool) -> str:
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
        return "subject_identity"
    if role == "face_reference":
        return "face_identity"
    if role == "background_reference":
        return "background_identity" if _background_replace_requested(text) else "background_mood"
    if role == "style_reference":
        return "style_signal"
    if role == "composition_reference":
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
