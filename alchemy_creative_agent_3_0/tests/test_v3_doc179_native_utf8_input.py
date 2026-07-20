from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    PersistentVisualAssetLibraryCatalog,
)


CHINESE_INTENT = (
    "\u5efa\u7acb\u4e00\u4e2a\u53ef\u590d\u7528\u7684\u6807\u51c6\u4eba\u7269\u89c6\u89c9\u8d44\u4ea7\uff1a"
    "\u516d\u5c81\u5de6\u53f3\u7684\u4e1c\u4e9a\u5973\u7ae5\uff0c\u660e\u4eae\u5e72\u51c0\u7684\u767d\u5e95\u8eab\u4efd\u5efa\u6a21\u3002"
)


def test_fastapi_json_boundary_preserves_chinese_project_intent(monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "veyra_auth_enabled", False)
    monkeypatch.setattr(
        app_main,
        "v3_route_handlers",
        V3ProductRouteHandlers(
            service=V3ProductApiService(),
            project_store=InMemoryProjectStore(),
        ),
    )
    response = TestClient(app_main.app).post(
        "/api/v3/creative-agent/projects",
        json={"user_goal": CHINESE_INTENT, "title": "\u516d\u5c81\u5973\u7ae5\u6807\u51c6\u6a21\u578b"},
    )
    assert response.status_code == 200
    project = response.json()["project"]
    assert project["user_goal"] == CHINESE_INTENT
    assert project["title"] == "\u516d\u5c81\u5973\u7ae5\u6807\u51c6\u6a21\u578b"
    assert "\ufffd" not in response.text


def test_remote_brain_payload_keeps_chinese_as_utf8_user_intent() -> None:
    payload = json.loads(build_remote_payload(BrainRunRequest(user_input=CHINESE_INTENT)))
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert CHINESE_INTENT in serialized
    assert CHINESE_INTENT.encode("utf-8") in serialized.encode("utf-8")
    assert "?" * 4 not in serialized


def test_visual_asset_catalog_reopen_preserves_chinese_name_and_intent(tmp_path: Path) -> None:
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="\u516d\u5c81\u5973\u7ae5\u6807\u51c6\u4eba\u7269\u8d44\u4ea7",
            root_source_asset_id="root_upload",
            consent_reference="local-consent",
            preparation_intent=CHINESE_INTENT,
        ),
    )
    reopened = PersistentVisualAssetLibraryCatalog(tmp_path).get(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
    )
    assert reopened is not None
    assert reopened.display_name == "\u516d\u5c81\u5973\u7ae5\u6807\u51c6\u4eba\u7269\u8d44\u4ea7"
    assert reopened.preparation_intent == CHINESE_INTENT


def test_v3_browser_request_boundary_uses_native_unicode_json() -> None:
    source = Path("src_skeleton/app/static/app.js").read_text(encoding="utf-8")
    assert 'headers["Content-Type"] = "application/json"' in source
    assert "JSON.stringify(options.body)" in source
    assert "encodeURIComponent(options.body)" not in source
    assert "btoa(options.body)" not in source
