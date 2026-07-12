from __future__ import annotations

import os
import json
from pathlib import Path

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def _codex_auth_value(name: str) -> str | None:
    auth_path = Path(os.path.expandvars(os.getenv("CODEX_AUTH_FILE", r"%USERPROFILE%\.codex\auth.json")))
    if not auth_path.exists():
        return None
    try:
        value = json.loads(auth_path.read_text(encoding="utf-8")).get(name)
    except (OSError, json.JSONDecodeError):
        return None
    return value or None


def _claude_env_value(name: str) -> str | None:
    settings_path = Path(os.path.expandvars(os.getenv("CLAUDE_SETTINGS_FILE", r"%USERPROFILE%\.claude\settings.json")))
    if not settings_path.exists():
        return None
    try:
        env = json.loads(settings_path.read_text(encoding="utf-8")).get("env", {})
    except (OSError, json.JSONDecodeError):
        return None
    value = env.get(name)
    return value or None


def _normalize_openai_base_url(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped
    # OpenAI-compatible Python SDK endpoints are conventionally rooted at /v1.
    if "://" in stripped and "/" not in stripped.split("://", 1)[1]:
        return f"{stripped}/v1"
    return stripped


def openai_sdk_client_kwargs(*, api_key: str | None, base_url: str | None, **extra: object) -> dict[str, object]:
    kwargs: dict[str, object] = {key: value for key, value in extra.items() if value is not None}
    if api_key:
        kwargs["api_key"] = api_key
    # Explicitly pass a concrete base_url so the OpenAI SDK cannot inherit an
    # empty OPENAI_BASE_URL/OPENAI_API_BASE value from the process environment.
    kwargs["base_url"] = _normalize_openai_base_url(base_url) or "https://api.openai.com/v1"
    return kwargs


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings(BaseModel):
    media_agent_mode: str = os.getenv("MEDIA_AGENT_MODE", "live")
    v3_capability_activation_mode: str = os.getenv("V3_CAPABILITY_ACTIVATION_MODE", "shadow").strip().lower()
    v3_capability_catalog_reload_enabled: bool = os.getenv(
        "V3_CAPABILITY_CATALOG_RELOAD_ENABLED", "false"
    ).lower() in {"1", "true", "yes", "on"}
    v3_capability_plan_amendment_enabled: bool = os.getenv(
        "V3_CAPABILITY_PLAN_AMENDMENT_ENABLED", "false"
    ).lower() in {"1", "true", "yes", "on"}
    v3_capability_shadow_audit_enabled: bool = os.getenv(
        "V3_CAPABILITY_SHADOW_AUDIT_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    mock_image_provider_enabled: bool = os.getenv("MOCK_IMAGE_PROVIDER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or _codex_auth_value("OPENAI_API_KEY")
    openai_base_url: str | None = _normalize_openai_base_url(os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"))
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_auth_token: str | None = os.getenv("ANTHROPIC_AUTH_TOKEN") or _claude_env_value("ANTHROPIC_AUTH_TOKEN")
    anthropic_base_url: str | None = os.getenv("ANTHROPIC_BASE_URL") or _claude_env_value("ANTHROPIC_BASE_URL")
    gemini_image_api_key: str | None = os.getenv("GEMINI_IMAGE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    gemini_image_base_url: str | None = os.getenv("GEMINI_IMAGE_BASE_URL") or os.getenv("GOOGLE_GEMINI_BASE_URL")
    gemini_image_generation_enabled: bool = os.getenv("GEMINI_IMAGE_GENERATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    byteplus_api_key: str | None = os.getenv("BYTEPLUS_API_KEY")
    default_llm_provider: str = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
    default_llm_model: str = os.getenv(
        "DEFAULT_LLM_MODEL",
        os.getenv("DEEPSEEK_LLM_MODEL", os.getenv("V2_CLAUDE_ORCHESTRATOR_MODEL", "deepseek-v4-pro-260425")),
    )
    backup_llm_provider: str = os.getenv("BACKUP_LLM_PROVIDER", "openai")
    backup_llm_model: str = os.getenv(
        "BACKUP_LLM_MODEL",
        os.getenv("OPENAI_LLM_MODEL", "gpt-5.5"),
    )
    openai_llm_model: str = os.getenv("OPENAI_LLM_MODEL", "gpt-5.5")
    kimi_llm_model: str = os.getenv("KIMI_LLM_MODEL", "kimi-for-coding")
    deepseek_llm_model: str = os.getenv(
        "DEEPSEEK_LLM_MODEL",
        os.getenv("V2_CLAUDE_ORCHESTRATOR_MODEL", "deepseek-v4-pro-260425"),
    )
    deepseek_llm_base_url: str | None = (
        os.getenv("DEEPSEEK_LLM_BASE_URL")
        or os.getenv("V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL")
        or os.getenv("ANTHROPIC_BASE_URL")
        or os.getenv("LAB_DOUBAO_VISION_BASE_URL")
        or "https://aiself.vip"
    ).rstrip() or None
    deepseek_llm_api_key: str | None = (
        os.getenv("DEEPSEEK_LLM_API_KEY")
        or os.getenv("V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("LAB_DOUBAO_VISION_API_KEY")
    )
    llm_prompt_planning_enabled: bool = os.getenv("LLM_PROMPT_PLANNING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    lab_llm_enabled: bool = os.getenv("LAB_LLM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    lab_llm_provider: str = os.getenv("LAB_LLM_PROVIDER", os.getenv("DEFAULT_LLM_PROVIDER", "deepseek"))
    lab_llm_model: str = os.getenv(
        "LAB_LLM_MODEL",
        os.getenv("DEEPSEEK_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "deepseek-v4-pro-260425")),
    )
    lab_openai_api_key: str | None = os.getenv("LAB_OPENAI_API_KEY") or os.getenv("V2_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or _codex_auth_value("OPENAI_API_KEY")
    lab_openai_base_url: str | None = _normalize_openai_base_url(os.getenv("LAB_OPENAI_BASE_URL") or os.getenv("V2_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"))
    lab_kimi_api_key: str | None = os.getenv("LAB_KIMI_API_KEY") or os.getenv("V2_CLAUDE_ORCHESTRATOR_FALLBACK_AUTH_TOKEN") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
    lab_kimi_base_url: str | None = os.getenv("LAB_KIMI_BASE_URL") or os.getenv("V2_CLAUDE_ORCHESTRATOR_FALLBACK_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
    lab_vision_enabled: bool = os.getenv("LAB_VISION_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    lab_vision_provider: str = os.getenv("LAB_VISION_PROVIDER", "doubao")
    lab_doubao_vision_api_key: str | None = (
        os.getenv("LAB_DOUBAO_VISION_API_KEY")
        or os.getenv("V2_DOUBAO_VISION_API_KEY")
        or os.getenv("V2_DOUBAO_IMAGE_API_KEY")
        or os.getenv("DOUBAO_IMAGE_API_KEY")
        or os.getenv("BYTEPLUS_API_KEY")
    )
    lab_doubao_vision_base_url: str | None = _normalize_openai_base_url(
        os.getenv("LAB_DOUBAO_VISION_BASE_URL")
        or os.getenv("V2_DOUBAO_VISION_BASE_URL")
        or os.getenv("V2_DOUBAO_IMAGE_BASE_URL")
        or os.getenv("DOUBAO_IMAGE_BASE_URL")
        or "https://aiself.vip"
    )
    lab_doubao_vision_model: str = os.getenv(
        "LAB_DOUBAO_VISION_MODEL",
        os.getenv("V2_CLAUDE_ORCHESTRATOR_MULTIMODAL_MODEL", "doubao-seed-2-0-lite-260428"),
    )
    default_image_provider: str = os.getenv("DEFAULT_IMAGE_PROVIDER", "openai_gpt_image")
    default_image_model: str = os.getenv("DEFAULT_IMAGE_MODEL", "gpt-image-2")
    openai_image_model: str = os.getenv("OPENAI_IMAGE_MODEL", os.getenv("DEFAULT_IMAGE_MODEL", "gpt-image-2"))
    # Keep upstream-specific request quirks out of V3 planning.  The default is
    # the standard OpenAI Images contract; a constrained OpenAI-compatible
    # gateway can explicitly opt into a smaller, generation-only transport.
    openai_image_transport_profile: str = os.getenv("OPENAI_IMAGE_TRANSPORT_PROFILE", "openai_standard").strip().lower() or "openai_standard"
    # Zero keeps the V3 provider's normal prompt budget.  A constrained gateway
    # can lower this cap; user-authored direction stays lossless while repeated
    # framework guidance is compacted for transport.
    openai_image_transport_max_prompt_chars: int = _int_env("OPENAI_IMAGE_TRANSPORT_MAX_PROMPT_CHARS", 0)
    doubao_image_api_key: str | None = os.getenv("DOUBAO_IMAGE_API_KEY")
    doubao_image_base_url: str | None = _normalize_openai_base_url(
        os.getenv("DOUBAO_IMAGE_BASE_URL") or "https://aiself.vip"
    )
    doubao_image_model: str = os.getenv("DOUBAO_IMAGE_MODEL", "doubao-seedream-4-0-250828")
    openai_image_local_max_requests_per_minute: int = _int_env("OPENAI_IMAGE_LOCAL_MAX_REQUESTS_PER_MINUTE", 12)
    openai_image_local_max_outputs_per_minute: int = _int_env("OPENAI_IMAGE_LOCAL_MAX_OUTPUTS_PER_MINUTE", 24)
    openai_image_local_queue_timeout_seconds: float = _float_env("OPENAI_IMAGE_LOCAL_QUEUE_TIMEOUT_SECONDS", 900.0)
    openai_image_upstream_cooldown_seconds: float = _float_env("OPENAI_IMAGE_UPSTREAM_COOLDOWN_SECONDS", 90.0)
    openai_image_max_retry_after_seconds: float = _float_env("OPENAI_IMAGE_MAX_RETRY_AFTER_SECONDS", 900.0)
    openai_image_request_timeout_seconds: float = _float_env("OPENAI_IMAGE_REQUEST_TIMEOUT_SECONDS", 240.0)
    openai_image_edit_request_timeout_seconds: float = _float_env("OPENAI_IMAGE_EDIT_REQUEST_TIMEOUT_SECONDS", 420.0)
    # Some OpenAI-compatible gateways own line selection, retry and backoff for
    # one image request.  Opt in only when a gateway documents that contract:
    # V3 will keep exactly one request in flight per logical output instead of
    # racing its own retries against the gateway's failover workflow.
    openai_image_gateway_managed_failover: bool = os.getenv(
        "OPENAI_IMAGE_GATEWAY_MANAGED_FAILOVER", "false"
    ).lower() in {"1", "true", "yes", "on"}
    # This is V3's end-to-end client deadline, not a single upstream-line
    # timeout. It must be longer than the gateway's own end-to-end budget so
    # V3 does not cancel the gateway while it is returning its final terminal
    # result. aiself currently owns a 600-second image budget, so retain a
    # 60-second client-side finalization margin by default.
    openai_image_gateway_managed_failover_timeout_seconds: float = _float_env(
        "OPENAI_IMAGE_GATEWAY_MANAGED_FAILOVER_TIMEOUT_SECONDS", 660.0
    )
    openai_image_edit_transient_cooldown_seconds: float = _float_env("OPENAI_IMAGE_EDIT_TRANSIENT_COOLDOWN_SECONDS", 12.0)
    openai_image_reference_max_upload_bytes: int = _int_env("OPENAI_IMAGE_REFERENCE_MAX_UPLOAD_BYTES", 1_200_000)
    openai_image_reference_max_edge: int = _int_env("OPENAI_IMAGE_REFERENCE_MAX_EDGE", 1024)
    openai_image_reference_jpeg_quality: int = _int_env("OPENAI_IMAGE_REFERENCE_JPEG_QUALITY", 88)
    openai_image_input_fidelity_cache_ttl_seconds: float = _float_env(
        "OPENAI_IMAGE_INPUT_FIDELITY_CACHE_TTL_SECONDS", 86400.0
    )
    v3_identity_metric_enabled: bool = os.getenv("V3_IDENTITY_METRIC_ENABLED", "true").lower() in {
        "1", "true", "yes", "on"
    }
    v3_identity_model_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("V3_IDENTITY_MODEL_DIR", "/app/models/v3_identity"))
    )
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", os.getenv("GEMINI_MODEL", "gemini-3-pro-image-preview"))
    image_work_intensity: str = os.getenv("IMAGE_WORK_INTENSITY", "balanced")
    default_video_provider: str = os.getenv("DEFAULT_VIDEO_PROVIDER", "seedance")
    orchestration_mode: str = os.getenv("ORCHESTRATION_MODE", "runtime_first")
    persist_runtime_settings: bool = os.getenv("MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS", "true").lower() in {"1", "true", "yes", "on"}
    runtime_env_path: Path = Field(default_factory=lambda: Path(os.getenv("MEDIA_AGENT_RUNTIME_ENV_FILE", ".env")))
    media_storage_root: Path = Field(default_factory=lambda: Path(os.getenv("MEDIA_STORAGE_ROOT", ".media_storage")))
    max_asset_upload_bytes: int = _int_env("MAX_ASSET_UPLOAD_BYTES", 12 * 1024 * 1024)
    max_asset_upload_count: int = _int_env("MAX_ASSET_UPLOAD_COUNT", 6)
    veyra_auth_enabled: bool = os.getenv("VEYRA_AUTH_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    veyra_sub2api_base_url: str = os.getenv("VEYRA_SUB2API_BASE_URL", "http://127.0.0.1:8080")
    veyra_internal_token: str | None = os.getenv("VEYRA_INTERNAL_TOKEN")
    veyra_session_secret: str | None = os.getenv("VEYRA_SESSION_SECRET")
    veyra_require_ui_auth: bool = os.getenv("VEYRA_REQUIRE_UI_AUTH", "false").lower() in {"1", "true", "yes", "on"}
    veyra_login_base_url: str = os.getenv("VEYRA_LOGIN_BASE_URL", "https://aiself.vip").rstrip("/")
    veyra_session_cookie_name: str = os.getenv("VEYRA_SESSION_COOKIE_NAME", "alchemy_veyra_session")
    veyra_session_cookie_secure: bool = os.getenv("VEYRA_SESSION_COOKIE_SECURE", "true").lower() in {"1", "true", "yes", "on"}
    veyra_request_timeout_seconds: float = _float_env("VEYRA_REQUEST_TIMEOUT_SECONDS", 10.0)
    veyra_billing_settings_url: str = os.getenv("VEYRA_BILLING_SETTINGS_URL", "http://127.0.0.1:8020/api/v2/veyra/billing/settings/public")
    veyra_billing_rule_key_v1: str = os.getenv("VEYRA_BILLING_RULE_KEY_V1", "alchemy:v1")
    veyra_usage_path: Path = Field(default_factory=lambda: Path(os.getenv("VEYRA_USAGE_PATH", ".media_storage/veyra_usage.jsonl")))
    v2_api_proxy_base_url: str = os.getenv("V2_API_PROXY_BASE_URL", "http://127.0.0.1:8020").rstrip("/")
    v2_api_proxy_timeout_seconds: float = _float_env("V2_API_PROXY_TIMEOUT_SECONDS", 120.0)
    media_acceleration_enabled: bool = os.getenv("ALCHEMY_MEDIA_ACCELERATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    media_acceleration_base_url: str = os.getenv("ALCHEMY_MEDIA_BASE_URL", "").rstrip("/")
    media_acceleration_signing_secret: str | None = os.getenv("ALCHEMY_MEDIA_SIGNING_SECRET") or None
    media_acceleration_url_ttl_seconds: int = _int_env("ALCHEMY_MEDIA_URL_TTL_SECONDS", 300)
    media_acceleration_verify_remote: bool = os.getenv("ALCHEMY_MEDIA_VERIFY_REMOTE_EXISTS", "true").lower() in {"1", "true", "yes", "on"}
    media_acceleration_verify_timeout_seconds: float = _float_env("ALCHEMY_MEDIA_VERIFY_TIMEOUT_SECONDS", 1.2)

    @property
    def live_mode(self) -> bool:
        return self.media_agent_mode.lower() == "live"


settings = Settings()


def update_runtime_settings(
    *,
    default_image_provider: str | None = None,
    default_image_model: str | None = None,
    openai_image_model: str | None = None,
    doubao_image_model: str | None = None,
    doubao_image_api_key: str | None = None,
    doubao_image_base_url: str | None = None,
    gemini_image_model: str | None = None,
    default_llm_provider: str | None = None,
    default_llm_model: str | None = None,
    backup_llm_model: str | None = None,
    openai_llm_model: str | None = None,
    kimi_llm_model: str | None = None,
    deepseek_llm_model: str | None = None,
    deepseek_llm_base_url: str | None = None,
    lab_llm_provider: str | None = None,
    lab_llm_model: str | None = None,
    lab_openai_base_url: str | None = None,
    lab_kimi_base_url: str | None = None,
    lab_doubao_vision_model: str | None = None,
    lab_doubao_vision_base_url: str | None = None,
    image_work_intensity: str | None = None,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    anthropic_api_key: str | None = None,
    anthropic_base_url: str | None = None,
    deepseek_llm_api_key: str | None = None,
    gemini_image_api_key: str | None = None,
    gemini_image_base_url: str | None = None,
    gemini_image_generation_enabled: bool | None = None,
    lab_openai_api_key: str | None = None,
    lab_kimi_api_key: str | None = None,
    lab_doubao_vision_api_key: str | None = None,
) -> Settings:
    if default_image_provider:
        settings.default_image_provider = default_image_provider
    if openai_image_model:
        settings.openai_image_model = openai_image_model.strip()
    if doubao_image_model:
        settings.doubao_image_model = doubao_image_model.strip()
    if gemini_image_model:
        settings.gemini_image_model = gemini_image_model.strip()
    if default_image_model:
        settings.default_image_model = default_image_model.strip()
        if settings.default_image_provider == "gemini_image":
            settings.gemini_image_model = default_image_model.strip()
        elif settings.default_image_provider == "doubao_image":
            settings.doubao_image_model = default_image_model.strip()
        else:
            settings.openai_image_model = default_image_model.strip()
    if default_llm_provider:
        settings.default_llm_provider = default_llm_provider.strip()
    if openai_llm_model:
        settings.openai_llm_model = openai_llm_model.strip()
    if kimi_llm_model:
        settings.kimi_llm_model = kimi_llm_model.strip()
    if deepseek_llm_model:
        settings.deepseek_llm_model = deepseek_llm_model.strip()
    if deepseek_llm_base_url is not None:
        settings.deepseek_llm_base_url = deepseek_llm_base_url.strip().rstrip("/") or None
    if lab_llm_provider:
        settings.lab_llm_provider = lab_llm_provider.strip()
    if lab_llm_model:
        settings.lab_llm_model = lab_llm_model.strip()
    if lab_openai_base_url is not None:
        settings.lab_openai_base_url = _normalize_openai_base_url(lab_openai_base_url.strip()) if lab_openai_base_url.strip() else None
    if lab_kimi_base_url is not None:
        settings.lab_kimi_base_url = lab_kimi_base_url.strip() or None
    if lab_doubao_vision_model:
        settings.lab_doubao_vision_model = lab_doubao_vision_model.strip()
    if lab_doubao_vision_base_url is not None:
        settings.lab_doubao_vision_base_url = _normalize_openai_base_url(lab_doubao_vision_base_url.strip()) if lab_doubao_vision_base_url.strip() else None
    if default_llm_model:
        settings.default_llm_model = default_llm_model.strip()
        if settings.default_llm_provider in {"anthropic", "kimi"}:
            settings.kimi_llm_model = default_llm_model.strip()
        elif settings.default_llm_provider == "deepseek":
            settings.deepseek_llm_model = default_llm_model.strip()
        else:
            settings.openai_llm_model = default_llm_model.strip()
    if backup_llm_model:
        settings.backup_llm_model = backup_llm_model.strip()
    if settings.default_llm_provider in {"anthropic", "kimi"}:
        settings.default_llm_provider = "anthropic"
        settings.default_llm_model = settings.kimi_llm_model
        settings.backup_llm_provider = "openai"
        settings.backup_llm_model = settings.openai_llm_model
    elif settings.default_llm_provider == "deepseek":
        settings.default_llm_provider = "deepseek"
        settings.default_llm_model = settings.deepseek_llm_model
        settings.backup_llm_provider = "openai"
        settings.backup_llm_model = settings.openai_llm_model
    else:
        settings.default_llm_provider = "openai"
        settings.default_llm_model = settings.openai_llm_model
        settings.backup_llm_provider = "deepseek"
        settings.backup_llm_model = settings.deepseek_llm_model
    if settings.default_image_provider == "gemini_image" and settings.gemini_image_generation_enabled:
        settings.default_image_model = settings.gemini_image_model
    elif settings.default_image_provider == "doubao_image":
        settings.default_image_model = settings.doubao_image_model
    else:
        settings.default_image_provider = "openai_gpt_image"
        settings.default_image_model = settings.openai_image_model
    if image_work_intensity:
        settings.image_work_intensity = image_work_intensity
    if openai_api_key:
        settings.openai_api_key = openai_api_key.strip()
    if openai_base_url is not None:
        settings.openai_base_url = _normalize_openai_base_url(openai_base_url.strip()) if openai_base_url.strip() else None
    if doubao_image_api_key:
        settings.doubao_image_api_key = doubao_image_api_key.strip()
    if doubao_image_base_url is not None:
        settings.doubao_image_base_url = _normalize_openai_base_url(doubao_image_base_url.strip()) if doubao_image_base_url.strip() else None
    if anthropic_api_key:
        settings.anthropic_auth_token = anthropic_api_key.strip()
    if anthropic_base_url is not None:
        settings.anthropic_base_url = anthropic_base_url.strip() or None
    if deepseek_llm_api_key:
        settings.deepseek_llm_api_key = deepseek_llm_api_key.strip()
    if gemini_image_api_key:
        settings.gemini_image_api_key = gemini_image_api_key.strip()
    if gemini_image_base_url is not None:
        settings.gemini_image_base_url = gemini_image_base_url.strip() or None
    if gemini_image_generation_enabled is not None:
        settings.gemini_image_generation_enabled = bool(gemini_image_generation_enabled)
        if settings.gemini_image_generation_enabled and settings.default_image_provider == "gemini_image":
            settings.default_image_model = settings.gemini_image_model
    if lab_openai_api_key:
        settings.lab_openai_api_key = lab_openai_api_key.strip()
    if lab_kimi_api_key:
        settings.lab_kimi_api_key = lab_kimi_api_key.strip()
    if lab_doubao_vision_api_key:
        settings.lab_doubao_vision_api_key = lab_doubao_vision_api_key.strip()
    return settings


def persist_runtime_settings_to_env(env_path: Path | None = None) -> None:
    if not settings.persist_runtime_settings:
        return
    path = Path(env_path or settings.runtime_env_path)
    values = {
        "DEFAULT_IMAGE_PROVIDER": settings.default_image_provider,
        "DEFAULT_IMAGE_MODEL": settings.default_image_model,
        "OPENAI_IMAGE_MODEL": settings.openai_image_model,
        "DOUBAO_IMAGE_MODEL": settings.doubao_image_model,
        "DOUBAO_IMAGE_BASE_URL": settings.doubao_image_base_url or "",
        "GEMINI_IMAGE_MODEL": settings.gemini_image_model,
        "GEMINI_IMAGE_BASE_URL": settings.gemini_image_base_url or "",
        "GEMINI_IMAGE_GENERATION_ENABLED": "true" if settings.gemini_image_generation_enabled else "false",
        "DEFAULT_LLM_PROVIDER": settings.default_llm_provider,
        "DEFAULT_LLM_MODEL": settings.default_llm_model,
        "BACKUP_LLM_PROVIDER": settings.backup_llm_provider,
        "BACKUP_LLM_MODEL": settings.backup_llm_model,
        "OPENAI_LLM_MODEL": settings.openai_llm_model,
        "KIMI_LLM_MODEL": settings.kimi_llm_model,
        "DEEPSEEK_LLM_MODEL": settings.deepseek_llm_model,
        "DEEPSEEK_LLM_BASE_URL": settings.deepseek_llm_base_url or "",
        "LAB_LLM_PROVIDER": settings.lab_llm_provider,
        "LAB_LLM_MODEL": settings.lab_llm_model,
        "LAB_OPENAI_BASE_URL": settings.lab_openai_base_url or "",
        "LAB_KIMI_BASE_URL": settings.lab_kimi_base_url or "",
        "LAB_DOUBAO_VISION_MODEL": settings.lab_doubao_vision_model,
        "LAB_DOUBAO_VISION_BASE_URL": settings.lab_doubao_vision_base_url or "",
        "IMAGE_WORK_INTENSITY": settings.image_work_intensity,
        "OPENAI_BASE_URL": settings.openai_base_url or "",
        "ANTHROPIC_BASE_URL": settings.anthropic_base_url or "",
    }
    _write_env_values(path, values)


def _write_env_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    remaining = dict(values)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output.append(f"{key}={_env_value(remaining.pop(key))}")
        else:
            output.append(line)
    output.extend(f"{key}={_env_value(value)}" for key, value in remaining.items())
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def _env_value(value: str | None) -> str:
    return (value or "").replace("\r", "").replace("\n", "").strip()
