from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import openai_sdk_client_kwargs, settings
from app.schemas import ImagePromptPlan


INTENSITY_PROFILES: dict[str, dict[str, Any]] = {
    "swift": {
        "label": "快速",
        "planner": "local",
        "reasoning_effort": "none",
        "direction": "直接、干净、不过度复杂",
        "negative": ["画面不要过度复杂"],
    },
    "balanced": {
        "label": "均衡",
        "planner": "llm",
        "reasoning_effort": "low",
        "direction": "清晰主体、场景、构图和文字约束",
        "negative": ["避免杂乱版式", "避免视觉重心不清"],
    },
    "studio": {
        "label": "精修",
        "planner": "llm",
        "reasoning_effort": "medium",
        "direction": "工作室级灯光、镜头、材质、文字和质检",
        "negative": ["避免廉价图库感", "避免材质不一致", "避免文字不可读"],
    },
    "atelier": {
        "label": "臻选",
        "planner": "llm",
        "reasoning_effort": "high",
        "direction": "高级创意指导，强化概念、品牌气质、构图层级和预检",
        "negative": ["避免视觉噪音", "避免廉价商业风", "避免品牌气质漂移", "避免细节畸形"],
    },
}


async def apply_work_intensity(
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    work_intensity: str,
    provider_preference: str | None,
    asset_context: dict[str, Any] | None = None,
) -> tuple[ImagePromptPlan, dict[str, Any]]:
    intensity = work_intensity if work_intensity in INTENSITY_PROFILES else "balanced"
    profile = INTENSITY_PROFILES[intensity]
    local_plan = _apply_local_profile(
        plan,
        original_prompt=original_prompt,
        intensity=intensity,
        profile=profile,
        asset_context=asset_context,
    )
    summary: dict[str, Any] = {
        "work_intensity": intensity,
        "label": profile["label"],
        "planner": "local",
        "reasoning_effort": profile["reasoning_effort"],
        "llm_used": False,
    }
    if not _should_use_llm(intensity=intensity, provider_preference=provider_preference):
        return local_plan, summary

    llm_errors: dict[str, str] = {}
    for index, candidate in enumerate(_planner_candidates()):
        provider = candidate["provider"]
        model = candidate["model"]
        if not _planner_configured(provider):
            continue
        try:
            llm_patch = await _ask_provider_for_prompt_plan(
                provider,
                model,
                local_plan,
                original_prompt=original_prompt,
                intensity=intensity,
                profile=profile,
                asset_context=asset_context,
            )
            fallback_used = index > 0 and bool(llm_errors)
            merged = _merge_llm_patch(
                local_plan,
                llm_patch,
                intensity=intensity,
                profile=profile,
                llm_provider=provider,
                llm_model=model,
                fallback_used=fallback_used,
                original_prompt=original_prompt,
                asset_context=asset_context,
            )
            return merged, {
                **summary,
                "planner": "llm",
                "llm_used": True,
                "llm_provider": provider,
                "llm_model": model,
                "fallback_used": fallback_used,
                **llm_errors,
            }
        except Exception as exc:
            error_key = "selected_llm_error" if index == 0 else "fallback_llm_error"
            llm_errors[error_key] = type(exc).__name__

    return local_plan.model_copy(
        update={
            "variables": {
                **local_plan.variables,
                **llm_errors,
                "llm_planning_fallback": True,
            }
        }
    ), {
        **summary,
        **llm_errors,
        "llm_used": False,
    }


