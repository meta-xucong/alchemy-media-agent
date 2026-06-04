from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from app.schemas import ImagePromptPlan


INTENSITY_PROFILES: dict[str, dict[str, Any]] = {
    "swift": {
        "label": "快速",
        "planner": "local",
        "reasoning_effort": "none",
        "direction": "direct generation with concise prompt cleanup",
        "negative": ["avoid overcomplicated composition"],
    },
    "balanced": {
        "label": "均衡",
        "planner": "llm",
        "reasoning_effort": "low",
        "direction": "structured art direction with clear subject, scene, composition, and text constraints",
        "negative": ["avoid cluttered layout", "avoid weak focal hierarchy"],
    },
    "studio": {
        "label": "精修",
        "planner": "llm",
        "reasoning_effort": "medium",
        "direction": "studio-grade prompt planning with lighting, lens, material texture, typography, and quality checks",
        "negative": ["avoid generic stock-photo look", "avoid inconsistent materials", "avoid unreadable text"],
    },
    "atelier": {
        "label": "臻选",
        "planner": "llm",
        "reasoning_effort": "high",
        "direction": "premium art-director planning with concept refinement, brand mood, composition hierarchy, and critic-style preflight",
        "negative": ["avoid visual noise", "avoid cheap commercial styling", "avoid brand-tone drift", "avoid malformed details"],
    },
}


async def apply_work_intensity(
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    work_intensity: str,
    provider_preference: str | None,
) -> tuple[ImagePromptPlan, dict[str, Any]]:
    intensity = work_intensity if work_intensity in INTENSITY_PROFILES else "balanced"
    profile = INTENSITY_PROFILES[intensity]
    local_plan = _apply_local_profile(plan, original_prompt=original_prompt, intensity=intensity, profile=profile)
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
) -> ImagePromptPlan:
    prompt = _local_generation_prompt(plan, original_prompt=original_prompt, profile=profile)
    negatives = list(dict.fromkeys([*plan.negative_constraints, *profile["negative"]]))
    variables = {
        **plan.variables,
        "work_intensity": intensity,
        "work_intensity_label": profile["label"],
        "planner": "local",
        "reasoning_effort": profile["reasoning_effort"],
        "generation_prompt": prompt,
    }
    return plan.model_copy(update={"negative_constraints": negatives, "variables": variables})


def _local_generation_prompt(plan: ImagePromptPlan, *, original_prompt: str, profile: dict[str, Any]) -> str:
    lines = [
        f"User request: {original_prompt.strip()}",
        f"Work intensity: {profile['label']} - {profile['direction']}.",
        f"Main subject: {plan.main_subject}",
        f"Scene: {plan.scene or 'infer a coherent scene from the user request'}",
        f"Style: {plan.style or 'fit the user request with polished commercial visual direction'}",
        f"Composition: {plan.composition}",
        f"Canvas: {plan.size}, format: {plan.output_format}, quality: {plan.quality}.",
    ]
    if plan.brand_constraints:
        lines.append(f"Brand/material constraints: {', '.join(plan.brand_constraints)}.")
    if plan.text.get("required"):
        lines.append(f"Required text handling: {plan.text}.")
    lines.append(f"Negative constraints: {', '.join([*plan.negative_constraints, *profile['negative']])}.")
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
    fallback = "anthropic" if selected == "openai" else "openai"
    return [
        {"provider": selected, "model": _llm_model(selected)},
        {"provider": fallback, "model": _llm_model(fallback)},
    ]


def _normalize_llm_provider(provider: str | None) -> str:
    return "anthropic" if provider in {"anthropic", "kimi"} else "openai"


def _llm_model(provider: str) -> str:
    return settings.kimi_llm_model if provider == "anthropic" else settings.openai_llm_model


def _planner_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(_anthropic_token())
    return False


