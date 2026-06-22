from __future__ import annotations

import base64
import asyncio
import json
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import qrcode
import pytest

from app.config import settings
import app.providers.images.doubao_image as doubao_image_provider
import app.providers.images.openai_gpt_image_2 as openai_image_provider
import app.providers.images.response_payloads as response_payloads
from app.providers.images.base import V2ImageProviderNotConfiguredError, V2ImageProviderRequest
from app.providers.images.registry import get_v2_image_provider
import app.main as main_module
from app.main import app
import app.agents.runtime as runtime_module
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import CreateImageJobRequest, CreativeRun, ImageJob, ImagePromptPlan, PromptCase, PromptCaseSummary, ProviderInputImage
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_intelligence import build_case_profile
import app.services.claude_orchestrator as claude_orchestrator_service
import app.services.generation as generation_service
import app.services.qr_preservation as qr_preservation_service
from app.services.prompting import compose_prompt_plan
import app.services.queue_worker as queue_worker_service
import app.services.task_queue as task_queue_service
import app.services.veyra_auth as veyra_auth_module
from app.services.veyra_auth import issue_session_token
from app.services.veyra_billing_settings import reset_billing_settings_cache
from app.services.visual_signals import build_case_visual_signals


def fresh_client() -> TestClient:
    test_dir = Path(tempfile.mkdtemp(prefix="alchemy_v2_test_"))
    repository.reset()
    claude_orchestrator_service.reset_orchestrator_observability()
    object.__setattr__(settings, "data_dir", test_dir)
    object.__setattr__(settings, "storage_dir", test_dir / "storage")
    object.__setattr__(settings, "default_agent_model", "gpt-4.1-mini")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "openai_api_key", "sk-test-openai")
    object.__setattr__(settings, "doubao_image_api_key", "sk-test-doubao")
    object.__setattr__(settings, "doubao_image_base_url", "https://aiself.example.test/v1")
    object.__setattr__(settings, "doubao_image_model", "doubao-seedream-4-0-250828")
    object.__setattr__(settings, "gemini_api_key", "sk-test-gemini")
    object.__setattr__(settings, "gemini_image_generation_enabled", False)
    object.__setattr__(settings, "persist_image_history", False)
    object.__setattr__(settings, "sync_github_on_startup", False)
    object.__setattr__(settings, "claude_orchestrator_enabled", False)
    object.__setattr__(settings, "claude_orchestrator_model", None)
    object.__setattr__(settings, "claude_orchestrator_multimodal_model", "doubao-seed-2-0-lite-260428")
    object.__setattr__(settings, "claude_orchestrator_fallback_model", None)
    object.__setattr__(settings, "claude_orchestrator_timeout_seconds", 240.0)
    object.__setattr__(settings, "claude_orchestrator_max_output_tokens", 32000)
    object.__setattr__(settings, "claude_orchestrator_effort", "low")
    object.__setattr__(settings, "claude_orchestrator_tools", "none")
    object.__setattr__(settings, "claude_orchestrator_fallback_base_url", None)
    object.__setattr__(settings, "claude_orchestrator_fallback_auth_token", None)
    object.__setattr__(settings, "claude_orchestrator_fallback_max_models_per_stage", 3)
    object.__setattr__(settings, "claude_orchestrator_fallback_stage_timeout_seconds", 25.0)
    object.__setattr__(
        settings,
        "claude_orchestrator_fallback_models",
        (
            "deepseek-v4-pro-260425",
            "deepseek-v4-flash-260425",
            "deepseek-v3-2-251201",
            "doubao-seed-2-0-lite-260428",
            "doubao-seed-2-0-lite-260215",
            "doubao-seed-1-6-lite-251015",
            "glm-4-7-251222",
            "doubao-lite-128k-240428",
            "doubao-lite-32k-240428",
            "doubao-lite-4k-240328",
        ),
    )
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", False)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 2)
    object.__setattr__(settings, "claude_checkpoint_stage_timeout_seconds", 180.0)
    object.__setattr__(settings, "claude_checkpoint_soft_stage_timeout_seconds", 120.0)
    object.__setattr__(settings, "claude_checkpoint_cli_schema_enabled", False)
    object.__setattr__(settings, "claude_final_prompt_max_chars", 1400)
    object.__setattr__(settings, "claude_negative_prompt_max_chars", 320)
    object.__setattr__(settings, "claude_rationale_max_chars", 180)
    object.__setattr__(settings, "claude_orchestrator_cache_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_max_attempts", 2)
    object.__setattr__(settings, "claude_orchestrator_retry_delay_seconds", 0.0)
    object.__setattr__(settings, "task_queue_db_path", test_dir / "task_queue.sqlite3")
    object.__setattr__(settings, "task_queue_inline_worker_enabled", False)
    object.__setattr__(settings, "task_queue_poll_interval_seconds", 0.01)
    object.__setattr__(settings, "task_queue_max_attempts", 2)
    object.__setattr__(settings, "output_review_agent_enabled", False)
    object.__setattr__(settings, "output_review_agent_model", None)
    object.__setattr__(settings, "veyra_auth_enabled", False)
    object.__setattr__(settings, "veyra_internal_token", None)
    object.__setattr__(settings, "veyra_session_secret", None)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_generation_charge_amount", 0.0)
    object.__setattr__(settings, "media_acceleration_enabled", False)
    object.__setattr__(settings, "media_acceleration_base_url", "")
    object.__setattr__(settings, "media_acceleration_signing_secret", None)
    object.__setattr__(settings, "media_acceleration_url_ttl_seconds", 300)
    object.__setattr__(settings, "media_acceleration_verify_remote", True)
    object.__setattr__(settings, "media_acceleration_verify_timeout_seconds", 1.2)
    object.__setattr__(settings, "case_intelligence_provider", "rules")
    object.__setattr__(settings, "case_intelligence_model", None)
    object.__setattr__(settings, "case_index_path", test_dir / "case_index.json")
    object.__setattr__(settings, "image_history_path", test_dir / "image_history.jsonl")
    object.__setattr__(
        settings,
        "history_thumbnail_dir",
        test_dir / "history_thumbnails",
    )
    object.__setattr__(
        settings,
        "claude_orchestrator_workspace_dir",
        test_dir / "claude_orchestrator",
    )
    object.__setattr__(settings, "claude_orchestrator_cache_path", test_dir / "claude_orchestrator_cache.json")
    task_queue_service.clear_task_queue()
    bootstrap_v2_repository(seed_cases=True, use_persisted_index=False)
    return TestClient(app)


def make_prompt_case(
    case_id: str,
    title: str,
    category: str,
    raw_prompt: str,
    *,
    summary: str = "",
    style_tags: list[str] | None = None,
    use_case_tags: list[str] | None = None,
    quality_score: float = 0.86,
) -> PromptCase:
    return PromptCase(
        case_id=case_id,
        provider_id="test_provider",
        index_version="test-index",
        source_url=f"https://example.test/{case_id}",
        title=title,
        category=category,
        summary=summary or title,
        raw_prompt=raw_prompt,
        prompt_atoms={
            "subject": title,
            "scene": raw_prompt,
            "composition": raw_prompt,
            "mood": raw_prompt,
        },
        visual_features={"keywords": raw_prompt},
        style_tags=style_tags or [],
        use_case_tags=use_case_tags or [],
        risk_tags=[],
        quality_score=quality_score,
    )


def upload_test_asset(
    client: TestClient,
    *,
    role: str = "subject_reference",
    color=(32, 96, 180),
    intended_use: str | None = None,
) -> str:
    image_bytes = BytesIO()
    Image.new("RGB", (320, 240), color).save(image_bytes, format="PNG")
    return upload_image_asset(
        client,
        image_bytes.getvalue(),
        role=role,
        filename=f"{role}.png",
        intended_use=intended_use,
    )


