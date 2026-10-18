from __future__ import annotations

import json
import os
from typing import Any

from app.config import settings
from app.schemas import V2RuntimeModelSettingsRequest, V2RuntimeModelSettingsResponse


VALID_IMAGE_PROVIDERS = {"auto", "openai_gpt_image", "doubao_image", "gemini_image", "mock_image"}
VALID_CASE_INTELLIGENCE_PROVIDERS = {"rules", "claude-code"}
VALID_CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
RUNTIME_MODEL_FIELDS = {
    "image_generation_provider",
    "openai_image_model",
    "doubao_image_model",
    "gemini_image_model",
    "default_agent_model",
    "output_review_agent_enabled",
    "output_review_agent_model",
    "claude_orchestrator_enabled",
    "claude_orchestrator_model",
    "claude_orchestrator_multimodal_model",
    "claude_orchestrator_fallback_model",
    "claude_orchestrator_fallback_models",
    "claude_orchestrator_effort",
    "claude_orchestrator_tools",
    "claude_checkpoint_orchestrator_enabled",
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


def refresh_runtime_gateway_credentials() -> None:
    """Reload the shared runtime credential so separately running workers see API updates."""
    path = settings.data_dir / "llm_gateway.env"
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() in {"LLM_GATEWAY_API_KEY", "LLM_GATEWAY_BASE_URL"}:
            values[key.strip()] = value.strip().strip('"').strip("'")
    if "LLM_GATEWAY_API_KEY" in values:
        object.__setattr__(settings, "llm_gateway_api_key", values["LLM_GATEWAY_API_KEY"] or None)
    if "LLM_GATEWAY_BASE_URL" in values:
        object.__setattr__(settings, "llm_gateway_base_url", values["LLM_GATEWAY_BASE_URL"] or None)


def get_runtime_model_settings() -> V2RuntimeModelSettingsResponse:
    return V2RuntimeModelSettingsResponse(
        image_generation_provider=settings.image_generation_provider,
        openai_image_model=settings.openai_image_model,
        openai_api_key_configured=bool(settings.openai_api_key),
        openai_base_url_configured=bool(settings.openai_base_url),
        doubao_image_model=settings.doubao_image_model,
        doubao_image_api_key_configured=bool(settings.doubao_image_api_key),
        doubao_image_base_url_configured=bool(settings.doubao_image_base_url),
        gemini_image_model=settings.gemini_image_model,
        gemini_api_key_configured=bool(settings.gemini_api_key),
        gemini_base_url_configured=bool(settings.gemini_base_url),
        default_agent_model=settings.default_agent_model,
        output_review_agent_enabled=settings.output_review_agent_enabled,
        output_review_agent_model=settings.output_review_agent_model,
        claude_orchestrator_enabled=settings.claude_orchestrator_enabled,
        claude_orchestrator_cli=settings.claude_orchestrator_cli,
        claude_orchestrator_model=settings.claude_orchestrator_model,
        claude_orchestrator_multimodal_model=settings.claude_orchestrator_multimodal_model,
        claude_orchestrator_fallback_model=settings.claude_orchestrator_fallback_model,
        claude_orchestrator_effort=settings.claude_orchestrator_effort,
        claude_orchestrator_tools=settings.claude_orchestrator_tools,
        claude_orchestrator_timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        claude_orchestrator_max_output_tokens=settings.claude_orchestrator_max_output_tokens,
        claude_checkpoint_orchestrator_enabled=settings.claude_checkpoint_orchestrator_enabled,
        claude_orchestrator_fallback_models=list(settings.claude_orchestrator_fallback_models),
        llm_gateway_api_key_configured=bool(settings.llm_gateway_api_key),
        llm_gateway_base_url=settings.llm_gateway_base_url,
        case_intelligence_provider=settings.case_intelligence_provider,  # type: ignore[arg-type]
        case_intelligence_model=settings.case_intelligence_model,
        persisted=runtime_model_settings_path().exists(),
    )


def update_runtime_model_settings(body: V2RuntimeModelSettingsRequest) -> V2RuntimeModelSettingsResponse:
    updates = _normalize_updates(body.model_dump(exclude_unset=True))
    gateway_key = updates.pop("llm_gateway_api_key", None) if "llm_gateway_api_key" in updates else None
    gateway_base = updates.pop("llm_gateway_base_url", None) if "llm_gateway_base_url" in updates else None
    if gateway_key is not None or gateway_base is not None:
        next_key = gateway_key if gateway_key is not None else settings.llm_gateway_api_key
        next_base = gateway_base if gateway_base is not None else settings.llm_gateway_base_url
        _persist_gateway_env(gateway_key=next_key, gateway_base=next_base)
    _apply_runtime_updates(updates, persist=True)
    if gateway_key is not None or gateway_base is not None:
        if gateway_key is not None:
            object.__setattr__(settings, "llm_gateway_api_key", gateway_key)
        if gateway_base is not None:
            object.__setattr__(settings, "llm_gateway_base_url", gateway_base)
    return get_runtime_model_settings()


def _normalize_updates(raw: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in RUNTIME_MODEL_FIELDS and key not in {"llm_gateway_api_key", "llm_gateway_base_url"}:
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

    fallback_models = updates.get("claude_orchestrator_fallback_models")
    if fallback_models is not None:
        updates["claude_orchestrator_fallback_models"] = _normalize_model_queue(fallback_models)

    if updates.get("default_agent_model") is None:
        updates.pop("default_agent_model", None)
    if updates.get("openai_image_model") is None:
        updates.pop("openai_image_model", None)
    if updates.get("doubao_image_model") is None:
        updates.pop("doubao_image_model", None)
    if updates.get("gemini_image_model") is None:
        updates.pop("gemini_image_model", None)

    return updates


def _persist_gateway_env(*, gateway_key: str | None, gateway_base: str | None) -> None:
    """Persist the write-only gateway secret in V2 data, never JSON settings."""
    path = settings.data_dir / "llm_gateway.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    except OSError:
        lines = []
    values = {
        "LLM_GATEWAY_API_KEY": str(gateway_key or ""),
        "LLM_GATEWAY_BASE_URL": str(gateway_base or ""),
    }
    output: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].removeprefix("export ").strip() if "=" in stripped else ""
        if key in values:
            if key not in seen:
                output.append(f"{key}={values[key]}")
                seen.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={value}")
    temp = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output).rstrip() + "\n")
    temp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _normalize_model_queue(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple)):
        candidates = value
    else:
        return ()
    models: list[str] = []
    for item in candidates:
        model = str(item or "").strip()
        if model and model not in models:
            models.append(model)
    return tuple(models[:12])


def _coerce_configured_provider(provider: str) -> str:
    if provider in {"auto", "mock_image"}:
        return provider
    if provider == "gemini_image" and not settings.gemini_image_generation_enabled:
        return "auto"
    return provider


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
