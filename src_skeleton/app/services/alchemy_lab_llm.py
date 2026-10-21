from __future__ import annotations

import base64
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import openai_sdk_client_kwargs, settings


LAB_LLM_PROVIDERS = {"anthropic", "openai", "kimi", "deepseek", "doubao"}
LAB_TEXT_LOGICAL_TIMEOUT_SECONDS = 210.0
LAB_CANDIDATE_TIMEOUT_SECONDS = 90.0


class LabLLMError(RuntimeError):
    def __init__(self, message: str, *, model_attempts: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.model_attempts = list(model_attempts or [])


class LabStructuredOutputError(LabLLMError):
    """A remote LAB text model returned content outside the JSON contract."""


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
    if not image_paths and (not settings.llm_gateway_api_key or not settings.llm_gateway_base_url):
        raise LabLLMError("Unified text LLM gateway key and base URL must both be configured")
    errors: dict[str, str] = {}
    model_attempts: list[dict[str, Any]] = []
    request_deadline = time.monotonic() + (
        min(LAB_TEXT_LOGICAL_TIMEOUT_SECONDS, max(1.0, timeout_seconds * 2.0))
        if image_paths
        else LAB_TEXT_LOGICAL_TIMEOUT_SECONDS
    )
    candidates = _planner_candidates(image_paths=bool(image_paths))
    if not image_paths and any(candidate["provider"] == "unsupported" for candidate in candidates):
        raise LabLLMError("A configured LAB text model has no supported gateway protocol route.")
    for index, candidate in enumerate(candidates):
        provider = candidate["provider"]
        model = candidate["model"]
        remaining = request_deadline - time.monotonic()
        if remaining <= 0:
            break
        candidate_timeout = _lab_candidate_timeout_seconds(remaining, len(candidates) - index)
        started = time.perf_counter()
        try:
            async with asyncio.timeout(candidate_timeout):
                result = await _ask_provider_for_json(
                    provider=provider,
                    model=model,
                    system_prompt=system_prompt,
                    user_payload=user_payload,
                    reasoning_effort=reasoning_effort,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout_seconds=candidate_timeout,
                    image_paths=image_paths or [],
                )
            model_attempts.append({
                "model": model,
                "outcome": "accepted",
                "elapsed_ms": _elapsed_milliseconds(started),
            })
            return result, {
                "llm_provider": f"lab_{provider}",
                "llm_model": model,
                "primary_model": candidates[0]["model"],
                "selected_model": model,
                "selected_provider": provider,
                "fallback_used": index > 0 and bool(errors),
                "model_attempts": model_attempts,
                "vision_used": bool(image_paths),
                **errors,
            }
        except Exception as exc:
            model_attempts.append({
                "model": model,
                "outcome": "failed",
                "failure_class": _safe_failure_class(exc),
                "elapsed_ms": _elapsed_milliseconds(started),
            })
            errors["selected_llm_error" if index == 0 else f"fallback_llm_error_{index}"] = type(exc).__name__
            if not _is_failover_eligible(exc):
                break
    detail = "; ".join(f"{key}={value}" for key, value in errors.items())
    raise LabLLMError(
        f"No configured Lab LLM planner could return JSON{': ' + detail if detail else ''}",
        model_attempts=model_attempts,
    )


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
    vision_provider = _normalize_lab_provider(settings.lab_vision_provider)
    text_model = settings.default_llm_model or "claude-sonnet-5-5"
    text_provider = _text_model_protocol(text_model)
    return {
        "enabled": bool(settings.lab_llm_enabled),
        "provider": text_provider,
        "model": text_model,
        "configured": bool(settings.llm_gateway_api_key and settings.llm_gateway_base_url),
        "vision_enabled": bool(settings.lab_vision_enabled),
        "vision_provider": vision_provider,
        "vision_model": _lab_model(vision_provider),
        "vision_configured": bool(_lab_token(vision_provider)),
    }


def _planner_candidates(*, image_paths: bool) -> list[dict[str, str]]:
    if not image_paths:
        if not settings.llm_gateway_api_key:
            return []
        primary_model = settings.default_llm_model or "claude-sonnet-5-5"
        fallback_model = settings.backup_llm_model or "kimi-k3"
        fallback_models = ["kimi-k3", fallback_model, "gpt-6.1-sol"]
        return [
            {"provider": _text_model_protocol(primary_model), "model": primary_model},
            *[
                {"provider": _text_model_protocol(model), "model": model}
                for model in dict.fromkeys(fallback_models)
                if model.strip().lower() != primary_model.strip().lower()
            ],
        ]
    preferred = _normalize_lab_provider(settings.lab_vision_provider if image_paths else settings.lab_llm_provider)
    if image_paths and preferred == "deepseek":
        preferred = "doubao"
    order = [preferred]
    if image_paths:
        order.extend(["doubao", "openai", "kimi"])
    else:
        order.extend(["deepseek", "doubao", "openai", "kimi"])
    unique = []
    for provider in order:
        if provider in unique:
            continue
        if _lab_token(provider):
            unique.append(provider)
    return [{"provider": provider, "model": _lab_model(provider)} for provider in unique]


def _lab_candidate_timeout_seconds(remaining_seconds: float, remaining_candidates: int) -> float:
    """Bound each LAB attempt by wall clock and leave room for later candidates."""

    share = max(0.0, remaining_seconds) / max(1, remaining_candidates)
    return min(LAB_CANDIDATE_TIMEOUT_SECONDS, share)


def _elapsed_milliseconds(started: float) -> int:
    return max(0, min(3_600_000, int((time.perf_counter() - started) * 1000)))


def _safe_failure_class(exc: BaseException) -> str:
    if isinstance(exc, LabStructuredOutputError):
        return "invalid_structured_response"
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if _is_failover_eligible(exc):
        return "retryable_upstream"
    return "provider_error"


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
    if provider not in {"openai", "anthropic"} and not image_paths:
        raise LabLLMError("The selected LAB text model has no supported gateway protocol route")
    if provider == "openai" or provider == "kimi":
        return await _ask_openai_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            model=model,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            image_paths=image_paths,
            provider=provider,
        )
    return await _ask_anthropic_compatible_json(
        provider=provider,
        system_prompt=system_prompt,
        user_payload=user_payload,
        model=model,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
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
    provider: str = "openai",
) -> dict[str, Any]:
    if not image_paths and (not settings.llm_gateway_api_key or not settings.llm_gateway_base_url):
        raise LabLLMError("Unified text LLM gateway key and base URL must both be configured")
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise LabLLMError("openai package is not installed") from exc
    token = settings.llm_gateway_api_key if not image_paths else _lab_token(provider)
    if not token:
        raise LabLLMError("Lab OpenAI API key is not configured")
    client = AsyncOpenAI(
        **openai_sdk_client_kwargs(
            api_key=token,
            base_url=settings.llm_gateway_base_url if not image_paths else _lab_base_url(provider),
            timeout=httpx.Timeout(timeout_seconds, connect=min(8.0, timeout_seconds)),
            max_retries=0,
        )
    )
    if _is_kimi_k3(model):
        content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(user_payload, ensure_ascii=False)}]
        for path in image_paths[:4]:
            content.append({"type": "image_url", "image_url": {"url": _image_data_url(path)}})
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            reasoning_effort=_kimi_reasoning_effort(reasoning_effort),
        )
        return _loads_json_object(_chat_completion_text(response))

    content = [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}]
    for path in image_paths[:4]:
        content.append({"type": "input_image", "image_url": _image_data_url(path)})
    response_kwargs: dict[str, Any] = {}
    if not _is_gpt_6_1_sol(model):
        response_kwargs["temperature"] = temperature
    response = await client.responses.create(
        model=model,
        input=[{"role": "system", "content": system_prompt}, {"role": "user", "content": content}],
        reasoning={"effort": reasoning_effort},
        text={"format": {"type": "json_object"}},
        store=False,
        **response_kwargs,
    )
    return _loads_json_object(_response_text(response))


