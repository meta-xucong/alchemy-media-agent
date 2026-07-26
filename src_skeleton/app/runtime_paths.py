from __future__ import annotations

import os
from pathlib import Path


LOCAL_RUNTIME_DESCRIPTOR_SCHEMA_VERSION = "v3_local_runtime_descriptor_v1"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _configured_application_root() -> Path | None:
    for env_name in ("ALCHEMY_APP_ROOT", "ALCHEMY_REPO_ROOT"):
        raw = str(os.getenv(env_name) or "").strip()
        if raw:
            configured = Path(os.path.expandvars(raw)).expanduser()
            if not configured.is_absolute():
                raise RuntimeError(f"{env_name} must be an absolute path.")
            return configured.resolve()
    return None


def _path_or_parent(path: Path) -> Path:
    return path if path.is_dir() else path.parent


def discover_application_root(start: Path | None = None) -> Path:
    """Return the app/repository root for source checkouts and Docker images.

    Source checkouts load this module from ``<repo>/src_skeleton/app``.
    Docker images load it from ``/app/app`` while ``WORKDIR`` is ``/app``.
    The previous fixed ``parents[2]`` rule was correct for source checkouts
    but resolved Docker to ``/``; this discovery keeps both layouts anchored
    at the directory that owns ``.media_storage``.
    """

    configured = _configured_application_root()
    if configured is not None:
        return configured

    current = _path_or_parent((start or Path(__file__)).resolve())
    for candidate in (current, *current.parents):
        if (candidate / "src_skeleton" / "app").is_dir():
            return candidate
        if (candidate / "app").is_dir() and (candidate / "app" / "main.py").is_file():
            return candidate

    raise RuntimeError(
        "Alchemy application root could not be discovered. Set ALCHEMY_APP_ROOT to an absolute app root path."
    )


def repository_root() -> Path:
    """Return the runtime application root independent of process cwd."""

    return discover_application_root()


def _resolve_relative_to_application_root(raw_path: str) -> Path:
    configured = Path(os.path.expandvars(raw_path)).expanduser()
    return configured if configured.is_absolute() else repository_root() / configured


def resolve_runtime_storage_path(
    env_name: str,
    default_relative_path: str,
    *,
    legacy_relative_path: str | None = None,
) -> Path:
    """Resolve V3 runtime storage roots without depending on cwd.

    Explicit absolute paths are preserved. Explicit relative V3 paths are
    anchored to the discovered app root so source and Docker launches agree.
    For local compatibility, an existing legacy source-tree directory may be
    reused when the new app-root default does not exist yet.
    """

    raw = os.getenv(env_name)
    if raw:
        return _resolve_relative_to_application_root(raw)

    default_path = repository_root() / default_relative_path
    if legacy_relative_path:
        legacy_path = repository_root() / legacy_relative_path
        if legacy_path.exists() and not default_path.exists():
            return legacy_path
    return default_path


def local_runtime_descriptor_enabled() -> bool:
    """Whether the app should publish the local MCP discovery descriptor."""

    return bool(str(os.getenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR") or "").strip()) or _truthy(
        os.getenv("ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED")
    )


def local_runtime_descriptor_path() -> Path:
    """Path used by the running local V3 service to advertise its base URL."""

    raw = str(os.getenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR") or "").strip()
    if raw:
        return _resolve_relative_to_application_root(raw)
    return repository_root() / ".media_storage/v3_runtime/local_runtime.json"