async def _ask_provider_for_prompt_plan(
    provider: str,
    model: str,
    plan: ImagePromptPlan,
    *,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    if provider == "anthropic":
        return await _ask_anthropic_for_prompt_plan(
            plan,
            model=model,
            original_prompt=original_prompt,
            intensity=intensity,
            profile=profile,
        )
    return await _ask_openai_for_prompt_plan(
        plan,
        model=model,
        original_prompt=original_prompt,
        intensity=intensity,
        profile=profile,
    )


async def _ask_openai_for_prompt_plan(
    plan: ImagePromptPlan,
    *,
    model: str,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("openai package is not installed") from exc

    client_kwargs = {"api_key": settings.openai_api_key, "timeout": 30.0, "max_retries": 0}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    client = AsyncOpenAI(**client_kwargs)

    response = await client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": _planner_instruction()},
            {"role": "user", "content": json.dumps(_planner_user_payload(plan, original_prompt, intensity, profile), ensure_ascii=False)},
        ],
        reasoning={"effort": profile["reasoning_effort"]},
        text={"format": {"type": "json_object"}},
        store=False,
    )
    return _loads_json_object(_response_text(response))


async def _ask_anthropic_for_prompt_plan(
    plan: ImagePromptPlan,
    *,
    model: str,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    token = _anthropic_token()
    if not token:
        raise RuntimeError("Kimi LLM token is not configured")

    payload = {
        "model": model,
        "max_tokens": 1200,
        "temperature": 0.2,
        "system": _planner_instruction(),
        "messages": [
            {
                "role": "user",
                "content": json.dumps(_planner_user_payload(plan, original_prompt, intensity, profile), ensure_ascii=False),
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
        response = await client.post(_anthropic_messages_url(settings.anthropic_base_url), headers=headers, json=payload)
        response.raise_for_status()
    return _loads_json_object(_anthropic_response_text(response.json()))


def _planner_instruction() -> str:
    return (
        "You are the image prompt architect for a production image-generation agent. "
        "Return JSON only. Do not include chain-of-thought. Produce concise, high-signal art direction."
    )


def _planner_user_payload(
    plan: ImagePromptPlan,
    original_prompt: str,
    intensity: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "user_prompt": original_prompt,
        "work_intensity": intensity,
        "intensity_direction": profile["direction"],
        "current_plan": plan.model_dump(),
        "required_json_shape": {
            "main_subject": "string",
            "scene": "string",
            "style": "string",
            "composition": "string",
            "brand_constraints": ["string"],
            "negative_constraints": ["string"],
            "text": {"required": False, "content": "", "language": "zh-CN"},
            "generation_prompt": "final prompt to send to the image model",
            "planning_notes": ["brief non-sensitive checklist items"],
        },
    }


def _anthropic_token() -> str | None:
    return settings.anthropic_api_key or settings.anthropic_auth_token


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


def _merge_llm_patch(
    plan: ImagePromptPlan,
    patch: dict[str, Any],
    *,
    intensity: str,
    profile: dict[str, Any],
    llm_provider: str,
    llm_model: str,
    fallback_used: bool,
) -> ImagePromptPlan:
    generation_prompt = str(patch.get("generation_prompt") or plan.variables.get("generation_prompt") or "")
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
    }
    return plan.model_copy(
        update={
            "main_subject": patch.get("main_subject") or plan.main_subject,
            "scene": patch.get("scene") or plan.scene,
            "style": patch.get("style") or plan.style,
            "composition": patch.get("composition") or plan.composition,
            "brand_constraints": _list_or_existing(patch.get("brand_constraints"), plan.brand_constraints),
            "negative_constraints": _list_or_existing(patch.get("negative_constraints"), plan.negative_constraints),
            "text": patch.get("text") if isinstance(patch.get("text"), dict) else plan.text,
            "variables": variables,
        }
    )


def _list_or_existing(value: Any, existing: list[str]) -> list[str]:
    if not isinstance(value, list):
        return existing
    return [str(item) for item in value if str(item).strip()]
