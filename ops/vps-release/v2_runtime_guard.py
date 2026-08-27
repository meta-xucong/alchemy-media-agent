#!/usr/bin/env python3
"""Verify that a V2 virtual environment belongs to the active Alchemy release.

The guard is intentionally standard-library only so systemd can run it before
the V2 application starts.  Deployment writes a manifest only after installing
the candidate requirements and passing ``pip check``; every service restart
then rechecks that manifest against the active release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_NAME = ".alchemy-v2-runtime.json"
SCHEMA_VERSION = 1


class RuntimeGuardError(RuntimeError):
    """Raised when a release and its V2 runtime no longer agree."""


@dataclass(frozen=True)
class RuntimePaths:
    release: Path
    v2_root: Path
    requirements: Path
    python: Path
    manifest: Path


def runtime_paths(release: Path) -> RuntimePaths:
    resolved_release = release.resolve()
    v2_root = resolved_release / "custom_media_agent_2_0"
    return RuntimePaths(
        release=resolved_release,
        v2_root=v2_root,
        requirements=v2_root / "requirements.txt",
        python=v2_root / ".venv" / "bin" / "python",
        manifest=v2_root / MANIFEST_NAME,
    )


def requirements_sha256(requirements: Path) -> str:
    if not requirements.is_file():
        raise RuntimeGuardError("V2 requirements file is missing.")
    return hashlib.sha256(requirements.read_bytes()).hexdigest()


def build_manifest(paths: RuntimePaths) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "requirements_sha256": requirements_sha256(paths.requirements),
        "venv_python": str(paths.python),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_manifest(paths: RuntimePaths, manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise RuntimeGuardError("V2 runtime manifest is invalid.")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeGuardError("V2 runtime manifest schema does not match this release gate.")
    if manifest.get("requirements_sha256") != requirements_sha256(paths.requirements):
        raise RuntimeGuardError("V2 runtime manifest does not match the active requirements.")
    if manifest.get("venv_python") != str(paths.python):
        raise RuntimeGuardError("V2 runtime manifest points at a different release virtual environment.")


def _run(command: list[str], *, cwd: Path) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=60)
    except OSError as exc:
        raise RuntimeGuardError(f"Unable to execute V2 runtime verification: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeGuardError("V2 runtime verification timed out.") from exc
    if result.returncode:
        message = (result.stderr or result.stdout or "verification command failed").strip().splitlines()[-1]
        raise RuntimeGuardError(f"V2 runtime verification failed: {message}")


def verify_runtime(paths: RuntimePaths) -> None:
    if not paths.v2_root.is_dir():
        raise RuntimeGuardError("V2 release directory is missing.")
    if not paths.python.is_file() or not os.access(paths.python, os.X_OK):
        raise RuntimeGuardError("V2 release virtual environment is missing.")
    if not paths.manifest.is_file():
        raise RuntimeGuardError("V2 runtime manifest is missing.")
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeGuardError("V2 runtime manifest cannot be read.") from exc
    validate_manifest(paths, manifest)
    _run([str(paths.python), "-m", "pip", "check"], cwd=paths.v2_root)
    _run([str(paths.python), "-c", "import app.main; import httpx, httpcore"], cwd=paths.v2_root)


def write_manifest(paths: RuntimePaths) -> None:
    if not paths.python.is_file():
        raise RuntimeGuardError("Cannot prepare a V2 runtime without its release virtual environment.")
    _run([str(paths.python), "-m", "pip", "check"], cwd=paths.v2_root)
    _run([str(paths.python), "-c", "import app.main; import httpx, httpcore"], cwd=paths.v2_root)
    paths.manifest.write_text(
        json.dumps(build_manifest(paths), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an Alchemy V2 release runtime.")
    parser.add_argument("--release", required=True, help="Release directory or stable release symlink.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-manifest", action="store_true", help="Verify a prepared runtime and write its manifest.")
    mode.add_argument("--verify", action="store_true", help="Verify the active runtime against its manifest.")
    args = parser.parse_args()

    try:
        paths = runtime_paths(Path(args.release))
        if args.write_manifest:
            write_manifest(paths)
            print(f"V2_RUNTIME_MANIFEST_WRITTEN={paths.manifest}")
        else:
            verify_runtime(paths)
            print(f"V2_RUNTIME_VERIFIED={paths.release}")
        return 0
    except RuntimeGuardError as exc:
        print(f"V2_RUNTIME_GUARD_FAILED={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
