from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class BridgeSettings:
    mode: str = "disabled"
    base_url: str = ""
    token: str = field(default="", repr=False)
    workspace: str = ""
    storage: Path = Path(".render_bridge_preview")
    allow_local_preview: bool = False
    native_enabled: bool = False
    profiles: tuple[str, ...] = ("fake-image",)
    native_profiles: tuple[str, ...] = ("fake-image",)
    auto_fallback_enabled: bool = False
    queue_wait_seconds: int = 30
    poll_seconds: float = 2.0
    batch_size: int = 2
    max_jobs: int = 100
    max_storage_bytes: int = 128 * 1024 * 1024
    config_error: str | None = None

    @classmethod
    def from_env(cls, *, preserve_disabled: bool = False) -> "BridgeSettings":
        mode = os.getenv("ALCHEMY_RENDER_BRIDGE_MODE", "disabled").strip().lower()
        # Legacy disabled mounting reads no other settings. The administrator
        # control plane may inspect environment defaults without constructing
        # directories, clients or workers. Invalid settings never activate it.
        if mode == "disabled" and not preserve_disabled:
            return cls()
        if mode not in {"disabled", "enabled", "draining"}:
            return cls(mode="disabled", config_error="invalid_mode")
        base = os.getenv("ALCHEMY_RENDER_BRIDGE_URL", "").rstrip("/")
        token = os.getenv("ALCHEMY_RENDER_BRIDGE_TOKEN", "")
        workspace = os.getenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "")
        error = None
        try:
            parsed = urlsplit(base)
            loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            local_http = (loopback and parsed.scheme == "http" and
                          os.getenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK") == "true")
            if (not parsed.hostname or not (parsed.scheme == "https" or local_http)
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path not in {"", "/"}):
                error = "invalid_bridge_url"
        except ValueError:
            error = "invalid_bridge_url"
        if not token or not workspace:
            error = "bridge_configuration_missing"
        profiles = tuple(v.strip() for v in os.getenv(
            "ALCHEMY_RENDER_BRIDGE_PROFILES", "fake-image").split(",") if v.strip())
        if not profiles or any(p not in {"fake-image", "codex-image", "midjourney-manual"} for p in profiles):
            error = "invalid_profiles"
        native_profiles = tuple(v.strip() for v in os.getenv(
            "ALCHEMY_RENDER_BRIDGE_NATIVE_PROFILES", "fake-image").split(",") if v.strip())
        native_enabled = os.getenv("ALCHEMY_RENDER_BRIDGE_NATIVE_ENABLED") == "true"
        if (not native_profiles or len(set(native_profiles)) != len(native_profiles)
                or any(p not in {"fake-image", "codex-image", "midjourney-manual"} for p in native_profiles)
                or (native_enabled and any(p not in profiles for p in native_profiles))):
            error = "invalid_native_profiles"
        try:
            queue_wait = int(os.getenv("ALCHEMY_RENDER_BRIDGE_QUEUE_WAIT_SECONDS", "30"))
            if not 1 <= queue_wait <= 3600:
                raise ValueError()
        except ValueError:
            queue_wait, error = 30, "invalid_queue_wait_seconds"
        return cls(mode=mode, base_url=base, token=token, workspace=workspace,
                   storage=Path(os.getenv("ALCHEMY_RENDER_BRIDGE_STORAGE", ".render_bridge_preview")),
                   allow_local_preview=os.getenv("ALCHEMY_RENDER_BRIDGE_LOCAL_PREVIEW") == "true",
                   native_enabled=native_enabled,
                   auto_fallback_enabled=os.getenv("ALCHEMY_RENDER_BRIDGE_AUTO_FALLBACK_ENABLED") == "true",
                   queue_wait_seconds=queue_wait,
                   profiles=profiles, native_profiles=native_profiles, config_error=error)