def _apply_local_profile(
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> ImagePromptPlan:
    prompt = _local_generation_prompt(plan, original_prompt=original_prompt, profile=profile, asset_context=asset_context)
    negatives = list(dict.fromkeys([*plan.negative_constraints, *profile["negative"]]))
    variables = {
        **plan.variables,
        "work_intensity": intensity,
        "work_intensity_label": profile["label"],
        "planner": "local",
        "reasoning_effort": profile["reasoning_effort"],
        "generation_prompt": prompt,
    }
    if asset_context:
        variables["asset_context"] = asset_context
    return plan.model_copy(update={"negative_constraints": negatives, "variables": variables})


def _local_generation_prompt(
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> str:
    scene = plan.scene or "根据用户需求推导一个统一、可信的画面场景"
    style = plan.style or "符合用户需求的精致商业视觉风格"
    lines = [
        f"创作目标：{original_prompt.strip()}",
        f"画面主体：{plan.main_subject}",
        f"场景设定：{scene}",
        f"视觉风格：{style}",
        f"构图要求：{plan.composition}",
        f"画幅与输出：{plan.size}，{plan.output_format}，质量 {plan.quality}。",
        f"执行强度：{profile['label']}，{profile['direction']}。",
    ]
    if plan.brand_constraints:
        lines.append(f"品牌与素材约束：{_join_constraints(plan.brand_constraints)}。")
    if plan.text.get("required"):
        lines.append(f"文字要求：{_text_requirement(plan.text)}")
    lines.append(f"避免：{_join_constraints([*plan.negative_constraints, *profile['negative']])}。")
    return "\n".join(lines)


def _should_use_llm(*, intensity: str, provider_preference: str | None) -> bool:
    if intensity == "swift":
        return False
    if provider_preference == "mock_image":
        return False
    if not settings.llm_prompt_planning_enabled:
        return False
    return any(_planner_configured(candidate["provider"]) for candidate in _planner_candidates())


def _planner_candidates() -> list[dict[str, str]]:
    selected = _normalize_llm_provider(settings.default_llm_provider)
    fallback = _normalize_llm_provider(settings.backup_llm_provider)
    order: list[str] = []
    for provider in [selected, fallback]:
        if provider not in order:
            order.append(provider)
    return [{"provider": provider, "model": _llm_model(provider)} for provider in order]


def _normalize_llm_provider(provider: str | None) -> str:
    normalized = str(provider or "openai").strip().lower()
    if normalized in {"anthropic", "kimi", "moonshot"}:
        return "anthropic"
    if normalized in {"deepseek", "deepseek_v4", "deepseek-v4"}:
        return "deepseek"
    return "openai"


def _llm_model(provider: str) -> str:
    if provider == "anthropic":
        return settings.kimi_llm_model
    if provider == "deepseek":
        return settings.deepseek_llm_model
    return settings.openai_llm_model


def _planner_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider in {"anthropic", "deepseek"}:
        return bool(_anthropic_token(provider))
    return False


async def _ask_provider_for_prompt_plan(
    provider: str,
    model: str,
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if provider in {"anthropic", "deepseek"}:
        return await _ask_anthropic_for_prompt_plan(
            plan,
            provider=provider,
            model=model,
            original_prompt=original_prompt,
            intensity=intensity,
            profile=profile,
            asset_context=asset_context,
        )
    return await _ask_openai_for_prompt_plan(
        plan,
        model=model,
        original_prompt=original_prompt,
        intensity=intensity,
        profile=profile,
        asset_context=asset_context,
    )


async def ask_llm_json_plan(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    reasoning_effort: str = "low",
    max_tokens: int = 1200,
    temperature: float = 0.2,
    timeout_seconds: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not settings.llm_prompt_planning_enabled:
        raise RuntimeError("LLM prompt planning is disabled")
    errors: dict[str, str] = {}
    for index, candidate in enumerate(_planner_candidates()):
        provider = candidate["provider"]
        model = candidate["model"]
        if not _planner_configured(provider):
            continue
        try:
            if provider in {"anthropic", "deepseek"}:
                result = await _ask_anthropic_for_json_plan(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                )
            else:
                result = await _ask_openai_for_json_plan(
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                )
            return result, {
                "llm_provider": provider,
                "llm_model": model,
                "fallback_used": index > 0 and bool(errors),
                **errors,
            }
        except Exception as exc:
            errors["selected_llm_error" if index == 0 else "fallback_llm_error"] = type(exc).__name__
    detail = "; ".join(f"{key}={value}" for key, value in errors.items())
    raise RuntimeError(f"No configured LLM planner could return JSON{': ' + detail if detail else ''}")


async def _ask_openai_for_json_plan(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    model: str,
    reasoning_effort: str,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = AsyncOpenAI(
        **openai_sdk_client_kwargs(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
    )

    response = await client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        reasoning={"effort": reasoning_effort},
        text={"format": {"type": "json_object"}},
        temperature=temperature,
        store=False,
    )
    return _loads_json_object(_response_text(response))


async def _ask_anthropic_for_json_plan(
    *,
    provider: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    token = _anthropic_token(provider)
    if not token:
        raise RuntimeError(f"{provider} compatible LLM token is not configured")

    payload = {
        "model": model,
        "max_tokens": _anthropic_max_tokens(provider, model, max_tokens),
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
    }
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "authorization": f"Bearer {token}",
        "x-api-key": token,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(_anthropic_messages_url(_anthropic_base_url(provider)), headers=headers, json=payload)
        response.raise_for_status()
    return _loads_json_object(_anthropic_response_text(response.json()))


async def _ask_openai_for_prompt_plan(
    plan: ImagePromptPlan,
    *,
    model: str,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = AsyncOpenAI(
        **openai_sdk_client_kwargs(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=30.0,
            max_retries=0,
        )
    )

    response = await client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": _planner_instruction()},
            {
                "role": "user",
                "content": json.dumps(
                    _planner_user_payload(plan, original_prompt, intensity, profile, asset_context),
                    ensure_ascii=False,
                ),
            },
        ],
        reasoning={"effort": profile["reasoning_effort"]},
        text={"format": {"type": "json_object"}},
        store=False,
    )
    return _loads_json_object(_response_text(response))


async def _ask_anthropic_for_prompt_plan(
    plan: ImagePromptPlan,
    *,
    provider: str,
    model: str,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = _anthropic_token(provider)
    if not token:
        raise RuntimeError(f"{provider} compatible LLM token is not configured")

    payload = {
        "model": model,
        "max_tokens": _anthropic_max_tokens(provider, model, 1200),
        "temperature": 0.2,
        "system": _planner_instruction(),
        "messages": [
            {
                "role": "user",
                "content": json.dumps(_planner_user_payload(plan, original_prompt, intensity, profile, asset_context), ensure_ascii=False),
            }
        ],
    }
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "authorization": f"Bearer {token}",
        "x-api-key": token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(_anthropic_messages_url(_anthropic_base_url(provider)), headers=headers, json=payload)
        response.raise_for_status()
    return _loads_json_object(_anthropic_response_text(response.json()))


def _planner_instruction() -> str:
    return (
        "You are the image prompt architect for a production image-generation agent. "
        "Return JSON only. Do not include chain-of-thought. Produce concise, high-signal art direction. "
        "Enhance the user's intent without reversing it: do not add removal, no-text, no-logo, no-people, or replacement constraints unless the user explicitly asked for them. "
        "If required text is present, preserve the exact text string and require normal spacing, clear glyphs, and no extra characters. "
        "When image references are provided, use them as visual evidence for color, lighting, material, composition, identity, readable text, marks, UI, labels, and other concrete visible information. "
        "If the user asks to use an uploaded image as a prototype, template, original, or reference, preserve visible information by default and only change details that the user explicitly changes. "
        "Do not mention internal asset ids, storage paths, provider names, API operations, or endpoint details in the final prompt."
    )


def _planner_user_payload(
    plan: ImagePromptPlan,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
    asset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "user_prompt": original_prompt,
        "work_intensity": intensity,
        "intensity_direction": profile["direction"],
        "current_plan": plan.model_dump(),
        "asset_context": asset_context or {},
        "asset_context_rule": "Use structured asset context for concise prompt planning. If provider_input_plan includes real image/reference inputs, explicitly bind the final prompt to those uploaded images; otherwise treat material data as a weak brief only.",
        "intent_preservation_rule": "Planner output may refine quality, style, composition, and production details, but must not contradict the user prompt or silently remove visible content from uploaded references. Never add 'no text', 'no logo', 'no people', or similar exclusions unless the user explicitly requested that exclusion.",
        "required_json_shape": {
            "main_subject": "string",
            "scene": "string",
            "style": "string",
            "composition": "string",
            "brand_constraints": ["string"],
            "negative_constraints": ["string"],
            "text": {"required": False, "content": "", "language": "zh-CN"},
            "generation_prompt": "final prompt to send to the image model; include exact required text and reference-image constraints when present",
            "planning_notes": ["brief non-sensitive checklist items"],
        },
    }


def _anthropic_token(provider: str = "anthropic") -> str | None:
    if provider == "deepseek":
        return settings.deepseek_llm_api_key
    return settings.anthropic_api_key or settings.anthropic_auth_token


def _anthropic_base_url(provider: str = "anthropic") -> str | None:
    if provider == "deepseek":
        return settings.deepseek_llm_base_url
    return settings.anthropic_base_url


def _anthropic_max_tokens(provider: str, model: str, requested: int) -> int:
    # DeepSeek V4 often emits a short thinking block before the final text.
    # Keep tiny JSON probes from being truncated before the answer appears.
    if provider == "deepseek" or "deepseek" in (model or "").lower():
        return max(int(requested or 0), 768)
    return requested


def _anthropic_messages_url(base_url: str | None) -> str:
    base = (base_url or "https://api.anthropic.com").rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    if chunks:
        return "".join(chunks)
    raise RuntimeError("LLM planner response did not include text")


def _anthropic_response_text(payload: dict[str, Any]) -> str:
    content = payload.get("content") or []
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("text"):
            chunks.append(str(item["text"]))
    if chunks:
        return "".join(chunks)
    if payload.get("completion"):
        return str(payload["completion"])
    raise RuntimeError("Fallback LLM planner response did not include text")


def _loads_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM planner response was not a JSON object")
    return parsed


def _compact_asset_context(asset_context: dict[str, Any]) -> str:
    compact_assets = []
    for item in asset_context.get("assets", [])[:5]:
        profile = item.get("vision_profile") or {}
        compact_assets.append(
            {
                "role": item.get("role"),
                "provider_input_mode": item.get("provider_input_mode"),
                "summary": profile.get("summary"),
                "notes": item.get("notes"),
            }
        )
    compact = {
        "provider_input_plan": asset_context.get("provider_input_plan"),
        "assets": compact_assets,
        "warnings": asset_context.get("warnings", []),
    }
    return json.dumps(compact, ensure_ascii=False)


def _join_constraints(values: list[Any]) -> str:
    return "；".join(_clean_sentence_fragment(item) for item in values if _clean_sentence_fragment(item))


def _clean_sentence_fragment(value: Any) -> str:
    return str(value).strip().rstrip("。.;；")


def _text_requirement(text: dict[str, Any]) -> str:
    content = str(text.get("content") or "").strip()
    language = str(text.get("language") or "zh-CN").strip()
    if content:
        return f"文字必须严格为“{content}”，语言 {language}，不得增删改字，不要拆字，不要多余空格，正常字距，文字边缘干净可读，并与画面排版自然融合。"
    return f"如需出现文字，使用 {language}，保持短句、正常字距、清晰可读、无乱码。"


def _merge_llm_patch(
    plan: ImagePromptPlan,
    patch: dict[str, Any],
    *,
    intensity: str,
    profile: dict[str, Any],
    llm_provider: str,
    llm_model: str,
    fallback_used: bool,
    original_prompt: str = "",
    asset_context: dict[str, Any] | None = None,
) -> ImagePromptPlan:
    text_plan = _merge_text_plan(plan.text, patch.get("text"))
    generation_prompt = str(patch.get("generation_prompt") or plan.variables.get("generation_prompt") or "")
    generation_prompt = _sanitize_generation_prompt(generation_prompt)
    generation_prompt, guard_notes = _apply_intent_preservation_guard(
        generation_prompt,
        original_prompt=original_prompt,
        asset_context=asset_context,
        text_plan=text_plan,
    )
    generation_prompt = _ensure_required_text_instruction(generation_prompt, text_plan)
    negative_constraints = _list_or_existing(patch.get("negative_constraints"), plan.negative_constraints)
    if text_plan.get("required"):
        negative_constraints = list(
            dict.fromkeys(
                [
                    *negative_constraints,
                    "避免错别字或乱码",
                    "避免文字被拆开或多余空格",
                    "避免文字笔画变形",
                ]
            )
        )
    variables = {
        **plan.variables,
        "work_intensity": intensity,
        "work_intensity_label": profile["label"],
        "planner": "llm",
        "reasoning_effort": profile["reasoning_effort"],
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_fallback_used": fallback_used,
        "generation_prompt": generation_prompt,
        "planning_notes": patch.get("planning_notes") or [],
        "intent_preservation_guard": guard_notes,
    }
    return plan.model_copy(
        update={
            "main_subject": patch.get("main_subject") or plan.main_subject,
            "scene": patch.get("scene") or plan.scene,
            "style": patch.get("style") or plan.style,
            "composition": patch.get("composition") or plan.composition,
            "brand_constraints": _list_or_existing(patch.get("brand_constraints"), plan.brand_constraints),
            "negative_constraints": negative_constraints,
            "text": text_plan,
            "variables": variables,
        }
    )


def _merge_text_plan(original: dict[str, Any], candidate: Any) -> dict[str, Any]:
    merged = dict(original or {})
    if isinstance(candidate, dict):
        merged.update({key: value for key, value in candidate.items() if value not in {None, ""}})
    original_content = str((original or {}).get("content") or "").strip()
    if (original or {}).get("required") and original_content:
        merged["required"] = True
        merged["content"] = original_content
        merged["language"] = str((original or {}).get("language") or merged.get("language") or "zh-CN")
    return merged


def _ensure_required_text_instruction(generation_prompt: str, text: dict[str, Any]) -> str:
    content = str(text.get("content") or "").strip()
    if not text.get("required") or not content:
        return generation_prompt
    instruction = _text_requirement(text)
    if content in generation_prompt and ("不得增删改字" in generation_prompt or "exact" in generation_prompt.lower()):
        return generation_prompt
    return "\n".join(part for part in [generation_prompt.strip(), f"文字要求：{instruction}"] if part).strip()


TEXT_REMOVAL_PATTERN = re.compile(
    r"(?:"
    r"无文字|不要文字|不加文字|不出现文字|没有文字|去文字|去除文字|去掉文字|移除文字|删除文字|"
    r"无文案|不要文案|不加文案|不出现文案|去文案|去除文案|去掉文案|移除文案|删除文案|"
    r"无标题|不要标题|不加标题|不出现标题|去标题|去除标题|去掉标题|移除标题|删除标题|"
    r"no\s+text|without\s+text|textless|no\s+words|no\s+lettering|no\s+typography|remove\s+text|delete\s+text"
    r")",
    flags=re.IGNORECASE,
)

TEXT_DELETE_REQUEST_PATTERN = re.compile(
    r"(?:"
    r"(?:去掉|去除|移除|删除|擦除|清除|不要|不保留).{0,10}(?:文字|文案|标题|字幕|字样|标语|logo|Logo|标志|水印)|"
    r"(?:remove|delete|erase|clear|no|without).{0,20}(?:text|words|lettering|typography|logo|watermark)"
    r")",
    flags=re.IGNORECASE,
)

REFERENCE_PROTOTYPE_PATTERN = re.compile(
    r"(?:"
    r"(?:以|按|基于|根据|参考|照着|用).{0,12}(?:这张图|上传图|参考图|原图|图片|素材|reference image|uploaded image).{0,16}(?:原型|基础|模板|蓝本|参考|改|生成|制作|做)|"
    r"(?:这张图|上传图|参考图|原图|图片|素材|reference image|uploaded image).{0,16}(?:为原型|为基础|作模板|做模板|继续|改成|生成)"
    r")",
    flags=re.IGNORECASE,
)


def _apply_intent_preservation_guard(
    generation_prompt: str,
    *,
    original_prompt: str,
    asset_context: dict[str, Any] | None,
    text_plan: dict[str, Any],
) -> tuple[str, list[str]]:
    prompt = str(generation_prompt or "").strip()
    source = str(original_prompt or "")
    guard_notes: list[str] = []
    has_reference_input = _asset_context_has_reference_input(asset_context)
    user_requested_text_removal = _user_requested_text_removal(source)
    text_required = bool(text_plan.get("required"))

    if prompt and TEXT_REMOVAL_PATTERN.search(prompt) and (text_required or has_reference_input) and not user_requested_text_removal:
        prompt = TEXT_REMOVAL_PATTERN.sub("不要新增无关文字", prompt)
        prompt = _append_guard_line(
            prompt,
            "参考图中的可读文字、标题、品牌标识、标签、界面文字或招牌如果存在，默认属于用户提供的有效信息；除非用户明确要求删除或替换，不要擅自移除、改写或弱化。",
        )
        guard_notes.append("removed_unrequested_no_text_constraint")

    if has_reference_input and _uses_uploaded_image_as_prototype(source) and not user_requested_text_removal:
        prompt = _append_guard_line(
            prompt,
            "以上传参考图为原型时，规划器只能增强画面质量和表达方式，不得反向改变用户根本意图；参考图中已有的主体、结构、文字、标识、包装、界面或其他可见信息，除用户明确要求变化的部分外应尽量保留。",
        )
        guard_notes.append("added_reference_intent_preservation")

    return prompt, guard_notes


def _asset_context_has_reference_input(asset_context: dict[str, Any] | None) -> bool:
    if not isinstance(asset_context, dict):
        return False
    plan = asset_context.get("provider_input_plan") or {}
    if plan.get("requires_image_reference") or int(plan.get("reference_image_count") or 0) > 0:
        return True
    return any((item.get("provider_input_mode") == "reference_image") for item in asset_context.get("assets", []) if isinstance(item, dict))


def _user_requested_text_removal(prompt: str) -> bool:
    return bool(TEXT_DELETE_REQUEST_PATTERN.search(str(prompt or "")))


def _uses_uploaded_image_as_prototype(prompt: str) -> bool:
    return bool(REFERENCE_PROTOTYPE_PATTERN.search(str(prompt or "")))


def _append_guard_line(prompt: str, line: str) -> str:
    clean = prompt.strip()
    if line in clean:
        return clean
    return "\n".join(part for part in [clean, line] if part).strip()


def _sanitize_generation_prompt(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"\basset_[A-Za-z0-9_]+\b", "上传参考图", text)
    text = re.sub(r"`[^`]*(?:asset_|generated_images|\\.media_storage|reference-probe)[^`]*`", "上传参考图", text)
    text = re.sub(r"\bprovider\b", "image model", text, flags=re.IGNORECASE)
    text = re.sub(r"\bimages?\\.edit\b", "image reference", text, flags=re.IGNORECASE)
    return text.strip()


def _list_or_existing(value: Any, existing: list[str]) -> list[str]:
    if not isinstance(value, list):
        return existing
    return [str(item) for item in value if str(item).strip()]
