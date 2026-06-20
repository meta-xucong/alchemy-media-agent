from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.alchemy_lab_intent_director import reference_directive_for_asset
from app.services.alchemy_lab_uploads import (
    MAX_LAB_REFERENCE_ASSET_COUNT,
    get_lab_upload,
    lab_uploaded_asset_path,
    public_lab_asset_summary,
)
from app.services.alchemy_lab_uploads_models import LabReferenceAssetInput, LabUploadedAsset


ROLE_LABELS = {
    "subject_reference": "主体/商品参考",
    "product_reference": "产品参考",
    "logo_reference": "Logo/标识参考",
    "style_material_reference": "材质/色彩参考",
    "composition_reference": "构图参考",
    "negative_reference": "反向参考",
}
ROLE_PRIORITIES = {
    "product_reference": 95,
    "subject_reference": 90,
    "logo_reference": 85,
    "style_material_reference": 55,
    "composition_reference": 45,
    "negative_reference": 30,
}
REQUIRED_INPUT_ROLES = {"subject_reference", "product_reference", "logo_reference"}


class LabReferencePolicyError(ValueError):
    def __init__(self, code: str, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def build_lab_reference_plan(
    reference_assets: list[LabReferenceAssetInput],
    *,
    user_prompt: str,
    veyra_user_id: int | None = None,
    intent_plan: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not reference_assets:
        return None
    if len(reference_assets) > MAX_LAB_REFERENCE_ASSET_COUNT:
        raise LabReferencePolicyError(
            "lab_reference_count_exceeded",
            f"最多可添加 {MAX_LAB_REFERENCE_ASSET_COUNT} 张参考图片。",
            detail={"max": MAX_LAB_REFERENCE_ASSET_COUNT},
        )
    planned_assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in reference_assets:
        asset_id = item.asset_id.strip()
        if asset_id in seen:
            continue
        seen.add(asset_id)
        asset = get_lab_upload(asset_id)
        if not asset:
            raise LabReferencePolicyError("lab_reference_not_found", "参考图片不存在。", detail={"asset_id": asset_id})
        if asset.status != "ready":
            raise LabReferencePolicyError(
                "lab_reference_not_ready",
                "参考图片还没有处理完成。",
                detail={"asset_id": asset_id, "status": asset.status},
            )
        if asset.veyra_user_id not in {None, veyra_user_id}:
            raise LabReferencePolicyError("lab_reference_forbidden", "参考图片不属于当前账户。", detail={"asset_id": asset_id})
        path = lab_uploaded_asset_path(asset_id)
        if not path:
            raise LabReferencePolicyError("lab_reference_content_missing", "参考图片文件缺失。", detail={"asset_id": asset_id})
        directive = reference_directive_for_asset(intent_plan, asset_id) or {}
        asset_brief = asset.brief if isinstance(asset.brief, dict) else {}
        role = item.role or directive.get("recommended_role") or asset.role or asset_brief.get("role") or "subject_reference"
        strength = item.constraint_strength or directive.get("recommended_strength") or asset.constraint_strength or "strong"
        planned_assets.append(_planned_asset(asset, role=role, strength=strength, notes=item.notes, path=path, director_directive=directive))
    if not planned_assets:
        return None
    provider_input_plan = _provider_input_plan(planned_assets)
    summary = _reference_summary(planned_assets)
    warnings = _warnings(planned_assets)
    return {
        "asset_mode": "lab_reference",
        "source": "alchemy_lab_reference_policy",
        "summary": summary,
        "public_summary": _public_summary(planned_assets),
        "assets": planned_assets,
        "warnings": warnings,
        "provider_input_plan": provider_input_plan,
        "prompt_constraints": _prompt_constraints(planned_assets, user_prompt=user_prompt),
    }


def lab_reference_prompt_block(reference_plan: dict[str, Any] | None) -> str:
    if not reference_plan:
        return ""
    lines = [
        "参考图约束：" + str(reference_plan.get("summary") or "").strip(),
        "稀有风格仍然是主要视觉变量，参考图只固定主体、产品、Logo、材质、色彩或构图线索。",
    ]
    constraints = [str(item) for item in reference_plan.get("prompt_constraints") or [] if str(item).strip()]
    if constraints:
        lines.extend(constraints)
    warnings = [str(item) for item in reference_plan.get("warnings") or [] if str(item).strip()]
    if warnings:
        lines.append("参考图注意：" + "；".join(warnings))
    return "\n".join(lines)


def lab_reference_metadata(reference_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not reference_plan:
        return {
            "reference_summary": None,
            "reference_asset_roles": [],
            "reference_policy": None,
            "provider_input_plan": None,
            "reference_warnings": [],
        }
    roles = []
    for item in reference_plan.get("assets") or []:
        roles.append(
            {
                "role": item.get("role"),
                "role_label": item.get("role_label"),
                "constraint_strength": item.get("constraint_strength"),
                "director_directive": item.get("director_directive") or {},
            }
        )
    return {
        "reference_summary": reference_plan.get("public_summary") or reference_plan.get("summary"),
        "reference_asset_roles": roles,
        "reference_policy": {
            "asset_mode": "lab_reference",
            "source": reference_plan.get("source"),
            "reference_count": len(reference_plan.get("assets") or []),
        },
        "provider_input_plan": _public_provider_input_plan(reference_plan.get("provider_input_plan")),
        "reference_warnings": reference_plan.get("warnings") or [],
    }


def public_reference_history_metadata(reference_plan: dict[str, Any] | None) -> dict[str, Any]:
    metadata = lab_reference_metadata(reference_plan)
    return {
        "reference_summary": metadata["reference_summary"],
        "reference_asset_roles": metadata["reference_asset_roles"],
        "reference_policy": metadata["reference_policy"],
        "provider_input_plan": metadata["provider_input_plan"],
        "reference_warnings": metadata["reference_warnings"],
    }


def _planned_asset(
    asset: LabUploadedAsset,
    *,
    role: str,
    strength: str,
    notes: str | None,
    path: Path,
    director_directive: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_input_mode = "reference_image" if role != "negative_reference" else "brief_only"
    if strength == "soft" and role in {"style_material_reference", "composition_reference"}:
        provider_input_mode = "reference_image"
    brief = asset.brief or {}
    return {
        "asset_id": asset.asset_id,
        "role": role,
        "role_label": ROLE_LABELS.get(role, "参考图"),
        "constraint_strength": strength,
        "priority": ROLE_PRIORITIES.get(role, 50) + {"required": 8, "strong": 4, "soft": 0}.get(strength, 0),
        "provider_input_mode": provider_input_mode,
        "storage_path": str(path),
        "mime_type": asset.mime_type,
        "brief": public_lab_asset_summary(asset),
        "visual_summary": brief.get("visual_summary") if isinstance(brief, dict) else None,
        "notes": notes or asset.intended_use or "",
        "requires_image_reference": strength in {"required", "strong"} or role in REQUIRED_INPUT_ROLES,
        "director_directive": _public_directive(director_directive),
    }


def _provider_input_plan(assets: list[dict[str, Any]]) -> dict[str, Any]:
    reference_assets = [item for item in assets if item.get("provider_input_mode") == "reference_image"]
    return {
        "operation": "image_generation_with_reference_images" if reference_assets else "text_to_image_with_reference_brief",
        "requires_image_reference": any(item.get("requires_image_reference") for item in reference_assets),
        "reference_image_count": len(reference_assets),
        "reference_asset_ids": [item["asset_id"] for item in reference_assets],
        "roles": [item["role"] for item in reference_assets],
        "unsupported_provider_policy": "fail_or_reroute",
    }


def _reference_summary(assets: list[dict[str, Any]]) -> str:
    parts = []
    for item in assets:
        label = item.get("role_label") or ROLE_LABELS.get(item.get("role"), "参考图")
        strength = {"required": "必须保留", "strong": "强参考", "soft": "轻参考"}.get(item.get("constraint_strength"), "参考")
        brief = item.get("visual_summary") or item.get("notes") or "用于固定关键视觉线索"
        parts.append(f"{label}（{strength}）：{brief}")
    return "；".join(parts)


def _public_summary(assets: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in assets:
        label = item.get("role_label") or ROLE_LABELS.get(item.get("role"), "参考图")
        counts[label] = counts.get(label, 0) + 1
    return "参考图：" + "，".join(f"{label} {count} 张" for label, count in counts.items())


def _warnings(assets: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(item.get("role") == "style_material_reference" for item in assets):
        warnings.append("材质/色彩参考不能覆盖已选稀有风格。")
    if any(item.get("role") == "composition_reference" for item in assets):
        warnings.append("构图参考只作为布局启发，不复刻原图画面。")
    return warnings


def _prompt_constraints(assets: list[dict[str, Any]], *, user_prompt: str) -> list[str]:
    constraints = []
    for item in assets:
        role = item.get("role")
        notes = str(item.get("notes") or "").strip()
        if role == "subject_reference":
            constraints.append("保持参考图中的主体轮廓、身份线索和关键可识别特征，但允许稀有风格改变媒介、光线和质感。")
        elif role == "product_reference":
            constraints.append("保持参考图中的产品外观、包装比例、主要颜色和识别点。")
        elif role == "logo_reference":
            constraints.append(_logo_constraint(notes, user_prompt=user_prompt))
        elif role == "style_material_reference":
            constraints.append("只借鉴参考图的材质、色彩、纹理、颗粒或光感，不覆盖当前稀有风格。")
        elif role == "composition_reference":
            constraints.append("只参考上传图的大致空间层次和构图节奏，不直接复刻原图布局。")
        directive = item.get("director_directive") if isinstance(item.get("director_directive"), dict) else {}
        lock_constraints = [str(value) for value in directive.get("lock_constraints") or [] if str(value).strip()]
        allow_transformations = [str(value) for value in directive.get("allow_transformations") or [] if str(value).strip()]
        forbidden_changes = [str(value) for value in directive.get("forbidden_changes") or [] if str(value).strip()]
        if lock_constraints:
            constraints.append("智能判断需保留：" + "，".join(lock_constraints[:5]))
        if allow_transformations:
            constraints.append("智能判断允许变化：" + "，".join(allow_transformations[:5]))
        if forbidden_changes:
            constraints.append("智能判断禁止变化：" + "，".join(forbidden_changes[:5]))
    return constraints


def _logo_constraint(notes: str, *, user_prompt: str) -> str:
    text = f"{notes} {user_prompt}".lower()
    if any(marker in text for marker in ["衣服", "胸口", "瓶身", "包装", "招牌", "surface", "shirt", "bottle", "package", "sign"]):
        return "Logo/标识需要作为画面中物体表面的一部分自然融入，不要简单贴成角标。"
    return "Logo/标识需要作为品牌识别元素出现，尺寸克制，位置服从整体版式。"


def _public_provider_input_plan(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "operation": value.get("operation"),
        "requires_image_reference": bool(value.get("requires_image_reference")),
        "reference_image_count": int(value.get("reference_image_count") or 0),
        "roles": [str(item) for item in value.get("roles") or []],
        "unsupported_provider_policy": value.get("unsupported_provider_policy"),
    }


def _public_directive(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "recommended_role": value.get("recommended_role"),
        "recommended_strength": value.get("recommended_strength"),
        "role_source": value.get("role_source"),
        "provider_input_requirement": value.get("provider_input_requirement"),
        "lock_constraints": [str(item) for item in (value.get("lock_constraints") or []) if str(item).strip()][:6],
        "allow_transformations": [str(item) for item in (value.get("allow_transformations") or []) if str(item).strip()][:6],
        "forbidden_changes": [str(item) for item in (value.get("forbidden_changes") or []) if str(item).strip()][:6],
        "compatibility_note": value.get("compatibility_note"),
    }
