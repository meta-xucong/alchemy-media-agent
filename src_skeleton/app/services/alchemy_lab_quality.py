from __future__ import annotations

import re
from typing import Any

from app.services.work_intensity import ask_llm_json_plan


QUALITY_ENHANCEMENT_OPTIONS = {"auto", "off", "balanced", "curated"}
TEXT_RENDERING_POLICIES = {"exact", "semantic", "decorative", "avoid_rendering"}
TEXT_IMPORTANCE_LEVELS = {"primary", "secondary", "tertiary", "decorative"}
MAX_FINAL_PROMPT_CHARS = 4200


async def enhance_lab_prompt(
    *,
    request: Any,
    style: Any,
    prompt: Any,
    selected_styles: list[Any] | None = None,
    composer_factory: Any | None = None,
) -> Any:
    requested_mode = _quality_mode(getattr(request, "quality_enhancement", "auto"))
    hygiene_prompt, hygiene_metadata = prompt_hygiene(str(prompt.final_prompt or ""))
    prompt = prompt.model_copy(
        update={
            "final_prompt": hygiene_prompt,
            "prompt_metadata": {
                **dict(prompt.prompt_metadata or {}),
                "quality_enhancement": _base_metadata(requested_mode, hygiene_metadata),
            },
        }
    )
    strategy = _resolve_strategy(requested_mode, request=request, style=style, selected_styles=selected_styles)
    if strategy == "off":
        return _with_quality_metadata(
            prompt,
            requested_mode=requested_mode,
            strategy=strategy,
            applied=False,
            hygiene_metadata=hygiene_metadata,
            text_hierarchy={
                "applied": False,
                "has_text_intent": False,
                "text_strategy_summary": "",
                "text_roles": [],
                "avoid_text": [],
                "postprocess_recommendation": "",
            },
            art_direction_summary="",
            source="base_rare_style_prompt",
        )

    try:
        llm_plan, llm_metadata = await plan_lab_quality(
            request=request,
            style=style,
            base_prompt=hygiene_prompt,
            strategy=strategy,
            selected_styles=selected_styles or [],
        )
        enhanced_prompt = assemble_enhanced_prompt(
            request=request,
            style=style,
            base_prompt=hygiene_prompt,
            llm_plan=llm_plan,
        )
        enhanced_prompt, final_hygiene = prompt_hygiene(enhanced_prompt)
        merged_hygiene = _merge_hygiene_metadata(hygiene_metadata, final_hygiene)
        return _with_quality_metadata(
            prompt.model_copy(update={"final_prompt": enhanced_prompt}),
            requested_mode=requested_mode,
            strategy=strategy,
            applied=True,
            hygiene_metadata=merged_hygiene,
            text_hierarchy=_text_hierarchy_metadata(llm_plan),
            art_direction_summary=_clean_text(llm_plan.get("art_direction_summary")),
            source="llm_quality_enhancement",
            llm_metadata=llm_metadata,
        )
    except Exception as exc:
        if composer_factory is not None and strategy in {"balanced", "curated"}:
            local_prompt = composer_factory(
                request=request,
                style=style,
                base_prompt=hygiene_prompt,
                strategy=strategy,
            )
            local_prompt, final_hygiene = prompt_hygiene(local_prompt)
            merged_hygiene = _merge_hygiene_metadata(hygiene_metadata, final_hygiene)
            return _with_quality_metadata(
                prompt.model_copy(update={"final_prompt": local_prompt}),
                requested_mode=requested_mode,
                strategy=strategy,
                applied=True,
                hygiene_metadata=merged_hygiene,
                text_hierarchy={
                    "applied": False,
                    "has_text_intent": False,
                    "text_strategy_summary": "",
                    "text_roles": [],
                    "avoid_text": [],
                    "postprocess_recommendation": "",
                },
                art_direction_summary="",
                source="local_quality_enhancement",
                error={"type": type(exc).__name__, "message": str(exc)[:300]},
            )
        return _with_quality_metadata(
            prompt,
            requested_mode=requested_mode,
            strategy=strategy,
            applied=False,
            hygiene_metadata=hygiene_metadata,
            text_hierarchy={
                "applied": False,
                "has_text_intent": False,
                "text_strategy_summary": "",
                "text_roles": [],
                "avoid_text": [],
                "postprocess_recommendation": "",
            },
            art_direction_summary="",
            source="base_rare_style_prompt",
            error={"type": type(exc).__name__, "message": str(exc)[:300]},
        )


