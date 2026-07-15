"""Start the repository-owned Doc126 MCP without relying on install-directory paths."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys


_ROOT_ENV = "ALCHEMY_CODEX_LOCAL_REPO_ROOT"
_ENV_FILE_ENV = "ALCHEMY_CODEX_LOCAL_ENV_FILE"


def _is_alchemy_root(path: Path) -> bool:
    return (
        (path / "alchemy_creative_agent_3_0" / "app").is_dir()
        and (path / "services" / "alchemy_codex_local_adapter" / "mcp_server.py").is_file()
    )


def resolve_repository_root(*, environ: dict[str, str] | None = None, cwd: Path | None = None) -> Path:
    """Use an explicit non-secret root first, then source-tree ancestry only."""

    values = environ if environ is not None else os.environ
    candidates: list[Path] = []
    configured = str(values.get(_ROOT_ENV) or "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    start = (cwd or Path.cwd()).resolve()
    candidates.extend([start, *start.parents])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if _is_alchemy_root(resolved):
            return resolved
    raise RuntimeError(
        "Alchemy Codex Local Mode could not locate its repository. "
        f"Set {_ROOT_ENV} to the checked-out Alchemy repository root, then restart Codex."
    )


def load_runtime_environment(*, environ: dict[str, str] | None = None) -> None:
    """Load an explicitly configured existing environment file before V3 imports.

    The Local Mode configuration stores only this file path, never an API key.
    This lets a checked-out main worktree use the user's already configured
    remote Central Brain without copying credentials into a plugin or Codex
    configuration.  Existing process variables keep precedence.
    """

    values = environ if environ is not None else os.environ
    configured = str(values.get(_ENV_FILE_ENV) or "").strip()
    if not configured:
        return
    try:
        env_file = Path(configured).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise RuntimeError(
            f"Configured {_ENV_FILE_ENV} is not an available local environment file."
        ) from None
    if not env_file.is_file():
        raise RuntimeError(f"Configured {_ENV_FILE_ENV} is not an available local environment file.")
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError as exc:
        raise RuntimeError("Codex Local Mode requires python-dotenv to load its configured environment file.") from exc
    load_dotenv(dotenv_path=env_file, override=False)


def configure_import_paths(root: Path) -> None:
    """Expose both repository packages required by the V3 source layout.

    ``services`` is rooted at the repository, while established V3 modules
    retain absolute imports rooted at both ``alchemy_creative_agent_3_0`` and
    the compatibility-only ``src_skeleton`` package root. The plugin only
    needs these source paths to start its planning-only MCP; it does not load
    a Web Provider, secret, or runtime image route.
    """

    for candidate in (root, root / "alchemy_creative_agent_3_0", root / "src_skeleton"):
        value = str(candidate)
        if value not in sys.path:
            sys.path.insert(0, value)


def main() -> int:
    load_runtime_environment()
    root = resolve_repository_root()
    configure_import_paths(root)
    runpy.run_module("services.alchemy_codex_local_adapter.mcp_server", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
