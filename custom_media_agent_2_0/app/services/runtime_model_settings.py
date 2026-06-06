from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.schemas import V2RuntimeModelSettingsRequest, V2RuntimeModelSettingsResponse


VALID_IMAGE_PROVIDERS = {"auto", "openai_gpt_image", "gemini_image", "mock_image"}
VALID_CASE_INTELLIGENCE_PROVIDERS = {"rules", "claude-code"}
VALID_CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
RUNTIME_MODEL_FIELDS = {
    "image_generation_provider",
    "openai_image_model",
    "gemini_image_model",
    "default_agent_model",
    "output_review_agent_enabled",
    "output_review_agent_model",
    "claude_orchestrator_enabled",
    "claude_orchestrator_model",
    "claude_orchestrator_fallback_model",
    "claude_orchestrator_effort",
    "claude_orchestrator_tools",
    "case_intelligence_provider",
    "case_intelligence_model",
}


def runtime_model_settings_path():
    return settings.data_dir / "runtime_model_settings.json"


def apply_persisted_runtime_model_settings() -> None:
    path = runtime_model_settings_path()
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(payload, dict):
        _apply_runtime_updates(_normalize_updates(payload), persist=False)


def get_runtime_model_settings() -> V2RuntimeModelSettingsResponse:
    return V2RuntimeModelSettingsResponse(
        image_generation_provider=settings.image_generation_provider,
        openai_image_model=settings.openai_image_model,
        openai_api_key_configured=bool(settings.openai_api_key),
        openai_base_url_configured=bool(settings.openai_base_url),
        gemini_image_model=settings.gemini_image_model,
        gemini_api_key_configured=bool(settings.gemini_api_key),
        gemini_base_url_configured=bool(settings.gemini_base_url),
        default_agent_model=settings.default_agent_model,
        output_review_agent_enabled=settings.output_review_agent_enabled,
        output_review_agent_model=settings.output_review_agent_model,
        claude_orchestrator_enabled=settings.claude_orchestrator_enabled,
        claude_orchestrator_cli=settings.claude_orchestrator_cli,
        claude_orchestrator_model=settings.claude_orchestrator_model,
        claude_orchestrator_fallback_model=settings.claude_orchestrator_fallback_model,
        claude_orchestrator_effort=settings.claude_orchestrator_effort,
        claude_orchestrator_tools=settings.claude_orchestrator_tools,
        claude_orchestrator_timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        claude_orchestrator_max_output_tokens=settings.claude_orchestrator_max_output_tokens,
        case_intelligence_provider=settings.case_intelligence_provider,  # type: ignore[arg-type]
        case_intelligence_model=settings.case_intelligence_model,
        persisted=runtime_model_settings_path().exists(),
    )


def update_runtime_model_settings(body: V2RuntimeModelSettingsRequest) -> V2RuntimeModelSettingsResponse:
    updates = _normalize_updates(body.model_dump(exclude_unset=True))
    _apply_runtime_updates(updates, persist=True)
    return get_runtime_model_settings()


def _normalize_updates(raw: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in RUNTIME_MODEL_FIELDS:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                value = None
        updates[key] = value

    provider = updates.get("image_generation_provider")
    if provider and provider not in VALID_IMAGE_PROVIDERS:
        updates["image_generation_provider"] = "auto"
    elif provider:
        updates["image_generation_provider"] = _coerce_configured_provider(provider)

    intelligence_provider = updates.get("case_intelligence_provider")
    if intelligence_provider and intelligence_provider not in VALID_CASE_INTELLIGENCE_PROVIDERS:
        updates["case_intelligence_provider"] = "rules"

    effort = updates.get("claude_orchestrator_effort")
    if effort and effort not in VALID_CLAUDE_EFFORTS:
        updates["claude_orchestrator_effort"] = "low"

    if updates.get("default_agent_model") is None:
        updates.pop("default_agent_model", None)
    if updates.get("openai_image_model") is None:
        updates.pop("openai_image_model", None)
    if updates.get("gemini_image_model") is None:
        updates.pop("gemini_image_model", None)

    return updates


def _coerce_configured_provider(provider: str) -> str:
    if provider in {"auto", "mock_image"}:
        return provider
    if provider == "openai_gpt_image" and settings.openai_api_key:
        return provider
    if provider == "gemini_image" and settings.gemini_api_key:
        return provider
    if settings.openai_api_key:
        return "openai_gpt_image"
    if settings.gemini_api_key:
        return "gemini_image"
    return "mock_image" if settings.allow_mock_fallback else "auto"


def _apply_runtime_updates(updates: dict[str, Any], *, persist: bool) -> None:
    if not updates:
        return
    for key, value in updates.items():
        object.__setattr__(settings, key, value)
    if persist:
        _persist_runtime_updates()


def _persist_runtime_updates() -> None:
    path = runtime_model_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        field: getattr(settings, field)
        for field in sorted(RUNTIME_MODEL_FIELDS)
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
