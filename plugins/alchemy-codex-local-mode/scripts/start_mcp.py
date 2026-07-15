"""Start the repository-owned Doc126 MCP without relying on install-directory paths."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys


_ROOT_ENV = "ALCHEMY_CODEX_LOCAL_REPO_ROOT"


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
    root = resolve_repository_root()
    configure_import_paths(root)
    runpy.run_module("services.alchemy_codex_local_adapter.mcp_server", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
