"""Start the repository-owned Doc126 MCP without relying on install-directory paths."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys


_ROOT_ENV = "ALCHEMY_CODEX_LOCAL_REPO_ROOT"
_ENV_FILE_ENV = "ALCHEMY_CODEX_LOCAL_ENV_FILE"
_LOCAL_ENV_PATH_FILE = ".codex-local-env-path"


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


def _resolve_runtime_environment_file(
    *,
    repository_root: Path,
    environ: dict[str, str],
) -> Path | None:
    """Resolve the one existing runtime environment file Local Mode may use.

    The explicit environment-file variable remains authoritative.  When it is
    absent, only the selected checkout's own ``.env`` (or its legacy
    ``src_skeleton/.env`` location) is considered.  A tiny ignored pointer file
    is supported for a worktree whose secrets intentionally live in a separate
    user-owned checkout; it contains a path, never credentials.  We do not
    scan sibling directories or search Codex/application state.
    """

    configured = str(environ.get(_ENV_FILE_ENV) or "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    else:
        pointer = repository_root / _LOCAL_ENV_PATH_FILE
        if pointer.is_file():
            try:
                pointer_value = pointer.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RuntimeError(f"Could not read {pointer}: {exc}") from exc
            if pointer_value:
                candidates.append(Path(pointer_value).expanduser())
        candidates.extend((repository_root / ".env", repository_root / "src_skeleton" / ".env"))

    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved.is_file():
            return resolved

    if configured:
        raise RuntimeError(
            f"Configured {_ENV_FILE_ENV} is not an available local environment file."
        )
    return None


def load_runtime_environment(
    *,
    repository_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> None:
    """Load the selected checkout's existing environment before V3 imports.

    The Local Mode configuration stores only this file path, never an API key.
    This lets a checked-out main worktree use the user's already configured
    remote Central Brain without copying credentials into a plugin or Codex
    configuration.  Existing process variables keep precedence.  If the
    checkout has no environment file, the MCP remains safely blocked and the
    caller can set ``ALCHEMY_CODEX_LOCAL_ENV_FILE`` explicitly.
    """

    values = environ if environ is not None else os.environ
    root = repository_root or resolve_repository_root(environ=values)
    env_file = _resolve_runtime_environment_file(repository_root=root, environ=values)
    if env_file is None:
        return
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
        # An inherited PYTHONPATH can already contain src_skeleton.  Merely
        # skipping that existing entry would leave alchemy_creative_agent_3_0
        # ahead of it, making the historical absolute ``app.providers``
        # compatibility import resolve to the wrong package.  Normalize the
        # exact source order every time without reading any provider config:
        # src_skeleton, V3 package root, repository root.
        while value in sys.path:
            sys.path.remove(value)
        sys.path.insert(0, value)


def main() -> int:
    root = resolve_repository_root()
    load_runtime_environment(repository_root=root)
    configure_import_paths(root)
    runpy.run_module("services.alchemy_codex_local_adapter.mcp_server", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
