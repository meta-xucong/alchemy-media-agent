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


def _descriptor_payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "schema_version": "v3_local_runtime_descriptor_v1",
        "base_url": "http://127.0.0.1:49321",
        "runtime_id": "runtime-a",
        "visual_asset_catalog_root": "D:/alchemy/.media_storage/v3_visual_assets",
        "visual_asset_library_root": "D:/alchemy/.media_storage/v3_visual_asset_library",
    }
    payload.update(overrides)
    return payload


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
    descriptor.write_text(json.dumps(_descriptor_payload()), encoding="utf-8")
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)
    monkeypatch.setenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", str(descriptor))

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        assert request.full_url == "http://127.0.0.1:49321/api/v3/creative-agent/local-runtime"
        assert timeout == 1.0
        return _Response(_descriptor_payload(ok=True))

    monkeypatch.setattr(materialized_bridge, "urlopen", fake_urlopen)

    bridge = V3MaterializedMcpBridge()
    assert bridge.base_url == "http://127.0.0.1:49321"


def test_mcp_materialization_rejects_stale_or_cross_runtime_descriptor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    descriptor = tmp_path / "local_runtime.json"
    descriptor.write_text(json.dumps(_descriptor_payload(runtime_id="old-runtime")), encoding="utf-8")
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)
    monkeypatch.setenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", str(descriptor))

    def fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        return _Response(_descriptor_payload(ok=True, runtime_id="new-runtime"))

    monkeypatch.setattr(materialized_bridge, "urlopen", fake_urlopen)

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge()

    assert exc.value.code == "mcp_materialization_v3_runtime_mismatch"


def test_mcp_materialization_rejects_descriptor_without_runtime_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    descriptor = tmp_path / "local_runtime.json"
    payload = _descriptor_payload()
    payload.pop("runtime_id")
    descriptor.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.delenv("ALCHEMY_V3_BASE_URL", raising=False)
    monkeypatch.setenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", str(descriptor))

    with pytest.raises(MaterializedBridgeError) as exc:
        V3MaterializedMcpBridge()

    assert exc.value.code == "mcp_materialization_v3_runtime_descriptor_invalid"


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


def test_runtime_root_detects_source_checkout_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALCHEMY_APP_ROOT", raising=False)
    monkeypatch.delenv("ALCHEMY_REPO_ROOT", raising=False)
    repo = tmp_path / "repo"
    module_file = repo / "src_skeleton" / "app" / "runtime_paths.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")

    runtime_paths = importlib.import_module("app.runtime_paths")

    assert runtime_paths.discover_application_root(module_file) == repo


def test_runtime_root_detects_docker_app_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALCHEMY_APP_ROOT", raising=False)
    monkeypatch.delenv("ALCHEMY_REPO_ROOT", raising=False)
    app_root = tmp_path / "app"
    module_file = app_root / "app" / "runtime_paths.py"
    module_file.parent.mkdir(parents=True)
    (app_root / "app" / "main.py").write_text("", encoding="utf-8")
    module_file.write_text("", encoding="utf-8")

    runtime_paths = importlib.import_module("app.runtime_paths")

    assert runtime_paths.discover_application_root(module_file) == app_root


def test_v3_runtime_storage_paths_do_not_follow_process_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("V3_VISUAL_ASSET_CATALOG_ROOT", raising=False)
    monkeypatch.delenv("V3_VISUAL_ASSET_LIBRARY_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    runtime_paths = importlib.import_module("app.runtime_paths")
    app_root = runtime_paths.repository_root()

    assert runtime_paths.resolve_runtime_storage_path(
        "V3_VISUAL_ASSET_LIBRARY_ROOT",
        ".media_storage/v3_visual_asset_library",
    ) == (app_root / ".media_storage/v3_visual_asset_library")


def test_v3_runtime_storage_preserves_existing_legacy_source_tree_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "repo"
    legacy = app_root / "src_skeleton" / ".media_storage" / "v3_visual_asset_library"
    legacy.mkdir(parents=True)
    monkeypatch.setenv("ALCHEMY_APP_ROOT", str(app_root))
    monkeypatch.delenv("V3_VISUAL_ASSET_LIBRARY_ROOT", raising=False)

    runtime_paths = importlib.import_module("app.runtime_paths")

    assert runtime_paths.resolve_runtime_storage_path(
        "V3_VISUAL_ASSET_LIBRARY_ROOT",
        ".media_storage/v3_visual_asset_library",
        legacy_relative_path="src_skeleton/.media_storage/v3_visual_asset_library",
    ) == legacy


def test_relative_configured_v3_storage_paths_are_application_root_anchored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "repo"
    monkeypatch.setenv("ALCHEMY_APP_ROOT", str(app_root))
    monkeypatch.setenv("V3_VISUAL_ASSET_LIBRARY_ROOT", ".media_storage/custom_visual_library")

    runtime_paths = importlib.import_module("app.runtime_paths")

    assert runtime_paths.resolve_runtime_storage_path(
        "V3_VISUAL_ASSET_LIBRARY_ROOT",
        ".media_storage/v3_visual_asset_library",
    ) == (app_root / ".media_storage/custom_visual_library")


def test_local_runtime_descriptor_requires_explicit_local_discovery_enablement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_paths = importlib.import_module("app.runtime_paths")
    monkeypatch.delenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", raising=False)
    monkeypatch.delenv("ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED", raising=False)
    assert runtime_paths.local_runtime_descriptor_enabled() is False

    monkeypatch.setenv("ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED", "true")
    assert runtime_paths.local_runtime_descriptor_enabled() is True


def test_local_runtime_endpoint_is_disabled_until_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.delenv("ALCHEMY_V3_RUNTIME_DESCRIPTOR", raising=False)
    monkeypatch.delenv("ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED", raising=False)
    main_module = importlib.import_module("app.main")

    disabled = TestClient(main_module.app).get("/api/v3/creative-agent/local-runtime")
    assert disabled.status_code == 404
    assert disabled.json()["detail"]["code"] == "v3_local_runtime_discovery_disabled"

    monkeypatch.setenv("ALCHEMY_V3_LOCAL_RUNTIME_DISCOVERY_ENABLED", "true")
    monkeypatch.setenv("ALCHEMY_V3_BASE_URL", "http://127.0.0.1:49321")
    enabled = TestClient(main_module.app).get("/api/v3/creative-agent/local-runtime")
    payload = enabled.json()
    assert enabled.status_code == 200
    assert payload["ok"] is True
    assert payload["schema_version"] == "v3_local_runtime_descriptor_v1"
    assert payload["base_url"] == "http://127.0.0.1:49321"
    assert payload["runtime_id"]
    assert payload["visual_asset_catalog_root"]
    assert payload["visual_asset_library_root"]
