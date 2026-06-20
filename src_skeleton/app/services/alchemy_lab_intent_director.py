from __future__ import annotations

from typing import Any

from app.services.alchemy_lab_llm import LabLLMError, plan_lab_json
from app.services.alchemy_lab_uploads import get_lab_upload, lab_uploaded_asset_path, public_lab_asset_summary
from app.services.image_service import registry as image_registry


TARGET_USES = {"product", "poster", "portrait", "food", "packaging", "logo", "scene", "material", "abstract", "image_exploration"}
STYLE_FAMILIES = {"film", "fashion", "product", "photography", "illustration", "graphic", "craft", "digital", "space", "material"}


async def plan_lab_intent(
    *,
    request: Any,
    veyra_user_id: int | None = None,
) -> dict[str, Any]:
    if str(getattr(request, "intent_director", "auto") or "auto").strip().lower() == "off":
        return _fallback_plan(request, source="disabled", applied=False)
    if _uses_mock_image_provider(request):
        return _fallback_plan(request, source="mock_provider_local", applied=False, assets=_asset_payloads(request, veyra_user_id=veyra_user_id))
    assets = _asset_payloads(request, veyra_user_id=veyra_user_id)
    image_paths = [item["path"] for item in assets if item.get("path")]
    payload = _planner_payload(request, assets)
    try:
        plan, metadata = await plan_lab_json(
            system_prompt=_planner_instruction(),
            user_payload=payload,
            reasoning_effort="low",
            max_tokens=1400,
            temperature=0.15,
            timeout_seconds=75.0 if image_paths else 45.0,
            image_paths=image_paths,
        )
        normalized = _normalize_plan(plan, request=request, assets=assets)
        normalized.update(
            {
                "source": "llm_intent_director",
                "applied": True,
                "input_mode": "text_plus_reference" if assets else "text_only",
                "vision_source": "llm_vision" if image_paths and metadata.get("vision_used") else ("local_brief_only" if assets else "none"),
                "llm_provider": metadata.get("llm_provider"),
                "llm_model": metadata.get("llm_model"),
                "llm_fallback_used": bool(metadata.get("fallback_used")),
                "error": None,
            }
        )
        return normalized
    except Exception as exc:
        fallback = _fallback_plan(request, source="local_fallback", applied=False, assets=assets)
        fallback["error"] = {"type": type(exc).__name__, "message": str(exc)[:300]}
        return fallback


