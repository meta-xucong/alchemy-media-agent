from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import openai_sdk_client_kwargs, settings


LAB_LLM_PROVIDERS = {"openai", "kimi", "deepseek", "doubao"}


class LabLLMError(RuntimeError):
    pass


async def plan_lab_json(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    reasoning_effort: str = "low",
    max_tokens: int = 1200,
    temperature: float = 0.2,
    timeout_seconds: float = 30.0,
    image_paths: list[Path] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not settings.lab_llm_enabled:
        raise LabLLMError("Lab LLM planning is disabled")
    errors: dict[str, str] = {}
    for index, candidate in enumerate(_planner_candidates(image_paths=bool(image_paths))):
        provider = candidate["provider"]
        model = candidate["model"]
        try:
            result = await _ask_provider_for_json(
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_payload=user_payload,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                image_paths=image_paths or [],
            )
            return result, {
                "llm_provider": f"lab_{provider}",
                "llm_model": model,
                "fallback_used": index > 0 and bool(errors),
                "vision_used": bool(image_paths),
                **errors,
            }
        except Exception as exc:
            errors["selected_llm_error" if index == 0 else f"fallback_llm_error_{index}"] = type(exc).__name__
    detail = "; ".join(f"{key}={value}" for key, value in errors.items())
    raise LabLLMError(f"No configured Lab LLM planner could return JSON{': ' + detail if detail else ''}")


async def describe_lab_images(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    image_paths: list[Path],
    timeout_seconds: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not settings.lab_vision_enabled or not image_paths:
        raise LabLLMError("Lab vision planning is disabled or no images were supplied")
    return await plan_lab_json(
        system_prompt=system_prompt,
        user_payload=user_payload,
        reasoning_effort="low",
        max_tokens=1000,
        temperature=0.1,
        timeout_seconds=timeout_seconds,
        image_paths=image_paths,
    )


def lab_llm_status() -> dict[str, Any]:
    return {
        "enabled": bool(settings.lab_llm_enabled),
        "provider": _normalize_lab_provider(settings.lab_llm_provider),
        "model": _lab_model(_normalize_lab_provider(settings.lab_llm_provider)),
        "configured": bool(_lab_token(_normalize_lab_provider(settings.lab_llm_provider))),
        "vision_enabled": bool(settings.lab_vision_enabled),
        "vision_provider": _normalize_lab_provider(settings.lab_vision_provider),
        "vision_model": settings.lab_doubao_vision_model,
        "vision_configured": bool(settings.lab_doubao_vision_api_key),
    }


def _planner_candidates(*, image_paths: bool) -> list[dict[str, str]]:
    preferred = _normalize_lab_provider(settings.lab_vision_provider if image_paths else settings.lab_llm_provider)
    order = [preferred]
    if image_paths:
        order.extend(["doubao", "deepseek", "openai"])
    else:
        order.extend(["deepseek", "openai", "doubao"])
    unique = []
    for provider in order:
        if provider in unique:
            continue
        if _lab_token(provider):
            unique.append(provider)
    return [{"provider": provider, "model": _lab_model(provider)} for provider in unique]


async def _ask_provider_for_json(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    reasoning_effort: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
    image_paths: list[Path],
) -> dict[str, Any]:
    if provider == "openai":
        return await _ask_openai_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            model=model,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            image_paths=image_paths,
        )
    return await _ask_anthropic_compatible_json(
        provider=provider,
        system_prompt=system_prompt,
        user_payload=user_payload,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        image_paths=image_paths,
    )


async def _ask_openai_json(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    model: str,
    reasoning_effort: str,
    temperature: float,
    timeout_seconds: float,
    image_paths: list[Path],
) -> dict[str, Any]:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise LabLLMError("openai package is not installed") from exc
    token = _lab_token("openai")
    if not token:
        raise LabLLMError("Lab OpenAI API key is not configured")
    client = AsyncOpenAI(
        **openai_sdk_client_kwargs(
            api_key=token,
            base_url=settings.lab_openai_base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
    )
    content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]
    for path in image_paths[:4]:
        content.append({"type": "input_image", "image_url": _image_data_url(path)})
    response = await client.responses.create(
        model=model,
        input=[{"role": "system", "content": system_prompt}, {"role": "user", "content": content}],
        reasoning={"effort": reasoning_effort},
        text={"format": {"type": "json_object"}},
        temperature=temperature,
        store=False,
    )
    return _loads_json_object(_response_text(response))


async def _ask_anthropic_compatible_json(
    *,
    provider: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
    image_paths: list[Path],
) -> dict[str, Any]:
    token = _lab_token(provider)
    if not token:
        raise LabLLMError(f"Lab {provider} token is not configured")
    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(user_payload, ensure_ascii=False)}]
    for path in image_paths[:4]:
        mime = _image_mime(path)
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                },
            }
        )
    payload = {
        "model": model,
        "max_tokens": _anthropic_max_tokens(provider, model, max_tokens),
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "authorization": f"Bearer {token}",
        "x-api-key": token,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(_anthropic_messages_url(_lab_base_url(provider)), headers=headers, json=payload)
        response.raise_for_status()
    return _loads_json_object(_anthropic_response_text(response.json()))


def _normalize_lab_provider(provider: str | None) -> str:
    normalized = str(provider or "kimi").strip().lower()
    if normalized in {"anthropic", "moonshot"}:
        return "kimi"
    if normalized in {"deepseek", "deepseek_v4", "deepseek-v4"}:
        return "deepseek"
    if normalized in {"byteplus", "volcengine", "volc", "ark"}:
        return "doubao"
    return normalized if normalized in LAB_LLM_PROVIDERS else "kimi"


def _lab_model(provider: str) -> str:
    if provider == "openai":
        return settings.lab_llm_model if _normalize_lab_provider(settings.lab_llm_provider) == "openai" else settings.openai_llm_model
    if provider == "doubao":
        return settings.lab_doubao_vision_model
    if provider == "deepseek":
        return settings.lab_llm_model if _normalize_lab_provider(settings.lab_llm_provider) == "deepseek" else settings.deepseek_llm_model
    return settings.lab_llm_model or settings.kimi_llm_model


def _lab_token(provider: str) -> str | None:
    if provider == "openai":
        return settings.lab_openai_api_key
    if provider == "doubao":
        return settings.lab_doubao_vision_api_key
    if provider == "deepseek":
        return settings.deepseek_llm_api_key
    if provider == "kimi":
        return settings.lab_kimi_api_key
    return None


def _lab_base_url(provider: str) -> str | None:
    if provider == "openai":
        return settings.lab_openai_base_url
    if provider == "doubao":
        return settings.lab_doubao_vision_base_url
    if provider == "deepseek":
        return settings.deepseek_llm_base_url
    if provider == "kimi":
        return settings.lab_kimi_base_url
    return None


def _anthropic_messages_url(base_url: str | None) -> str:
    base = (base_url or "https://api.anthropic.com").rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _anthropic_max_tokens(provider: str, model: str, requested: int) -> int:
    if provider == "deepseek" or "deepseek" in (model or "").lower():
        return max(int(requested or 0), 768)
    return requested


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
    raise LabLLMError("Lab LLM response did not include text")


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
    raise LabLLMError("Lab LLM response did not include text")


def _loads_json_object(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
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
        raise LabLLMError("Lab LLM response was not a JSON object")
    return parsed


def _image_data_url(path: Path) -> str:
    return f"data:{_image_mime(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