async def plan_lab_quality(
    *,
    request: Any,
    style: Any,
    base_prompt: str,
    strategy: str,
    selected_styles: list[Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    reasoning_effort = "medium" if strategy == "curated" else "low"
    timeout_seconds = 150.0 if strategy == "curated" else 90.0
    return await ask_llm_json_plan(
        system_prompt=_planner_instruction(strategy),
        user_payload=_planner_payload(request=request, style=style, base_prompt=base_prompt, strategy=strategy, selected_styles=selected_styles),
        reasoning_effort=reasoning_effort,
        max_tokens=1600 if strategy == "curated" else 1200,
        temperature=0.18,
        timeout_seconds=timeout_seconds,
    )


def prompt_hygiene(prompt: str) -> tuple[str, dict[str, Any]]:
    removed: list[str] = []
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in str(prompt or "").splitlines():
        line = " ".join(raw_line.strip().split())
        if not line:
            continue
        signature = _line_signature(line)
        if signature in seen:
            removed.append(line[:160])
            continue
        seen.add(signature)
        line = _remove_internal_ids(line)
        lines.append(line)
    text = "\n".join(lines).strip()
    truncated = False
    if len(text) > MAX_FINAL_PROMPT_CHARS:
        text = text[:MAX_FINAL_PROMPT_CHARS].rstrip()
        truncated = True
    return text, {
        "deduplicated": bool(removed),
        "removed_duplicate_lines": removed[:12],
        "removed_generic_lines": [],
        "truncated": truncated,
        "final_length": len(text),
    }


def assemble_enhanced_prompt(*, request: Any, style: Any, base_prompt: str, llm_plan: dict[str, Any]) -> str:
    subject = _clean_text(llm_plan.get("subject_and_intent")) or str(getattr(request, "idea", "")).strip()
    style_boundary = _clean_text(llm_plan.get("style_boundary")) or _style_summary(style)
    art_direction = _clean_text(llm_plan.get("art_direction_summary"))
    composition = _clean_text(llm_plan.get("composition_guidance"))
    finish = _clean_text(llm_plan.get("finish_quality"))
    text_hierarchy = _text_hierarchy_metadata(llm_plan)

    lines = [
        f"用户创意与主体：{subject}",
        f"稀有风格方向：{style_boundary}",
    ]
    if art_direction:
        lines.append(f"视觉精修指导：{art_direction}")
    if composition:
        lines.append(f"构图与光线：{composition}")
    if finish:
        lines.append(f"完成度要求：{finish}")
    text_lines = _text_hierarchy_prompt_lines(text_hierarchy)
    if text_lines:
        lines.append("智能文案层级：")
        lines.extend(text_lines)
    lines.append(f"基础风格约束：{base_prompt}")
    negative = _negative_guidance(llm_plan, style=style)
    if negative:
        lines.append(f"避免：{negative}")
    return "\n".join(line for line in lines if str(line).strip())


def local_quality_prompt(*, request: Any, style: Any, base_prompt: str, strategy: str) -> str:
    idea = str(getattr(request, "idea", "") or "").strip()
    aspect = str(getattr(request, "aspect_ratio", "") or "square")
    density = "保持克制留白和清晰主视觉" if aspect in {"portrait", "square"} else "保持横向视觉动线和清晰主视觉"
    lines = [
        f"用户创意与主体：{idea}",
        f"稀有风格方向：{_style_summary(style)}",
        f"视觉精修指导：明确单一视觉中心，主体轮廓清楚，风格只服务主体识别，{density}。",
        "构图与光线：前景、中景、背景分层清楚，使用统一光源、可读材质、干净负空间和稳定色彩关系。",
        "完成度要求：商业成片质感，高细节但不堆砌，避免廉价模板感、杂乱装饰、随机符号和无意义文字。",
        f"基础风格约束：{base_prompt}",
    ]
    return "\n".join(lines)


def quality_summary(metadata: dict[str, Any] | None) -> dict[str, Any]:
    value = metadata if isinstance(metadata, dict) else {}
    transform = value.get("quality_enhancement") if isinstance(value.get("quality_enhancement"), dict) else {}
    text_hierarchy = transform.get("text_hierarchy") if isinstance(transform.get("text_hierarchy"), dict) else {}
    return {
        "quality_enhancement_mode": transform.get("mode"),
        "quality_enhancement_strategy": transform.get("strategy"),
        "quality_enhancement_applied": bool(transform.get("applied")),
        "text_hierarchy_applied": bool(text_hierarchy.get("applied")),
        "text_hierarchy_summary": text_hierarchy.get("text_strategy_summary") or "",
        "art_direction_summary": transform.get("art_direction_summary") or "",
    }


def _quality_mode(value: Any) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in QUALITY_ENHANCEMENT_OPTIONS else "auto"


def _resolve_strategy(mode: str, *, request: Any, style: Any, selected_styles: list[Any] | None) -> str:
    if mode == "off":
        return "off"
    if mode in {"balanced", "curated"}:
        return mode
    idea = str(getattr(request, "idea", "") or "")
    style_count = len(selected_styles or [])
    if style_count >= 6 or _looks_text_heavy(idea) or getattr(request, "mode", "") in {"poster", "product"}:
        return "balanced"
    if getattr(style, "family", "") in {"graphic", "product", "material"}:
        return "balanced"
    return "off"


def _looks_text_heavy(value: str) -> bool:
    text = str(value or "").lower()
    markers = [
        "海报",
        "封面",
        "包装",
        "菜单",
        "邀请",
        "活动",
        "标题",
        "文案",
        "招牌",
        "poster",
        "cover",
        "menu",
        "packaging",
        "invitation",
        "event",
    ]
    return any(marker in text for marker in markers) or bool(re.search(r"\d{1,2}[:：]\d{2}", text))


def _planner_instruction(strategy: str) -> str:
    return (
        "You are Alchemy Lab's visual quality planner for rare style image exploration. "
        "Return JSON only. Do not reveal chain-of-thought. "
        "Improve visual finish while preserving the user's concrete intent and the rare style. "
        "You must decide text hierarchy by judgment, not by fixed poster slots. "
        "Never output fixed title/time/location fields. Use a flexible text_roles array only. "
        "Do not mention provider ids, API ids, session ids, case ids, asset ids, repositories, or storage paths. "
        f"Quality strategy: {strategy}."
    )


def _planner_payload(*, request: Any, style: Any, base_prompt: str, strategy: str, selected_styles: list[Any]) -> dict[str, Any]:
    return {
        "original_idea": getattr(request, "idea", ""),
        "normalized_idea": getattr(request, "idea", ""),
        "style_preset_snapshot": _style_snapshot(style),
        "all_selected_style_names": [getattr(item, "display_name", "") for item in selected_styles[:8]],
        "base_rare_style_prompt": base_prompt,
        "exploration_mode": getattr(request, "mode", "minimal"),
        "aspect_ratio": getattr(request, "aspect_ratio", None),
        "target_use_hint": _target_use_hint(request),
        "language_hint": "zh-CN",
        "avoid_generic": bool(getattr(request, "avoid_generic", True)),
        "required_json_shape": {
            "subject_and_intent": "natural-language subject and user intent, no internal ids",
            "style_boundary": "how to apply the rare style without damaging subject readability",
            "art_direction_summary": "concise visual art direction for premium finish",
            "composition_guidance": "composition, lighting, material, color, density",
            "finish_quality": "final image finish requirements",
            "text_hierarchy": {
                "has_text_intent": False,
                "text_strategy_summary": "LLM decides whether and how text should serve the image",
                "text_roles": [
                    {
                        "role_name": "flexible role name created by the model; not a fixed slot",
                        "content": "short text or semantic text intent",
                        "importance": "primary|secondary|tertiary|decorative",
                        "rendering_policy": "exact|semantic|decorative|avoid_rendering",
                        "placement_intent": "natural language placement intent, no grid formula",
                        "reason": "brief reason",
                    }
                ],
                "avoid_text": ["text that should not be directly rendered"],
                "postprocess_recommendation": "optional post-layout suggestion",
            },
            "negative_guidance": ["concise avoid items"],
        },
    }


def _target_use_hint(request: Any) -> str:
    mode = str(getattr(request, "mode", "") or "")
    idea = str(getattr(request, "idea", "") or "").lower()
    if any(marker in idea for marker in ["包装", "packaging", "瓶", "罐"]):
        return "packaging"
    if any(marker in idea for marker in ["菜单", "menu"]):
        return "menu"
    if any(marker in idea for marker in ["封面", "cover"]):
        return "cover"
    if any(marker in idea for marker in ["招牌", "sign"]):
        return "signage"
    if mode == "poster" or any(marker in idea for marker in ["海报", "活动", "邀请", "poster", "event"]):
        return "poster-like"
    if mode == "product":
        return "product"
    if mode == "character":
        return "portrait-or-character"
    return "image-exploration"


def _style_snapshot(style: Any) -> dict[str, Any]:
    return {
        "id": getattr(style, "id", ""),
        "display_name": getattr(style, "display_name", ""),
        "family": getattr(style, "family", ""),
        "category": getattr(style, "category", ""),
        "tags": list(getattr(style, "tags", []) or [])[:12],
        "prompt_directives": list(getattr(style, "prompt_directives", []) or [])[:8],
        "negative_directives": list(getattr(style, "negative_directives", []) or [])[:8],
    }


def _style_summary(style: Any) -> str:
    directives = [str(item).strip() for item in (getattr(style, "prompt_directives", []) or []) if str(item).strip()]
    name = str(getattr(style, "display_name", "") or "").strip()
    return "，".join([name, *directives[:5]]) if directives else name


def _text_hierarchy_metadata(plan: dict[str, Any]) -> dict[str, Any]:
    raw = plan.get("text_hierarchy") if isinstance(plan.get("text_hierarchy"), dict) else {}
    roles = []
    for item in raw.get("text_roles") or []:
        if not isinstance(item, dict):
            continue
        policy = str(item.get("rendering_policy") or "semantic").strip()
        importance = str(item.get("importance") or "secondary").strip()
        roles.append(
            {
                "role_name": _clean_text(item.get("role_name"))[:80],
                "content": _clean_text(item.get("content"))[:140],
                "importance": importance if importance in TEXT_IMPORTANCE_LEVELS else "secondary",
                "rendering_policy": policy if policy in TEXT_RENDERING_POLICIES else "semantic",
                "placement_intent": _clean_text(item.get("placement_intent"))[:180],
                "reason": _clean_text(item.get("reason"))[:180],
            }
        )
        if len(roles) >= 6:
            break
    return {
        "applied": True,
        "has_text_intent": bool(raw.get("has_text_intent") or roles),
        "text_strategy_summary": _clean_text(raw.get("text_strategy_summary"))[:220],
        "text_roles": roles,
        "avoid_text": [_clean_text(item)[:160] for item in (raw.get("avoid_text") or []) if _clean_text(item)][:8],
        "postprocess_recommendation": _clean_text(raw.get("postprocess_recommendation"))[:220],
    }


def _text_hierarchy_prompt_lines(text_hierarchy: dict[str, Any]) -> list[str]:
    if not text_hierarchy.get("has_text_intent") and not text_hierarchy.get("text_roles"):
        recommendation = text_hierarchy.get("postprocess_recommendation")
        return [f"不强行生成可读文字；{recommendation}"] if recommendation else []
    lines = []
    summary = text_hierarchy.get("text_strategy_summary")
    if summary:
        lines.append(f"- {summary}")
    for role in text_hierarchy.get("text_roles") or []:
        content = role.get("content") or "视觉文字意图"
        line = (
            f"- {role.get('role_name') or '文字角色'}：{content}；"
            f"重要性 {role.get('importance')}；渲染策略 {role.get('rendering_policy')}；"
            f"{role.get('placement_intent') or '位置由画面自然决定'}。"
        )
        if role.get("rendering_policy") == "exact":
            line += " 必须保持文字完全一致、正常字距、清晰 glyph、无额外字符。"
        lines.append(line)
    avoid_text = text_hierarchy.get("avoid_text") or []
    if avoid_text:
        lines.append("- 不直接渲染：" + "；".join(avoid_text[:4]))
    recommendation = text_hierarchy.get("postprocess_recommendation")
    if recommendation:
        lines.append(f"- 后期建议：{recommendation}")
    return lines


def _negative_guidance(plan: dict[str, Any], *, style: Any) -> str:
    items = []
    for source in [plan.get("negative_guidance"), getattr(style, "negative_directives", [])]:
        for item in source or []:
            clean = _clean_text(item)
            if clean:
                items.append(clean)
    base = ["随机乱码", "额外无关文字", "主体不清", "廉价模板感", "风格覆盖主体识别"]
    return "；".join(dict.fromkeys([*items, *base]))


def _with_quality_metadata(
    prompt: Any,
    *,
    requested_mode: str,
    strategy: str,
    applied: bool,
    hygiene_metadata: dict[str, Any],
    text_hierarchy: dict[str, Any],
    art_direction_summary: str,
    source: str,
    llm_metadata: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> Any:
    current = dict(prompt.prompt_metadata or {})
    current["quality_enhancement"] = {
        "mode": requested_mode,
        "applied": applied,
        "strategy": strategy,
        "llm_provider": (llm_metadata or {}).get("llm_provider"),
        "llm_model": (llm_metadata or {}).get("llm_model"),
        "llm_fallback_used": bool((llm_metadata or {}).get("fallback_used")),
        "text_hierarchy": text_hierarchy,
        "art_direction_summary": art_direction_summary,
        "prompt_hygiene": hygiene_metadata,
        "source": source,
        "error": error,
    }
    return prompt.model_copy(update={"prompt_metadata": current})


def _base_metadata(mode: str, hygiene_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": mode,
        "applied": False,
        "strategy": "off",
        "llm_provider": None,
        "llm_model": None,
        "llm_fallback_used": False,
        "text_hierarchy": {"applied": False, "has_text_intent": False, "text_roles": []},
        "art_direction_summary": "",
        "prompt_hygiene": hygiene_metadata,
        "source": "base_rare_style_prompt",
        "error": None,
    }


def _merge_hygiene_metadata(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    return {
        "deduplicated": bool(first.get("deduplicated") or second.get("deduplicated")),
        "removed_duplicate_lines": [*(first.get("removed_duplicate_lines") or []), *(second.get("removed_duplicate_lines") or [])][:12],
        "removed_generic_lines": [*(first.get("removed_generic_lines") or []), *(second.get("removed_generic_lines") or [])][:12],
        "truncated": bool(first.get("truncated") or second.get("truncated")),
        "final_length": second.get("final_length", first.get("final_length", 0)),
    }


def _line_signature(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return text[:240]


def _remove_internal_ids(value: str) -> str:
    text = re.sub(r"\b(?:case|asset|provider|source|session|job|variant|prompt)_[A-Za-z0-9_-]{6,}\b", "内部参考", value)
    text = re.sub(r"\b(?:case_id|asset_id|provider_id|source_url|api|repository|storage)\b[:：]?\s*\\S*", "内部参考", text, flags=re.IGNORECASE)
    return text


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())