def public_intent_metadata(intent_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(intent_plan, dict):
        return {
            "summary": None,
            "target_use": None,
            "confidence": None,
            "must_keep": [],
            "may_change": [],
            "avoid": [],
            "style_routing": {},
            "warnings": [],
        }
    if _is_disabled_plan(intent_plan):
        return {
            "summary": None,
            "target_use": None,
            "confidence": None,
            "must_keep": [],
            "may_change": [],
            "avoid": [],
            "style_routing": {},
            "warnings": [],
        }
    prompt_constraints = intent_plan.get("prompt_constraints") if isinstance(intent_plan.get("prompt_constraints"), dict) else {}
    return {
        "summary": intent_plan.get("user_goal_summary") or intent_plan.get("director_summary"),
        "target_use": intent_plan.get("target_use"),
        "confidence": intent_plan.get("confidence"),
        "must_keep": [str(item) for item in (prompt_constraints.get("must_keep") or []) if str(item).strip()][:8],
        "may_change": [str(item) for item in (prompt_constraints.get("may_change") or []) if str(item).strip()][:8],
        "avoid": [str(item) for item in (prompt_constraints.get("avoid") or []) if str(item).strip()][:8],
        "style_routing": _public_style_routing(intent_plan.get("style_routing")),
        "warnings": [str(item) for item in (intent_plan.get("warnings") or []) if str(item).strip()][:6],
    }


def intent_prompt_block(intent_plan: dict[str, Any] | None) -> str:
    if _is_disabled_plan(intent_plan):
        return ""
    metadata = public_intent_metadata(intent_plan)
    summary = metadata.get("summary")
    must_keep = metadata.get("must_keep") or []
    may_change = metadata.get("may_change") or []
    avoid = metadata.get("avoid") or []
    lines = []
    if summary:
        lines.append(f"智能意图约束：{summary}")
    if must_keep:
        lines.append("必须保留：" + "，".join(must_keep[:6]))
    if may_change:
        lines.append("允许变化：" + "，".join(may_change[:6]))
    if avoid:
        lines.append("避免变化：" + "，".join(avoid[:6]))
    return "\n".join(lines)


def style_family_hints(intent_plan: dict[str, Any] | None) -> list[str]:
    if not isinstance(intent_plan, dict):
        return []
    if _is_disabled_plan(intent_plan):
        return []
    routing = intent_plan.get("style_routing") if isinstance(intent_plan.get("style_routing"), dict) else {}
    families = []
    for value in routing.get("preferred_families") or []:
        clean = str(value or "").strip()
        if clean in STYLE_FAMILIES and clean not in families:
            families.append(clean)
    return families


def reference_directive_for_asset(intent_plan: dict[str, Any] | None, asset_id: str) -> dict[str, Any] | None:
    if not isinstance(intent_plan, dict):
        return None
    directives = intent_plan.get("reference_directives") or []
    for item in directives:
        if isinstance(item, dict) and str(item.get("asset_id") or "") == asset_id:
            return item
    return None


def _is_disabled_plan(intent_plan: dict[str, Any] | None) -> bool:
    return isinstance(intent_plan, dict) and str(intent_plan.get("source") or "").strip().lower() == "disabled"


def _uses_mock_image_provider(request: Any) -> bool:
    provider_name = str(getattr(request, "provider_preference", "") or "").strip().lower()
    if provider_name == "mock_image":
        return True
    provider = image_registry.image_providers.get(provider_name) if provider_name else None
    if provider is None:
        return False
    return provider.__class__.__name__.lower().endswith("mockprovider") or "mockimageprovider" in {
        cls.__name__.lower() for cls in provider.__class__.mro()
    }


def _planner_instruction() -> str:
    return (
        "You are Alchemy Lab's Intent Director for rare-style image exploration. "
        "Return JSON only. Do not reveal chain-of-thought. "
        "Decide what the user wants, how uploaded references should be used, and how automatic rare-style selection should be scoped. "
        "Do not replace manually selected styles. User-declared roles and strengths are higher priority than your recommendation. "
        "Rare style remains the exploration variable; references constrain subject, product, logo, material, color, or composition only. "
        "Do not mention internal ids, storage paths, URLs, providers, APIs, repositories, or account data."
    )


def _planner_payload(request: Any, assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "idea": getattr(request, "idea", ""),
        "mode": getattr(request, "mode", "minimal"),
        "style_family": getattr(request, "style_family", None),
        "aspect_ratio": getattr(request, "aspect_ratio", None),
        "selected_style_ids_count": len(getattr(request, "selected_style_ids", []) or []),
        "has_manual_styles": bool((getattr(request, "style_id", "") or "").strip() or getattr(request, "selected_style_ids", [])),
        "quality_enhancement": getattr(request, "quality_enhancement", "auto"),
        "reference_assets": [_public_asset_payload(item) for item in assets],
        "required_json_shape": {
            "target_use": "product|poster|portrait|food|packaging|logo|scene|material|abstract|image_exploration",
            "subject_kind": "natural-language subject type",
            "main_subject": "natural-language main subject",
            "user_goal_summary": "short summary visible to the user",
            "confidence": "low|medium|high",
            "reference_directives": [
                {
                    "asset_id": "copy from provided non-secret local handle",
                    "recommended_role": "subject_reference|product_reference|logo_reference|style_material_reference|composition_reference|negative_reference",
                    "recommended_strength": "required|strong|soft",
                    "lock_constraints": ["what must remain"],
                    "allow_transformations": ["what rare styles may change"],
                    "forbidden_changes": ["what must not change"],
                    "provider_input_requirement": "required|preferred|optional|brief_only",
                    "compatibility_note": "short note",
                }
            ],
            "style_routing": {
                "auto_selection_scope": "full_library|compatible_families|user_family",
                "preferred_families": ["product"],
                "avoid_families": ["fashion"],
                "style_strength_guidance": "short guidance",
                "reason": "short reason",
            },
            "prompt_constraints": {
                "must_keep": ["concrete constraints"],
                "may_change": ["allowed changes"],
                "avoid": ["forbidden drift"],
                "director_summary": "one-sentence rule",
            },
            "quality_hints": {
                "visual_focus": "short hint",
                "text_intent": "short hint",
            },
            "warnings": [],
        },
    }


def _asset_payloads(request: Any, *, veyra_user_id: int | None) -> list[dict[str, Any]]:
    output = []
    for item in getattr(request, "reference_assets", []) or []:
        asset_id = str(getattr(item, "asset_id", "") or "").strip()
        asset = get_lab_upload(asset_id)
        if not asset:
            continue
        path = lab_uploaded_asset_path(asset_id)
        brief = asset.brief if isinstance(asset.brief, dict) else {}
        output.append(
            {
                "asset_id": asset_id,
                "declared_role": getattr(item, "role", None) or asset.role,
                "declared_strength": getattr(item, "constraint_strength", None),
                "local_suggested_role": brief.get("role") if isinstance(brief, dict) else None,
                "local_suggested_strength": asset.constraint_strength,
                "user_notes": getattr(item, "notes", None) or asset.intended_use or "",
                "brief": public_lab_asset_summary(asset),
                "local_brief": brief,
                "owner_matches": asset.veyra_user_id in {None, veyra_user_id},
                "path": path,
            }
        )
    return output


def _public_asset_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": item.get("asset_id"),
        "declared_role": item.get("declared_role"),
        "declared_strength": item.get("declared_strength"),
        "local_suggested_role": item.get("local_suggested_role"),
        "local_suggested_strength": item.get("local_suggested_strength"),
        "user_notes": item.get("user_notes"),
        "brief": item.get("brief"),
        "local_brief": item.get("local_brief"),
    }


