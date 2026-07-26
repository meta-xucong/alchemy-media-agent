from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from services.alchemy_codex_local_adapter.materialized_bridge import (
    MaterializedBridgeError,
    V3MaterializedMcpBridge,
)


def test_mcp_materialization_requires_explicit_v3_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge()

    assert exc.value.code == "mcp_materialization_v3_base_url_required"


def test_mcp_materialization_accepts_only_explicit_local_v3_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALCHEMY_V3_BASE_URL", "http://127.0.0.1:8772")

    bridge = V3MaterializedMcpBridge()
    assert bridge.base_url == "http://127.0.0.1:8772"

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge("https://example.com")
    assert exc.value.code == "mcp_materialization_local_only"


def test_repo_storage_paths_do_not_follow_process_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MEDIA_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("V3_VISUAL_ASSET_CATALOG_ROOT", raising=False)
    monkeypatch.delenv("V3_VISUAL_ASSET_LIBRARY_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    runtime_paths = importlib.import_module("app.runtime_paths")
    repo_root = runtime_paths.repository_root()

    assert runtime_paths.resolve_repo_storage_path("MEDIA_STORAGE_ROOT", ".media_storage") == (
        repo_root / ".media_storage"
    )
    assert runtime_paths.resolve_repo_storage_path(
        "V3_VISUAL_ASSET_LIBRARY_ROOT",
        ".media_storage/v3_visual_asset_library",
    ) == (repo_root / ".media_storage/v3_visual_asset_library")


def test_relative_configured_storage_paths_are_repo_anchored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("V3_VISUAL_ASSET_LIBRARY_ROOT", ".media_storage/custom_visual_library")
    monkeypatch.chdir(tmp_path)

    runtime_paths = importlib.import_module("app.runtime_paths")

    assert runtime_paths.resolve_repo_storage_path(
        "V3_VISUAL_ASSET_LIBRARY_ROOT",
        ".media_storage/v3_visual_asset_library",
    ) == (runtime_paths.repository_root() / ".media_storage/custom_visual_library")
