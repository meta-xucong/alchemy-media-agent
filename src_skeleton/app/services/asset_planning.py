from __future__ import annotations

import re
from typing import Any

from app.providers.base import ProviderCapabilities, ProviderCapabilityMismatchError
from app.repositories import repository
from app.schemas import Asset, AssetIntent, ImagePromptPlan
from app.storage import media_store


ROLE_LABELS = {
    "style_reference": "风格参考",
    "subject_reference": "主体参考",
    "logo_overlay": "Logo/标识",
    "portrait_identity": "人物脸/身份",
    "background_reference": "背景参考",
    "composition_reference": "构图参考",
    "local_edit": "局部修改",
    "negative_reference": "反向参考",
}

REFERENCE_ROLES = {"style_reference", "subject_reference", "portrait_identity", "background_reference", "composition_reference"}
STRICT_FILE_ROLES = {"subject_reference", "portrait_identity", "logo_overlay", "local_edit"}


class AssetPlanError(Exception):
    def __init__(self, code: str, message: str, *, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def build_advanced_asset_plan(asset_intents: list[AssetIntent], *, user_prompt: str = "") -> dict[str, Any]:
    if not asset_intents:
        raise AssetPlanError("asset_role_required", "高级版需要至少一个素材用途。")

    assets: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    requirements = {
        "needs_image_reference": False,
        "needs_image_edit": False,
        "needs_mask_edit": False,
        "needs_postprocess": False,
    }
    seen: set[tuple[str, str]] = set()

    for intent in sorted(asset_intents, key=lambda item: item.priority, reverse=True):
        key = (intent.asset_id, intent.role)
        if key in seen:
            continue
        seen.add(key)
        asset = repository.get_asset(intent.asset_id)
        _validate_intent(intent, asset)
        stored = media_store.find_asset_file(intent.asset_id) is not None
        placement_intent = _placement_intent(intent, user_prompt)
        provider_input_mode = _provider_input_mode(intent, stored, placement_intent)
        vision_profile = _vision_profile(asset)
        if provider_input_mode == "reference_image":
            requirements["needs_image_reference"] = True
        if intent.role == "local_edit":
            requirements["needs_image_edit"] = True
            requirements["needs_mask_edit"] = True
        if intent.role == "logo_overlay" and provider_input_mode == "postprocess_only":
            requirements["needs_postprocess"] = True

        if intent.role in REFERENCE_ROLES and provider_input_mode == "material_brief_only":
            warnings.append(
                {
                    "code": "reference_image_unavailable",
                    "asset_id": intent.asset_id,
                    "role": intent.role,
                    "message": "素材没有真实文件内容，已退化为素材摘要提示。",
                }
            )

        assets.append(
            {
                "asset_id": intent.asset_id,
                "role": intent.role,
                "role_label": ROLE_LABELS.get(intent.role, intent.role),
                "priority": intent.priority,
                "preservation": intent.preservation,
                "strength": intent.strength,
                "notes": intent.notes,
                "placement": intent.placement.model_dump() if intent.placement else None,
                "placement_intent": placement_intent,
                "mask_id": intent.mask_id,
                "asset_type": asset.material_brief.asset_type if asset and asset.material_brief else _asset_type(asset),
                "material_brief_used": True,
                "vision_profile_used": bool(vision_profile and vision_profile.get("status") == "ready"),
                "vision_profile_status": vision_profile.get("status") if vision_profile else None,
                "vision_profile": _compact_vision_profile(vision_profile),
                "has_stored_file": stored,
                "provider_input_mode": provider_input_mode,
                "reference_image_url": media_store.asset_url(intent.asset_id) if provider_input_mode == "reference_image" else None,
                "prompt_constraints": _prompt_constraints(intent, asset, placement_intent),
                "negative_constraints": _negative_constraints(intent),
                "postprocess_steps": _postprocess_steps(intent) if intent.role == "logo_overlay" and provider_input_mode == "postprocess_only" else [],
            }
        )

    provider_input_plan = _provider_input_plan(assets, requirements)

    return {
        "asset_mode": "advanced",
        "assets": assets,
        "provider_requirements": requirements,
        "provider_input_plan": provider_input_plan,
        "warnings": warnings,
    }


def apply_asset_plan_to_prompt_plan(
    prompt_plan: ImagePromptPlan,
    *,
    original_prompt: str,
    asset_plan: dict[str, Any],
) -> ImagePromptPlan:
    blocks = _prompt_blocks(asset_plan)
    provider_input_plan = asset_plan.get("provider_input_plan") or _provider_input_plan(asset_plan.get("assets", []), asset_plan.get("provider_requirements", {}))
    asset_vision_profiles = _asset_vision_profiles(asset_plan)
    base_prompt = _existing_generation_prompt(prompt_plan)
    final_prompt = "\n".join(
        part
        for part in [
            base_prompt,
            "",
            "上传素材要求：",
            blocks["style_block"],
            blocks["subject_block"],
            blocks["layout_block"],
            blocks["safety_block"],
        ]
        if part is not None and str(part).strip() != ""
    ).strip()

    negative = list(dict.fromkeys([*prompt_plan.negative_constraints, *blocks["negative_constraints"]]))
    variables = {
        **prompt_plan.variables,
        "original_prompt": original_prompt,
        "generation_prompt": final_prompt,
        "asset_mode": "advanced",
        "asset_plan": asset_plan,
        "asset_vision_profiles": asset_vision_profiles,
        "provider_input_plan": provider_input_plan,
        "advanced_prompt_plan": {
            "original_prompt": original_prompt,
            **blocks,
            "asset_vision_profiles": asset_vision_profiles,
            "provider_input_plan": provider_input_plan,
            "negative_prompt": ", ".join(negative),
            "final_prompt": final_prompt,
        },
    }
    return prompt_plan.model_copy(
        update={
            "brand_constraints": list(dict.fromkeys([*prompt_plan.brand_constraints, *blocks["brand_constraints"]])),
            "negative_constraints": negative,
            "variables": variables,
        }
    )


def asset_context_for_prompt_planner(asset_plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not asset_plan:
        return None
    assets = []
    for index, item in enumerate(asset_plan.get("assets", []), start=1):
        assets.append(
            {
                "reference_label": f"uploaded_reference_{index}",
                "role": item.get("role"),
                "role_label": item.get("role_label"),
                "preservation": item.get("preservation"),
                "strength": item.get("strength"),
                "provider_input_mode": item.get("provider_input_mode"),
                "vision_profile": item.get("vision_profile"),
                "prompt_constraints": item.get("prompt_constraints", []),
                "notes": item.get("notes"),
            }
        )
    return {
        "asset_mode": "advanced",
        "provider_input_plan": _public_provider_input_plan(asset_plan.get("provider_input_plan")),
        "assets": assets,
        "warnings": asset_plan.get("warnings", []),
        "instruction": "用这些结构化素材信息辅助规划；如果有真实图片输入，请把它称为上传参考图，不要在最终提示词里输出内部素材编号、路径或 provider 技术细节。",
    }


def validate_asset_plan_with_provider(asset_plan: dict[str, Any] | None, capabilities: ProviderCapabilities) -> None:
    if not asset_plan or asset_plan.get("asset_mode") != "advanced":
        return
    supported_roles = set(capabilities.advanced_asset_roles or capabilities.limits.get("advanced_asset_roles", []))
    if not supported_roles:
        supported_roles = {"style_reference", "background_reference", "composition_reference", "logo_overlay"}
    requested_roles = {asset.get("role") for asset in asset_plan.get("assets", [])}
    unsupported = sorted(role for role in requested_roles if role and role not in supported_roles)
    if unsupported:
        raise ProviderCapabilityMismatchError(
            "The selected image provider does not support one or more advanced asset roles.",
            provider=capabilities.provider,
            detail={
                "unsupported_roles": unsupported,
                "supported_roles": sorted(supported_roles),
                "message": "当前生图模型不支持这些高级素材用途，请切换模型或改用基础版。",
            },
        )

    required = asset_plan.get("provider_requirements", {})
    operations = set(capabilities.operations or [])
    if required.get("needs_image_reference") and "image_reference" not in operations:
        raise ProviderCapabilityMismatchError(
            "The selected image provider does not support image references.",
            provider=capabilities.provider,
            detail={"missing_capability": "image_reference"},
        )
    if required.get("needs_image_edit") and "image_edit" not in operations:
        raise ProviderCapabilityMismatchError(
            "The selected image provider does not support image editing.",
            provider=capabilities.provider,
            detail={"missing_capability": "image_edit"},
        )
    if required.get("needs_mask_edit") and "mask_edit" not in operations:
        raise ProviderCapabilityMismatchError(
            "The selected image provider does not support mask editing.",
            provider=capabilities.provider,
            detail={"missing_capability": "mask_edit"},
        )


def reference_image_paths(asset_plan: dict[str, Any] | None, *, max_images: int = 5) -> list:
    if not asset_plan:
        return []
    paths = []
    candidates = sorted(asset_plan.get("assets", []), key=lambda item: item.get("priority", 0), reverse=True)
    for item in candidates:
        if item.get("provider_input_mode") != "reference_image":
            continue
        path = _reference_path_for_asset_item(item)
        if path:
            paths.append(path)
        if len(paths) >= max_images:
            break
    return paths


def _reference_path_for_asset_item(item: dict[str, Any]):
    storage_path = item.get("storage_path")
    if storage_path:
        try:
            from pathlib import Path

            path = Path(str(storage_path))
            if path.exists() and path.is_file():
                return path
        except OSError:
            return None
    return media_store.find_asset_file(str(item.get("asset_id")))


def logo_overlay_specs(asset_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not asset_plan:
        return []
    specs = []
    for item in asset_plan.get("assets", []):
        if item.get("role") != "logo_overlay":
            continue
        if item.get("provider_input_mode") != "postprocess_only":
            continue
        path = media_store.find_asset_file(str(item.get("asset_id")))
        if not path:
            continue
        specs.append(
            {
                "asset_id": item.get("asset_id"),
                "path": path,
                "placement": item.get("placement") or {},
                "priority": item.get("priority", 50),
            }
        )
    return sorted(specs, key=lambda item: item.get("priority", 0), reverse=True)


def _validate_intent(intent: AssetIntent, asset: Asset | None) -> None:
    if not asset:
        raise AssetPlanError("asset_not_found", "素材不存在。", detail={"asset_id": intent.asset_id})
    if asset.status != "ready":
        raise AssetPlanError("asset_not_ready", "素材还没有处理完成。", detail={"asset_id": intent.asset_id, "status": asset.status})
    if intent.role == "local_edit" and not intent.mask_id:
        raise AssetPlanError("mask_required", "局部修改需要先选择编辑区域。", detail={"asset_id": intent.asset_id})
    consent = _merged_consent(asset, intent)
    if intent.role == "portrait_identity" and not consent.get("portrait_identity_allowed"):
        raise AssetPlanError("asset_consent_required", "人物脸/身份参考需要确认肖像授权。", detail={"asset_id": intent.asset_id, "role": intent.role})
    if intent.role == "logo_overlay" and not consent.get("logo_or_trademark_allowed"):
        raise AssetPlanError("asset_consent_required", "Logo/标识素材需要确认品牌或商标使用权。", detail={"asset_id": intent.asset_id, "role": intent.role})
    if intent.role in STRICT_FILE_ROLES and media_store.find_asset_file(intent.asset_id) is None:
        raise AssetPlanError("asset_content_required", "该高级素材用途需要真实图片文件。", detail={"asset_id": intent.asset_id, "role": intent.role})


def _merged_consent(asset: Asset, intent: AssetIntent) -> dict[str, Any]:
    asset_consent = asset.consent.model_dump() if hasattr(asset.consent, "model_dump") else dict(asset.consent or {})
    intent_consent = intent.consent.model_dump()
    return {**asset_consent, **{key: value for key, value in intent_consent.items() if value not in {None, False, ""}}}


def _placement_intent(intent: AssetIntent, user_prompt: str = "") -> dict[str, Any]:
    text = _placement_text(intent, user_prompt)
    canvas_target = _canvas_overlay_target(text)
    scene_target = _scene_surface_target(text)
    if scene_target:
        return {
            "mode": "scene_surface",
            "target_label": scene_target,
            "source": "user_prompt_or_notes",
            "instruction": f"Place the uploaded asset on {scene_target} as part of the scene, not as a canvas overlay.",
        }
    if intent.role == "logo_overlay":
        placement = intent.placement.model_dump() if intent.placement else {}
        return {
            "mode": "canvas_overlay",
            "target_label": canvas_target or _canvas_anchor_label(placement.get("anchor") or "bottom_right"),
            "source": "placement_anchor",
            "instruction": "Apply the uploaded asset as a deterministic canvas overlay.",
        }
    if canvas_target:
        return {
            "mode": "canvas_overlay_hint",
            "target_label": canvas_target,
            "source": "user_prompt_or_notes",
            "instruction": f"Use the uploaded asset as a layout cue around {canvas_target}.",
        }
    return {"mode": "reference", "target_label": None, "source": "role_default", "instruction": ""}


def _placement_text(intent: AssetIntent, user_prompt: str) -> str:
    placement = intent.placement.model_dump() if intent.placement else {}
    parts = [
        user_prompt or "",
        intent.notes or "",
        str(placement.get("anchor") or ""),
    ]
    return " ".join(part for part in parts if part).lower()


def _scene_surface_target(text: str) -> str | None:
    checks = [
        (r"(胸口|左胸|右胸|衣服上|衣服表面|衣服胸前|polo|polo衫|t恤|t-shirt|shirt|hoodie|sweatshirt|chest|apparel|clothing|fabric)", "衣服胸口或服装表面"),
        (r"(商品上|产品上|产品表面|商品表面|包装上|包装正面|盒子上|盒身|盒面|package|packaging|box front|product surface)", "商品或包装表面"),
        (r"(瓶身|瓶子上|罐身|杯身|杯子上|bottle|jar|can|cup|mug)", "瓶身、杯身或容器表面"),
        (r"(鞋面|鞋侧|鞋舌|鞋上|sneaker|shoe|footwear)", "鞋面或鞋侧表面"),
        (r"(设备上|机身|外壳|手机背面|电脑外壳|device|phone back|case|laptop lid)", "设备外壳或机身表面"),
        (r"(墙面|门头|招牌|店招|店铺外立面|wall|signboard|storefront)", "墙面、招牌或门头表面"),
        (r"(贴在|印在|绣在|烫印|压印|刻在|附着|贴附|融合到|apply to|printed on|embroidered on|attached to)", "用户指定的物体表面"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def _canvas_overlay_target(text: str) -> str | None:
    checks = [
        (r"(右下|右下角|bottom right)", "画布右下角"),
        (r"(左下|左下角|bottom left)", "画布左下角"),
        (r"(右上|右上角|top right)", "画布右上角"),
        (r"(左上|左上角|top left)", "画布左上角"),
        (r"(底部居中|下方居中|bottom center)", "画布底部居中"),
        (r"(顶部居中|top center)", "画布顶部居中"),
        (r"(角标|水印|边角|海报下方|海报底部|poster corner|watermark|corner badge)", "海报角标或水印区域"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return None


def _canvas_anchor_label(anchor: str) -> str:
    labels = {
        "top_left": "画布左上角",
        "top_center": "画布顶部居中",
        "top_right": "画布右上角",
        "center_left": "画布左侧居中",
        "center": "画布居中",
        "center_right": "画布右侧居中",
        "bottom_left": "画布左下角",
        "bottom_center": "画布底部居中",
        "bottom_right": "画布右下角",
        "custom": "自定义画布位置",
    }
    return labels.get(anchor, "画布右下角")


def _placement_prompt_suffix(placement_intent: dict[str, Any] | None) -> str:
    if not placement_intent or placement_intent.get("mode") != "scene_surface":
        return ""
    target = placement_intent.get("target_label") or "用户指定的物体表面"
    return f" 位置约束：把上传素材融入{target}，作为画面内真实元素，不要放成海报角标、水印或独立贴片。"


def _provider_input_mode(intent: AssetIntent, stored: bool, placement_intent: dict[str, Any] | None = None) -> str:
    if intent.role == "logo_overlay":
        if stored and (placement_intent or {}).get("mode") == "scene_surface":
            return "reference_image"
        return "postprocess_only"
    if intent.role == "local_edit":
        return "mask_edit_source"
    if intent.role in REFERENCE_ROLES:
        return "reference_image" if stored else "material_brief_only"
    return "material_brief_only"


def _prompt_constraints(intent: AssetIntent, asset: Asset | None, placement_intent: dict[str, Any] | None = None) -> list[str]:
    label = ROLE_LABELS.get(intent.role, intent.role)
    brief = _material_brief_hint(asset)
    vision_hint = _vision_prompt_hint(asset)
    strength = _reference_weight_label(intent)
    placement_hint = _placement_prompt_suffix(placement_intent)
    prototype_reference = _prototype_preservation_hint(intent)
    if intent.role == "style_reference":
        return [f"{label}：{strength}参考上传图片的配色、光线、材质、背景气质和整体审美；同时保留小面积但有识别度的强调色、金属感或深色点缀；按用户新主题重构内容，不复刻原图主体。{placement_hint}{brief}{vision_hint}"]
    if intent.role == "subject_reference":
        return [f"{label}：以上传图片中的主体为视觉依据，保持关键可见特征、轮廓、产品身份和比例关系，场景与风格可按用户提示重构。{placement_hint}{brief}{vision_hint}"]
    if intent.role == "logo_overlay":
        if (placement_intent or {}).get("mode") == "scene_surface":
            target = placement_intent.get("target_label") or "用户指定的物体表面"
            return [
                (
                    f"Logo/标识：必须把上传图片作为真实 Logo 参考，将品牌标识自然贴附、印刷、刺绣或融合到{target}；"
                    "保持 Logo 形状、比例和文字，不要虚构新 Logo，不要把 Logo 放到海报下方、角落、边框、水印区或独立装饰贴片。"
                    f"{vision_hint}"
                )
            ]
        return [f"Logo/标识：预留干净安全区域供后处理叠加；不要虚构 Logo 文字，不要让模型重绘品牌标识。{vision_hint}"]
    if intent.role == "portrait_identity":
        return [f"人物脸/身份：以授权上传人像作为身份参考，保持主要面部身份特征，场景和风格按用户提示重构，同时控制身份漂移。{placement_hint}{brief}{vision_hint}"]
    if intent.role == "background_reference":
        return [f"{label}：借鉴上传背景的环境、纵深、氛围和空间线索，让新画面保持相近的空间气质。{placement_hint}{brief}{vision_hint}"]
    if intent.role == "composition_reference":
        if prototype_reference:
            return [f"{label}：参考上传图片的机位、取景、主体位置和留白结构；仅替换用户明确要求改变的内容，其余可见主体、文字、标识、包装、界面或场景信息默认保留。{placement_hint}{brief}{vision_hint}"]
        return [f"{label}：参考上传图片的机位、取景、主体位置和留白结构，主体内容按用户需求替换。{placement_hint}{brief}{vision_hint}"]
    if intent.role == "local_edit":
        return ["局部修改：只改变选中的蒙版区域，保持其他区域不被改动。"]
    if intent.role == "negative_reference":
        return ["反向参考：避免重复上传素材中不想要的风格、主体或构图。"]
    return []


def _negative_constraints(intent: AssetIntent) -> list[str]:
    if intent.role == "logo_overlay":
        return ["虚假 Logo", "变形 Logo", "不可读品牌文字"]
    if intent.role == "portrait_identity":
        return ["脸部畸形", "身份漂移", "不必要的年龄变化"]
    if intent.role == "local_edit":
        return ["蒙版外不必要改动"]
    if intent.role == "negative_reference":
        return [intent.notes or "避免参考素材中不想要的特征"]
    return []


def _postprocess_steps(intent: AssetIntent) -> list[dict[str, Any]]:
    placement = intent.placement.model_dump() if intent.placement else {}
    return [{"type": "logo_overlay", "placement": placement or {"anchor": "bottom_right"}}]


def _prompt_blocks(asset_plan: dict[str, Any]) -> dict[str, Any]:
    style_parts: list[str] = []
    subject_parts: list[str] = []
    layout_parts: list[str] = []
    safety_parts: list[str] = []
    negative: list[str] = []
    brand: list[str] = []
    for item in asset_plan.get("assets", []):
        constraints = item.get("prompt_constraints", [])
        if item.get("role") in {"style_reference", "background_reference"}:
            style_parts.extend(constraints)
        elif item.get("role") in {"subject_reference", "portrait_identity"}:
            subject_parts.extend(constraints)
        elif item.get("role") in {"composition_reference", "logo_overlay", "local_edit"}:
            layout_parts.extend(constraints)
        elif item.get("role") == "negative_reference":
            safety_parts.extend(constraints)
        if item.get("role") == "logo_overlay":
            if item.get("provider_input_mode") == "reference_image":
                target = (item.get("placement_intent") or {}).get("target_label") or "用户指定的物体表面"
                brand.append(f"Logo/标识作为上传参考图进入生图模型，需融合到{target}，不得被放成海报角标或底部贴片。")
            else:
                brand.append("Logo/标识使用确定性后处理叠加，优先保持原素材形态。")
        negative.extend(item.get("negative_constraints", []))
        if item.get("notes"):
            style_parts.append(f"用户素材备注：{item['notes']}")
    warnings = asset_plan.get("warnings", [])
    if warnings:
        safety_parts.append("部分素材没有可读原图，只能退化为素材摘要约束。")
    safety_parts.append("尊重用户上传素材授权，不添加虚假水印或未授权第三方标识。")
    return {
        "style_block": "\n".join(style_parts),
        "subject_block": "\n".join(subject_parts),
        "layout_block": "\n".join(layout_parts),
        "safety_block": "\n".join(safety_parts),
        "vision_profile_summary": _vision_profile_summary(asset_plan),
        "negative_constraints": list(dict.fromkeys(negative)),
        "brand_constraints": list(dict.fromkeys(brand)),
    }


def _vision_profile(asset: Asset | None) -> dict[str, Any] | None:
    profile = getattr(asset, "vision_profile", None) if asset else None
    if not profile:
        return None
    if hasattr(profile, "model_dump"):
        return profile.model_dump()
    return dict(profile)


def _compact_vision_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "asset_id": profile.get("asset_id"),
        "status": profile.get("status"),
        "summary": profile.get("summary"),
        "image": profile.get("image") or {},
        "style": profile.get("style") or {},
        "composition": profile.get("composition") or {},
        "subjects": profile.get("subjects") or [],
        "logo_candidates": profile.get("logo_candidates") or [],
        "faces": profile.get("faces") or [],
        "risks": profile.get("risks") or [],
        "recommended_roles": profile.get("recommended_roles") or [],
    }


def _vision_prompt_hint(asset: Asset | None) -> str:
    profile = _compact_vision_profile(_vision_profile(asset))
    if not profile or profile.get("status") != "ready":
        return ""
    style = profile.get("style") or {}
    composition = profile.get("composition") or {}
    parts = []
    keywords = [str(item).strip() for item in (style.get("style_keywords") or []) if str(item).strip()]
    if keywords:
        parts.append(f"保留{'、'.join(keywords[:4])}的整体气质")
    if style.get("accent_colors") or style.get("dark_accent_colors") or style.get("warm_metal_colors"):
        parts.append("不要只继承背景色，也要迁移有识别度的点缀色和材质氛围")
    if composition.get("orientation"):
        parts.append(f"参考{_zh_vision_label(composition['orientation'])}构图的留白节奏")
    compact = "；".join(str(part) for part in parts if part)
    return f" 视觉重点：{compact}。" if compact else ""


def _material_brief_hint(asset: Asset | None) -> str:
    if not asset or not asset.material_brief:
        return " 素材画像：用户上传图片。"
    profile = _compact_vision_profile(_vision_profile(asset))
    if profile and profile.get("status") == "ready":
        image = profile.get("image") or {}
        style = profile.get("style") or {}
        composition = profile.get("composition") or {}
        parts: list[str] = []
        width = image.get("width")
        height = image.get("height")
        if width and height:
            parts.append(f"{width}x{height}")
        orientation = composition.get("orientation")
        if orientation:
            parts.append(f"{_zh_vision_label(orientation)}构图")
        dominant = style.get("dominant_color")
        if dominant:
            parts.append(f"主色 {dominant}")
        palette = _palette_hex_values(style.get("palette") or [])
        if palette:
            parts.append(f"辅助色 {'、'.join(palette[:4])}")
        accent_colors = _palette_hex_values(style.get("accent_colors") or [])
        if accent_colors:
            parts.append(f"强调色 {'、'.join(accent_colors[:4])}")
        dark_accents = _palette_hex_values(style.get("dark_accent_colors") or [])
        if dark_accents:
            parts.append(f"深色强调 {'、'.join(dark_accents[:3])}")
        warm_metals = _palette_hex_values(style.get("warm_metal_colors") or [])
        if warm_metals:
            parts.append(f"暖金/琥珀点缀 {'、'.join(warm_metals[:3])}")
        keywords = [str(item).strip() for item in (style.get("style_keywords") or []) if str(item).strip()]
        if keywords:
            parts.append(f"风格关键词 {'、'.join(keywords[:4])}")
        brightness = style.get("brightness_label")
        if brightness:
            parts.append(f"{_zh_vision_label(brightness)}光感")
        contrast = style.get("contrast_label")
        if contrast:
            parts.append(f"{_zh_vision_label(contrast)}对比度")
        return f" 素材画像：{'，'.join(parts)}。" if parts else " 素材画像：用户上传图片。"
    summary = _clean_material_summary(asset.material_brief.summary)
    return f" 素材画像：{summary}。" if summary else " 素材画像：用户上传图片。"


def _reference_weight_label(intent: AssetIntent) -> str:
    if intent.preservation in {"strict", "exact"} or intent.strength >= 0.75:
        return "强参考，优先保留参考图的主色、光感、质感、构图气质和关键视觉线索。"
    if intent.preservation == "medium" or intent.strength >= 0.4:
        return "中等参考，保留主要色调、光线气质和审美方向，同时允许主体按用户需求重构。"
    return "轻度参考，只借鉴整体审美，不复刻具体内容。"


def _prototype_preservation_hint(intent: AssetIntent) -> bool:
    text = f"{intent.notes or ''} {intent.role or ''}"
    return bool(
        re.search(
            r"(原型|原图|模板|蓝本|继续|复用|一致性|保留|不要移除|不要删除|prototype|template|continue|preserve|keep)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _palette_hex_values(values: list[Any]) -> list[str]:
    colors: list[str] = []
    for item in values:
        if isinstance(item, dict):
            value = item.get("hex")
        else:
            value = item
        text = str(value or "").strip()
        if text:
            colors.append(text)
    return colors


def _public_provider_input_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "operation": value.get("operation"),
        "reference_image_count": value.get("reference_image_count"),
        "requires_image_reference": value.get("requires_image_reference"),
        "requires_postprocess": value.get("requires_postprocess"),
        "placement_targets": value.get("placement_targets") or [],
    }


def _clean_material_summary(value: Any) -> str:
    text = str(value or "").strip().rstrip("。.;；")
    noise = [
        "可用于提示词规划，但真实保真仍依赖 provider 图片输入",
        "真实保真仍依赖 provider 图片输入",
        "provider 图片输入",
    ]
    for item in noise:
        text = text.replace(item, "")
    return text.strip(" ；;。")


def _zh_vision_label(value: Any) -> str:
    labels = {
        "square": "方图",
        "portrait": "竖图",
        "landscape": "横图",
        "bright": "明亮",
        "dark": "偏暗",
        "balanced": "均衡",
        "high": "高",
        "medium": "中等",
        "low": "低",
    }
    return labels.get(str(value), str(value))


def _asset_vision_profiles(asset_plan: dict[str, Any]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for item in asset_plan.get("assets", []):
        profile = item.get("vision_profile")
        if profile:
            profiles.append(profile)
    return profiles


def _vision_profile_summary(asset_plan: dict[str, Any]) -> str:
    summaries = []
    for item in asset_plan.get("assets", []):
        profile = item.get("vision_profile") or {}
        summary = profile.get("summary")
        if summary:
            summaries.append(f"{item.get('role_label') or item.get('role')}: {summary}")
    return "\n".join(summaries)


def _provider_input_plan(assets: list[dict[str, Any]], requirements: dict[str, Any]) -> dict[str, Any]:
    reference_ids = list(dict.fromkeys(str(item.get("asset_id")) for item in assets if item.get("provider_input_mode") == "reference_image"))
    edit_source_ids = list(dict.fromkeys(str(item.get("asset_id")) for item in assets if item.get("provider_input_mode") == "mask_edit_source"))
    postprocess_ids = list(dict.fromkeys(str(item.get("asset_id")) for item in assets if item.get("provider_input_mode") == "postprocess_only"))
    placement_targets = [
        {
            "asset_id": item.get("asset_id"),
            "role": item.get("role"),
            "mode": (item.get("placement_intent") or {}).get("mode"),
            "target_label": (item.get("placement_intent") or {}).get("target_label"),
        }
        for item in assets
        if isinstance(item.get("placement_intent"), dict)
        and (item.get("placement_intent") or {}).get("mode") in {"scene_surface", "canvas_overlay"}
    ]
    operation = "generate"
    if edit_source_ids:
        operation = "image_edit_with_mask"
    elif reference_ids:
        operation = "image_edit_with_reference_images"
    return {
        "operation": operation,
        "reference_image_asset_ids": reference_ids,
        "reference_image_count": len(reference_ids),
        "edit_source_asset_ids": edit_source_ids,
        "postprocess_asset_ids": postprocess_ids,
        "requires_image_reference": bool(requirements.get("needs_image_reference")),
        "requires_postprocess": bool(requirements.get("needs_postprocess")),
        "placement_targets": placement_targets,
        "provider_contract": "OpenAI gpt-image-2 参考图走 images.edit 图片输入；Gemini 走 inline image parts。需要视觉保真的用途不能只依赖 prompt。",
    }


def _existing_generation_prompt(prompt_plan: ImagePromptPlan) -> str:
    existing = prompt_plan.variables.get("generation_prompt") if prompt_plan.variables else None
    if existing:
        return str(existing)
    return "\n".join(
        part
        for part in [
            f"创作目标：{prompt_plan.main_subject}",
            f"场景：{prompt_plan.scene or ''}",
            f"风格：{prompt_plan.style or ''}",
            f"构图：{prompt_plan.composition or ''}",
            f"品牌约束：{'；'.join(prompt_plan.brand_constraints)}",
            f"文字要求：{prompt_plan.text}",
        ]
        if part.strip()
    )


def _asset_type(asset: Asset | None) -> str:
    if not asset:
        return "unknown"
    if asset.mime_type.startswith("image/"):
        return "image"
    return "file"


def _strength_label(value: float) -> str:
    if value >= 0.75:
        return "强"
    if value >= 0.4:
        return "中等"
    return "轻度"