async def _ask_anthropic_compatible_json(
    *,
    provider: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    model: str,
    max_tokens: int,
    reasoning_effort: str,
    temperature: float,
    timeout_seconds: float,
    image_paths: list[Path],
) -> dict[str, Any]:
    if not image_paths and (not settings.llm_gateway_api_key or not settings.llm_gateway_base_url):
        raise LabLLMError("Unified text LLM gateway key and base URL must both be configured")
    token = settings.llm_gateway_api_key if not image_paths else _lab_token(provider)
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
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }
    if _is_claude_sonnet_55(model) and reasoning_effort in {"low", "medium", "high", "xhigh", "max"}:
        payload["output_config"] = {"effort": reasoning_effort}
    elif "claude" not in model.lower():
        payload["temperature"] = temperature
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "authorization": f"Bearer {token}",
        "x-api-key": token,
    }
    base_url = settings.llm_gateway_base_url if not image_paths else _lab_base_url(provider)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=min(8.0, timeout_seconds))) as client:
        response = await client.post(_anthropic_messages_url(base_url), headers=headers, json=payload)
        response.raise_for_status()
    return _loads_json_object(_anthropic_response_text(response.json()))


def _normalize_lab_provider(provider: str | None) -> str:
    normalized = str(provider or "deepseek").strip().lower()
    # Keep the legacy LAB vision route mapping isolated from text-model
    # protocol selection; _text_model_protocol handles unified text routes.
    if normalized in {"anthropic", "moonshot"}:
        return "kimi"
    if normalized in {"deepseek", "deepseek_v4", "deepseek-v4"}:
        return "deepseek"
    if normalized in {"byteplus", "volcengine", "volc", "ark"}:
        return "doubao"
    return normalized if normalized in LAB_LLM_PROVIDERS else "deepseek"