def upload_image_asset(
    client: TestClient,
    image_content: bytes,
    *,
    role: str,
    filename: str = "uploaded.png",
    intended_use: str | None = None,
) -> str:
    upload_payload = {
        "filename": filename,
        "mime_type": "image/png",
        "size_bytes": len(image_content),
        "role": role,
        "constraint_strength": "required",
    }
    if intended_use:
        upload_payload["intended_use"] = intended_use
    upload = client.post(
        "/api/v2/uploads",
        json=upload_payload,
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    content = client.put(
        f"/api/v2/uploads/{asset_id}/content",
        json={
            "content_base64": base64.b64encode(image_content).decode("ascii"),
            "mime_type": "image/png",
        },
    )
    assert content.status_code == 200
    completed = client.post(f"/api/v2/uploads/{asset_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "ready"
    return asset_id


def issue_test_veyra_session_token(user_id: int) -> str:
    import hashlib
    import hmac
    import time

    secret = str(settings.veyra_session_secret or settings.veyra_internal_token).encode("utf-8")
    now = int(time.time())
    payload = {"user_id": int(user_id), "iat": now, "exp": now + 3600}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).decode("ascii").rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
    return raw + "." + signature


def make_qr_reference_image(payload: str) -> bytes:
    qr = qrcode.QRCode(border=4, box_size=8)
    qr.add_data(payload)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    canvas = Image.new("RGB", (720, 480), (248, 244, 235))
    canvas.paste(qr_image.resize((176, 176), Image.Resampling.NEAREST), (492, 252))
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def decode_qr_from_image(path: Path) -> str:
    import cv2
    import numpy as np

    with Image.open(path) as image:
        array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    decoded, _points, _ = cv2.QRCodeDetector().detectAndDecode(array)
    return decoded


def test_health_reports_v2_isolation() -> None:
    client = fresh_client()
    response = client.get("/api/v2/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "custom-media-agent-v2"
    assert body["isolation"]["api_prefix"] == "/api/v2"
    assert body["isolation"]["db_namespace"] == "alchemy_v2"
    assert body["isolation"]["storage_prefix"] == "v2/"


def test_v2_creative_run_rejects_empty_request() -> None:
    client = fresh_client()

    response = client.post("/api/v2/creative/runs/async", json={"user_prompt": "   ", "output": {"count": 1}})

    assert response.status_code == 422
    assert "提示词" in response.text


def test_v2_creative_run_allows_template_without_prompt() -> None:
    client = fresh_client()
    template_id = client.get("/api/v2/templates", params={"limit": 1}).json()["templates"][0]["case_id"]

    response = client.post(
        "/api/v2/creative/runs/async",
        json={"user_prompt": "   ", "template_case_id": template_id, "output": {"count": 1}},
    )

    assert response.status_code == 202
    assert response.json()["run_id"].startswith("run_")


def test_provider_sync_publishes_seed_cases() -> None:
    client = fresh_client()
    providers = client.get("/api/v2/resource-providers").json()["providers"]
    assert providers[0]["provider_id"] == "github_evolinkai_gpt_image_cases"

    response = client.post("/api/v2/resource-providers/github_evolinkai_gpt_image_cases/sync")
    assert response.status_code == 202
    sync = response.json()
    assert sync["status"] == "completed"
    assert sync["stats"]["cases_published"] >= 6
    assert sync["stats"]["case_index_path"].endswith("case_index.json")

    lookup = client.get(
        f"/api/v2/resource-providers/github_evolinkai_gpt_image_cases/sync-runs/{sync['sync_run_id']}"
    )
    assert lookup.status_code == 200
    assert lookup.json()["sync_run_id"] == sync["sync_run_id"]


def test_case_search_and_template_detail() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={
            "query_text": "premium skincare product advertising studio lighting",
            "use_case_filters": ["ecommerce"],
            "style_filters": ["premium"],
            "limit": 3,
        },
    )
    assert response.status_code == 200
    results = response.json()
    assert results["cases"]
    assert results["index_version"]
    case_id = results["cases"][0]["case_id"]

    detail = client.get(f"/api/v2/prompt-cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["license_policy"]["raw_image_final_use_allowed"] is False

    templates = client.get("/api/v2/templates", params={"limit": 2})
    assert templates.status_code == 200
    assert len(templates.json()["templates"]) == 2


def test_template_index_and_page_endpoints_support_lightweight_browsing() -> None:
    client = fresh_client()

    index = client.get("/api/v2/templates/index")
    assert index.status_code == 200
    index_payload = index.json()
    assert index_payload["total"] > 2
    assert index_payload["index_version"]
    assert index_payload["facets"]

    first_page = client.get("/api/v2/templates/page", params={"limit": 2})
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 2
    assert first_payload["total"] == index_payload["total"]
    assert first_payload["cursor"] == "0"
    assert first_payload["next_cursor"] == "2"
    assert first_payload["has_more"] is True

    second_page = client.get("/api/v2/templates/page", params={"limit": 2, "cursor": first_payload["next_cursor"]})
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["cursor"] == "2"
    assert {item["case_id"] for item in first_payload["items"]}.isdisjoint(
        {item["case_id"] for item in second_payload["items"]}
    )


def test_template_page_endpoint_filters_by_facet() -> None:
    client = fresh_client()
    facet = client.get("/api/v2/templates/index").json()["facets"][0]["value"]

    response = client.get("/api/v2/templates/page", params={"limit": 10, "facet": facet})

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    for item in items:
        assert facet in {item["category"], *item["style_tags"], *item["use_case_tags"]}


def test_template_index_and_page_support_private_etag_cache() -> None:
    client = fresh_client()

    index = client.get("/api/v2/templates/index")
    assert index.status_code == 200
    assert index.headers["etag"].startswith('"v2-templates-')
    assert "private" in index.headers["cache-control"]
    assert "authorization" in index.headers["vary"].lower()

    cached_index = client.get("/api/v2/templates/index", headers={"If-None-Match": index.headers["etag"]})
    assert cached_index.status_code == 304
    assert cached_index.content == b""
    assert cached_index.headers["etag"] == index.headers["etag"]

    first_page = client.get("/api/v2/templates/page", params={"limit": 2})
    second_page = client.get("/api/v2/templates/page", params={"limit": 2, "cursor": "2"})
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.headers["etag"].startswith('"v2-templates-')
    assert first_page.headers["etag"] != second_page.headers["etag"]

    cached_page = client.get("/api/v2/templates/page", params={"limit": 2}, headers={"If-None-Match": first_page.headers["etag"]})
    assert cached_page.status_code == 304
    assert cached_page.content == b""


def test_template_index_and_page_use_in_process_response_cache(monkeypatch) -> None:
    client = fresh_client()
    import app.main as main_module

    main_module._template_response_cache.clear()
    original_index = main_module.case_intelligence.list_template_index
    original_page = main_module.case_intelligence.list_templates_page
    calls = {"index": 0, "page": 0}

    def counted_index():
        calls["index"] += 1
        return original_index()

    def counted_page(**kwargs):
        calls["page"] += 1
        return original_page(**kwargs)

    monkeypatch.setattr(main_module.case_intelligence, "list_template_index", counted_index)
    monkeypatch.setattr(main_module.case_intelligence, "list_templates_page", counted_page)

    first_index = client.get("/api/v2/templates/index")
    second_index = client.get("/api/v2/templates/index")
    assert first_index.status_code == 200
    assert second_index.status_code == 200
    assert calls["index"] == 1

    first_page = client.get("/api/v2/templates/page", params={"limit": 2})
    second_page = client.get("/api/v2/templates/page", params={"limit": 2})
    other_page = client.get("/api/v2/templates/page", params={"limit": 3})
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert other_page.status_code == 200
    assert calls["page"] == 2

    cached_304 = client.get("/api/v2/templates/page", params={"limit": 2}, headers={"If-None-Match": first_page.headers["etag"]})
    assert cached_304.status_code == 304
    assert calls["page"] == 2


def test_case_asset_endpoint_serves_images_from_local_snapshot(tmp_path) -> None:
    client = fresh_client()
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    object.__setattr__(settings, "remote_snapshot_dir", snapshot_dir)
    snapshot_path = snapshot_dir / "github-test123.zip"
    with zipfile.ZipFile(snapshot_path, "w") as archive:
        archive.writestr("repo-main/images/sample_case/output.jpg", b"fake-jpg")

    provider = repository.get_provider("github_evolinkai_gpt_image_cases")
    assert provider is not None
    repository.upsert_provider(provider.model_copy(update={"active_index_version": "github_evolinkai_gpt_image_cases:github-test123"}))

    response = client.get("/api/v2/case-assets/images/sample_case/output.jpg")

    assert response.status_code == 200
    assert response.content == b"fake-jpg"
    assert response.headers["content-type"].startswith("image/jpeg")


def test_case_asset_endpoint_reuses_archive_member_index(tmp_path, monkeypatch) -> None:
    client = fresh_client()
    import app.services.case_assets as case_assets

    case_assets._archive_member_index_cache.clear()
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    object.__setattr__(settings, "remote_snapshot_dir", snapshot_dir)
    snapshot_path = snapshot_dir / "github-testindexcache.zip"
    with zipfile.ZipFile(snapshot_path, "w") as archive:
        archive.writestr("repo-main/images/sample_case/output-a.jpg", b"fake-a")
        archive.writestr("repo-main/images/sample_case/output-b.jpg", b"fake-b")

    provider = repository.get_provider("github_evolinkai_gpt_image_cases")
    assert provider is not None
    repository.upsert_provider(
        provider.model_copy(update={"active_index_version": "github_evolinkai_gpt_image_cases:github-testindexcache"})
    )

    calls = {"namelist": 0}
    original_namelist = case_assets.zipfile.ZipFile.namelist

    def counted_namelist(self):
        calls["namelist"] += 1
        return original_namelist(self)

    monkeypatch.setattr(case_assets.zipfile.ZipFile, "namelist", counted_namelist)

    first = client.get("/api/v2/case-assets/images/sample_case/output-a.jpg")
    second = client.get("/api/v2/case-assets/images/sample_case/output-b.jpg")

    assert first.status_code == 200
    assert first.content == b"fake-a"
    assert second.status_code == 200
    assert second.content == b"fake-b"
    assert calls["namelist"] == 1


def test_case_thumbnail_endpoint_generates_cached_webp_from_snapshot(tmp_path) -> None:
    client = fresh_client()
    snapshot_dir = tmp_path / "snapshots"
    thumbnail_dir = tmp_path / "thumbs"
    snapshot_dir.mkdir()
    object.__setattr__(settings, "remote_snapshot_dir", snapshot_dir)
    object.__setattr__(settings, "case_thumbnail_dir", thumbnail_dir)
    source_image = BytesIO()
    Image.new("RGB", (1200, 1800), (180, 120, 40)).save(source_image, format="JPEG")
    snapshot_path = snapshot_dir / "github-testthumb.zip"
    with zipfile.ZipFile(snapshot_path, "w") as archive:
        archive.writestr("repo-main/images/sample_case/output.jpg", source_image.getvalue())

    provider = repository.get_provider("github_evolinkai_gpt_image_cases")
    assert provider is not None
    repository.upsert_provider(provider.model_copy(update={"active_index_version": "github_evolinkai_gpt_image_cases:github-testthumb"}))

    response = client.get("/api/v2/case-thumbnails/images/sample_case/output.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/webp")
    assert list(thumbnail_dir.rglob("*.webp"))
    with Image.open(BytesIO(response.content)) as image:
        assert image.width <= 720
        assert image.height <= 900

    preview = client.get("/api/v2/case-thumbnails/preview/images/sample_case/output.jpg")

    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/webp")
    with Image.open(BytesIO(preview.content)) as image:
        assert image.width <= 1280
        assert image.height <= 1600


def test_case_thumbnail_endpoint_returns_404_for_unthumbnailable_assets(tmp_path) -> None:
    client = fresh_client()
    snapshot_dir = tmp_path / "snapshots"
    thumbnail_dir = tmp_path / "thumbs"
    snapshot_dir.mkdir()
    object.__setattr__(settings, "remote_snapshot_dir", snapshot_dir)
    object.__setattr__(settings, "case_thumbnail_dir", thumbnail_dir)
    snapshot_path = snapshot_dir / "github-testsvg.zip"
    with zipfile.ZipFile(snapshot_path, "w") as archive:
        archive.writestr("repo-main/images/sample_case/vector.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")

    provider = repository.get_provider("github_evolinkai_gpt_image_cases")
    assert provider is not None
    repository.upsert_provider(provider.model_copy(update={"active_index_version": "github_evolinkai_gpt_image_cases:github-testsvg"}))

    response = client.get("/api/v2/case-thumbnails/images/sample_case/vector.svg")
    original = client.get("/api/v2/case-assets/images/sample_case/vector.svg")

    assert response.status_code == 404
    assert original.status_code == 200
    assert original.headers["content-type"].startswith("image/svg+xml")


def test_v2_upload_image_completes_with_asset_brief() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(32, 96, 180))

    asset = client.get(f"/api/v2/uploads/{asset_id}")
    content = client.get(f"/api/v2/uploads/{asset_id}/content")

    assert asset.status_code == 200
    body = asset.json()
    assert body["status"] == "ready"
    assert body["brief"]["role"] == "subject_reference"
    assert body["brief"]["provider_input_required"] is True
    assert body["brief"]["image"]["width"] == 320
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")


def test_v2_upload_rejects_oversized_declared_and_actual_content() -> None:
    client = fresh_client()
    original_limit = settings.max_uploaded_asset_bytes
    object.__setattr__(settings, "max_uploaded_asset_bytes", 4)
    try:
        upload = client.post(
            "/api/v2/uploads",
            json={
                "filename": "large.png",
                "mime_type": "image/png",
                "size_bytes": 5,
                "role": "subject_reference",
                "constraint_strength": "required",
            },
        )
        assert upload.status_code == 200
        rejected_asset = client.get(f"/api/v2/uploads/{upload.json()['asset_id']}")
        assert rejected_asset.status_code == 200
        assert rejected_asset.json()["status"] == "rejected"
        assert rejected_asset.json()["error"]["code"] == "asset_too_large"

        accepted = client.post(
            "/api/v2/uploads",
            json={
                "filename": "small-declared.png",
                "mime_type": "image/png",
                "size_bytes": 4,
                "role": "subject_reference",
                "constraint_strength": "required",
            },
        )
        assert accepted.status_code == 200
        content = client.put(
            f"/api/v2/uploads/{accepted.json()['asset_id']}/content",
            json={"content_base64": base64.b64encode(b"12345").decode("ascii"), "mime_type": "image/png"},
        )
        assert content.status_code == 400
        assert content.json()["detail"]["error_code"] == "asset_too_large"
    finally:
        object.__setattr__(settings, "max_uploaded_asset_bytes", original_limit)


def test_v2_upload_rejects_invalid_image_content() -> None:
    client = fresh_client()
    upload = client.post(
        "/api/v2/uploads",
        json={
            "filename": "fake.png",
            "mime_type": "image/png",
            "size_bytes": 11,
            "role": "subject_reference",
            "constraint_strength": "required",
        },
    )

    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    content = client.put(
        f"/api/v2/uploads/{asset_id}/content",
        json={"content_base64": base64.b64encode(b"not an image").decode("ascii"), "mime_type": "image/png"},
    )

    assert content.status_code == 400
    assert content.json()["detail"]["error_code"] == "invalid_image_content"
    asset = client.get(f"/api/v2/uploads/{asset_id}")
    assert asset.status_code == 200
    assert asset.json()["status"] == "failed"


def test_v2_upload_complete_requires_stored_image_content() -> None:
    client = fresh_client()
    upload = client.post(
        "/api/v2/uploads",
        json={
            "filename": "missing.png",
            "mime_type": "image/png",
            "size_bytes": 10,
            "role": "subject_reference",
            "constraint_strength": "required",
        },
    )

    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    completed = client.post(f"/api/v2/uploads/{asset_id}/complete")

    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "asset_file_missing"


def test_v2_uploaded_assets_are_bound_to_current_veyra_account(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    owner_token = issue_test_veyra_session_token(42)
    other_token = issue_test_veyra_session_token(77)

    upload = client.post(
        "/api/v2/uploads",
        json={
            "filename": "owned.png",
            "mime_type": "image/png",
            "size_bytes": 4,
            "role": "subject_reference",
            "constraint_strength": "required",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    assert repository.get_uploaded_asset(asset_id).veyra_user_id == 42

    owner_lookup = client.get(f"/api/v2/uploads/{asset_id}", headers={"Authorization": f"Bearer {owner_token}"})
    other_lookup = client.get(f"/api/v2/uploads/{asset_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert owner_lookup.status_code == 200
    assert other_lookup.status_code == 403

    run = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Use another account's uploaded image as the required product.",
            "assets": [{"asset_id": asset_id, "role": "subject_reference", "constraint_strength": "required"}],
            "output": {"count": 1},
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert run.status_code == 202
    body = run.json()
    assert body["status"] == "failed"
    assert "Uploaded asset binding failed" in body["next_actions"][0]


def test_v2_favorite_reference_asset_is_bound_to_current_account(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "veyra_billing_enabled", False)
    reset_billing_settings_cache()

    async def fake_account(user_id: int):
        return SimpleNamespace(user_id=user_id, role="user", balance=100.0)

    monkeypatch.setattr(main_module.VeyraSub2APIClient, "account", lambda self, user_id: fake_account(user_id))

    owner_token = issue_test_veyra_session_token(42)
    other_token = issue_test_veyra_session_token(77)
    create_response = client.post(
        "/api/v2/image/jobs",
        json={
            "run_id": "run_account_favorite_reference",
            "prompt_plan": {
                "plan_id": "plan_account_favorite_reference",
                "mode": "smart_enhance",
                "prompt": "owner image",
                "user_variables": {"generation_prompt": "owner image", "user_prompt": "owner image"},
            },
            "provider_hint": "mock_image",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_response.status_code == 202
    output_id = create_response.json()["outputs"][0]["output_id"]

    owner_favorite = client.put(
        f"/api/v2/image/history/{output_id}/favorite",
        json={"favorite": True},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_favorite.status_code == 200
    other_history = client.get("/api/v2/image/history?limit=10", headers={"Authorization": f"Bearer {other_token}"})
    assert other_history.status_code == 200
    assert output_id not in {item["output_id"] for item in other_history.json()["items"]}

    blocked_reference = client.post(
        f"/api/v2/image/history/{output_id}/reference-asset",
        json={"intended_use": "continue_modifying_selected_favorite_image"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert blocked_reference.status_code == 403

    reference = client.post(
        f"/api/v2/image/history/{output_id}/reference-asset",
        json={"intended_use": "continue_modifying_selected_favorite_image"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert reference.status_code == 200
    asset_id = reference.json()["asset_id"]
    assert repository.get_uploaded_asset(asset_id).veyra_user_id == 42

    owner_lookup = client.get(f"/api/v2/uploads/{asset_id}", headers={"Authorization": f"Bearer {owner_token}"})
    other_lookup = client.get(f"/api/v2/uploads/{asset_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert owner_lookup.status_code == 200
    assert other_lookup.status_code == 403


def test_v2_creative_run_enforces_uploaded_asset_count_limit() -> None:
    client = fresh_client()
    original_limit = settings.max_uploaded_asset_count
    object.__setattr__(settings, "max_uploaded_asset_count", 1)
    try:
        response = client.post(
            "/api/v2/creative/runs",
            json={
                "user_prompt": "Combine several uploaded images into one visual.",
                "assets": [
                    {"asset_id": "asset_a", "role": "style_reference"},
                    {"asset_id": "asset_b", "role": "subject_reference"},
                ],
                "output": {"count": 1},
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error_code"] == "asset_count_exceeded"
    finally:
        object.__setattr__(settings, "max_uploaded_asset_count", original_limit)


def test_case_search_filters_unmatched_free_text() -> None:
    client = fresh_client()
    templates = client.get("/api/v2/templates", params={"limit": 1000}).json()["templates"]
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={
            "query_text": "premium ecommerce skincare studio lighting",
            "risk_filters": ["exclude_protected_ip", "exclude_unlicensed_logo"],
            "limit": 1000,
        },
    )

    assert response.status_code == 200
    results = response.json()["cases"]
    assert results
    assert len(results) < len(templates)
    assert all(
        "feature tag match" in item["why_selected"]
        or "semantic prompt overlap" in item["why_selected"]
        or "fuzzy text match" in item["why_selected"]
        for item in results
    )


def test_case_search_computes_query_features_once(monkeypatch) -> None:
    client = fresh_client()
    calls = 0
    original = main_module.case_intelligence._query_feature_tags

    def counted_query_features(query_text: str):
        nonlocal calls
        calls += 1
        return original(query_text)

    monkeypatch.setattr(main_module.case_intelligence, "_query_feature_tags", counted_query_features)
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={
            "query_text": "premium skincare product advertising studio lighting",
            "use_case_filters": ["ecommerce"],
            "style_filters": ["premium"],
            "limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["cases"]
    assert calls == 1


def test_case_search_prewarm_populates_case_caches() -> None:
    fresh_client()
    intelligence = main_module.case_intelligence
    intelligence._CASE_SEARCH_TEXT_CACHE.clear()
    intelligence._CASE_TOKEN_COUNTER_CACHE.clear()
    intelligence._CASE_TOKEN_SET_CACHE.clear()

    stats = intelligence.prewarm_case_search_index()

    assert stats["cases"] == len(repository.list_cases(active_only=True))
    assert stats["search_text_cache"] >= stats["cases"]
    assert stats["token_counter_cache"] >= stats["cases"]
    assert stats["token_set_cache"] >= stats["cases"]


def test_chinese_case_search_uses_feature_tags() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={
            "query_text": "奢华香水 电商主图 黑金 玻璃瓶",
            "risk_filters": ["exclude_protected_ip", "exclude_unlicensed_logo"],
            "limit": 10,
        },
    )

    assert response.status_code == 200
    results = response.json()["cases"]
    assert results
    assert "feature tag match" in results[0]["why_selected"]
    assert "skincare" in results[0]["title"].lower() or "perfume" in results[0]["title"].lower()


def test_case_profile_endpoint_and_search_summary_tags() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={"query_text": "科技 UI 仪表盘 蓝色 界面", "limit": 5},
    )

    assert response.status_code == 200
    results = response.json()["cases"]
    assert results
    assert results[0]["profile_tags"]

    profile = client.get(f"/api/v2/case-profiles/{results[0]['case_id']}")
    assert profile.status_code == 200
    profile_body = profile.json()
    assert profile_body["source"] == "rules"
    assert any(profile_body[key] for key in ["subject_tags", "style_tags", "use_case_tags", "composition_tags"])


def test_chinese_food_search_does_not_return_unrelated_quality_only_cases() -> None:
    client = fresh_client()
    templates = client.get("/api/v2/templates", params={"limit": 1000}).json()["templates"]
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={"query_text": "食物", "limit": 1000},
    )

    assert response.status_code == 200
    results = response.json()["cases"]
    assert len(results) < len(templates)
    assert all("食品饮料" in item["profile_tags"] or "food" in item["title"].lower() for item in results)


def test_unknown_chinese_search_returns_empty_results() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/prompt-cases/search",
        json={"query_text": "完全不存在的乱码词zzzxxy", "limit": 20},
    )

    assert response.status_code == 200
    assert response.json()["cases"] == []


def test_general_chinese_case_search_uses_profile_axes_beyond_single_keywords() -> None:
    client = fresh_client()
    repository.upsert_cases(
        [
            make_prompt_case(
                "test_pet_cat_poster",
                "Cute Cat Adoption Poster",
                "poster",
                "cute cat pet animal adoption poster playful soft illustration with typography-safe layout",
                style_tags=["cute", "illustration"],
                use_case_tags=["poster"],
            ),
            make_prompt_case(
                "test_sofa_interior",
                "Modern Sofa Interior Campaign",
                "ecommerce",
                "modern sofa furniture living room interior wood table home product campaign with natural light",
                style_tags=["minimal"],
                use_case_tags=["ecommerce", "product-listing"],
            ),
            make_prompt_case(
                "test_city_travel_map",
                "Illustrated City Travel Map",
                "poster",
                "illustrated city travel map landmark tourism guide poster with collage layout",
                style_tags=["illustration"],
                use_case_tags=["poster"],
            ),
            make_prompt_case(
                "test_hoodie_fashion_ad",
                "Hoodie Fashion Lookbook Ad",
                "ad-creative",
                "fashion apparel hoodie outfit lookbook studio advertising campaign with fabric texture",
                style_tags=["editorial"],
                use_case_tags=["ad-creative"],
            ),
            make_prompt_case(
                "test_fintech_banking_ui",
                "Fintech Banking App Dashboard",
                "ui",
                "finance banking fintech app ui dashboard blue interface for wealth and insurance products",
                style_tags=["ui", "clean"],
                use_case_tags=["ui"],
            ),
            make_prompt_case(
                "test_unrelated_perfume",
                "Premium Perfume Bottle",
                "ecommerce",
                "luxury perfume glass bottle black gold commercial product hero shot",
                style_tags=["luxury"],
                use_case_tags=["ecommerce"],
            ),
        ]
    )

    checks = [
        ("宠物 猫 海报", "test_pet_cat_poster"),
        ("家具 沙发 室内", "test_sofa_interior"),
        ("旅行 城市 地图 插画", "test_city_travel_map"),
        ("服装 卫衣 时尚广告", "test_hoodie_fashion_ad"),
        ("金融 银行 App 界面", "test_fintech_banking_ui"),
    ]
    for query, expected_case_id in checks:
        response = client.post("/api/v2/prompt-cases/search", json={"query_text": query, "limit": 8})
        assert response.status_code == 200
        results = response.json()["cases"]
        result_ids = [item["case_id"] for item in results]
        assert expected_case_id in result_ids[:3], (query, result_ids)
        assert "test_unrelated_perfume" not in result_ids[:3], (query, result_ids)
        expected = next(item for item in results if item["case_id"] == expected_case_id)
        assert "feature tag match" in expected["why_selected"]
        assert expected["profile_tags"]


def test_v2_visual_signals_feed_profile_and_prompt_composer() -> None:
    case = make_prompt_case(
        "case_test_visual_signal_0001",
        "Premium Tea Gift Box Hero",
        "ecommerce",
        (
            "premium tea gift box hero product image on a warm beige background, tiny emerald deep green seal, "
            "thin gold foil edge, transparent glass tea jar, soft studio lighting, centered hero composition"
        ),
        style_tags=["premium", "minimal"],
        use_case_tags=["ecommerce"],
    )

    signals = build_case_visual_signals(case)
    profile = build_case_profile(case)
    plan = compose_prompt_plan(
        mode="template_customize",
        user_prompt="Create a premium chocolate gift box ecommerce image using this template style.",
        cases=[case],
        output={"count": 1, "aspect_ratio": "4:5"},
    )

    assert "deep green accent" in signals.accent_color_signals
    assert "warm gold/amber metallic accent" in signals.accent_color_signals
    assert any("glass" in item for item in signals.material_tags)
    assert "green" in [item.lower() for item in profile.color_tags]
    assert "gold" in [item.lower() for item in profile.color_tags]
    prompt_lower = plan.prompt.lower()
    assert "deep green accent" in prompt_lower
    assert "warm gold" in prompt_lower or "gold foil" in prompt_lower
    assert "transparent glass" in prompt_lower
    assert "case_test_visual_signal" not in prompt_lower


def test_claude_orchestrator_case_detail_exposes_visual_signal_brief() -> None:
    case = make_prompt_case(
        "case_test_claude_visual_signal_0001",
        "Black Gold Perfume Reference",
        "ecommerce",
        (
            "luxury perfume bottle with black background, warm gold rim light, transparent glass highlights, "
            "dramatic studio lighting, centered commercial hero shot"
        ),
        style_tags=["luxury"],
        use_case_tags=["ecommerce"],
    )

    detail = claude_orchestrator_service._case_detail_for_claude(case)
    compact = claude_orchestrator_service._compact_inline_cases(
        [PromptCaseSummary.model_validate(case.model_dump()).model_dump()],
        [detail],
    )

    assert detail["visual_signal_brief"]["brief"]
    assert "warm gold/amber metallic accent" in detail["visual_signal_brief"]["accent_color_signals"]
    assert compact[0]["visual_signal_brief"]["brief"]
    assert compact[0]["visual_signal_brief"]["accent_color_signals"]


def test_claude_inline_prompt_template_fast_path_compacts_to_single_case(tmp_path: Path) -> None:
    template = make_prompt_case(
        "test_template_fast_path_case",
        "Editorial Template",
        "ad-creative",
        (
            "A pale blue editorial poster with giant background typography, glossy reflective floor, oversized "
            "product sculpture, and a model leaning against the subject."
        ),
        style_tags=["editorial", "studio-lighting"],
        use_case_tags=["ad-creative", "poster"],
    )
    other = make_prompt_case(
        "test_other_fast_path_case",
        "Unrelated Food Poster",
        "food",
        "A warm burger poster with cheese, fries, ketchup, and rustic wood table.",
        style_tags=["food"],
        use_case_tags=["poster"],
    )
    summaries = [
        PromptCaseSummary.model_validate(template.model_dump()).model_dump(mode="json"),
        PromptCaseSummary.model_validate(other.model_dump()).model_dump(mode="json"),
    ]
    details = [
        claude_orchestrator_service._case_detail_for_claude(template),
        claude_orchestrator_service._case_detail_for_claude(other),
    ]
    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "request": {
                    "user_prompt": "Turn the selected template into a deep green premium polo shirt poster.",
                    "template_case_id": template.case_id,
                    "output": {"count": 1, "provider_hint": "mock_image"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps(
            {
                "mode": "template_customize",
                "selected_case_ids": [template.case_id, other.case_id],
                "generation_directives": {"count": 1},
                "quality_gates": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "candidate_cases.json").write_text(json.dumps(summaries, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "candidate_case_details.json").write_text(json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "template_lock_contract.json").write_text(
        json.dumps({"locked_case_id": template.case_id, "priority": "highest"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "uploaded_assets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "asset_binding_policy.json").write_text(
        json.dumps(
            {
                "mode": "template_lock",
                "bindings": [
                    {
                        "role": "logo_reference",
                        "constraint_strength": "required",
                        "binding_slot": "logo",
                        "fusion_mode": "logo_product_surface",
                        "placement_intent": {"mode": "scene_surface", "target_surface": "apparel_chest"},
                        "target_surface": "apparel_chest",
                        "provider_input_required": True,
                        "prompt_instruction": "x" * 500,
                        "review_expectations": ["logo on apparel", "no footer badge"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prompt = claude_orchestrator_service._build_inline_json_prompt(tmp_path)
    payload = json.loads(prompt.split("\n", 1)[1])

    assert prompt.startswith("Return compact JSON only.")
    assert f"Total JSON <= {claude_orchestrator_service._CLAUDE_INLINE_JSON_CHAR_BUDGET} chars" in prompt
    assert payload["fallback"]["selected_case_ids"] == [template.case_id]
    assert [item["case_id"] for item in payload["candidate_cases"]] == [template.case_id]
    assert other.title not in prompt
    assert "prompt_instruction" not in json.dumps(payload["asset_binding_policy"], ensure_ascii=False)
    assert len(prompt) < 3600


def test_claude_inline_invocation_overrides_stale_output_token_env(monkeypatch, tmp_path: Path) -> None:
    old_limit = settings.claude_orchestrator_max_output_tokens
    object.__setattr__(settings, "claude_orchestrator_max_output_tokens", 12288)
    monkeypatch.setenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "8192")
    captured: dict[str, str | None] = {}

    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "request": {
                    "user_prompt": "Create a premium perfume ecommerce hero image.",
                    "template_case_id": None,
                    "output": {"count": 1, "provider_hint": "mock_image"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps(
            {
                "mode": "smart_enhance",
                "selected_case_ids": ["case_seed"],
                "generation_directives": {"count": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "candidate_cases.json").write_text("[]", encoding="utf-8")
    (tmp_path / "candidate_case_details.json").write_text("[]", encoding="utf-8")
    (tmp_path / "template_lock_contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "asset_binding_policy.json").write_text("{}", encoding="utf-8")

    def fake_run(command_line, **kwargs):
        captured["max_output_tokens"] = kwargs["env"].get("CLAUDE_CODE_MAX_OUTPUT_TOKENS")
        captured["structured_retries"] = kwargs["env"].get("MAX_STRUCTURED_OUTPUT_RETRIES")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "structured_output": {
                        "mode": "smart_enhance",
                        "selected_case_ids": ["case_seed"],
                        "final_prompt": "Premium perfume ecommerce hero, black glass bottle, gold rim light, clean studio surface.",
                        "negative_prompt": "watermark, garbled text",
                        "provider_parameters": {"count": 1},
                        "prompt_rationale": "Compact prompt keeps the commercial hero direction.",
                        "confidence": 0.82,
                    }
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(claude_orchestrator_service, "_run_claude_subprocess", fake_run)
    try:
        decision = claude_orchestrator_service._invoke_claude_inline_json(
            command=["claude"],
            workspace=tmp_path,
        )
    finally:
        object.__setattr__(settings, "claude_orchestrator_max_output_tokens", old_limit)

    assert captured["max_output_tokens"] == "12288"
    assert captured["structured_retries"] == "1"
    assert decision is not None
    assert decision["final_prompt"].startswith("Premium perfume")


def test_claude_final_prompt_strips_internal_reference_ids(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "final_prompt": (
                "Use case_github_evolinkai_ad_0001 and asset_abc123 only as internal planning markers, "
                "then create a premium perfume ecommerce hero image with black background, gold rim light, and glass highlights."
            ),
            "negative_prompt": "provider_id, source_url, watermark",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "The internal references should not leak into the downstream image prompt.",
            "confidence": 0.86,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium perfume ecommerce hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    prompt = response.json()["prompt_plan"]["prompt"]
    assert "case_github" not in prompt
    assert "asset_" not in prompt
    assert "provider_id" not in prompt
    assert "selected visual reference" in prompt
    assert "uploaded visual reference" in prompt


def test_checkpoint_orchestrator_runs_all_stages_and_compresses_output(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_final_prompt_max_chars", 240)
    object.__setattr__(settings, "claude_negative_prompt_max_chars", 90)
    object.__setattr__(settings, "claude_rationale_max_chars", 60)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        candidates = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))
        fallback = json.loads((workspace / "fallback_decision.json").read_text(encoding="utf-8"))
        candidate = (
            candidates[0]["case_id"]
            if candidates
            else (fallback.get("selected_case_ids") or ["case_synthetic_checkpoint"])[0]
        )
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "three armored infantry",
                "scene_goal": "fantasy dungeon breach battle",
                "must_keep": ["tower shields", "spears", "crossbow cover fire"],
                "must_avoid": ["cartoon tone"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.84,
            }
        if stage_name.startswith("visual_strategy"):
            payload = json.loads(prompt.split("\n", 1)[1])
            assert payload["stage"] == "visual_strategy_ultra_micro"
            assert payload["candidate_cases"] == []
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "shield wall compresses the doorway, rear shooters visible over shoulders",
                "lighting": "torchlit smoke and cold metal glints",
                "palette": "dark stone, silver armor, ember orange",
                "spatial_hierarchy": "frontline dominates foreground, defenders pushed back at the threshold",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.88,
            }
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": (
                "Epic dark fantasy dungeon battle, three emotionless human infantry in heavy silver plate armor "
                "advance as a disciplined shield wall with nearly two-meter tower shields and long spears, rear "
                "crossbowmen firing controlled cover volleys through smoke and torchlight, cinematic realism, "
                "cold steel highlights, gritty stone doorway, compressed brutal momentum. "
            )
            * 2,
            "negative_prompt": "watermark, modern weapons, cheerful cartoon tone, unreadable text, blurry armor details",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": (
                "Checkpoint compression keeps the hard combat staging, metal armor, formation logic, and cover fire "
                "while removing internal planning prose."
            ),
            "confidence": 0.91,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": (
                "生成一张西幻背景下的巢穴入口作战场景，三名重甲步兵用塔盾和长矛冷酷推进，"
                "身后两名十字弩射手覆盖射击。"
            ),
            "output": {"count": 1},
        },
    )

    assert response.status_code == 202
    run = response.json()
    decision = run["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "generation_decision"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 3
    assert len(decision["final_prompt"]) <= 240
    assert len(decision["negative_prompt"]) <= 90
    assert len(decision["prompt_rationale"]) <= 60
    assert run["prompt_plan"]["user_variables"]["prompt_source"] == "claude_final_prompt"
    assert run["generation_jobs"][0]["provider_id"] == "mock_image"


def test_creative_run_exposes_claude_progress_summary(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "light meal poster",
                "scene_goal": "redesign a food promotion image",
                "must_keep": ["offer text", "QR code"],
                "must_avoid": ["dropping policy text"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.84,
            }
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "hero food image plus structured menu modules",
                "lighting": "warm clean commercial light",
                "palette": "cream, gold, fresh green",
                "spatial_hierarchy": "hero first, offer and QR preserved in side modules",
                "template_lock_notes": "preserve template frame",
                "asset_fusion_notes": "uploaded poster supplies food, copy, QR",
                "confidence": 0.88,
            }
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": "Commercial light meal poster with strong template hierarchy, hero food image, complete offer copy, QR module.",
            "negative_prompt": "missing QR, dropped offer text, unreadable menu",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Preserve composition and information integrity.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "做一张轻食菜单海报，保留优惠政策和二维码", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["progress_summary"]["scope"] == "claude_orchestration"
    assert run["progress_summary"]["finished_stage_count"] == 3
    assert run["progress_events"][0]["status"] == "running"
    assert run["progress_events"][-1]["status"] == "success"
    assert "Claude Code" in run["progress_summary"]["message"]
    assert len(run["orchestrator_decision"]["claude_stage_trace"]) == 3


def test_claude_progress_summary_uses_wall_clock_not_aggregate_duration() -> None:
    events = [
        {
            "scope": "claude_orchestration",
            "stage": "visual_strategy",
            "status": "running",
            "provider": "kimi",
            "created_at": "2026-06-09T00:00:00+00:00",
        },
        {
            "scope": "claude_orchestration",
            "stage": "visual_strategy",
            "status": "error",
            "provider": "kimi",
            "duration_ms": 120000,
            "created_at": "2026-06-09T00:02:00+00:00",
        },
        {
            "scope": "claude_orchestration",
            "stage": "visual_strategy_model_fallback_1",
            "status": "error",
            "provider": "claude-code-model-fallback",
            "duration_ms": 25000,
            "created_at": "2026-06-09T00:02:25+00:00",
        },
        {
            "scope": "claude_orchestration",
            "stage": "visual_strategy_model_fallback",
            "status": "success",
            "provider": "claude-code-model-fallback",
            "duration_ms": 36000,
            "created_at": "2026-06-09T00:02:36+00:00",
        },
    ]

    summary = runtime_module._claude_progress_summary(events)

    assert summary["elapsed_ms"] == 156000


def test_checkpoint_orchestrator_micro_retries_output_limit_stage(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
        if stage_name == "visual_strategy":
            raise claude_orchestrator_service.ClaudeInvocationError("claude_output_token_limit")
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product",
                "scene_goal": "commercial hero image",
                "must_keep": ["premium lighting"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.82,
            }
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "centered product hero composition",
                "lighting": "soft rim lighting",
                "palette": "black, gold, clear glass",
                "spatial_hierarchy": "product first, quiet background",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.87,
            }
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": "Premium product hero image, centered composition, black-gold rim light, clean commercial finish.",
            "negative_prompt": "watermark, clutter",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Recovered with a compact visual strategy retry.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "visual_strategy_micro_retry_1", "generation_decision"]
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 4


def test_checkpoint_orchestrator_micro_retries_timeout_stage(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
        if stage_name == "visual_strategy":
            raise claude_orchestrator_service.ClaudeInvocationError("claude_timeout")
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product",
                "scene_goal": "commercial hero image",
                "must_keep": ["premium lighting"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.82,
            }
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "centered product hero composition",
                "lighting": "soft rim lighting",
                "palette": "black, gold, clear glass",
                "spatial_hierarchy": "product first, quiet background",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.87,
            }
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": "Premium product hero image, centered composition, black-gold rim light, clean commercial finish.",
            "negative_prompt": "watermark, clutter",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Recovered with a compact timeout retry.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "visual_strategy_micro_retry_1", "generation_decision"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 4


def test_checkpoint_orchestrator_recovers_from_intent_after_visual_timeout_exhaustion(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "Japanese poster product",
                "scene_goal": "preserve product copy and scannable QR in a refined layout",
                "must_keep": ["product identity", "copy text", "QR code clarity"],
                "must_avoid": ["QR obstruction", "text loss"],
                "asset_requirements": [],
                "risk_notes": ["QR needs deterministic preservation"],
                "confidence": 0.84,
            }
        candidates = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))
        fallback = json.loads((workspace / "fallback_decision.json").read_text(encoding="utf-8"))
        candidate = candidates[0]["case_id"] if candidates else (fallback.get("selected_case_ids") or ["case_seed"])[0]
        if stage_name.startswith("visual_strategy"):
            raise claude_orchestrator_service.ClaudeInvocationError("claude_timeout")
        if stage_name.startswith("generation_decision_recovery"):
            return {
                "mode": "smart_enhance",
                "selected_case_ids": [candidate],
                "final_prompt": (
                    "Refined Japanese commercial poster using the uploaded reference image as the product identity, "
                    "preserve the original product content, integrate original copy cleanly, reserve a clear scannable QR area."
                ),
                "negative_prompt": "unreadable QR, distorted product, missing copy",
                "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
                "prompt_rationale": "Recovered through compressed Claude intent checkpoint.",
                "confidence": 0.86,
            }
        raise AssertionError(stage_name)

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "保留产品、文案和二维码，做更精美的日式海报。", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "visual_strategy_micro_retry_1", "generation_decision_recovery"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["final_prompt"]
    assert decision["fallback_reason"] is None
    assert "deterministic" not in decision["provider"]


def test_checkpoint_orchestrator_compacts_from_checkpoints_after_final_output_limit(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    object.__setattr__(settings, "claude_final_prompt_max_chars", 180)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product poster",
                "scene_goal": "commercial layout with preserved product and QR",
                "must_keep": ["product identity", "QR clarity"],
                "must_avoid": ["unreadable QR"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.83,
            }
        candidates = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))
        fallback = json.loads((workspace / "fallback_decision.json").read_text(encoding="utf-8"))
        candidate = candidates[0]["case_id"] if candidates else (fallback.get("selected_case_ids") or ["case_seed"])[0]
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "Japanese poster grid with product as the visual anchor and QR in a clean scan-safe zone",
                "lighting": "soft daylight",
                "palette": "warm paper, muted blue, restrained black text",
                "spatial_hierarchy": "product first, copy second, QR clear and separate",
                "template_lock_notes": "",
                "asset_fusion_notes": "uploaded product remains provider input image",
                "confidence": 0.88,
            }
        raise claude_orchestrator_service.ClaudeInvocationError("claude_output_token_limit")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "保留产品和二维码，做日式海报。", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "generation_decision", "generation_decision_ultra_micro_retry_1"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert len(decision["final_prompt"]) <= 180
    assert "deterministic" not in decision["provider"]


def test_checkpoint_orchestrator_continues_after_final_soft_timeout(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 2)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product poster",
                "scene_goal": "commercial product hero",
                "must_keep": ["clean hierarchy"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.84,
            }
        candidates = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))
        fallback = json.loads((workspace / "fallback_decision.json").read_text(encoding="utf-8"))
        candidate = candidates[0]["case_id"] if candidates else (fallback.get("selected_case_ids") or ["case_seed"])[0]
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "minimal centered product with negative space",
                "lighting": "soft studio key light",
                "palette": "warm ivory and champagne gold",
                "spatial_hierarchy": "product dominates, background recedes",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.88,
            }
        raise claude_orchestrator_service.ClaudeInvocationError("claude_soft_timeout")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product poster.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "generation_decision", "generation_decision_ultra_micro_retry_1"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 4
    assert decision["fallback_reason"] is None


def test_checkpoint_orchestrator_retries_structured_output_exhaustion(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product",
                "scene_goal": "commercial hero image",
                "must_keep": ["premium lighting"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.82,
            }
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "centered product hero composition",
                "lighting": "soft rim lighting",
                "palette": "black, gold, clear glass",
                "spatial_hierarchy": "product first, quiet background",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.87,
            }
        if stage_name == "generation_decision":
            raise claude_orchestrator_service.ClaudeInvocationError("claude_structured_output_retries_exhausted")
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": "Premium product hero image, centered composition, black-gold rim light, clean commercial finish.",
            "negative_prompt": "watermark, clutter",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Recovered after structured output retry exhaustion.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "generation_decision", "generation_decision_ultra_micro_retry_1"]
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 4


def test_checkpoint_orchestrator_retries_kimi_sub2api_502(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
        if stage_name.startswith("intent"):
            return {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product",
                "scene_goal": "commercial hero image",
                "must_keep": ["premium lighting"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.82,
            }
        if stage_name == "visual_strategy":
            raise claude_orchestrator_service.ClaudeInvocationError("kimi_sub2api_502")
        if stage_name.startswith("visual_strategy"):
            return {
                "stage": "visual_strategy",
                "selected_case_ids": [candidate],
                "composition": "centered product hero composition",
                "lighting": "soft rim lighting",
                "palette": "black, gold, clear glass",
                "spatial_hierarchy": "product first, quiet background",
                "template_lock_notes": "",
                "asset_fusion_notes": "",
                "confidence": 0.87,
            }
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate],
            "final_prompt": "Premium product hero image, centered composition, black-gold rim light, clean commercial finish.",
            "negative_prompt": "watermark, clutter",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Recovered after Kimi upstream 502.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    assert calls == ["intent", "visual_strategy", "visual_strategy_micro_retry_1", "generation_decision"]
    assert decision["invocation_status"] == "checkpoint_success"
    assert decision["attempts"] == 4


def test_checkpoint_orchestrator_stops_generation_after_initial_checkpoint_exhaustion(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    calls: list[str] = []

    monkeypatch.setattr(claude_orchestrator_service, "_resolve_claude_command", lambda: ["claude"])

    def always_output_limit(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        raise claude_orchestrator_service.ClaudeInvocationError("claude_output_token_limit")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", always_output_limit)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium product hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    decision = response.json()["orchestrator_decision"]
    run = response.json()
    assert run["status"] == "failed"
    assert run["generation_jobs"] == []
    assert calls == ["intent", "intent_ultra_micro_retry_1"]
    assert decision["provider"] == "deterministic-fallback"
    assert decision["invocation_status"] == "checkpoint_fallback"
    assert decision["fallback_reason"] == "claude_checkpoint_missing_decision"
    assert decision["attempts"] == 2


def test_checkpoint_stage_uses_cli_schema_with_local_retry_control(monkeypatch, tmp_path: Path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_checkpoint_cli_schema_enabled", False)
    object.__setattr__(settings, "claude_orchestrator_timeout_seconds", 240.0)
    object.__setattr__(settings, "claude_checkpoint_stage_timeout_seconds", 123.0)
    object.__setattr__(settings, "claude_checkpoint_soft_stage_timeout_seconds", 60.0)
    captured: dict[str, object] = {}

    def fake_run(command_line, **kwargs):
        captured["command_line"] = command_line
        captured["env"] = kwargs["env"]
        captured["timeout"] = kwargs["timeout_seconds"]
        result = json.dumps(
            {
                "stage": "intent",
                "mode": "smart_enhance",
                "primary_subject": "premium product",
                "scene_goal": "commercial hero image",
                "must_keep": ["premium lighting"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": [],
                "confidence": 0.9,
            }
        )
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}), stderr="")

    monkeypatch.setattr(claude_orchestrator_service, "_run_claude_subprocess", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed["stage"] == "intent"
    assert "--json-schema" in captured["command_line"]
    assert captured["env"]["MAX_STRUCTURED_OUTPUT_RETRIES"] == "0"
    assert captured["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "4096"
    assert captured["timeout"] == 60.0
    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("generation_decision") == 60.0
    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("intent_micro_retry_1") == 45.0
    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("intent_ultra_micro_retry_2") == 30.0


def test_checkpoint_generation_decision_uses_configured_soft_timeout(monkeypatch) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_timeout_seconds", 240.0)
    object.__setattr__(settings, "claude_checkpoint_stage_timeout_seconds", 180.0)
    object.__setattr__(settings, "claude_checkpoint_soft_stage_timeout_seconds", 120.0)

    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("generation_decision") == 120.0


def test_checkpoint_retry_plan_skips_duplicate_micro_prompt(monkeypatch, tmp_path: Path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 2)
    calls: list[str] = []

    def fake_stage_json(*, command, workspace, stage_name, prompt, schema):
        calls.append(stage_name)
        if stage_name == "intent":
            raise claude_orchestrator_service.ClaudeInvocationError("claude_timeout")
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "menu poster",
            "scene_goal": "compact food poster",
            "must_keep": ["price tiers"],
            "must_avoid": ["duplicates"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_stage_json)
    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="same micro prompt",
        micro_prompt="same micro prompt",
        ultra_micro_prompt="shorter ultra prompt",
        trace=[],
    )

    assert result is not None
    assert attempts == 2
    assert calls == ["intent", "intent_ultra_micro_retry_1"]


def test_claude_policy_refusal_is_classified_separately() -> None:
    stdout = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "stop_reason": "refusal",
            "result": "API Error: Claude Code is unable to respond to this request, which appears to violate our Usage Policy.",
        }
    )

    assert claude_orchestrator_service._classify_claude_failure(stdout, "", 0) == "claude_policy_refusal"


def test_claude_checkpoint_timeout_salvages_valid_stdout(monkeypatch, tmp_path: Path) -> None:
    fresh_client()

    payload = {
        "stage": "intent",
        "mode": "smart_enhance",
        "primary_subject": "premium menu poster",
        "scene_goal": "information-dense commercial food poster",
        "must_keep": ["QR code", "offer policy"],
        "must_avoid": ["copying source layout"],
        "asset_requirements": [],
        "risk_notes": [],
        "confidence": 0.86,
    }
    stdout = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(payload, ensure_ascii=False),
        },
        ensure_ascii=False,
    )

    def fake_run(command_line, **kwargs):
        raise claude_orchestrator_service.subprocess.TimeoutExpired(
            cmd=command_line,
            timeout=kwargs["timeout_seconds"],
            output=stdout,
            stderr="",
        )

    monkeypatch.setattr(claude_orchestrator_service, "_run_claude_subprocess", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed is not None
    assert parsed["stage"] == "intent"
    assert parsed["mode"] == "smart_enhance"
    assert parsed["must_keep"] == ["QR code", "offer policy"]


def test_checkpoint_stage_accepts_safe_micro_alias_and_confidence_label(monkeypatch, tmp_path: Path) -> None:
    fresh_client()
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps({"mode": "smart_enhance"}, ensure_ascii=False),
        encoding="utf-8",
    )

    def fake_run(command_line, **kwargs):
        result = json.dumps(
            {
                "stage": "intent_micro",
                "mode": "direct",
                "primary_subject": "premium product poster",
                "scene_goal": "compact commercial hero image",
                "must_keep": ["clean hierarchy"],
                "must_avoid": ["clutter"],
                "asset_requirements": [],
                "risk_notes": "no specific product identity supplied",
                "confidence": "high",
            }
        )
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}), stderr="")

    monkeypatch.setattr(claude_orchestrator_service, "_run_claude_subprocess", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent_micro_retry_1",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed["stage"] == "intent"
    assert parsed["mode"] == "smart_enhance"
    assert parsed["confidence"] == 0.9
    assert parsed["risk_notes"] == ["no specific product identity supplied"]


def test_checkpoint_stage_rejects_missing_required_fields(monkeypatch, tmp_path: Path) -> None:
    fresh_client()

    def fake_run(command_line, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": json.dumps({"stage": "intent"})}), stderr="")

    monkeypatch.setattr(claude_orchestrator_service, "_run_claude_subprocess", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed is None


def test_checkpoint_intent_prompt_uses_bounded_context(tmp_path: Path) -> None:
    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "request": {
                    "user_prompt": "Create a complex fantasy battle scene.",
                    "template_case_id": None,
                    "output": {"count": 1},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps({"mode": "smart_enhance", "selected_case_ids": ["case_seed"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "candidate_cases.json").write_text(
        json.dumps(
            [
                {
                    "case_id": "case_seed",
                    "title": "Dense candidate",
                    "summary": "This should not be sent to the intent stage.",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "candidate_case_details.json").write_text(
        json.dumps([{"case_id": "case_seed", "raw_prompt_excerpt": "x" * 5000}], ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "template_lock_contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "asset_binding_policy.json").write_text("{}", encoding="utf-8")

    prompt = claude_orchestrator_service._build_checkpoint_stage_prompt(tmp_path, stage_name="intent")
    payload = json.loads(prompt.split("\n", 1)[1])

    assert payload["candidate_cases"] == []
    assert "output_contract" in payload
    assert payload["output_limits"]["total_json_chars"] == 1300
    assert payload["json_skeleton"]["stage"] == "intent"
    assert "Start with { immediately" in prompt
    assert "Think fully" not in prompt
    assert "bounded internal" in claude_orchestrator_service._checkpoint_system_prompt()
    assert len(prompt) < 2500


def test_checkpoint_generation_prompt_uses_compact_checkpoints_only(tmp_path: Path) -> None:
    (tmp_path / "context.json").write_text(
        json.dumps(
            {
                "request": {
                    "user_prompt": "Create a complex fantasy battle scene.",
                    "template_case_id": None,
                    "output": {"count": 1},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps({"mode": "smart_enhance", "selected_case_ids": ["case_seed"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "candidate_cases.json").write_text(
        json.dumps(
            [{"case_id": "case_seed", "title": "Dense candidate", "summary": "x" * 2000}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "candidate_case_details.json").write_text(
        json.dumps([{"case_id": "case_seed", "raw_prompt_excerpt": "y" * 8000}], ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "template_lock_contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "asset_binding_policy.json").write_text("{}", encoding="utf-8")
    checkpoints = {
        "intent": {
            "mode": "smart_enhance",
            "primary_subject": "armored infantry " * 20,
            "scene_goal": "dungeon breach " * 30,
            "must_keep": ["tower shields " * 20, "rear crossbow cover fire " * 20],
            "must_avoid": ["modern weapons " * 20],
        },
        "visual_strategy": {
            "selected_case_ids": ["case_seed"],
            "composition": "shield wall foreground " * 30,
            "lighting": "torch rim light " * 20,
            "palette": "silver armor and amber torch " * 20,
            "spatial_hierarchy": "frontline dominates " * 30,
            "template_lock_notes": "none",
            "asset_fusion_notes": "none",
        },
    }

    prompt = claude_orchestrator_service._build_checkpoint_stage_prompt(
        tmp_path,
        stage_name="generation_decision",
        checkpoints=checkpoints,
    )
    payload = json.loads(prompt.split("\n", 1)[1])

    assert payload["candidate_cases"] == []
    assert payload["output_limits"]["total_json_chars"] == 1800
    assert payload["json_skeleton"]["final_prompt"] == "..."
    assert payload["checkpoints"]["intent"]["primary_subject"].endswith("...")
    assert payload["checkpoints"]["visual_strategy"]["composition"].endswith("...")
    assert len(prompt) < 4000


def test_checkpoint_visual_ultra_micro_prompt_drops_candidate_context(tmp_path: Path) -> None:
    (tmp_path / "context.json").write_text(
        json.dumps({"request": {"user_prompt": "Create a complex battle scene.", "output": {"count": 1}}}),
        encoding="utf-8",
    )
    (tmp_path / "fallback_decision.json").write_text(
        json.dumps({"mode": "smart_enhance", "selected_case_ids": ["case_seed"]}),
        encoding="utf-8",
    )
    (tmp_path / "candidate_cases.json").write_text(
        json.dumps([{"case_id": "case_seed", "title": "Candidate", "summary": "x" * 1000}]),
        encoding="utf-8",
    )
    (tmp_path / "candidate_case_details.json").write_text(
        json.dumps([{"case_id": "case_seed", "raw_prompt_excerpt": "y" * 5000}]),
        encoding="utf-8",
    )
    (tmp_path / "template_lock_contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text("[]", encoding="utf-8")
    (tmp_path / "asset_binding_policy.json").write_text("{}", encoding="utf-8")

    prompt = claude_orchestrator_service._build_checkpoint_stage_prompt(
        tmp_path,
        stage_name="visual_strategy_ultra_micro",
        checkpoints={
            "intent": {
                "mode": "smart_enhance",
                "primary_subject": "armored infantry",
                "scene_goal": "dungeon breach",
                "must_keep": ["tower shields"],
                "must_avoid": ["modern weapons"],
            }
        },
    )
    payload = json.loads(prompt.split("\n", 1)[1])

    assert payload["candidate_cases"] == []
    assert len(prompt) < 2200


def test_runtime_model_settings_can_switch_v2_models() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/runtime/model-settings",
        json={
            "image_generation_provider": "mock_image",
            "default_agent_model": "gpt-4.1",
            "output_review_agent_enabled": True,
            "output_review_agent_model": "gpt-4.1-mini",
            "claude_orchestrator_enabled": True,
            "claude_orchestrator_model": "claude-sonnet-test",
            "claude_orchestrator_multimodal_model": "doubao-seed-2-0-lite-260428",
            "claude_orchestrator_fallback_model": "claude-haiku-test",
            "claude_orchestrator_effort": "medium",
            "claude_checkpoint_orchestrator_enabled": True,
            "case_intelligence_provider": "claude-code",
            "case_intelligence_model": "claude-sonnet-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["image_generation_provider"] == "mock_image"
    assert body["default_agent_model"] == "gpt-4.1"
    assert body["output_review_agent_enabled"] is True
    assert body["claude_orchestrator_enabled"] is True
    assert body["claude_orchestrator_model"] == "claude-sonnet-test"
    assert body["claude_orchestrator_multimodal_model"] == "doubao-seed-2-0-lite-260428"
    assert body["claude_checkpoint_orchestrator_enabled"] is True
    assert body["case_intelligence_provider"] == "claude-code"
    assert body["case_intelligence_model"] == "claude-sonnet-test"

    status = client.get("/api/v2/orchestrator/status")
    assert status.status_code == 200
    assert status.json()["model"] == "claude-sonnet-test"
    assert status.json()["multimodal_model"] == "doubao-seed-2-0-lite-260428"
    assert status.json()["timeout_seconds"] == settings.claude_orchestrator_timeout_seconds
    assert status.json()["max_output_tokens"] == settings.claude_orchestrator_max_output_tokens
    assert status.json()["checkpoint_enabled"] is True

    profile = client.get("/api/v2/case-profiles/case_github_evolinkai_ad_0001")
    assert profile.status_code == 200
    assert profile.json()["source"] == "rules"


def test_runtime_model_settings_rejects_temporarily_disabled_gemini_image_provider() -> None:
    client = fresh_client()

    response = client.post("/api/v2/runtime/model-settings", json={"image_generation_provider": "gemini_image"})

    assert response.status_code == 200
    assert response.json()["image_generation_provider"] == "auto"
    assert settings.image_generation_provider == "auto"


def test_runtime_model_settings_can_select_doubao_image_provider() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/runtime/model-settings",
        json={
            "image_generation_provider": "doubao_image",
            "doubao_image_model": "doubao-seedream-v2-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["image_generation_provider"] == "doubao_image"
    assert body["doubao_image_model"] == "doubao-seedream-v2-test"
    assert body["doubao_image_api_key_configured"] is True
    assert settings.image_generation_provider == "doubao_image"
    assert settings.doubao_image_model == "doubao-seedream-v2-test"


def test_v2_auto_provider_hint_ignores_temporarily_disabled_gemini_setting() -> None:
    fresh_client()
    object.__setattr__(settings, "image_generation_provider", "gemini_image")
    object.__setattr__(settings, "gemini_api_key", "test-gemini-key")
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_test_provider_hint",
            mode="smart_enhance",
            prompt="Create a premium tea poster.",
            provider_parameters={"provider_hint": "auto"},
        ),
        provider_hint="auto",
    )

    assert request.prompt_plan.provider_parameters["provider_hint"] == "auto"
    provider = asyncio.run(get_v2_image_provider(request.provider_hint))
    assert provider.name == "openai_gpt_image"
    assert generation_service._requested_model(request.provider_hint) == settings.openai_image_model


def test_v2_auto_provider_hint_can_use_doubao_when_openai_missing() -> None:
    fresh_client()
    object.__setattr__(settings, "image_generation_provider", "auto")
    object.__setattr__(settings, "openai_api_key", None)
    object.__setattr__(settings, "doubao_image_api_key", "test-doubao-key")
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_test_doubao_auto_provider_hint",
            mode="smart_enhance",
            prompt="Create a premium tea poster.",
            provider_parameters={"provider_hint": "auto"},
        ),
        provider_hint="auto",
    )

    provider = asyncio.run(get_v2_image_provider(request.provider_hint))
    assert provider.name == "doubao_image"
    assert generation_service._requested_model(request.provider_hint) == settings.doubao_image_model


def test_v2_doubao_image_provider_requires_dedicated_key_even_when_openai_is_configured() -> None:
    fresh_client()
    object.__setattr__(settings, "openai_api_key", "sk-openai-only")
    object.__setattr__(settings, "doubao_image_api_key", None)

    provider = asyncio.run(get_v2_image_provider("doubao_image"))
    caps = asyncio.run(provider.capabilities())

    assert provider.name == "doubao_image"
    assert caps.configured is False
    assert "V2_OPENAI_API_KEY" not in (caps.reason or "")

    with pytest.raises(V2ImageProviderNotConfiguredError):
        asyncio.run(
            provider.generate(
                V2ImageProviderRequest(
                    prompt_plan=ImagePromptPlan(
                        plan_id="plan_test_doubao_key_isolation",
                        mode="smart_enhance",
                        prompt="Create a poster.",
                    )
                )
            )
        )


def test_openai_image_provider_accepts_proxy_wrapped_data_url_response() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_proxy_wrapped_openai_response",
        mode="template_customize",
        prompt="Create a product poster.",
        provider_parameters={"size": "1024x1024", "output_format": "png"},
    )
    response = {"data": [{"result": {"url": "data:image/png;base64,ZmFrZS1wbmc="}}]}

    outputs = asyncio.run(
        openai_image_provider._outputs_from_openai_response(
            response,
            plan,
            index=0,
            operation="images.edit",
            reference_count=1,
        )
    )

    assert outputs[0].b64_json == "ZmFrZS1wbmc="
    assert outputs[0].mime_type == "image/png"
    assert outputs[0].metadata["response_delivery"] == "data_url"
    assert outputs[0].metadata["reference_image_count"] == 1


def test_openai_image_provider_accepts_proxy_image_url_response(monkeypatch) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\nproxy-image"

    class FakeResponse:
        content = png_bytes
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            assert url == "https://proxy.example.test/image.png?token=secret"
            return FakeResponse()

    monkeypatch.setattr(response_payloads.httpx, "AsyncClient", FakeAsyncClient)
    plan = ImagePromptPlan(
        plan_id="plan_proxy_url_openai_response",
        mode="template_customize",
        prompt="Create a product poster.",
        provider_parameters={"size": "1024x1024", "output_format": "png"},
    )
    response = {"output": [{"image_url": "https://proxy.example.test/image.png?token=secret"}]}

    outputs = asyncio.run(
        openai_image_provider._outputs_from_openai_response(
            response,
            plan,
            index=0,
            operation="images.edit",
            reference_count=1,
        )
    )

    assert base64.b64decode(outputs[0].b64_json) == png_bytes
    assert outputs[0].metadata["response_delivery"] == "url"


def test_doubao_image_provider_sends_reference_images_to_proxy_edit_endpoint(monkeypatch) -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(20, 130, 90))
    calls: list[dict[str, object]] = []

    class FakeResponse:
        status_code = 200
        text = '{"data":[{"b64_json":"ZmFrZS1wbmc="}]}'

        def json(self):
            return {"data": [{"b64_json": "ZmFrZS1wbmc="}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers=None, json=None, data=None, files=None):
            calls.append({"url": url, "headers": headers, "json": json, "data": data, "files": files})
            return FakeResponse()

    monkeypatch.setattr(doubao_image_provider.httpx, "AsyncClient", FakeAsyncClient)
    provider = asyncio.run(get_v2_image_provider("doubao_image"))

    result = asyncio.run(
        provider.generate(
            V2ImageProviderRequest(
                prompt_plan=ImagePromptPlan(
                    plan_id="plan_doubao_reference_edit",
                    mode="template_customize",
                    prompt="Create a product poster using the uploaded product.",
                    provider_parameters={"size": "1024x1024"},
                ),
                input_images=[
                    ProviderInputImage(
                        asset_id=asset_id,
                        role="subject_reference",
                        mime_type="image/png",
                        provider_input_required=True,
                    )
                ],
            )
        )
    )

    assert calls[0]["url"] == "https://aiself.example.test/v1/images/edits"
    assert calls[0]["json"] is None
    assert calls[0]["data"]["model"] == settings.doubao_image_model
    assert calls[0]["files"][0][0] == "image"
    assert result.outputs[0].b64_json == "ZmFrZS1wbmc="
    assert result.outputs[0].metadata["api_operation"] == "images.edit"
    assert result.outputs[0].metadata["reference_image_count"] == 1


def test_v2_gemini_image_provider_can_be_reenabled_by_flag() -> None:
    fresh_client()
    object.__setattr__(settings, "image_generation_provider", "gemini_image")
    object.__setattr__(settings, "gemini_api_key", "test-gemini-key")
    object.__setattr__(settings, "gemini_image_generation_enabled", True)
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_test_provider_hint_enabled",
            mode="smart_enhance",
            prompt="Create a premium tea poster.",
            provider_parameters={"provider_hint": "auto"},
        ),
        provider_hint="auto",
    )

    provider = asyncio.run(get_v2_image_provider(request.provider_hint))
    assert provider.name == "gemini_image"
    assert generation_service._requested_model(request.provider_hint) == settings.gemini_image_model


def test_v2_native_generation_preserves_uploaded_logo_reference() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="logo_reference", color=(255, 255, 255))
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_native_asset",
            mode="template_customize",
            prompt="Create a premium product image using the uploaded logo reference image.",
            provider_parameters={"count": 1},
        ),
        provider_hint="mock_image",
        input_images=[
            {
                "asset_id": asset_id,
                "role": "logo_reference",
                "constraint_strength": "required",
                "source_url": f"/api/v2/uploads/{asset_id}/content",
                "mime_type": "image/png",
                "provider_input_required": True,
                "prompt_instruction": "Use uploaded logo reference as a required brand mark.",
            }
        ],
    )

    job = asyncio.run(generation_service.create_image_job(request))

    assert job.status == "completed"
    assert job.provider_id == "mock_image"
    output = job.outputs[0]
    assert output.url.startswith("/api/v2/outputs/")
    assert output.metadata["native_v2"] is True
    assert output.metadata["native_v2_storage"] is True
    assert output.metadata["thumbnail_url"].startswith("/api/v2/image/history/")
    assert output.metadata["preview_url"].startswith("/api/v2/image/history/")
    assert output.metadata["input_images"][0]["asset_id"] == asset_id
    assert output.metadata["input_images"][0]["role"] == "logo_reference"
    assert "logo_overlay" not in str(output.metadata)
    assert Path(output.metadata["storage_path"]).exists()
    assert Path(output.metadata["preview_path"]).exists()


def test_uploaded_asset_metadata_survives_repository_reset_for_worker() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(20, 130, 90))
    assert (settings.storage_dir / "uploads" / asset_id / "asset.json").exists()
    repository.reset()
    bootstrap_v2_repository(seed_cases=True, use_persisted_index=False)

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传图片里的产品保留下来，套入高级海报模板。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [{"asset_id": asset_id, "role": "subject_reference", "constraint_strength": "required"}],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "completed"
    variables = run["prompt_plan"]["user_variables"]
    assert variables["uploaded_assets"][0]["asset_id"] == asset_id
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    assert run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"][0]["asset_id"] == asset_id


def test_missing_uploaded_asset_fails_before_text_only_generation() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传图片里的产品保留下来，套入高级海报模板。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {"asset_id": "asset_missing_for_test", "role": "subject_reference", "constraint_strength": "required"}
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "failed"
    assert "Uploaded asset binding failed" in run["next_actions"][0]
    assert run["generation_jobs"] == []


def test_requested_qr_code_is_pixel_preserved_from_uploaded_asset() -> None:
    client = fresh_client()
    qr_payload = "https://alchemy.test/qr/preserve-original"
    asset_id = upload_image_asset(
        client,
        make_qr_reference_image(qr_payload),
        role="subject_reference",
        filename="product-with-qr.png",
    )

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "保留上传图中的产品和二维码，版式使用选定案例，二维码附加在图片中合适的位置。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "subject_reference",
                    "constraint_strength": "required",
                    "notes": "产品和二维码必须沿用原图，不要重画二维码。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image", "aspect_ratio": "1024x1024"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    output = run["generation_jobs"][0]["outputs"][0]
    preservation = output["metadata"]["pixel_preservation"]["qr_code"]
    assert preservation["applied"] is True
    assert preservation["source_asset_id"] == asset_id
    assert decode_qr_from_image(Path(output["metadata"]["storage_path"])) == qr_payload


def test_information_dense_qr_preservation_repositions_unsafe_placeholder(tmp_path: Path) -> None:
    client = fresh_client()
    qr_payload = "https://alchemy.test/qr/info-dense-original"
    asset_id = upload_image_asset(
        client,
        make_qr_reference_image(qr_payload),
        role="subject_reference",
        filename="source-menu-with-qr.png",
    )

    wrong_qr = qrcode.QRCode(border=4, box_size=10)
    wrong_qr.add_data("https://alchemy.test/qr/generated-placeholder")
    wrong_qr.make(fit=True)
    wrong_qr_image = wrong_qr.make_image(fill_color="black", back_color="white").convert("RGB")
    output = Image.new("RGB", (1024, 1536), (250, 246, 238))
    output.paste(wrong_qr_image.resize((260, 260), Image.Resampling.NEAREST), (382, 360))
    encoded = BytesIO()
    output.save(encoded, format="PNG")

    result = qr_preservation_service.preserve_requested_qr_code(
        content=encoded.getvalue(),
        metadata={
            "user_prompt": "做信息完整的菜单海报，保留上传图二维码和购买优惠政策。",
            "input_images": [{"asset_id": asset_id, "role": "subject_reference"}],
            "provider_input_plan": {"reference_image_asset_ids": [asset_id]},
            "information_integrity_lock_enabled": True,
            "information_integrity_contract": {"active": True, "priority": "hard"},
        },
        output_format="png",
        mime_type="image/png",
    )

    assert result.metadata is not None
    assert result.metadata["applied"] is True
    assert result.metadata["method"] == "unsafe_output_qr_repositioned"
    assert result.metadata["placement"] == "right_lower"
    paste_box = result.metadata["paste_box"]
    assert paste_box[1] > int(1536 * 0.52)
    assert paste_box[2] - paste_box[0] <= int(1024 * 0.24)
    saved = tmp_path / "repositioned-qr.png"
    saved.write_bytes(result.content)
    assert decode_qr_from_image(saved) == qr_payload


def test_information_dense_qr_preservation_replaces_right_rail_placeholder(tmp_path: Path) -> None:
    client = fresh_client()
    qr_payload = "https://alchemy.test/qr/right-rail-original"
    asset_id = upload_image_asset(
        client,
        make_qr_reference_image(qr_payload),
        role="subject_reference",
        filename="source-menu-with-right-rail-qr.png",
    )

    wrong_qr = qrcode.QRCode(border=4, box_size=8)
    wrong_qr.add_data("https://alchemy.test/qr/generated-right-rail")
    wrong_qr.make(fit=True)
    wrong_qr_image = wrong_qr.make_image(fill_color="black", back_color="white").convert("RGB")
    output = Image.new("RGB", (1024, 1536), (250, 246, 238))
    output.paste(wrong_qr_image.resize((176, 176), Image.Resampling.NEAREST), (812, 270))
    encoded = BytesIO()
    output.save(encoded, format="PNG")

    result = qr_preservation_service.preserve_requested_qr_code(
        content=encoded.getvalue(),
        metadata={
            "user_prompt": "做信息完整的菜单海报，右侧二维码卡片保留上传图原码。",
            "input_images": [{"asset_id": asset_id, "role": "subject_reference"}],
            "provider_input_plan": {"reference_image_asset_ids": [asset_id]},
            "information_integrity_lock_enabled": True,
            "information_integrity_contract": {"active": True, "priority": "hard"},
        },
        output_format="png",
        mime_type="image/png",
    )

    assert result.metadata is not None
    assert result.metadata["applied"] is True
    assert result.metadata["method"] == "detected_output_qr_placeholder_overlay"
    paste_box = result.metadata["paste_box"]
    assert paste_box[0] >= int(1024 * 0.74)
    assert paste_box[1] < int(1536 * 0.52)
    assert result.metadata["verified_decoded"] is True
    saved = tmp_path / "right-rail-qr.png"
    saved.write_bytes(result.content)
    assert decode_qr_from_image(saved) == qr_payload


def test_v2_generation_running_job_is_reused_for_final_result() -> None:
    fresh_client()
    request = CreateImageJobRequest(
        run_id="run_observable_generation",
        prompt_plan=ImagePromptPlan(
            plan_id="plan_observable_generation",
            mode="smart_enhance",
            prompt="Create a premium tea poster.",
            provider_parameters={"count": 1},
        ),
        provider_hint="mock_image",
    )

    running = asyncio.run(generation_service.create_running_image_job(request))
    final = asyncio.run(
        generation_service.create_image_job(request, job_id=running.job_id, created_at=running.created_at)
    )

    assert running.status == "running"
    assert final.status == "completed"
    assert final.job_id == running.job_id
    assert final.created_at == running.created_at
    assert repository.get_image_job(running.job_id).status == "completed"


def test_v2_logo_notes_preserve_specific_right_chest_target() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="logo_reference", color=(255, 255, 255))
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "设计一款高端的POLO衫海报，颜色为深绿色。品牌叫 ALCOEN。",
            "mode_hint": "template_customize",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "logo_reference",
                    "constraint_strength": "strong",
                    "notes": "把logo绣在衣服上，右胸处",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    uploaded = variables["uploaded_assets"][0]
    prompt = run["prompt_plan"]["prompt"]
    negative = run["prompt_plan"]["negative_prompt"]

    assert binding["fusion_mode"] == "logo_product_surface"
    assert binding["target_surface"] == "apparel_right_chest"
    assert binding["placement_intent"]["target_label"] == "衣服右胸位置"
    assert "衣服右胸位置" in binding["prompt_instruction"]
    assert "Do not move it to the collar" in binding["prompt_instruction"]
    assert prompt.index("衣服右胸位置") < 900
    assert uploaded["brief"]["identity_requirements"][0].startswith("preserve the uploaded logo")
    assert "copied logos" not in negative
    assert "direct reproduction of reference images" not in negative


def test_creative_run_smart_enhance_creates_mock_outputs() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 2},
        },
    )
    assert response.status_code == 202
    run = response.json()
    assert run["mode"] == "smart_enhance"
    assert run["status"] == "completed"
    assert run["selected_cases"]
    assert run["prompt_plan"]["style_basis"]
    assert run["safety_decision"]["decision"] == "allow_with_warning"
    assert len(run["generation_jobs"]) == 1
    assert len(run["generation_jobs"][0]["outputs"]) == 2
    assert run["generation_jobs"][0]["outputs"][0]["review"]["decision"] == "needs_review"
    assert run["generation_jobs"][0]["outputs"][0]["review"]["score"] < 0.7

    fetched = client.get(f"/api/v2/creative/runs/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["run_id"]


def test_creative_run_template_lock_binds_uploaded_subject_asset() -> None:
    client = fresh_client()
    templates = client.get("/api/v2/templates", params={"limit": 1}).json()["templates"]
    template_case_id = templates[0]["case_id"]
    asset_id = upload_test_asset(client, role="subject_reference", color=(48, 96, 192))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传的蓝色护肤品放进这个案例模板，做高级电商主图。",
            "template_case_id": template_case_id,
            "assets": [{"asset_id": asset_id, "role": "subject_reference", "constraint_strength": "required"}],
            "output": {"count": 1, "provider_hint": "mock_image", "aspect_ratio": "4:5"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["mode"] == "template_customize"
    assert run["selected_cases"][0]["case_id"] == template_case_id
    prompt_plan = run["prompt_plan"]
    variables = prompt_plan["user_variables"]
    assert variables["template_lock_enabled"] is True
    assert variables["template_lock_contract"]["locked_case_id"] == template_case_id
    assert variables["asset_binding_plan"]["mode"] == "template_lock"
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["asset_id"] == asset_id
    assert binding["binding_slot"] == "main_subject"
    assert "composition" in binding["not_allowed_to_override"]
    assert variables["provider_input_plan"]["reference_image_count"] == 1
    assert variables["provider_input_asset_ids"] == [asset_id]
    assert "TEMPLATE LOCK" in prompt_plan["prompt"]
    assert "uploaded reference image" in prompt_plan["prompt"]
    output_metadata = run["generation_jobs"][0]["outputs"][0]["metadata"]
    assert output_metadata["input_images"][0]["asset_id"] == asset_id
    assert output_metadata["provider_input_plan"]["reference_image_count"] == 1
    review = run["generation_jobs"][0]["outputs"][0]["review"]
    assert any("Template Lock" in note for note in review["notes"])


def test_creative_run_without_template_uses_free_agent_asset_binding() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="style_reference", color=(190, 140, 80))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "给咖啡礼盒生成一张温暖高级广告图。",
            "assets": [{"asset_id": asset_id, "role": "style_reference", "constraint_strength": "required"}],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    variables = response.json()["prompt_plan"]["user_variables"]
    assert variables["template_lock_enabled"] is False
    assert variables["asset_binding_plan"]["mode"] == "free_agent"
    assert variables["asset_binding_plan"]["bindings"][0]["role"] == "style_reference"
    assert variables["provider_input_plan"]["reference_image_count"] == 1


def test_v2_creative_run_accepts_multiple_uploaded_reference_images() -> None:
    client = fresh_client()
    subject_asset_id = upload_test_asset(client, role="subject_reference", color=(48, 96, 192))
    logo_asset_id = upload_test_asset(client, role="logo_reference", color=(240, 240, 240))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传的产品主体和 Logo 结合起来，生成一张高级品牌广告图。",
            "assets": [
                {"asset_id": subject_asset_id, "role": "subject_reference", "constraint_strength": "required"},
                {"asset_id": logo_asset_id, "role": "logo_reference", "constraint_strength": "required"},
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    provider_plan = variables["provider_input_plan"]
    assert provider_plan["reference_image_count"] == 2
    assert provider_plan["reference_image_asset_ids"] == [subject_asset_id, logo_asset_id]
    input_images = run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"]
    assert [item["asset_id"] for item in input_images] == [subject_asset_id, logo_asset_id]
    assert [item["role"] for item in input_images] == ["subject_reference", "logo_reference"]


def test_v2_asset_request_role_controls_provider_input_requirement() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="style_reference", color=(48, 96, 192))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传图片里的产品作为主体，生成一张高级广告图。",
            "assets": [{"asset_id": asset_id, "role": "subject_reference", "constraint_strength": "strong"}],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    variables = response.json()["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["role"] == "subject_reference"
    assert binding["provider_input_required"] is True
    assert variables["uploaded_assets"][0]["role"] == "subject_reference"
    assert variables["uploaded_assets"][0]["brief"]["role"] == "subject_reference"
    assert variables["uploaded_assets"][0]["brief"]["visual_summary"].startswith("subject reference image")
    assert variables["provider_input_plan"]["reference_image_count"] == 1


def test_v2_single_asset_can_bind_multiple_roles_without_duplicate_provider_input() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="style_reference", color=(48, 96, 192))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传图片里的产品和标识一起放进高级广告图。",
            "assets": [
                {"asset_id": asset_id, "role": "subject_reference", "constraint_strength": "required"},
                {"asset_id": asset_id, "role": "logo_reference", "constraint_strength": "required"},
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    bindings = variables["asset_binding_plan"]["bindings"]
    assert [item["role"] for item in bindings] == ["subject_reference", "logo_reference"]
    assert variables["uploaded_assets"][0]["roles"] == ["subject_reference", "logo_reference"]
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    assert variables["provider_input_plan"]["reference_image_count"] == 1
    input_images = run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"]
    assert len(input_images) == 1
    assert input_images[0]["asset_id"] == asset_id
    assert input_images[0]["role"] == "subject_reference"
    assert "additional binding" in input_images[0]["prompt_instruction"]


def test_v2_logo_on_polo_surface_gets_structured_fusion_intent() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="logo_reference", color=(255, 255, 255))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "设计一款高端的POLO衫海报，颜色为深绿色。品牌叫 ALCOEN，要求高级感、时尚、大气，上传的 Logo 要印在衣服胸口。",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "logo_reference",
                    "constraint_strength": "required",
                    "notes": "Logo 贴到衣服胸口，不要放在海报下方或角落。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["fusion_mode"] == "logo_product_surface"
    assert binding["placement_intent"]["mode"] == "scene_surface"
    assert binding["placement_intent"]["target_surface"] == "apparel_chest_or_surface"
    assert "衣服" in binding["placement_intent"]["target_label"]
    assert binding["provider_input_required"] is True
    assert "poster footer" in binding["prompt_instruction"]
    assert "corner badge" in binding["prompt_instruction"]
    assert "uploaded_logo_visible_on_scene_surface" in binding["review_expectations"]
    provider_plan = variables["provider_input_plan"]
    assert provider_plan["reference_image_asset_ids"] == [asset_id]
    assert provider_plan["placement_targets"][0]["fusion_mode"] == "logo_product_surface"
    assert provider_plan["placement_targets"][0]["target_surface"] == "apparel_chest_or_surface"
    assert "uploaded_logo_visible_on_scene_surface" in provider_plan["review_expectations"]
    assert "logo_product_surface" in provider_plan["fusion_modes"]
    assert "uploaded reference image" in run["prompt_plan"]["prompt"]
    assert "海报下方" in run["prompt_plan"]["prompt"] or "poster footer" in run["prompt_plan"]["prompt"]
    output = run["generation_jobs"][0]["outputs"][0]
    input_image = output["metadata"]["input_images"][0]
    assert input_image["asset_id"] == asset_id
    assert input_image["fusion_mode"] == "logo_product_surface"
    assert input_image["placement_intent"]["target_surface"] == "apparel_chest_or_surface"
    review = output["review"]
    assert any("scene surface" in note for note in review["notes"])


def test_v2_logo_as_poster_corner_stays_canvas_brand_mark() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="logo_reference", color=(255, 255, 255))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "生成一张品牌发布海报，上传 Logo 作为右下角角标。",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "logo_reference",
                    "constraint_strength": "required",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    variables = response.json()["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["fusion_mode"] == "logo_canvas_brand_mark"
    assert binding["placement_intent"]["mode"] == "canvas_overlay"
    assert binding["placement_intent"]["target_surface"] == "canvas_bottom_right"
    assert "uploaded_logo_used_as_brand_mark" in binding["review_expectations"]
    provider_plan = variables["provider_input_plan"]
    assert provider_plan["placement_targets"][0]["fusion_mode"] == "logo_canvas_brand_mark"
    assert provider_plan["placement_targets"][0]["target_surface"] == "canvas_bottom_right"


def test_v2_asset_fusion_guard_survives_claude_final_prompt(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    asset_id = upload_test_asset(client, role="logo_reference", color=(255, 255, 255))

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id] if candidate_cases else fallback.selected_case_ids,
            "final_prompt": "Create a premium dark green POLO shirt poster and place the brand logo as a poster footer badge.",
            "negative_prompt": "watermark, messy logo text",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Deliberately conflicting fake decision for guard testing.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "设计一款高端深绿色 POLO 衫海报，上传的 Logo 要印在衣服胸口。",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "logo_reference",
                    "constraint_strength": "required",
                    "notes": "Logo 必须贴到衣服胸口，不要作为角标。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["orchestrator_decision"]["provider"] == "claude-code"
    prompt = run["prompt_plan"]["prompt"]
    assert "poster footer badge" in prompt
    assert "Fusion policy: logo_product_surface" in prompt
    assert "Do not place it as a poster footer" in prompt
    variables = run["prompt_plan"]["user_variables"]
    assert variables["asset_binding_plan"]["bindings"][0]["fusion_mode"] == "logo_product_surface"


def test_creative_manager_registers_openai_agents_sdk_tools() -> None:
    fresh_client()
    manager = main_module.creative_manager
    if not manager.sdk_available:
        assert manager._sdk_agent is None
        return

    assert manager._sdk_agent is not None
    tool_names = {tool.name for tool in manager._sdk_agent.tools}
    assert {"case_strategist_search", "case_detail", "prompt_safety_check"}.issubset(tool_names)


def test_output_review_agent_boundary_can_be_enabled() -> None:
    client = fresh_client()
    object.__setattr__(settings, "output_review_agent_enabled", True)

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    )

    assert response.status_code == 202
    run = response.json()
    review = run["generation_jobs"][0]["outputs"][0]["review"]
    assert review["reviewer"] == "visual-critic-agent"
    assert review["analysis_mode"] == "sdk_agent_metadata_fallback"
    assert review["agent_trace_id"]
    assert any("VisualCriticAgent" in note for note in review["notes"])

    status = client.get("/api/v2/review-agent/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True


def test_creative_run_async_entry_is_pollable() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    )

    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "planning"
    assert queued["run_id"]

    queue_status = client.get("/api/v2/task-queue/status")
    assert queue_status.status_code == 200
    assert queue_status.json()["counts"]["queued"] == 1

    processed = queue_worker_service.process_next_task_once(main_module.creative_manager, "test-worker")
    assert processed is True

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}")
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["run_id"] == queued["run_id"]
    assert run["status"] == "completed"
    assert run["prompt_plan"]
    assert run["generation_jobs"][0]["outputs"]

    completed_status = client.get("/api/v2/task-queue/status").json()
    assert completed_status["counts"]["completed"] == 1


def test_creative_run_async_user_balance_failure_stops_queue() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    )
    queued = response.json()

    class UserBalanceRuntime:
        async def complete_queued_run(self, request, run_id: str) -> CreativeRun:
            now = utc_now()
            prompt_plan = ImagePromptPlan(
                plan_id="plan_user_balance_stop",
                mode="smart_enhance",
                prompt="Create a premium skincare product hero image.",
            )
            job = ImageJob(
                job_id="job_user_balance_stop",
                run_id=run_id,
                status="failed",
                provider_id="veyra_billing",
                model="gpt-image-2",
                prompt_plan=prompt_plan,
                outputs=[],
                error={
                    "error_code": "veyra_insufficient_balance",
                    "message": "账户余额不足，请先充值后再生成。",
                    "detail": {"reason": "user_balance_insufficient"},
                    "provider": "veyra_billing",
                    "retryable": False,
                    "native_v2": True,
                },
                created_at=now,
                updated_at=now,
            )
            return CreativeRun(
                run_id=run_id,
                status="failed",
                mode="smart_enhance",
                intent_summary="premium skincare product hero image",
                prompt_plan=prompt_plan,
                generation_jobs=[job],
                trace_id="trace_upstream_wait",
                next_actions=["账户余额不足，请先充值后再生成。"],
                created_at=now,
                updated_at=now,
            )

    assert queue_worker_service.process_next_task_once(UserBalanceRuntime(), "test-worker") is True

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}")
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["status"] == "failed"
    assert run["generation_jobs"][0]["status"] == "failed"
    assert run["generation_jobs"][0]["error"]["provider"] == "veyra_billing"
    assert "账户余额不足" in run["next_actions"][0]

    queue_status = client.get("/api/v2/task-queue/status").json()
    assert queue_status["counts"]["completed"] == 1
    assert queue_status["counts"].get("queued", 0) == 0


def test_creative_run_async_preflights_user_balance_before_runtime(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_generation_charge_amount", 20.0)
    reset_billing_settings_cache()

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="low@example.com", balance=1.0, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    token = issue_session_token(42)
    auth_headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
        headers=auth_headers,
    )
    assert response.status_code == 202
    queued = response.json()

    class RuntimeShouldNotRun:
        async def complete_queued_run(self, request, run_id: str) -> CreativeRun:
            raise AssertionError("runtime should not run when Veyra balance preflight fails")

    assert queue_worker_service.process_next_task_once(RuntimeShouldNotRun(), "test-worker") is True

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}", headers=auth_headers)
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["status"] == "failed"
    assert run["generation_jobs"][0]["provider_id"] == "veyra_billing"
    assert run["generation_jobs"][0]["model"] == "veyra-billing-preflight"
    assert run["generation_jobs"][0]["error"]["error_code"] == "veyra_insufficient_balance"
    assert run["generation_jobs"][0]["error"]["provider"] == "veyra_billing"
    assert "账户余额不足" in run["next_actions"][0]

    queue_status = client.get("/api/v2/task-queue/status", headers=auth_headers).json()
    assert queue_status["counts"]["completed"] == 1
    assert queue_status["counts"].get("queued", 0) == 0


def test_task_worker_startup_releases_own_running_locks() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    )
    queued = response.json()

    claimed = task_queue_service.claim_next_task("v2-worker-1")
    assert claimed is not None
    assert claimed.run_id == queued["run_id"]

    assert task_queue_service.release_worker_running_tasks("other-worker") == 0
    queue_status = client.get("/api/v2/task-queue/status").json()
    assert queue_status["counts"]["running"] == 1

    assert task_queue_service.release_worker_running_tasks("v2-worker-1") == 1
    queue_status = client.get("/api/v2/task-queue/status").json()
    assert queue_status["counts"]["queued"] == 1
    assert queue_status["counts"].get("running", 0) == 0

    reclaimed = task_queue_service.claim_next_task("v2-worker-1")
    assert reclaimed is not None
    assert reclaimed.run_id == queued["run_id"]


def test_openai_image_operation_has_outer_timeout(monkeypatch) -> None:
    object.__setattr__(settings, "openai_image_timeout_seconds", 0.01)

    async def never_returns():
        await asyncio.sleep(60)

    with pytest.raises(TimeoutError):
        asyncio.run(openai_image_provider._call_openai_image_operation(never_returns))


def test_creative_run_async_upstream_balance_failure_waits_in_queue() -> None:
    client = fresh_client()
    response = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    )
    queued = response.json()

    class UpstreamBalanceRuntime:
        async def complete_queued_run(self, request, run_id: str) -> CreativeRun:
            now = utc_now()
            prompt_plan = ImagePromptPlan(
                plan_id="plan_upstream_wait",
                mode="smart_enhance",
                prompt="Create a premium skincare product hero image.",
            )
            job = ImageJob(
                job_id="job_upstream_wait",
                run_id=run_id,
                status="failed",
                provider_id="openai_gpt_image",
                model="gpt-image-2",
                prompt_plan=prompt_plan,
                outputs=[],
                error={
                    "error_code": "provider_runtime_error",
                    "message": "Sub2api balance is insufficient.",
                    "detail": {},
                    "provider": "openai_gpt_image",
                    "retryable": False,
                    "native_v2": True,
                },
                created_at=now,
                updated_at=now,
            )
            return CreativeRun(
                run_id=run_id,
                status="failed",
                mode="smart_enhance",
                intent_summary="premium skincare product hero image",
                prompt_plan=prompt_plan,
                generation_jobs=[job],
                trace_id="trace_upstream_wait",
                next_actions=["Sub2api balance is insufficient."],
                created_at=now,
                updated_at=now,
            )

    assert queue_worker_service.process_next_task_once(UpstreamBalanceRuntime(), "test-worker") is True

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}")
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["status"] == "generating"
    assert run["generation_jobs"][0]["status"] == "queued"
    assert run["generation_jobs"][0]["error"] is None
    assert "上游线路或额度暂时不可用" in run["next_actions"][0]

    queue_status = client.get("/api/v2/task-queue/status").json()
    assert queue_status["counts"]["queued"] == 1
    assert queue_worker_service.process_next_task_once(UpstreamBalanceRuntime(), "test-worker") is False


def test_creative_run_async_result_survives_repository_reset() -> None:
    client = fresh_client()
    queued = client.post(
        "/api/v2/creative/runs/async",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    ).json()

    assert queue_worker_service.process_next_task_once(main_module.creative_manager, "test-worker") is True
    repository.reset()

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}")
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["run_id"] == queued["run_id"]
    assert run["status"] == "completed"
    assert run["generation_jobs"][0]["outputs"]


def test_output_revision_run_preserves_source_context() -> None:
    client = fresh_client()
    original = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    ).json()
    output_id = original["generation_jobs"][0]["outputs"][0]["output_id"]

    response = client.post(
        f"/api/v2/outputs/{output_id}/revisions",
        json={"feedback": "make it ready for customer delivery", "provider_hint": "mock_image"},
    )

    assert response.status_code == 202
    revision = response.json()
    assert revision["status"] == "completed"
    assert revision["mode"] == "revision"
    source = revision["prompt_plan"]["user_variables"]["revision_source"]
    assert source["source_output_id"] == output_id
    assert source["source_run_id"] == original["run_id"]
    assert "Run with a live image provider" in revision["prompt_plan"]["prompt"]
    assert "make it ready for customer delivery" in revision["prompt_plan"]["prompt"]


def test_output_revision_async_entry_is_pollable() -> None:
    client = fresh_client()
    original = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create a premium skincare product hero image for ecommerce with soft studio lighting.",
            "output": {"aspect_ratio": "4:5", "count": 1},
        },
    ).json()
    output_id = original["generation_jobs"][0]["outputs"][0]["output_id"]

    response = client.post(
        f"/api/v2/outputs/{output_id}/revisions/async",
        json={"feedback": "make it ready for customer delivery", "provider_hint": "mock_image"},
    )

    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "planning"

    assert queue_worker_service.process_next_task_once(main_module.creative_manager, "test-worker") is True

    fetched = client.get(f"/api/v2/creative/runs/{queued['run_id']}")
    assert fetched.status_code == 200
    revision = fetched.json()
    assert revision["status"] == "completed"
    assert revision["mode"] == "revision"
    assert revision["prompt_plan"]["user_variables"]["revision_source"]["source_output_id"] == output_id


def test_template_customize_keeps_selected_case_primary() -> None:
    client = fresh_client()
    template_id = "case_github_evolinkai_ad_0001"
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Use this template for my premium tea bottle campaign.",
            "template_case_id": template_id,
            "output": {"aspect_ratio": "1:1", "count": 1},
        },
    )
    assert response.status_code == 202
    run = response.json()
    assert run["mode"] == "template_customize"
    assert run["selected_cases"][0]["case_id"] == template_id
    assert run["prompt_plan"]["user_variables"]["primary_case_id"] == template_id


def test_template_customize_forces_hand_selected_case_through_claude(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    template_id = "test_pastel_jellyfish_template"
    repository.upsert_cases(
        [
            make_prompt_case(
                template_id,
                "Pastel Jellyfish Room Goods Poster",
                "ad-creative",
                '"theme":"soft dreamy lavender jellyfish aesthetic","style":"Japanese cute editorial graphic, airy white background, pastel lilac palette, delicate handwritten notes","background":"clean white with faint pastel doodles of stars, bubbles and tiny jellyfish","orientation":"vertical poster"',
                style_tags=["studio-lighting", "minimal", "editorial", "product"],
                use_case_tags=["ad-creative", "poster", "portrait", "character"],
            )
        ]
    )

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        assert request.template_case_id == template_id
        assert fallback.selected_case_ids[0] == template_id
        assert candidate_cases[0].case_id == template_id
        assert candidate_case_details[0].case_id == template_id
        return {
            "mode": "template_customize",
            "selected_case_ids": ["case_github_evolinkai_portrait_0001"],
            "final_prompt": "Generic minimal studio portrait of a fantasy cosplayer on a plain pale seamless backdrop, no text.",
            "negative_prompt": "text, watermark, logo",
            "provider_parameters": {"count": 1, "quality": "high", "aspect_ratio": "1024x1536", "provider_hint": "mock_image"},
            "prompt_rationale": "Claude attempted to use a broader studio portrait reference.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "生成一个《原神》中茜特菈莉的真人版COSER照片",
            "mode_hint": "template_customize",
            "template_case_id": template_id,
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["orchestrator_decision"]["selected_case_ids"][0] == template_id
    assert run["selected_cases"][0]["case_id"] == template_id
    assert run["prompt_plan"]["style_basis"][0]["case_id"] == template_id
    assert run["prompt_plan"]["user_variables"]["primary_case_id"] == template_id
    prompt = run["prompt_plan"]["prompt"]
    assert prompt.startswith("TEMPLATE LOCK: the selected case is the highest-priority visual template.")
    assert "Visual Grammar Lock" in prompt
    assert "User semantic content controls" in prompt
    assert "TEMPLATE LOCK: use the hand-selected template 'Pastel Jellyfish Room Goods Poster'" in prompt
    assert "soft dreamy lavender jellyfish aesthetic" in run["prompt_plan"]["prompt"]
    assert "let the template win" in run["prompt_plan"]["prompt"]
    assert "Generic minimal studio portrait" in run["prompt_plan"]["prompt"]
    negative_terms = {term.strip().lower() for term in run["prompt_plan"]["negative_prompt"].split(",")}
    assert "text" not in negative_terms
    assert "highest-priority visual anchor" in run["prompt_plan"]["risk_notes"][0]
    grammar = run["prompt_plan"]["user_variables"]["visual_grammar_contract"]
    assert grammar["mode"] == "template_visual_grammar_lock"
    assert grammar["lock_strength"] == "strong"
    assert grammar["primary_anchor_case_id"] == template_id


def test_template_lock_claude_boundary_failure_keeps_template_but_stops_generation(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_max_attempts", 3)
    template_id = "test_osaka_editorial_template"
    repository.upsert_cases(
        [
            make_prompt_case(
                template_id,
                "Editorial Osaka Six Sweatshirt Ad",
                "ad-creative",
                (
                    "A clean editorial fashion advertisement poster on a pale powder-blue studio background with a "
                    "glossy reflective floor. The composition is vertical and minimal, dominated by oversized bold "
                    "white condensed sans-serif typography in the background reading OSAKA SIX, filling most of the "
                    "upper half behind the subject. Centered in the lower middle is an oversized forest-green "
                    "crewneck sweatshirt standing upright like a sculptural object. Leaning against the right side "
                    "of the giant sweatshirt is a slim female fashion model."
                ),
                style_tags=["editorial", "studio-lighting", "premium"],
                use_case_tags=["ad-creative", "poster"],
            ),
            make_prompt_case(
                "test_unrelated_food_case",
                "Juicy Burger Food Poster",
                "food",
                "A warm burger poster with melted cheese, fries, red ketchup, and rustic wood table.",
                style_tags=["food", "warm"],
                use_case_tags=["poster"],
            ),
            make_prompt_case(
                "test_unrelated_perfume_case",
                "Black Gold Perfume Hero",
                "ecommerce",
                "A black gold perfume bottle hero image with amber glass and dark luxury lighting.",
                style_tags=["luxury"],
                use_case_tags=["ecommerce"],
            ),
        ]
    )

    def timeout_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        assert request.template_case_id == template_id
        assert [item.case_id for item in candidate_cases] == [template_id]
        assert [item.case_id for item in candidate_case_details] == [template_id]
        raise claude_orchestrator_service.ClaudeInvocationError("claude_timeout")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", timeout_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "设计一款高端的POLO衫海报，颜色为深绿色。品牌叫 ALCOEN，要求高级感、时尚、大气。",
            "mode_hint": "template_customize",
            "template_case_id": template_id,
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "failed"
    assert run["orchestrator_decision"]["provider"] == "deterministic-fallback"
    assert run["orchestrator_decision"]["selected_case_ids"] == [template_id]
    assert [item["case_id"] for item in run["selected_cases"]] == [template_id]
    assert run["prompt_plan"] is None
    assert run["generation_jobs"] == []
    assert "deterministic creative fallback" in run["next_actions"][0]


def test_claude_required_failure_message_reports_multimodal_source_error() -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    decision = SimpleNamespace(
        provider="deterministic-fallback",
        invocation_status="checkpoint_fallback",
        fallback_reason=(
            "claude_checkpoint_error:"
            "claude_multimodal_required_unavailable:claude_reasoning_not_supported"
        ),
    )

    message = runtime_module._claude_required_failure_message(decision)

    assert message is not None
    assert "multimodal orchestration is required" in message
    assert "text-only fallback" in message


def test_template_anchor_preserves_concrete_visual_skeleton_without_copying_brand_text() -> None:
    template = make_prompt_case(
        "test_osaka_skeleton_template",
        "Editorial Osaka Six Sweatshirt Ad",
        "ad-creative",
        (
            "A clean editorial fashion advertisement poster on a pale powder-blue studio background with a glossy "
            "reflective floor. The composition is vertical and minimal, dominated by oversized bold white condensed "
            "sans-serif typography in the background reading “OSAKA SIX:” on the top line and “006 REMAINS” below, "
            "filling most of the upper half behind the subject. Centered in the lower middle is an oversized "
            "forest-green crewneck sweatshirt standing upright like a sculptural object, with soft heavy cotton "
            "fabric and extra-long sleeves pooled on the floor. Leaning against the right side of the giant "
            "sweatshirt is a slim female fashion model with long straight black hair."
        ),
        style_tags=["editorial", "studio-lighting", "premium"],
        use_case_tags=["ad-creative", "poster"],
    )
    support = make_prompt_case(
        "test_support_case_that_must_not_shape_template",
        "Black Gold Perfume Hero",
        "ecommerce",
        "A black gold perfume bottle hero image with amber glass and dark luxury lighting.",
    )

    plan = compose_prompt_plan(
        mode="template_customize",
        user_prompt="把这个模板改成深绿色高端 POLO 衫海报，品牌 ALCOEN。",
        cases=[template, support],
        output={"count": 1, "provider_hint": "mock_image"},
    )
    prompt = plan.prompt

    assert "template_visual_skeleton" in prompt
    assert "pale powder-blue studio background" in prompt
    assert "glossy reflective floor" in prompt
    assert "oversized bold white condensed sans-serif typography" in prompt
    assert "giant sweatshirt" in prompt
    assert "OSAKA SIX" not in prompt
    assert "006 REMAINS" not in prompt
    assert support.title not in prompt
    assert [item["case_id"] for item in plan.style_basis] == [template.case_id]


def test_smart_enhance_uses_auto_visual_grammar_anchor() -> None:
    client = fresh_client()
    repository.upsert_cases(
        [
            make_prompt_case(
                "test_auto_food_anchor",
                "Premium Healthy Meal Poster",
                "poster",
                (
                    "A premium healthy meal poster with a large hero food scene in the upper half, refined typography, "
                    "warm daylight, cream background, clear information modules, recipe-card hierarchy, and polished editorial layout."
                ),
                style_tags=["premium", "editorial", "food"],
                use_case_tags=["poster"],
            ),
            make_prompt_case(
                "test_auto_aux_color",
                "Cool Blue Menu Card",
                "poster",
                "A clean blue restaurant menu card with compact typography and simple grid spacing.",
                style_tags=["clean", "blue"],
                use_case_tags=["poster"],
            ),
        ]
    )
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create a premium healthy meal food poster with rich composition and clear information hierarchy.",
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["mode"] == "smart_enhance"
    assert run["selected_cases"]
    variables = run["prompt_plan"]["user_variables"]
    grammar = variables["visual_grammar_contract"]
    assert variables["visual_grammar_lock_enabled"] is True
    assert grammar["mode"] == "auto_visual_grammar_lock"
    assert grammar["lock_strength"] == "medium_strong"
    assert grammar["primary_anchor_case_id"] == run["selected_cases"][0]["case_id"]
    prompt = run["prompt_plan"]["prompt"]
    assert prompt.startswith("AUTO VISUAL GRAMMAR LOCK:")
    assert "one primary curated case as the main visual grammar anchor" in prompt
    assert "Do not average multiple cases into a vague hybrid" in prompt


def test_no_template_uploaded_layout_reference_becomes_frame_primary() -> None:
    client = fresh_client()
    repository.upsert_cases(
        [
            make_prompt_case(
                "test_polish_case",
                "Luxury Editorial Poster Polish",
                "poster",
                "A refined commercial poster with premium lighting, elegant typography, polished material texture, and controlled color mood.",
                style_tags=["premium", "editorial"],
                use_case_tags=["poster"],
            )
        ]
    )
    asset_id = upload_test_asset(client, role="composition_reference", color=(245, 220, 180))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "参考上传图片的版式和构图，做一张高级餐饮活动海报，整体更精致。",
            "assets": [{"asset_id": asset_id, "role": "composition_reference", "constraint_strength": "required"}],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    strategy = variables["asset_frame_strategy"]
    grammar = variables["visual_grammar_contract"]
    assert strategy["mode"] == "uploaded_frame_primary"
    assert strategy["uploaded_layout_may_override_case"] is True
    assert grammar["mode"] == "uploaded_frame_visual_grammar"
    assert grammar["lock_strength"] == "medium"
    assert grammar["asset_frame_strategy"]["mode"] == "uploaded_frame_primary"
    assert run["case_retrieval_plan"]["query_text"]
    assert run["selected_cases"]
    prompt = run["prompt_plan"]["prompt"]
    assert prompt.startswith("UPLOADED FRAME VISUAL GRAMMAR:")
    assert "Retrieved case" in prompt
    assert "not the frame owner" in prompt
    assert "uploaded layout/composition wins" in prompt


def test_v2_favorite_continuation_reference_keeps_current_user_edit_in_prompt() -> None:
    client = fresh_client()
    repository.upsert_cases(
        [
            make_prompt_case(
                "test_continuation_polish_case",
                "Commercial Continuation Polish",
                "poster",
                "A polished commercial image with refined lighting and controlled background detail.",
                style_tags=["commercial", "polished"],
                use_case_tags=["poster"],
            )
        ]
    )
    asset_id = upload_test_asset(
        client,
        role="composition_reference",
        color=(245, 180, 90),
        intended_use="continue_modifying_selected_favorite_image",
    )

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把主体人物手中的橙汁换成咖啡，其他画面尽量保持一致。",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "composition_reference",
                    "constraint_strength": "required",
                    "notes": (
                        "Use the selected starred V2 history image as the continuation frame: preserve its composition, "
                        "lighting, palette, spatial hierarchy, and visual rhythm while applying the current user changes."
                    ),
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    strategy = variables["asset_frame_strategy"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert strategy["mode"] == "uploaded_frame_primary"
    assert strategy["continuation_frame"] is True
    assert strategy["uploaded_layout_may_override_case"] is True
    assert binding["fusion_mode"] == "continuation_frame"
    assert "highest-priority local edit" in binding["prompt_instruction"]
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    prompt = run["prompt_plan"]["prompt"]
    assert "STARRED HISTORY CONTINUATION FRAME" in prompt
    assert "把主体人物手中的橙汁换成咖啡" in prompt
    assert "replace the conflicting reference detail" in prompt
    input_images = run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"]
    assert input_images[0]["asset_id"] == asset_id
    assert input_images[0]["fusion_mode"] == "continuation_frame"


def test_no_template_composition_reference_strong_is_visible_but_not_frame_primary_without_explicit_layout_intent() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="composition_reference", color=(245, 220, 180))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "用上传图片作为参考素材，做一张高级餐饮活动海报，整体更精致。",
            "assets": [{"asset_id": asset_id, "role": "composition_reference", "constraint_strength": "strong"}],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    strategy = variables["asset_frame_strategy"]
    assert strategy["mode"] == "case_frame_primary"
    assert strategy["uploaded_layout_may_override_case"] is False
    assert variables["visual_grammar_contract"]["mode"] == "auto_visual_grammar_lock"
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    assert variables["provider_input_plan"]["reference_image_count"] == 1
    input_images = run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"]
    assert input_images[0]["asset_id"] == asset_id
    assert input_images[0]["role"] == "composition_reference"


def test_no_template_content_source_keeps_case_frame_primary() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(180, 220, 240))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "只提取上传旧菜单里的菜品、价格、优惠和二维码，不要沿用旧版式，重新做一张高级海报。",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "subject_reference",
                    "constraint_strength": "required",
                    "notes": "旧菜单整图，只提取内容，不要沿用版式。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    strategy = variables["asset_frame_strategy"]
    grammar = variables["visual_grammar_contract"]
    assert strategy["mode"] == "case_frame_primary"
    assert strategy["content_extraction"] is True
    assert strategy["uploaded_layout_may_override_case"] is False
    assert grammar["mode"] == "auto_visual_grammar_lock"
    assert variables["asset_binding_plan"]["bindings"][0]["fusion_mode"] == "composite_content_source"
    prompt = run["prompt_plan"]["prompt"]
    assert "UPLOADED CONTENT SOURCE" in prompt
    assert "Source-layout risk detected" in prompt
    assert "do not copy its overall grid" in prompt


def test_finished_menu_source_is_content_evidence_under_template_lock() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(180, 220, 240))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上次的图片里面的食物部分摘取出来，对应的文案也摘取出来，匹配到新的海报上。二维码、页脚政策区、购买优惠和配送规则也完整保留。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "subject_reference",
                    "constraint_strength": "required",
                    "notes": "这是一张旧菜单海报整图，包含页脚政策区、优惠价格和二维码；只提取内容，不要沿用原版式。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["binding_slot"] == "semantic_content"
    assert binding["fusion_mode"] == "composite_content_source"
    assert binding["target_surface"] == "semantic_content_slots"
    assert "Do not copy its whole poster/menu/screenshot layout" in binding["prompt_instruction"]
    assert "source of extractable content" in binding["prompt_instruction"]
    assert "original information architecture" in binding["prompt_instruction"]
    assert "uploaded_source_layout_not_copied" in binding["review_expectations"]
    assert "uploaded_information_complete" in binding["review_expectations"]
    assert "business_offer_policy_preserved" in binding["review_expectations"]
    grammar = variables["visual_grammar_contract"]
    assert grammar["source_layout_risk"]["detected"] is True
    assert variables["information_integrity_lock_enabled"] is True
    assert variables["information_integrity_contract"]["active"] is True
    assert variables["information_integrity_contract"]["priority"] == "hard"
    assert "purchase rules" in variables["information_integrity_contract"]["critical_fields"][3]
    prompt = run["prompt_plan"]["prompt"]
    assert "Source-layout risk detected" in prompt
    assert "do not copy its overall grid" in prompt
    assert "CONTENT EXTRACTION LOCK" in prompt
    assert "template's own information hierarchy" in prompt
    assert "Food-to-copy, offer-to-product, and QR/CTA correspondence" in prompt
    assert "must not stretch the canvas" in prompt
    assert "full menu grid" in prompt
    assert "original information architecture" in prompt
    assert "aspect_ratio" not in run["prompt_plan"]["provider_parameters"]
    assert "copied source menu grid" in run["prompt_plan"]["negative_prompt"]
    review = run["generation_jobs"][0]["outputs"][0]["review"]
    assert "information_dense_content_may_be_incomplete" in review["detected_risks"]


def test_template_content_correspondence_keeps_full_anchor_skeleton_primary() -> None:
    template = make_prompt_case(
        "test_recipe_correspondence_template",
        "Premium Food Recipe Poster Elegant Layout",
        "poster",
        (
            "Create a premium food preparation poster with a beautiful hero dish, warm natural lighting, cream "
            "background, elegant step-by-step recipe layout, ingredients, cooking process, refined English "
            "typography, clear information modules, centered hero product hierarchy, poster layout with "
            "typography-safe space, and paper card print texture."
        ),
        summary="Premium recipe poster with hero dish, step-by-step modules, ingredients cards, QR-safe lower area.",
        style_tags=["premium", "minimal", "typography"],
        use_case_tags=["poster"],
    )

    plan = compose_prompt_plan(
        mode="template_customize",
        user_prompt=(
            "把上传图片的食物内容、文案、二维码，单独拆分出来。用这个模板样式形成新的海报。"
            "上传图片拆分出的文字与食物内容，要严格对应，不要漏信息。"
        ),
        cases=[template],
        output={"count": 1, "provider_hint": "mock_image"},
        asset_context={
            "uploaded_assets": [
                {
                    "asset_id": "asset_source_menu",
                    "filename": "source_menu.png",
                    "role": "subject_reference",
                    "brief": {
                        "visual_summary": "finished menu poster with food images, item names, prices, copy and QR",
                        "detected_text": ["menu", "offer", "qr"],
                    },
                }
            ],
            "template_lock_contract": {"locked_case_id": template.case_id},
            "asset_frame_strategy": {
                "mode": "template_frame_primary",
                "frame_source": "selected_template",
                "uploaded_layout_may_override_case": False,
                "content_extraction": True,
            },
            "asset_binding_plan": {
                "bindings": [
                    {
                        "role": "subject_reference",
                        "fusion_mode": "composite_content_source",
                        "binding_slot": "semantic_content",
                        "target_surface": "semantic_content_slots",
                        "provider_input_required": True,
                        "placement_intent": {"target_label": "内容、文案、二维码、菜品或业务信息槽"},
                        "prompt_instruction": "Treat uploaded image as content evidence only.",
                        "not_allowed_to_override": ["composition", "spatial_hierarchy", "layout_structure"],
                        "review_expectations": ["selected_template_frame_preserved", "uploaded_information_complete"],
                    }
                ],
                "provider_input_plan": {"reference_image_count": 1, "requires_image_reference": True},
            },
            "provider_input_plan": {"reference_image_count": 1, "requires_image_reference": True},
            "provider_input_images": [],
        },
    )

    prompt = plan.prompt
    assert "Reusable visual grammar from the anchor: visual skeleton:" in prompt
    assert "beautiful hero dish" in prompt
    assert "step-by-step recipe layout" in prompt
    assert "centered hero product hierarchy" in prompt
    assert "visual skele." not in prompt
    assert "Food-to-copy, offer-to-product, and QR/CTA correspondence" in prompt
    assert "must not stretch the canvas" in prompt
    assert "source frame dominant" in prompt


def test_uploaded_style_reference_with_food_copy_qr_auto_becomes_content_source() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="style_reference", color=(180, 220, 240))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "把上传图片的食物内容、文案、二维码，设计成Premium Food Recipe Poster Elegant Layout模板的样式。 替换主体：poster",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "style_reference",
                    "constraint_strength": "strong",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["role"] == "subject_reference"
    assert binding["binding_slot"] == "semantic_content"
    assert binding["fusion_mode"] == "composite_content_source"
    assert binding["provider_input_required"] is True
    assert binding["target_surface"] == "semantic_content_slots"
    assert variables["provider_input_plan"]["operation"] == "image_edit_with_reference_images"
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    assert variables["provider_input_plan"]["reference_image_count"] == 1
    assert variables["asset_frame_strategy"]["mode"] == "template_frame_primary"
    assert variables["asset_frame_strategy"]["content_extraction"] is True
    assert variables["visual_grammar_contract"]["source_layout_risk"]["detected"] is True
    assert variables["information_integrity_contract"]["priority"] == "strong"
    prompt = run["prompt_plan"]["prompt"]
    assert "UPLOADED CONTENT SOURCE" in prompt
    assert "use the selected template for the new visual frame" in prompt
    assert "Provider input images required: 1 uploaded reference image(s)" in prompt
    assert "CONTENT EXTRACTION LOCK" in prompt
    assert "INFORMATION INTEGRITY LOCK" not in prompt


def test_v2_template_style_reference_strong_is_sent_to_provider_without_overriding_template_frame() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="style_reference", color=(180, 220, 240))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "参考上传图片的整体质感，使用选定案例模板做一张高级海报。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "style_reference",
                    "constraint_strength": "strong",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    variables = run["prompt_plan"]["user_variables"]
    binding = variables["asset_binding_plan"]["bindings"][0]
    assert binding["role"] == "style_reference"
    assert binding["fusion_mode"] == "style_signal"
    assert binding["provider_input_required"] is True
    assert "composition" in binding["not_allowed_to_override"]
    assert variables["provider_input_plan"]["reference_image_asset_ids"] == [asset_id]
    assert variables["provider_input_plan"]["reference_image_count"] == 1
    assert variables["asset_frame_strategy"]["mode"] == "template_frame_primary"
    assert variables["asset_frame_strategy"]["uploaded_layout_may_override_case"] is False
    input_images = run["generation_jobs"][0]["outputs"][0]["metadata"]["input_images"]
    assert input_images[0]["asset_id"] == asset_id
    assert input_images[0]["role"] == "style_reference"


def test_product_qr_preservation_stays_subject_identity_under_template_lock() -> None:
    client = fresh_client()
    asset_id = upload_test_asset(client, role="subject_reference", color=(240, 240, 255))

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "保留上传图中的产品和二维码，版式使用选定案例，做成高级海报。",
            "template_case_id": "case_github_evolinkai_ad_0001",
            "assets": [
                {
                    "asset_id": asset_id,
                    "role": "subject_reference",
                    "constraint_strength": "required",
                    "notes": "产品和二维码必须沿用原图，不要重画二维码。",
                }
            ],
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    binding = run["prompt_plan"]["user_variables"]["asset_binding_plan"]["bindings"][0]
    assert binding["binding_slot"] == "main_subject"
    assert binding["fusion_mode"] == "subject_identity"
    assert "uploaded_subject_identity_preserved" in binding["review_expectations"]
    assert "uploaded_source_layout_not_copied" not in binding["review_expectations"]


def test_creative_run_consumes_claude_orchestrator_decision(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        assert candidate_cases
        assert candidate_case_details
        assert candidate_case_details[0].case_id == candidate_cases[0].case_id
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[-1].case_id, candidate_cases[0].case_id],
            "final_prompt": (
                "Claude final prompt: create a black-gold luxury glass bottle ecommerce hero image with dramatic "
                "rim light, centered product silhouette, transparent glass highlights, controlled negative space, "
                "and a premium commercial finish."
            ),
            "negative_prompt": "crowded background, watermark, logo",
            "provider_parameters": {"count": 1, "quality": "high", "aspect_ratio": "4:5", "provider_hint": "mock_image"},
            "prompt_rationale": "Claude selected contrasting visual references for stronger product drama.",
            "prompt_directives": {
                "visual_strategy": "black-gold luxury glass bottle campaign with a premium commercial finish",
                "case_selection_rationale": "Claude selected contrasting visual references for stronger product drama.",
                "reusable_prompt_atoms": ["dramatic rim light", "centered hero product silhouette"],
                "color_palette": ["black", "gold", "transparent glass"],
                "negative_prompt_additions": ["avoid crowded background"],
                "safety_notes": ["use cases as structure only"],
            },
            "stage_commands": [
                {"stage": "retrieve_cases", "priority": 90, "reason": "Recall only; Claude makes the final selection."},
                {"stage": "generate", "priority": 80, "reason": "Generate after prompt strategy is composed."},
            ],
            "generation_directives": {"count": 1, "quality": "high"},
            "quality_gates": {"premium_finish_required": True},
            "confidence": 0.92,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a luxury perfume ecommerce hero image with black gold glass bottle mood."},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["orchestrator_decision"]["provider"] == "claude-code"
    assert run["orchestrator_decision"]["confidence"] == 0.92
    assert run["selected_cases"][0]["case_id"] == run["orchestrator_decision"]["selected_case_ids"][0]
    assert [item["case_id"] for item in run["selected_cases"]] == run["orchestrator_decision"]["selected_case_ids"]
    assert [item["case_id"] for item in run["prompt_plan"]["style_basis"]] == run["orchestrator_decision"]["selected_case_ids"]
    assert run["orchestrator_decision"]["final_prompt"].startswith("Claude final prompt")
    assert run["orchestrator_decision"]["final_prompt"] in run["prompt_plan"]["prompt"]
    assert run["prompt_plan"]["prompt"].startswith("AUTO VISUAL GRAMMAR LOCK:")
    assert run["prompt_plan"]["user_variables"]["visual_grammar_contract"]["mode"] == "auto_visual_grammar_lock"
    assert run["prompt_plan"]["user_variables"]["prompt_source"] == "claude_final_prompt"
    assert run["prompt_plan"]["provider_parameters"]["aspect_ratio"] == "4:5"
    assert run["prompt_plan"]["provider_parameters"]["provider_hint"] == "mock_image"
    assert "avoid crowded background" in run["prompt_plan"]["negative_prompt"]
    assert "unlicensed third-party logos" in run["prompt_plan"]["negative_prompt"]
    assert len(run["generation_jobs"][0]["outputs"]) == 1


def test_creative_run_defaults_to_one_output_when_count_omitted() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal ecommerce product image.", "output": {"provider_hint": "mock_image"}},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["orchestrator_decision"]["provider"] == "deterministic-fallback"
    assert run["orchestrator_decision"]["generation_directives"]["count"] == 1
    assert run["prompt_plan"]["provider_parameters"]["count"] == 1
    assert "aspect_ratio" not in run["prompt_plan"]["provider_parameters"]
    assert len(run["generation_jobs"][0]["outputs"]) == 1


def test_creative_run_preserves_manual_aspect_ratio_only() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Minimal ecommerce product image.",
            "output": {"provider_hint": "mock_image", "aspect_ratio": "1536x1024"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    assert run["prompt_plan"]["provider_parameters"]["aspect_ratio"] == "1536x1024"


def test_creative_run_infers_a4_size_when_output_aspect_is_auto() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "以这张图为原型，生成一张极具商业化风格的A4海报。",
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    params = run["prompt_plan"]["provider_parameters"]
    assert params["size"] == "2400x3392"
    assert "aspect_ratio" not in params


def test_creative_run_manual_aspect_overrides_prompt_a4_inference() -> None:
    client = fresh_client()

    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "生成一张A4商业海报。",
            "output": {"count": 1, "provider_hint": "mock_image", "aspect_ratio": "1536x1024"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    params = run["prompt_plan"]["provider_parameters"]
    assert params["aspect_ratio"] == "1536x1024"
    assert "size" not in params


def test_exploration_mode_preserves_manual_aspect_ratio_and_adds_prompt_fallback(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def claude_changes_aspect(*, request, fallback, candidate_cases, candidate_case_details):
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "final_prompt": "Claude final prompt: exploratory portrait direction with dramatic side light.",
            "negative_prompt": "watermark",
            "provider_parameters": {
                "aspect_ratio": "1024x1536",
                "count": 1,
                "provider_hint": "mock_image",
                "quality": "high",
            },
            "generation_directives": {"aspect_ratio": "1024x1536", "count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "Claude explored a portrait crop, but user-selected output aspect is authoritative.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", claude_changes_aspect)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create an exploratory cinematic food poster.",
            "output": {
                "count": 1,
                "provider_hint": "mock_image",
                "prompt_transform_mode": "exploration",
                "aspect_ratio": "1536x1024",
            },
        },
    )

    assert response.status_code == 202
    run = response.json()
    plan = run["prompt_plan"]
    assert run["orchestrator_decision"]["provider_parameters"]["aspect_ratio"] == "1536x1024"
    assert run["orchestrator_decision"]["generation_directives"]["aspect_ratio"] == "1536x1024"
    assert plan["provider_parameters"]["aspect_ratio"] == "1536x1024"
    assert plan["user_variables"]["aspect_lock"]["locked"] is True
    assert plan["user_variables"]["aspect_lock"]["aspect_ratio"] == "3:2"
    assert "Required output aspect ratio: 3:2." in plan["prompt"]
    job_plan = run["generation_jobs"][0]["prompt_plan"]
    assert job_plan["provider_parameters"]["aspect_ratio"] == "1536x1024"
    assert job_plan["user_variables"]["prompt_transform"]["transform_mode"] == "exploration"


def test_exploration_auto_aspect_does_not_add_manual_aspect_lock(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def claude_auto_aspect(*, request, fallback, candidate_cases, candidate_case_details):
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "final_prompt": "Claude final prompt: exploratory square composition with layered props.",
            "negative_prompt": "watermark",
            "provider_parameters": {"count": 1, "provider_hint": "mock_image", "quality": "high"},
            "generation_directives": {"count": 1, "provider_hint": "mock_image"},
            "prompt_rationale": "No user aspect was selected; provider can use automatic output shape.",
            "confidence": 0.88,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", claude_auto_aspect)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Create an exploratory cinematic food poster.",
            "output": {"count": 1, "provider_hint": "mock_image", "prompt_transform_mode": "exploration"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    plan = run["prompt_plan"]
    assert "aspect_ratio" not in plan["provider_parameters"]
    assert "size" not in plan["provider_parameters"]
    assert plan["user_variables"]["aspect_lock"]["locked"] is False
    assert plan["user_variables"]["aspect_lock"]["mode"] == "auto"
    assert "Required output aspect ratio:" not in plan["prompt"]


def test_user_count_overrides_claude_provider_parameters(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def count_four_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        selected_case_id = candidate_cases[0].case_id if candidate_cases else "case_seed"
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [selected_case_id],
            "final_prompt": "Claude final prompt: premium product poster with one refined hero composition.",
            "negative_prompt": "watermark, clutter",
            "provider_parameters": {"count": 4, "provider_hint": "mock_image", "quality": "high"},
            "generation_directives": {"count": 4, "provider_hint": "mock_image"},
            "prompt_rationale": "Claude tried to request multiple variants, but user output settings are authoritative.",
            "confidence": 0.86,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", count_four_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={
            "user_prompt": "Generate exactly one premium product poster.",
            "output": {"count": 1, "provider_hint": "mock_image"},
        },
    )

    assert response.status_code == 202
    run = response.json()
    decision = run["orchestrator_decision"]
    assert decision["provider"] == "claude-code"
    assert decision["provider_parameters"]["count"] == 1
    assert decision["generation_directives"]["count"] == 1
    assert run["prompt_plan"]["provider_parameters"]["count"] == 1
    assert len(run["generation_jobs"][0]["outputs"]) == 1


def test_creative_run_stops_generation_when_required_claude_orchestrator_fails(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def failing_claude_decision(**_kwargs):
        raise RuntimeError("claude unavailable")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", failing_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal ecommerce product image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "failed"
    assert run["generation_jobs"] == []
    assert run["orchestrator_decision"]["provider"] == "deterministic-fallback"
    assert run["orchestrator_decision"]["fallback_reason"].startswith("claude_invoke_error")
    assert run["orchestrator_decision"]["invocation_status"] == "fallback"
    assert run["orchestrator_decision"]["attempts"] == 2


def test_creative_run_caches_claude_orchestrator_decision(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    calls = {"count": 0}

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        calls["count"] += 1
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "prompt_directives": {
                "visual_strategy": "cached luxury hero product direction",
                "case_selection_rationale": "best cached case",
                "reusable_prompt_atoms": ["soft studio light"],
            },
            "generation_directives": {"count": 1},
            "confidence": 0.88,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    payload = {"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}}

    first = client.post("/api/v2/creative/runs", json=payload).json()
    second = client.post("/api/v2/creative/runs", json=payload).json()

    assert calls["count"] == 1
    assert first["orchestrator_decision"]["provider"] == "claude-code"
    assert first["orchestrator_decision"]["cache_hit"] is False
    assert first["orchestrator_decision"]["invocation_status"] == "success"
    assert second["orchestrator_decision"]["provider"] == "claude-code"
    assert second["orchestrator_decision"]["cache_hit"] is True
    assert second["orchestrator_decision"]["invocation_status"] == "cache_hit"

    status = client.get("/api/v2/orchestrator/status")
    assert status.status_code == 200
    body = status.json()
    assert body["cache_entries"] == 1
    assert body["recent_invocations"][0]["cache_hit"] is True


def test_creative_run_uses_semantic_cache_for_near_duplicate_prompt(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_semantic_cache_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_semantic_cache_threshold", 0.92)
    calls = {"count": 0}

    def fake_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        calls["count"] += 1
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "final_prompt": "Claude final prompt for a luxury perfume ecommerce hero image.",
            "negative_prompt": "watermark, logo",
            "provider_parameters": {"count": 1, "quality": "high"},
            "prompt_rationale": "Near-duplicate cache source decision.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", fake_claude_decision)
    first_payload = {"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}}
    second_payload = {"user_prompt": "Create a luxury perfume ecommerce hero image!", "output": {"count": 1}}

    first = client.post("/api/v2/creative/runs", json=first_payload).json()
    second = client.post("/api/v2/creative/runs", json=second_payload).json()

    assert calls["count"] == 1
    assert first["orchestrator_decision"]["invocation_status"] == "success"
    assert second["orchestrator_decision"]["invocation_status"] == "semantic_cache_hit"
    assert second["orchestrator_decision"]["cache_hit"] is True
    assert second["orchestrator_decision"]["attempts"] == 0
    assert second["prompt_plan"]["prompt"] == first["prompt_plan"]["prompt"]


def test_creative_run_retries_transient_kimi_context_cancel(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    calls = {"count": 0}

    def flaky_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        calls["count"] += 1
        if calls["count"] == 1:
            raise claude_orchestrator_service.ClaudeInvocationError("kimi_context_canceled")
        return {
            "mode": "smart_enhance",
            "selected_case_ids": [candidate_cases[0].case_id],
            "prompt_directives": {
                "visual_strategy": "retry recovered premium product direction",
                "case_selection_rationale": "Kimi retry recovered and selected a case.",
                "reusable_prompt_atoms": ["warm rim light"],
            },
            "confidence": 0.81,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", flaky_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert calls["count"] == 2
    assert run["orchestrator_decision"]["provider"] == "claude-code"
    assert run["orchestrator_decision"]["attempts"] == 2
    assert run["orchestrator_decision"]["invocation_status"] == "success"


def test_creative_run_stops_generation_after_single_shot_claude_output_token_limit(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_max_attempts", 3)
    calls = {"count": 0}

    def token_limit_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        calls["count"] += 1
        raise claude_orchestrator_service.ClaudeInvocationError("claude_output_token_limit")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", token_limit_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert calls["count"] == 1
    assert run["status"] == "failed"
    assert run["generation_jobs"] == []
    assert run["orchestrator_decision"]["provider"] == "deterministic-fallback"
    assert run["orchestrator_decision"]["fallback_reason"] == "claude_invoke_error:claude_output_token_limit"
    assert run["orchestrator_decision"]["attempts"] == 1


def test_creative_run_stops_generation_after_single_shot_claude_timeout(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_max_attempts", 3)
    calls = {"count": 0}

    def timeout_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        calls["count"] += 1
        raise claude_orchestrator_service.ClaudeInvocationError("claude_timeout")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", timeout_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert calls["count"] == 1
    assert run["status"] == "failed"
    assert run["generation_jobs"] == []
    assert run["orchestrator_decision"]["provider"] == "deterministic-fallback"
    assert run["orchestrator_decision"]["fallback_reason"] == "claude_invoke_error:claude_timeout"
    assert run["orchestrator_decision"]["attempts"] == 1


def test_creative_run_coerces_alternate_claude_generation_shape(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "claude_orchestrator_enabled", True)

    def alternate_claude_decision(*, request, fallback, candidate_cases, candidate_case_details):
        return {
            "selected_cases": [
                {"case_id": candidate_cases[0].case_id, "reason": "closest perfume ecommerce reference"},
            ],
            "generation_directives": {
                "prompt": "Commercial hero shot of Noir Halo perfume, black-gold glass bottle, glowing liquid.",
                "negative_prompt": "logo, watermark, busy background",
                "style": "photorealistic premium product photography",
                "color_palette": "black, gold, amber glow",
            },
            "quality_gates": {"prefer_commercial_composition": True},
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_file_mode", alternate_claude_decision)
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a luxury perfume ecommerce hero image.", "output": {"count": 1}},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["orchestrator_decision"]["provider"] == "claude-code"
    assert run["selected_cases"][0]["case_id"] == run["orchestrator_decision"]["selected_case_ids"][0]
    assert "Noir Halo perfume" in run["prompt_plan"]["prompt"]
    assert "logo" in run["prompt_plan"]["negative_prompt"]


def test_claude_decision_reader_accepts_windows_path_residue(tmp_path) -> None:
    weird = tmp_path / "D_AIAlchemyOScustom_media_agent_2_0.v2_dataclaude_orchestrator_runsorc_xdecision.json"
    weird.write_text('{"mode":"smart_enhance","selected_case_ids":[],"prompt_directives":{}}', encoding="utf-8")

    parsed = claude_orchestrator_service._read_claude_decision(tmp_path)

    assert parsed is not None
    assert parsed["mode"] == "smart_enhance"


def test_claude_structured_output_parser_extracts_decision() -> None:
    parsed = claude_orchestrator_service._parse_structured_output(
        '{"type":"result","structured_output":{"mode":"smart_enhance","selected_case_ids":["case_1"],"prompt_directives":{"visual_strategy":"clean hero"}}}'
    )

    assert parsed is not None
    assert parsed["selected_case_ids"] == ["case_1"]


def test_claude_failure_classifier_detects_kimi_context_cancel() -> None:
    failure = claude_orchestrator_service._classify_claude_failure(
        'Post "https://api.kimi.com/messages?beta=true": context canceled',
        "",
        1,
    )

    assert failure == "kimi_context_canceled"


def test_claude_failure_classifier_detects_kimi_no_available_accounts() -> None:
    failure = claude_orchestrator_service._classify_claude_failure(
        '{"type":"result","subtype":"error","is_error":true,"api_error_status":503,'
        '"error":"no available accounts"}',
        "",
        1,
    )

    assert failure == "kimi_no_available_accounts"


def test_claude_failure_classifier_detects_reasoning_not_supported() -> None:
    failure = claude_orchestrator_service._classify_claude_failure(
        '{"type":"result","is_error":true,"api_error_status":400,'
        '"result":"API Error: 400 The parameter `reasoning` specified in the request are not valid: '
        'reasoning is not supported by current model."}',
        "",
        1,
    )

    assert failure == "claude_reasoning_not_supported"


def test_claude_code_fallback_model_queue_prioritizes_stronger_models() -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_fallback_model", None)

    queue = claude_orchestrator_service._claude_code_model_fallback_queue()

    assert queue[:3] == [
        "deepseek-v4-pro-260425",
        "deepseek-v4-flash-260425",
        "deepseek-v3-2-251201",
    ]
    assert queue[-1] == "doubao-lite-4k-240328"


def test_checkpoint_stage_soft_timeout_retries_kimi_before_model_fallback(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_fallback_base_url", "https://aiself.vip")
    object.__setattr__(settings, "claude_orchestrator_fallback_auth_token", "sk-test-fallback")
    object.__setattr__(settings, "claude_orchestrator_fallback_models", ("deepseek-v4-pro-260425",))
    calls: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
            }
        )
        if kwargs["stage_name"] == "intent":
            raise claude_orchestrator_service.ClaudeInvocationError("claude_soft_timeout")
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "premium lunch poster",
            "scene_goal": "redesign a food promotion image",
            "must_keep": ["offer text", "QR code"],
            "must_avoid": ["layout copying"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
    )

    assert result is not None
    assert result["stage"] == "intent"
    assert attempts == 2
    assert calls == [
        {"stage_name": "intent", "model_override": None},
        {"stage_name": "intent_micro_retry_1", "model_override": None},
    ]
    assert all(item.get("provider") != "claude-code-model-fallback" for item in trace)


def test_checkpoint_stage_emits_progress_events(monkeypatch, tmp_path) -> None:
    fresh_client()
    events: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "premium lunch poster",
            "scene_goal": "redesign a food promotion image",
            "must_keep": ["offer text", "QR code"],
            "must_avoid": ["layout copying"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
        progress_callback=events.append,
    )

    assert result is not None
    assert attempts == 1
    assert events[0]["status"] == "running"
    assert events[0]["stage_label"] == "意图与素材理解"
    assert "Claude Code 主源" in str(events[0]["message"])
    assert events[-1]["status"] == "success"
    assert events[-1]["duration_ms"] >= 0
    assert "完成" in str(events[-1]["message"])


def test_checkpoint_stage_external_primary_uses_isolated_no_effort_mode(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "deepseek-v4-pro-260425")
    calls: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
                "setting_sources_override": kwargs.get("setting_sources_override"),
                "include_effort": kwargs.get("include_effort"),
                "strip_model_fallback_env": kwargs.get("strip_model_fallback_env"),
            }
        )
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "future product launch poster",
            "scene_goal": "compose a complex commercial poster",
            "must_keep": ["clear title", "product hierarchy"],
            "must_avoid": ["garbled text"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.86,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
        progress_callback=events.append,
    )

    assert result is not None
    assert attempts == 1
    assert calls == [
        {
            "stage_name": "intent",
            "model_override": None,
            "setting_sources_override": "project,local",
            "include_effort": False,
            "strip_model_fallback_env": True,
        }
    ]
    assert trace[-1]["provider"] == "claude-code-primary"
    assert trace[-1]["model"] == "deepseek-v4-pro-260425"
    assert events[0]["provider"] == "claude-code-primary"
    assert events[0]["model"] == "deepseek-v4-pro-260425"
    assert "主源 deepseek-v4-pro-260425" in str(events[0]["message"])
    assert "Kimi 主源" not in str(events[0]["message"])


def test_claude_source_selection_keeps_deepseek_for_text_only() -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "deepseek-v4-pro-260425")
    object.__setattr__(settings, "claude_orchestrator_multimodal_model", "doubao-seed-2-0-lite-260428")

    selection = claude_orchestrator_service._select_claude_source_for_request(
        request=claude_orchestrator_service.CreateCreativeRunRequest(
            user_prompt="生成一张高端科技产品发布海报",
            output={"count": 1},
        ),
        asset_context={"uploaded_assets": [], "provider_input_images": [], "asset_binding_plan": {}},
    )

    assert selection["provider"] == "claude-code-primary"
    assert selection["model"] == "deepseek-v4-pro-260425"
    assert selection["reason"] == "default_text_primary"
    assert selection["multimodal_requested"] is False


def test_claude_source_selection_uses_doubao_for_uploaded_hard_reference() -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "deepseek-v4-pro-260425")
    object.__setattr__(settings, "claude_orchestrator_multimodal_model", "doubao-seed-2-0-lite-260428")

    selection = claude_orchestrator_service._select_claude_source_for_request(
        request=claude_orchestrator_service.CreateCreativeRunRequest(
            user_prompt="保留上传图里的产品和二维码，按选定模板重做海报",
            assets=["asset_test_product"],
            output={"count": 1},
        ),
        asset_context={
            "uploaded_assets": [{"asset_id": "asset_test_product", "role": "subject_reference"}],
            "provider_input_plan": {"reference_image_count": 1, "requires_image_reference": True},
            "provider_input_images": [
                {
                    "asset_id": "asset_test_product",
                    "role": "subject_reference",
                    "fusion_mode": "subject_identity",
                    "provider_input_required": True,
                }
            ],
            "asset_binding_plan": {"bindings": []},
        },
    )

    assert selection["provider"] == "claude-code-primary"
    assert selection["model"] == "doubao-seed-2-0-lite-260428"
    assert selection["reason"] == "provider_input_images_required"
    assert selection["multimodal_requested"] is True


def test_checkpoint_stage_uses_workspace_multimodal_primary(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "deepseek-v4-pro-260425")
    (tmp_path / "claude_source_selection.json").write_text(
        json.dumps(
            {
                "provider": "claude-code-primary",
                "model": "doubao-seed-2-0-lite-260428",
                "reason": "provider_input_images_required",
                "multimodal_requested": True,
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
                "setting_sources_override": kwargs.get("setting_sources_override"),
                "include_effort": kwargs.get("include_effort"),
                "strip_model_fallback_env": kwargs.get("strip_model_fallback_env"),
            }
        )
        return {
            "stage": "intent",
            "mode": "template_customize",
            "primary_subject": "uploaded menu poster content",
            "scene_goal": "redesign while preserving product and QR information",
            "must_keep": ["product identity", "QR code", "offer copy"],
            "must_avoid": ["copying uploaded layout"],
            "asset_requirements": ["use uploaded reference image"],
            "risk_notes": [],
            "confidence": 0.87,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
        progress_callback=events.append,
    )

    assert result is not None
    assert attempts == 1
    assert calls == [
        {
            "stage_name": "intent",
            "model_override": "doubao-seed-2-0-lite-260428",
            "setting_sources_override": "project,local",
            "include_effort": False,
            "strip_model_fallback_env": True,
        }
    ]
    assert trace[-1]["provider"] == "claude-code-primary"
    assert trace[-1]["model"] == "doubao-seed-2-0-lite-260428"
    assert trace[-1]["source_reason"] == "provider_input_images_required"
    assert events[0]["model"] == "doubao-seed-2-0-lite-260428"
    assert "主源 doubao-seed-2-0-lite-260428" in str(events[0]["message"])


def test_checkpoint_stage_required_multimodal_blocks_text_model_fallback_on_reasoning_error(
    monkeypatch, tmp_path
) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "deepseek-v4-pro-260425")
    object.__setattr__(settings, "claude_orchestrator_fallback_base_url", "https://aiself.vip")
    object.__setattr__(settings, "claude_orchestrator_fallback_auth_token", "sk-test-fallback")
    object.__setattr__(settings, "claude_orchestrator_fallback_models", ("kimi-for-coding",))
    (tmp_path / "claude_source_selection.json").write_text(
        json.dumps(
            {
                "provider": "claude-code-primary",
                "model": "doubao-seed-2-0-lite-260428",
                "reason": "provider_input_images_required",
                "multimodal_requested": True,
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []
    events: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
            }
        )
        raise claude_orchestrator_service.ClaudeInvocationError("claude_reasoning_not_supported")

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    with pytest.raises(claude_orchestrator_service.ClaudeInvocationError) as exc:
        claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
            command=["claude"],
            workspace=tmp_path,
            stage_name="intent",
            schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
            prompt="{}",
            micro_prompt="{}",
            trace=trace,
            progress_callback=events.append,
        )

    assert str(exc.value) == "claude_multimodal_required_unavailable:claude_reasoning_not_supported"
    assert calls == [{"stage_name": "intent", "model_override": "doubao-seed-2-0-lite-260428"}]
    assert trace[-1]["text_fallback_blocked"] is True
    assert trace[-1]["failure_code"] == "claude_multimodal_required_unavailable:claude_reasoning_not_supported"
    assert all(item.get("provider") != "claude-code-model-fallback" for item in trace)
    assert events[-1]["status"] == "failed"
    assert "多模态主源不可用" in str(events[-1]["message"])


def test_checkpoint_stage_kimi_primary_keeps_kimi_progress_label(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_model", "kimi-for-coding")
    events: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "premium lunch poster",
            "scene_goal": "redesign a food promotion image",
            "must_keep": ["offer text"],
            "must_avoid": ["garbled text"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)

    result, _ = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=[],
        progress_callback=events.append,
    )

    assert result is not None
    assert events[0]["provider"] == "kimi"
    assert events[0]["model"] == "kimi-for-coding"
    assert "Kimi 主源" in str(events[0]["message"])


def test_checkpoint_stage_uses_claude_code_model_fallback_after_kimi_exhaustion(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_orchestrator_fallback_base_url", "https://aiself.vip")
    object.__setattr__(settings, "claude_orchestrator_fallback_auth_token", "sk-test-fallback")
    object.__setattr__(settings, "claude_orchestrator_fallback_models", ("deepseek-v4-pro-260425", "doubao-lite-4k-240328"))
    calls: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
                "fallback_model_override": kwargs.get("fallback_model_override"),
                "env_overrides": kwargs.get("env_overrides"),
                "setting_sources_override": kwargs.get("setting_sources_override"),
                "include_effort": kwargs.get("include_effort"),
                "strip_model_fallback_env": kwargs.get("strip_model_fallback_env"),
            }
        )
        if kwargs.get("model_override") is None:
            raise claude_orchestrator_service.ClaudeInvocationError("kimi_no_available_accounts")
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "premium lunch poster",
            "scene_goal": "redesign a food promotion image",
            "must_keep": ["offer text", "QR code"],
            "must_avoid": ["layout copying"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
    )

    assert result is not None
    assert result["stage"] == "intent"
    assert attempts == 2
    assert calls[1]["model_override"] == "deepseek-v4-pro-260425"
    assert calls[1]["fallback_model_override"] == "doubao-lite-4k-240328"
    assert calls[1]["env_overrides"] == {
        "ANTHROPIC_BASE_URL": "https://aiself.vip",
        "ANTHROPIC_AUTH_TOKEN": "sk-test-fallback",
        "ANTHROPIC_API_KEY": "sk-test-fallback",
    }
    assert calls[1]["setting_sources_override"] == "project,local"
    assert calls[1]["include_effort"] is False
    assert calls[1]["strip_model_fallback_env"] is True
    assert trace[-1]["provider"] == "claude-code-model-fallback"
    assert trace[-1]["model"] == "deepseek-v4-pro-260425"


def test_checkpoint_stage_uses_model_fallback_after_compressed_kimi_retries_exhaust(monkeypatch, tmp_path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 1)
    object.__setattr__(settings, "claude_orchestrator_fallback_base_url", "https://aiself.vip")
    object.__setattr__(settings, "claude_orchestrator_fallback_auth_token", "sk-test-fallback")
    object.__setattr__(settings, "claude_orchestrator_fallback_models", ("deepseek-v4-pro-260425",))
    calls: list[dict[str, object]] = []

    def fake_claude_stage(**kwargs):
        calls.append(
            {
                "stage_name": kwargs["stage_name"],
                "model_override": kwargs.get("model_override"),
            }
        )
        if kwargs.get("model_override") is None:
            raise claude_orchestrator_service.ClaudeInvocationError("claude_soft_timeout")
        return {
            "stage": "intent",
            "mode": "smart_enhance",
            "primary_subject": "premium lunch poster",
            "scene_goal": "redesign a food promotion image",
            "must_keep": ["offer text", "QR code"],
            "must_avoid": ["layout copying"],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.82,
        }

    monkeypatch.setattr(claude_orchestrator_service, "_invoke_claude_stage_json", fake_claude_stage)
    trace: list[dict[str, object]] = []

    result, attempts = claude_orchestrator_service._invoke_checkpoint_stage_with_micro(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt="{}",
        micro_prompt="{}",
        trace=trace,
    )

    assert result is not None
    assert result["stage"] == "intent"
    assert attempts == 3
    assert calls == [
        {"stage_name": "intent", "model_override": None},
        {"stage_name": "intent_micro_retry_1", "model_override": None},
        {"stage_name": "intent_model_fallback_1", "model_override": "deepseek-v4-pro-260425"},
    ]
    assert trace[-1]["provider"] == "claude-code-model-fallback"
    assert trace[-1]["model"] == "deepseek-v4-pro-260425"
    assert trace[-1]["after_compression_retries"] is True


def test_claude_failure_classifier_ignores_successful_result_text_noise() -> None:
    stdout = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "api_error_status": None,
            "result": json.dumps(
                {
                    "mode": "smart_enhance",
                    "selected_case_ids": ["case_1"],
                    "final_prompt": "Do not treat the words sub2api or 502 in successful content as an upstream error.",
                    "negative_prompt": "watermark",
                    "provider_parameters": {"count": 1},
                    "prompt_rationale": "Successful compact JSON.",
                    "confidence": 0.8,
                }
            ),
        }
    )

    failure = claude_orchestrator_service._classify_claude_failure(stdout, "", 0)

    assert failure is None


def test_claude_failure_classifier_detects_output_token_limit() -> None:
    failure = claude_orchestrator_service._classify_claude_failure(
        "API Error: Claude's response exceeded the 2048 output token maximum. "
        "To configure this behavior, set the CLAUDE_CODE_MAX_OUTPUT_TOKENS environment variable.",
        "",
        0,
    )

    assert failure == "claude_output_token_limit"


def test_claude_failure_classifier_detects_structured_output_exhaustion() -> None:
    failure = claude_orchestrator_service._classify_claude_failure(
        '{"type":"result","subtype":"error_max_structured_output_retries","errors":["Failed to provide valid structured output after 1 attempts"]}',
        "",
        1,
    )

    assert failure == "claude_structured_output_retries_exhausted"


def test_image_job_endpoint_and_feedback() -> None:
    client = fresh_client()
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal clean ecommerce product listing image.", "output": {"count": 1}},
    ).json()
    prompt_plan = run["prompt_plan"]
    response = client.post("/api/v2/image/jobs", json={"run_id": run["run_id"], "prompt_plan": prompt_plan})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "completed"
    assert job["outputs"]

    fetched_job = client.get(f"/api/v2/image/jobs/{job['job_id']}")
    assert fetched_job.status_code == 200

    output_id = job["outputs"][0]["output_id"]
    feedback = client.post(
        f"/api/v2/outputs/{output_id}/feedback",
        json={"feedback_type": "selected", "payload": {"note": "best variant"}},
    )
    assert feedback.status_code == 201
    assert feedback.json()["output_id"] == output_id


def test_v2_media_acceleration_redirects_v2_native_output() -> None:
    client = fresh_client()
    object.__setattr__(settings, "media_acceleration_enabled", True)
    object.__setattr__(settings, "media_acceleration_base_url", "https://media.example.test")
    object.__setattr__(settings, "media_acceleration_signing_secret", "test-secret")
    object.__setattr__(settings, "media_acceleration_url_ttl_seconds", 120)
    object.__setattr__(settings, "media_acceleration_verify_remote", False)
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal clean ecommerce product listing image.", "output": {"count": 1}},
    ).json()
    prompt_plan = run["prompt_plan"]
    job = client.post("/api/v2/image/jobs", json={"run_id": run["run_id"], "prompt_plan": prompt_plan}).json()
    output_id = job["outputs"][0]["output_id"]

    response = client.get(f"/api/v2/outputs/{output_id}/download", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://media.example.test/dl/v2/outputs/")
    assert f"/{output_id}.png?" in location
    assert "expires=" in location
    assert "md5=" in location


def test_v2_media_acceleration_falls_back_when_remote_file_missing(monkeypatch) -> None:
    client = fresh_client()
    object.__setattr__(settings, "media_acceleration_enabled", True)
    object.__setattr__(settings, "media_acceleration_base_url", "https://media.example.test")
    object.__setattr__(settings, "media_acceleration_signing_secret", "test-secret")
    object.__setattr__(settings, "media_acceleration_url_ttl_seconds", 120)
    object.__setattr__(settings, "media_acceleration_verify_remote", True)

    async def fake_remote_missing(url: str) -> bool:
        return False

    monkeypatch.setattr("app.services.media_acceleration._remote_exists", fake_remote_missing)
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal clean ecommerce product listing image.", "output": {"count": 1}},
    ).json()
    job = client.post("/api/v2/image/jobs", json={"run_id": run["run_id"], "prompt_plan": run["prompt_plan"]}).json()
    output_id = job["outputs"][0]["output_id"]

    response = client.get(f"/api/v2/outputs/{output_id}/download", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert "location" not in response.headers


def test_image_history_records_generated_outputs(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Minimal clean ecommerce product listing image.", "output": {"count": 1}},
    ).json()

    response = client.get("/api/v2/image/history", params={"limit": 10})
    assert response.status_code == 200
    history = response.json()
    assert history["total"] == 1
    assert history["items"][0]["run_id"] == run["run_id"]
    assert history["items"][0]["provider_id"] == "mock_image"
    assert history["items"][0]["prompt"]
    assert history["items"][0]["url"].startswith("/api/v2/outputs/")
    assert history["items"][0]["thumbnail_url"].startswith("/api/v2/image/history/")
    assert history["items"][0]["preview_url"].startswith("/api/v2/image/history/")
    assert history["items"][0]["metadata"]["original_prompt"] == "Minimal clean ecommerce product listing image."
    assert history["items"][0]["metadata"]["final_prompt"] == history["items"][0]["prompt"]
    assert history["items"][0]["metadata"]["native_v2"] is True
    assert history["items"][0]["metadata"]["native_v2_storage"] is True


def test_v2_image_history_supports_offset_pagination(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    records = []
    for index in range(4):
        output_number = index + 1
        record = {
            "output_id": f"out_v2_page_{output_number}",
            "job_id": f"job_v2_page_{output_number}",
            "run_id": f"run_v2_page_{output_number}",
            "status": "completed",
            "provider_id": "mock_image",
            "model": "mock-image-v2",
            "mode": "smart_enhance",
            "template_case_id": None,
            "prompt": f"Paged V2 history {output_number}",
            "url": f"/api/v2/outputs/out_v2_page_{output_number}/download",
            "thumbnail_url": "",
            "score": {},
            "metadata": {"format": "png"},
            "created_at": f"2026-06-0{output_number}T09:00:00Z",
            "updated_at": f"2026-06-0{output_number}T09:00:00Z",
        }
        records.append(record)
    settings.image_history_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    first_page = client.get("/api/v2/image/history", params={"limit": 2, "offset": 0})
    second_page = client.get("/api/v2/image/history", params={"limit": 2, "offset": 2})
    veyra_page = client.get("/api/v2/veyra/history", params={"limit": 2, "offset": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert veyra_page.status_code == 200
    assert first_page.json()["total"] == 4
    assert second_page.json()["total"] == 4
    assert [item["output_id"] for item in first_page.json()["items"]] == ["out_v2_page_4", "out_v2_page_3"]
    assert [item["output_id"] for item in second_page.json()["items"]] == ["out_v2_page_2", "out_v2_page_1"]
    assert [item["output_id"] for item in veyra_page.json()["items"]] == ["out_v2_page_2", "out_v2_page_1"]


def test_image_history_thumbnail_endpoint_serves_v2_native_webp(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Luxury skincare poster.", "output": {"count": 1}},
    ).json()
    output_id = run["generation_jobs"][0]["outputs"][0]["output_id"]

    response = client.get(f"/api/v2/image/history/{output_id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert list((settings.storage_dir / "thumbnails").rglob("*.webp"))
    with Image.open(BytesIO(response.content)) as thumbnail:
        assert thumbnail.width <= 512
        assert thumbnail.height <= 512


def test_image_history_preview_endpoint_serves_v2_native_webp(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Premium coffee poster.", "output": {"count": 1}},
    ).json()
    output_id = run["generation_jobs"][0]["outputs"][0]["output_id"]

    response = client.get(f"/api/v2/image/history/{output_id}/preview")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert list((settings.storage_dir / "previews").rglob("*.webp"))
    with Image.open(BytesIO(response.content)) as preview:
        assert preview.width <= 1600
        assert preview.height <= 1600


def test_image_history_normalizes_external_thumbnail_url_to_v2_endpoint(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    record = {
        "output_id": "out_external",
        "job_id": "job_external",
        "run_id": "run_external",
        "status": "completed",
        "provider_id": "openai_gpt_image",
        "model": "gpt-image-2",
        "mode": "template_customize",
        "template_case_id": None,
        "prompt": "ALCOEN poster with uploaded logo.",
        "url": "/external/outputs/out_external/download",
        "thumbnail_url": "/external/outputs/out_external/thumbnail",
        "score": {},
        "metadata": {
            "thumbnail_url": "/external/outputs/out_external/thumbnail",
            "format": "png",
        },
        "created_at": "2026-06-06T14:16:49.093980Z",
        "updated_at": "2026-06-06T14:18:48.900239Z",
    }
    settings.image_history_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    response = client.get("/api/v2/image/history", params={"limit": 10})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["thumbnail_url"] == "/api/v2/image/history/out_external/thumbnail"


def test_image_history_derives_v2_thumbnail_url_for_non_native_record(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    record = {
        "output_id": "out_external_derived",
        "job_id": "job_external_derived",
        "run_id": "run_external_derived",
        "status": "completed",
        "provider_id": "openai_gpt_image",
        "model": "gpt-image-2",
        "mode": "template_customize",
        "template_case_id": None,
        "prompt": "External output without a stored thumbnail.",
        "url": "/external/outputs/out_external_derived/download",
        "thumbnail_url": "",
        "score": {},
        "metadata": {"format": "png"},
        "created_at": "2026-06-06T14:16:49.093980Z",
        "updated_at": "2026-06-06T14:18:48.900239Z",
    }
    settings.image_history_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    response = client.get("/api/v2/image/history", params={"limit": 10})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["thumbnail_url"] == "/api/v2/image/history/out_external_derived/thumbnail"


def test_delete_image_history_removes_v2_record_and_native_files(tmp_path) -> None:
    client = fresh_client()
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    run = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Delete history smoke image.", "output": {"count": 1}},
    ).json()
    output = run["generation_jobs"][0]["outputs"][0]
    output_id = output["output_id"]
    storage_path = Path(output["metadata"]["storage_path"])
    thumbnail_path = Path(output["metadata"]["thumbnail_path"])
    assert storage_path.exists()
    assert thumbnail_path.exists()

    response = client.delete(f"/api/v2/image/history/{output_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["removed_history_records"] == 1
    assert payload["deleted_file"] is True
    assert payload["deleted_thumbnail"] is True
    assert not storage_path.exists()
    assert not thumbnail_path.exists()
    history = client.get("/api/v2/image/history", params={"limit": 10}).json()
    assert history["total"] == 0


def test_creative_run_uses_v2_native_image_provider() -> None:
    client = fresh_client()
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a premium perfume ecommerce hero image.", "output": {"count": 1}},
    )
    assert response.status_code == 202
    run = response.json()
    job = run["generation_jobs"][0]
    output = job["outputs"][0]
    assert job["provider_id"] == "mock_image"
    assert output["url"].startswith("/api/v2/outputs/")
    assert output["metadata"]["native_v2"] is True
    assert output["metadata"]["native_v2_storage"] is True
    assert output["metadata"]["thumbnail_url"].startswith("/api/v2/image/history/")
    assert Path(output["metadata"]["storage_path"]).exists()
    assert output["review"]["decision"] in {"needs_review", "pass"}
