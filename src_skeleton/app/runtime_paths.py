from __future__ import annotations

import os
from pathlib import Path


def repository_root() -> Path:
    """Return the checkout root independent of the process working directory."""

    return Path(__file__).resolve().parents[2]


def resolve_repo_storage_path(env_name: str, default_relative_path: str) -> Path:
    """Resolve local storage roots without depending on cwd.

    Desktop validation can start the FastAPI app as either
    ``src_skeleton.app.main:app`` from the repository root or ``app.main:app``
    from ``src_skeleton``. Relative defaults such as ``.media_storage`` must
    still point at the same repository-owned catalog; otherwise two local
    ports can appear to contain different Visual Asset libraries.
    """

    raw = os.getenv(env_name)
    if raw:
        configured = Path(os.path.expandvars(raw)).expanduser()
        return configured if configured.is_absolute() else repository_root() / configured
    return repository_root() / default_relative_path


def local_runtime_descriptor_path() -> Path:
    """Path used by the running local V3 service to advertise its base URL."""

    return resolve_repo_storage_path(
        "ALCHEMY_V3_RUNTIME_DESCRIPTOR",
        ".media_storage/v3_runtime/local_runtime.json",
    )
