from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _bool_env(name: str, default: bool) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


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


class SidecarSettings(BaseModel):
    service_name: str = "alchemy-v3-identity-sidecar"
    contract_version: str = "doc98-v1"
    backend: str = Field(default_factory=lambda: os.getenv("IDENTITY_SIDECAR_BACKEND", "comfyui").strip().lower())
    api_key: str | None = Field(default_factory=lambda: os.getenv("IDENTITY_SIDECAR_API_KEY") or None)
    provider_family: str = Field(default_factory=lambda: os.getenv("IDENTITY_PROVIDER_FAMILY", "custom").strip().lower())
    model_name: str = Field(default_factory=lambda: os.getenv("IDENTITY_MODEL_NAME", "identity-native").strip())
    model_license_confirmed: bool = Field(
        default_factory=lambda: _bool_env("IDENTITY_MODEL_LICENSE_CONFIRMED", False)
    )
    identity_conditioning_confirmed: bool = Field(
        default_factory=lambda: _bool_env("IDENTITY_CONDITIONING_CONFIRMED", False)
    )
    identity_local_repair_confirmed: bool = Field(
        default_factory=lambda: _bool_env("IDENTITY_LOCAL_REPAIR_CONFIRMED", False)
    )
    workflow_path: Path = Field(
        default_factory=lambda: Path(os.getenv("IDENTITY_WORKFLOW_PATH", "/workflows/identity.json"))
    )
    repair_workflow_path: Path | None = Field(
        default_factory=lambda: Path(value)
        if (value := os.getenv("IDENTITY_REPAIR_WORKFLOW_PATH", "").strip())
        else None
    )
    comfyui_base_url: str = Field(
        default_factory=lambda: os.getenv("COMFYUI_BASE_URL", "http://comfyui:8188").strip().rstrip("/")
    )
    comfyui_api_key: str | None = Field(default_factory=lambda: os.getenv("COMFYUI_API_KEY") or None)
    comfyui_output_node_ids: list[str] = Field(
        default_factory=lambda: [
            item.strip()
            for item in os.getenv("COMFYUI_OUTPUT_NODE_IDS", "").split(",")
            if item.strip()
        ]
    )
    request_timeout_seconds: float = Field(
        default_factory=lambda: _float_env("IDENTITY_REQUEST_TIMEOUT_SECONDS", 420.0)
    )
    health_timeout_seconds: float = Field(
        default_factory=lambda: _float_env("IDENTITY_HEALTH_TIMEOUT_SECONDS", 10.0)
    )
    capability_ttl_seconds: float = Field(
        default_factory=lambda: max(0.0, _float_env("IDENTITY_CAPABILITY_TTL_SECONDS", 15.0))
    )
    poll_interval_seconds: float = Field(
        default_factory=lambda: _float_env("IDENTITY_POLL_INTERVAL_SECONDS", 1.0)
    )
    max_concurrency: int = Field(default_factory=lambda: max(1, _int_env("IDENTITY_MAX_CONCURRENCY", 1)))
    max_references: int = Field(default_factory=lambda: max(1, min(8, _int_env("IDENTITY_MAX_REFERENCES", 3))))
    max_file_bytes: int = Field(
        default_factory=lambda: max(64 * 1024, _int_env("IDENTITY_MAX_FILE_BYTES", 2_000_000))
    )
    max_total_upload_bytes: int = Field(
        default_factory=lambda: max(256 * 1024, _int_env("IDENTITY_MAX_TOTAL_UPLOAD_BYTES", 8_000_000))
    )
    max_prompt_chars: int = Field(
        default_factory=lambda: max(1000, _int_env("IDENTITY_MAX_PROMPT_CHARS", 18_000))
    )
    max_output_bytes: int = Field(
        default_factory=lambda: max(1_000_000, _int_env("IDENTITY_MAX_OUTPUT_BYTES", 32_000_000))
    )
    idempotency_ttl_seconds: float = Field(
        default_factory=lambda: max(0.0, _float_env("IDENTITY_IDEMPOTENCY_TTL_SECONDS", 180.0))
    )
    idempotency_max_entries: int = Field(
        default_factory=lambda: max(1, _int_env("IDENTITY_IDEMPOTENCY_MAX_ENTRIES", 4))
    )


settings = SidecarSettings()