def _text_model_protocol(model: str) -> str:
    normalized = str(model or "").strip().lower()
    if normalized.startswith("claude-"):
        return "anthropic"
    if normalized.startswith(("gpt-", "o1", "o3", "o4", "deepseek-", "kimi-", "doubao-")):
        return "openai"
    return "unsupported"


def _is_claude_sonnet_55(model: str) -> bool:
    return str(model or "").strip().lower().startswith("claude-sonnet-5-5")


def _is_kimi_k3(model: str) -> bool:
    return str(model or "").strip().lower().startswith("kimi-k3")


def _is_gpt_6_1_sol(model: str) -> bool:
    return str(model or "").strip().lower().startswith("gpt-6.1-sol")


def _kimi_reasoning_effort(configured_effort: str | None) -> str:
    normalized = str(configured_effort or "").strip().lower()
    return {
        "low": "low",
        "medium": "high",
        "high": "high",
        "xhigh": "max",
        "max": "max",
    }.get(normalized, "low")


def _lab_model(provider: str) -> str:
    if provider == "kimi":
        return settings.kimi_llm_model or "kimi-k2.6"
    if provider == "openai":
        return settings.lab_llm_model if _normalize_lab_provider(settings.lab_llm_provider) == "openai" else settings.openai_llm_model
    if provider == "doubao":
        return settings.lab_doubao_vision_model
    if provider == "deepseek":
        return settings.lab_llm_model if _normalize_lab_provider(settings.lab_llm_provider) == "deepseek" else settings.deepseek_llm_model
    return settings.lab_llm_model or "claude-sonnet-5-5"


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


def _is_failover_eligible(exc: BaseException) -> bool:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 8 and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    for item in chain:
        if isinstance(item, LabStructuredOutputError):
            return True
        if isinstance(item, TimeoutError):
            return True
        if isinstance(item, (httpx.TimeoutException, httpx.TransportError)):
            return True
        response = getattr(item, "response", None)
        status = getattr(response, "status_code", None) or getattr(item, "status_code", None)
        if not isinstance(status, int):
            continue
        if status in {408, 425, 429, 500, 502, 503, 504}:
            return True
        if status == 403:
            try:
                body = response.json() if response is not None else getattr(item, "body", None)
            except Exception:
                body = None
            if not isinstance(body, dict):
                return False
            error = body.get("error") if isinstance(body.get("error"), dict) else body
            code = str(error.get("code") or error.get("type") or "").strip().lower()
            scope = str(error.get("scope") or error.get("category") or "").strip().lower()
            return code in {"model_not_found", "model_not_available", "model_access_denied", "model_permission"} and scope in {"model", "candidate"}
        return False
    return False


def _anthropic_max_tokens(provider: str, model: str, requested: int) -> int:
    if provider == "deepseek" or "deepseek" in (model or "").lower():
        return max(int(requested or 0), 768)
    return requested


def _response_text(response: Any) -> str:
    incomplete = getattr(response, "incomplete_details", None)
    incomplete_reason = getattr(incomplete, "reason", None)
    if str(incomplete_reason or "").lower() in {"content_filter", "refusal"}:
        raise PermissionError("OpenAI-compatible LAB model refused or filtered the request; fallback is not permitted")
    output_text = getattr(response, "output_text", None)
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        if str(getattr(item, "type", "")).lower() == "refusal":
            raise PermissionError("OpenAI-compatible LAB model refused the request; fallback is not permitted")
        for content in getattr(item, "content", []) or []:
            content_type = str(getattr(content, "type", "")).lower()
            if content_type == "refusal" or getattr(content, "refusal", None):
                raise PermissionError("OpenAI-compatible LAB model refused the request; fallback is not permitted")
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    if output_text and str(getattr(response, "status", "")).lower() != "incomplete":
        return output_text
    if chunks:
        return "".join(chunks)
    raise LabStructuredOutputError("Lab LLM response did not include text")


def _chat_completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    choice = choices[0] if choices else None
    message = getattr(choice, "message", None)
    refusal = getattr(message, "refusal", None)
    if refusal or str(getattr(choice, "finish_reason", "") or "").lower() == "content_filter":
        raise PermissionError("Kimi refused or filtered the request; fallback is not permitted")
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text = "".join(str(getattr(item, "text", "") or "") for item in content)
        if text.strip():
            return text
    raise LabStructuredOutputError("Kimi response did not include text")


def _anthropic_response_text(payload: dict[str, Any]) -> str:
    if str(payload.get("stop_reason") or "").lower() == "refusal":
        raise PermissionError("Claude refused the request; fallback is not permitted")
    content = payload.get("content") or []
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("text"):
            chunks.append(str(item["text"]))
    if chunks:
        return "".join(chunks)
    if payload.get("completion"):
        return str(payload["completion"])
    raise LabStructuredOutputError("Lab LLM response did not include text")


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
    except json.JSONDecodeError as first_error:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise LabStructuredOutputError("Lab LLM response was not valid JSON") from first_error
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LabStructuredOutputError("Lab LLM response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LabStructuredOutputError("Lab LLM response was not a JSON object")
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