def _normalize_plan(plan: dict[str, Any], *, request: Any, assets: list[dict[str, Any]]) -> dict[str, Any]:
    target_use = str(plan.get("target_use") or _target_use_from_text(getattr(request, "idea", ""), getattr(request, "mode", ""))).strip()
    confidence = str(plan.get("confidence") or "medium").strip().lower()
    prompt_constraints = plan.get("prompt_constraints") if isinstance(plan.get("prompt_constraints"), dict) else {}
    reference_directives = _normalize_reference_directives(plan.get("reference_directives"), assets)
    return {
        "target_use": target_use if target_use in TARGET_USES else "image_exploration",
        "subject_kind": _clean(plan.get("subject_kind"))[:120],
        "main_subject": _clean(plan.get("main_subject"))[:180] or _clean(getattr(request, "idea", ""))[:180],
        "user_goal_summary": _clean(plan.get("user_goal_summary"))[:220] or _clean(getattr(request, "idea", ""))[:220],
        "confidence": confidence if confidence in {"low", "medium", "high"} else "medium",
        "reference_directives": reference_directives,
        "style_routing": _normalize_style_routing(plan.get("style_routing"), request=request),
        "prompt_constraints": {
            "must_keep": _clean_list(prompt_constraints.get("must_keep"), 8),
            "may_change": _clean_list(prompt_constraints.get("may_change"), 8),
            "avoid": _clean_list(prompt_constraints.get("avoid"), 8),
            "director_summary": _clean(prompt_constraints.get("director_summary"))[:220],
        },
        "quality_hints": plan.get("quality_hints") if isinstance(plan.get("quality_hints"), dict) else {},
        "warnings": _clean_list(plan.get("warnings"), 8),
    }


def _normalize_reference_directives(value: Any, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("asset_id")): item for item in value or [] if isinstance(item, dict)}
    output = []
    for asset in assets:
        asset_id = str(asset.get("asset_id"))
        item = by_id.get(asset_id) or {}
        output.append(
            {
                "asset_id": asset_id,
                "recommended_role": _reference_role(
                    item.get("recommended_role") or asset.get("declared_role") or asset.get("local_suggested_role")
                ),
                "recommended_strength": _reference_strength(
                    item.get("recommended_strength") or asset.get("declared_strength") or asset.get("local_suggested_strength")
                ),
                "role_source": "llm" if item else "upload_default",
                "lock_constraints": _clean_list(item.get("lock_constraints"), 8),
                "allow_transformations": _clean_list(item.get("allow_transformations"), 8),
                "forbidden_changes": _clean_list(item.get("forbidden_changes"), 8),
                "provider_input_requirement": _provider_input_requirement(item.get("provider_input_requirement")),
                "compatibility_note": _clean(item.get("compatibility_note"))[:220],
            }
        )
    return output


def _normalize_style_routing(value: Any, *, request: Any) -> dict[str, Any]:
    routing = value if isinstance(value, dict) else {}
    preferred = [item for item in _clean_list(routing.get("preferred_families"), 6) if item in STYLE_FAMILIES]
    avoid = [item for item in _clean_list(routing.get("avoid_families"), 6) if item in STYLE_FAMILIES]
    if not preferred:
        preferred = _preferred_families_for_target(_target_use_from_text(getattr(request, "idea", ""), getattr(request, "mode", "")))
    return {
        "manual_styles_respected": bool((getattr(request, "style_id", "") or "").strip() or getattr(request, "selected_style_ids", [])),
        "auto_selection_scope": _clean(routing.get("auto_selection_scope")) or "compatible_families",
        "preferred_families": preferred,
        "avoid_families": avoid,
        "style_strength_guidance": _clean(routing.get("style_strength_guidance"))[:220],
        "reason": _clean(routing.get("reason"))[:220],
    }


