from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from services.alchemy_codex_local_adapter import materialized_bridge
from services.alchemy_codex_local_adapter.materialized_bridge import (
    MaterializedBridgeError,
    V3MaterializedMcpBridge,
)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_mcp_materialization_fails_closed_without_explicit_or_discovered_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)
    monkeypatch.setenv("ALCHEMY_CODEX_LOCAL_REPO_ROOT", str(tmp_path))

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge()

    assert exc.value.code == "mcp_materialization_v3_runtime_not_discovered"


def test_mcp_materialization_discovers_current_runtime_from_descriptor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    descriptor = tmp_path / "local_runtime.json"
    descriptor.write_text(
        json.dumps(
            {
                "schema_version": "v3_local_runtime_descriptor_v1",
                "base_url": "http://127.0.0.1:49321",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)
    monkeypatch.setenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", str(descriptor))

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        assert request.full_url == "http://127.0.0.1:49321/healthz"
        assert timeout == 1.0
        return _Response({"ok": True})

    monkeypatch.setattr(materialized_bridge, "urlopen", fake_urlopen)

    bridge = V3MaterializedMcpBridge()
    assert bridge.base_url == "http://127.0.0.1:49321"


def test_mcp_materialization_accepts_only_explicit_local_v3_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALCHEMY_V3_BASE_URL", "http://127.0.0.1:49322")

    bridge = V3MaterializedMcpBridge()
    assert bridge.base_url == "http://127.0.0.1:49322"

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge("https://example.com")
    assert exc.value.code == "mcp_materialization_local_only"


def test_mcp_materialization_has_no_hidden_default_port() -> None:
    source = Path("services/alchemy_codex_local_adapter/materialized_bridge.py").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8017" not in source
    assert "http://127.0.0.1:8772" not in source


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