def _fallback_plan(request: Any, *, source: str, applied: bool, assets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    target = _target_use_from_text(getattr(request, "idea", ""), getattr(request, "mode", ""))
    assets = assets if assets is not None else _asset_payloads(request, veyra_user_id=None)
    has_assets = bool(assets)
    return {
        "source": source,
        "applied": applied,
        "input_mode": "text_plus_reference" if has_assets else "text_only",
        "vision_source": "local_brief_only" if has_assets else "none",
        "confidence": "low" if has_assets else "medium",
        "target_use": target,
        "subject_kind": target,
        "main_subject": _clean(getattr(request, "idea", ""))[:180],
        "user_goal_summary": _fallback_summary(request, target=target, has_assets=has_assets),
        "reference_directives": _normalize_reference_directives([], assets),
        "style_routing": {
            "manual_styles_respected": bool((getattr(request, "style_id", "") or "").strip() or getattr(request, "selected_style_ids", [])),
            "auto_selection_scope": "compatible_families",
            "preferred_families": _preferred_families_for_target(target),
            "avoid_families": [],
            "style_strength_guidance": "稀有风格保持为主要视觉变量。",
            "reason": "本地 fallback 根据文字和模式推断。",
        },
        "prompt_constraints": _fallback_prompt_constraints(target=target, has_assets=has_assets),
        "quality_hints": {},
        "warnings": ["LLM 意图判断不可用，已使用本地保守判断。"] if source == "local_fallback" else [],
        "llm_provider": None,
        "llm_model": None,
        "llm_fallback_used": False,
        "error": None,
    }


def _target_use_from_text(idea: str, mode: str) -> str:
    text = f"{idea} {mode}".lower()
    if any(marker in text for marker in ["包装", "package", "packaging", "瓶", "罐"]):
        return "packaging"
    if any(marker in text for marker in ["产品", "商品", "product"]):
        return "product"
    if any(marker in text for marker in ["人像", "portrait", "角色", "character"]):
        return "portrait"
    if any(marker in text for marker in ["食物", "美食", "food", "蛋糕", "饮品"]):
        return "food"
    if any(marker in text for marker in ["海报", "poster", "封面", "cover", "活动"]):
        return "poster"
    if any(marker in text for marker in ["场景", "scene", "空间"]):
        return "scene"
    if any(marker in text for marker in ["材质", "material", "纹理"]):
        return "material"
    return "image_exploration"


def _preferred_families_for_target(target: str) -> list[str]:
    mapping = {
        "product": ["product", "photography", "graphic", "material"],
        "packaging": ["graphic", "product", "material", "photography"],
        "poster": ["graphic", "film", "illustration", "photography"],
        "portrait": ["photography", "fashion", "film", "illustration"],
        "food": ["photography", "graphic", "product", "craft"],
        "scene": ["space", "film", "photography", "digital"],
        "material": ["material", "craft", "photography", "product"],
    }
    return mapping.get(target, ["graphic", "photography", "product", "film"])


def _fallback_summary(request: Any, *, target: str, has_assets: bool) -> str:
    if has_assets:
        return "系统将参考图作为约束输入，保留关键主体或材质线索，同时让稀有风格控制视觉变化。"
    return f"系统判断这是 {target} 方向的稀有风格探索，将优先抽取更匹配的风格族。"


def _fallback_prompt_constraints(*, target: str, has_assets: bool) -> dict[str, Any]:
    must_keep = ["用户描述的主体与用途"]
    if has_assets:
        must_keep.append("参考图中的关键识别线索")
    if target in {"product", "packaging"}:
        must_keep.extend(["产品比例", "包装识别点"])
    may_change = ["背景", "光线", "构图细节", "稀有风格媒介语言"]
    avoid = ["风格覆盖主体识别", "随机无关文字", "廉价模板感"]
    return {
        "must_keep": must_keep[:8],
        "may_change": may_change,
        "avoid": avoid,
        "director_summary": "参考图或文字意图决定主体边界，稀有风格决定视觉语言。",
    }


def _reference_role(value: Any) -> str:
    clean = str(value or "").strip()
    allowed = {"subject_reference", "product_reference", "logo_reference", "style_material_reference", "composition_reference", "negative_reference"}
    return clean if clean in allowed else "subject_reference"


def _reference_strength(value: Any) -> str:
    clean = str(value or "").strip()
    return clean if clean in {"required", "strong", "soft"} else "strong"


def _provider_input_requirement(value: Any) -> str:
    clean = str(value or "").strip()
    return clean if clean in {"required", "preferred", "optional", "brief_only"} else "preferred"


def _public_style_routing(value: Any) -> dict[str, Any]:
    routing = value if isinstance(value, dict) else {}
    return {
        "auto_selection_scope": routing.get("auto_selection_scope"),
        "preferred_families": [str(item) for item in (routing.get("preferred_families") or []) if str(item).strip()][:6],
        "avoid_families": [str(item) for item in (routing.get("avoid_families") or []) if str(item).strip()][:6],
        "style_strength_guidance": routing.get("style_strength_guidance") or "",
        "reason": routing.get("reason") or "",
    }


def _clean_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    output = []
    for item in value:
        clean = _clean(item)
        if clean and clean not in output:
            output.append(clean[:180])
        if len(output) >= limit:
            break
    return output


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())
