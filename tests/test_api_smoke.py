from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config import settings
from app.main import app
from app.repositories import repository
from app.storage import media_store


@pytest.fixture(autouse=True)
def isolate_repository_and_media_store(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    yield
    repository.reset()


def test_http_smoke_image_revision_video_and_providers():
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    session = client.post("/v1/sessions", json={"project_id": "proj_test", "title": "Smoke"})
    assert session.status_code == 200
    session_id = session.json()["id"]

    providers = client.get("/v1/providers")
    assert providers.status_code == 200
    assert any(provider["provider"] == "mock_image" for provider in providers.json()["providers"])

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "brand.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "consent": {"rights_confirmed": True},
        },
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]

    completed_asset = client.post(f"/v1/assets/{asset_id}/complete")
    assert completed_asset.status_code == 200
    assert completed_asset.json()["status"] == "ready"
    assert completed_asset.json()["material_brief"]["asset_type"] == "image"

    asset_lookup = client.get(f"/v1/assets/{asset_id}")
    assert asset_lookup.status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 4 张竖版咖啡新品海报，日系清爽风格。",
            "count": 4,
        },
    )
    assert image_job.status_code == 200
    image_body = image_job.json()
    assert image_body["status"] == "ready"
    assert len(image_body["outputs"]) == 4

    job_lookup = client.get(f"/v1/image/jobs/{image_body['id']}")
    assert job_lookup.status_code == 200

    download = client.get(image_body["outputs"][0]["url"])
    assert download.status_code == 200
    assert download.content
    thumbnail = client.get(image_body["outputs"][0]["thumbnail_url"])
    assert thumbnail.status_code == 200
    assert thumbnail.content
    assert image_body["outputs"][0]["thumbnail_url"].endswith("/thumbnail")

    revision = client.post(
        f"/v1/image/jobs/{image_body['id']}/revise",
        json={"output_id": image_body["outputs"][0]["id"], "feedback": "保持构图，把背景改成冬天。"},
    )
    assert revision.status_code == 200
    assert revision.json()["version_parent_id"] == image_body["outputs"][0]["id"]

    history = client.get(f"/v1/image/history?session_id={session_id}")
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["total"] == 5
    assert history_body["items"][0]["source"] == "repository"
    assert history_body["items"][0]["url"].startswith("/v1/outputs/")
    assert history_body["items"][0]["thumbnail_url"].endswith("/thumbnail")

    deleted_url = history_body["items"][0]["url"]
    deleted_thumbnail_url = history_body["items"][0]["thumbnail_url"]
    delete_history_item = client.delete(f"/v1/image/history/{history_body['items'][0]['id']}")
    assert delete_history_item.status_code == 200
    assert delete_history_item.json()["removed_repository_output"] is True
    assert delete_history_item.json()["deleted_thumbnail"] is True
    history_after_delete = client.get(f"/v1/image/history?session_id={session_id}")
    assert history_after_delete.status_code == 200
    assert history_after_delete.json()["total"] == 4
    assert client.get(deleted_url).status_code == 404
    assert client.get(deleted_thumbnail_url).status_code == 404

    video_job = client.post(
        "/v1/video/jobs",
        json={
            "session_id": session_id,
            "task_type": "text_to_video",
            "prompt": "让咖啡海报变成 6 秒镜头。",
        },
    )
    assert video_job.status_code == 200
    assert video_job.json()["status"] == "provider_not_configured"

    events = client.get(f"/v1/sessions/{session_id}/events")
    assert events.status_code == 200
    assert "job.status" in events.text


def test_frontend_static_app_is_served():
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert "Alchemy Media Agent" in index.text
    assert "/static/app.js" in index.text
    assert "sampleGuideModal" in index.text
    assert "Coffee Poster Atelier" in index.text
    assert "case-carousel" in index.text
    assert "/static/showcase/city-poster.jpg" in index.text
    assert "生成的结果板块" in index.text
    assert "历史图片" in index.text
    assert "调参、素材" in index.text
    assert "图片质量" in index.text
    assert "工作强度" in index.text
    assert "生图模型" in index.text
    assert "思考模型" in index.text
    assert "高级 API 配置" in index.text
    assert "改动即时生效" in index.text
    assert "自动应用" in index.text
    assert "Gemini Image" in index.text
    assert "Gemini 生图 Base URL" in index.text
    assert "Kimi 思考 Base URL" in index.text
    assert "geminiImageBaseUrlInput" in index.text
    assert "geminiImageApiKeyInput" in index.text
    assert "openaiImageModelInput" in index.text
    assert "geminiImageModelInput" in index.text
    assert "openaiLlmModelInput" in index.text
    assert "kimiLlmModelInput" in index.text
    assert "anthropicBaseUrlInput" in index.text
    assert "heroHistoryCarousel" in index.text
    assert "lightboxPromptPanel" in index.text
    assert "lightboxPromptText" in index.text
    assert "Your Work" not in index.text
    assert "assetPreview" in index.text
    assert "模型与 API" in index.text
    assert "保存配置" not in index.text
    assert "saveProviderBtn" not in index.text
    flow_labels = ["工作台", "调参、素材", "生成的结果板块", "继续修改", "历史图片", "模型与 API", "事件"]
    last_position = -1
    for label in flow_labels:
        position = index.text.index(label)
        assert position > last_position
        last_position = position
    assert 'id="countInput" type="range" min="1" max="10" step="1" value="1"' in index.text
    assert '<strong id="countValue">1</strong>' in index.text
    assert "4:5" not in index.text
    assert "后续接入" not in index.text

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert "backdrop-filter" in styles.text
    assert "sample-modal" in styles.text
    assert "global-toast" in styles.text
    assert "caseFade" in styles.text
    assert "pointer-events: none" in styles.text
    assert "pointer-events: auto" in styles.text
    assert "empty-history" in styles.text
    assert "image-lightbox" in styles.text
    assert "delete-link" in styles.text
    assert "prompt-trigger" in styles.text
    assert "lightbox-prompt-panel" in styles.text
    assert "aspect-ratio: 1 / 1" in styles.text
    assert "max-height: 560px" in styles.text
    assert "segmented.quality" in styles.text
    assert "asset-preview" in styles.text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in styles.text

    showcase = client.get("/static/showcase/city-poster.jpg")
    assert showcase.status_code == 200
    assert showcase.content

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "/v1/image/jobs" in script.text
    assert "/v1/image/history" in script.text
    assert "output.thumbnail_url || output.url" in script.text
    assert 'image.loading = "lazy"' in script.text
    assert "noticeBar" in script.text
    assert "生成中" in script.text
    assert "scrollIntoView" in script.text
    assert "unhandledrejection" in script.text
    assert "startNewSession" in script.text
    assert 'const defaultImageCount = "1"' in script.text
    assert "openSampleGuide" in script.text
    assert "applyCoffeeSample" in script.text
    assert "refreshHistory" in script.text
    assert "openImageLightbox" in script.text
    assert "toggleLightboxPrompt" in script.text
    assert "promptTextFromJob" in script.text
    assert "renderHeroHistory" in script.text
    assert "openActiveHeroHistorySlide" in script.text
    assert "state.heroHistoryItems[activeIndex]" in script.text
    assert "deleteHistoryItem" in script.text
    assert "compareHistoryItems" in script.text
    assert "historyTime" in script.text
    assert "/v1/image/history/" in script.text
    assert 'method: "DELETE"' in script.text
    assert "selectedQuality" in script.text
    assert "openaiLlmModelInput" in script.text
    assert "kimiLlmModelInput" in script.text
    assert "anthropicBaseUrlInput" in script.text
    assert "default_llm_provider" in script.text
    assert "default_llm_model" in script.text
    assert "openai_image_model" in script.text
    assert "gemini_image_model" in script.text
    assert "openai_llm_model" in script.text
    assert "kimi_llm_model" in script.text
    assert "anthropic_api_key" in script.text
    assert "gemini_image_base_url" in script.text
    assert "gemini_image_api_key" in script.text
    assert "geminiImageBaseUrlInput" in script.text
    assert "geminiImageApiKeyInput" in script.text
    assert "bindProviderAutosave" in script.text
    assert "scheduleProviderSettingsSync" in script.text
    assert "providerChangeVersion" in script.text
    assert "flushProviderSettingsSync" in script.text
    assert "modelEffectMessage" in script.text
    assert "配置已生效" in script.text
    assert "renderAssetPreview" in script.text
    assert "syncProviderSettings({ silent: false, version }).catch" in script.text
    assert "saveProviderBtn" not in script.text
    assert "保存配置" not in script.text
    assert "quality: state.selectedQuality" in script.text
    assert "work_intensity: state.selectedIntensity" in script.text
    assert "生成修改版本" in script.text
    assert "后续接入" not in script.text


def test_image_history_manifest_after_repository_reset_ignores_stray_files(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_history"}).json()["id"]

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张历史图片测试图。",
            "count": 1,
            "provider_preference": "mock_image",
        },
    )
    assert image_job.status_code == 200
    output_url = image_job.json()["outputs"][0]["url"]

    repository.reset()
    stray_dir = tmp_path / "generated_images" / "job_stray"
    stray_dir.mkdir(parents=True)
    (stray_dir / "out_stray.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    history = client.get("/v1/image/history")

    assert history.status_code == 200
    body = history.json()
    assert body["total"] == 1
    assert body["items"][0]["source"] == "manifest"
    assert body["items"][0]["url"] == output_url
    assert body["items"][0]["thumbnail_url"].endswith("/thumbnail")
    assert "User request:" in body["items"][0]["prompt"]
    assert client.get(output_url).status_code == 200
    assert client.get(body["items"][0]["thumbnail_url"]).status_code == 200

    delete = client.delete(f"/v1/image/history/{body['items'][0]['id']}")
    assert delete.status_code == 200
    assert delete.json()["ok"] is True

    after_delete = client.get("/v1/image/history")
    assert after_delete.status_code == 200
    assert after_delete.json()["total"] == 0
    assert client.get(output_url).status_code == 404


def test_image_history_is_sorted_by_created_time_descending(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    client = TestClient(app)
    records = [
        ("out_mid", "job_mid", "2026-02-01T09:00:00+00:00"),
        ("out_old", "job_old", "2026-01-01T09:00:00+00:00"),
        ("out_new", "job_new", "2026-03-01T09:00:00+00:00"),
    ]
    for output_id, job_id, created_at in records:
        path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": output_id,
                "job_id": job_id,
                "session_id": "ses_history_order",
                "url": f"/v1/outputs/{output_id}/download",
                "thumbnail_url": f"/v1/outputs/{output_id}/download",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": output_id,
                "created_at": created_at,
                "updated_at": "2026-04-01T09:00:00+00:00",
            }
        )

    response = client.get("/v1/image/history?session_id=ses_history_order")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["out_new", "out_mid", "out_old"]


def test_image_quality_request_is_preserved_in_prompt_plan():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_quality"}).json()["id"]

    response = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张质量参数测试图。",
            "count": 1,
            "quality": "low",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_plan"]["quality"] == "low"


def test_image_work_intensity_changes_prompt_planning():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_intensity"}).json()["id"]

    response = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张精品咖啡海报。",
            "count": 1,
            "work_intensity": "atelier",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    body = response.json()
    variables = body["prompt_plan"]["variables"]
    assert variables["work_intensity"] == "atelier"
    assert variables["reasoning_effort"] == "high"
    assert variables["planner"] == "local"
    assert "premium art-director planning" in variables["generation_prompt"]
    assert body["raw_response_summary"]["prompt_planning"]["work_intensity"] == "atelier"

    history = client.get(f"/v1/image/history?session_id={session_id}")
    assert history.status_code == 200
    history_item = history.json()["items"][0]
    assert history_item["work_intensity"] == "atelier"
    assert history_item["work_intensity_label"] == "臻选"


def test_openapi_paths_are_implemented():
    import yaml

    openapi_path = Path(__file__).resolve().parents[1] / "specs" / "openapi.yaml"
    expected = set(yaml.safe_load(open(openapi_path, encoding="utf-8"))["paths"])
    actual = {route.path for route in app.routes if hasattr(route, "path")}
    assert expected <= actual


def test_send_message_auto_routes_to_image_job():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_test"}).json()["id"]

    response = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "生成 1 张电商主图", "target": "auto"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_ids"]
    assert "图片生成任务" in body["assistant_text"]


def test_unknown_provider_returns_controlled_error_instead_of_500():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_test"}).json()["id"]

    image_response = client.post(
        "/v1/image/jobs",
        json={"session_id": session_id, "prompt": "生成 1 张电商主图", "provider_preference": "missing_provider"},
    )
    assert image_response.status_code == 200
    image_body = image_response.json()
    assert image_body["status"] == "failed"
    assert image_body["error"]["code"] == "provider_capability_mismatch"

    video_response = client.post(
        "/v1/video/jobs",
        json={
            "session_id": session_id,
            "task_type": "text_to_video",
            "prompt": "生成视频",
            "provider_preference": "missing_video_provider",
        },
    )
    assert video_response.status_code == 200
    video_body = video_response.json()
    assert video_body["status"] == "provider_not_configured"
    assert video_body["error"]["code"] == "provider_capability_mismatch"


def test_runtime_provider_settings_are_safe_and_take_effect(tmp_path):
    client = TestClient(app)
    original_persist = settings.persist_runtime_settings
    original_runtime_env_path = settings.runtime_env_path
    original_model = settings.default_image_model
    original_llm_model = settings.default_llm_model
    original_provider = settings.default_image_provider
    original_llm_provider = settings.default_llm_provider
    original_openai_image_model = settings.openai_image_model
    original_gemini_image_model = settings.gemini_image_model
    original_gemini_image_base_url = settings.gemini_image_base_url
    original_gemini_image_api_key = settings.gemini_image_api_key
    original_openai_llm_model = settings.openai_llm_model
    original_kimi_llm_model = settings.kimi_llm_model
    original_intensity = settings.image_work_intensity
    original_base_url = settings.openai_base_url
    original_key = settings.openai_api_key
    original_backup_provider = settings.backup_llm_provider
    original_backup_model = settings.backup_llm_model
    original_anthropic_base_url = settings.anthropic_base_url
    original_anthropic_api_key = settings.anthropic_api_key
    original_anthropic_auth_token = settings.anthropic_auth_token

    try:
        settings.persist_runtime_settings = True
        settings.runtime_env_path = tmp_path / "runtime.env"
        response = client.post(
            "/v1/runtime/provider-settings",
            json={
                "default_image_provider": "openai_gpt_image",
                "default_image_model": "gpt-image-2-test",
                "openai_image_model": "gpt-image-2-test",
                "gemini_image_model": "gemini-image-test",
                "gemini_image_api_key": "sk-test-gemini-image-only",
                "gemini_image_base_url": "https://gemini-image.example.test",
                "default_llm_provider": "anthropic",
                "default_llm_model": "kimi-for-coding-test",
                "openai_llm_model": "gpt-5.5-test",
                "kimi_llm_model": "kimi-for-coding-test",
                "image_work_intensity": "studio",
                "openai_api_key": "sk-test-runtime-only",
                "openai_base_url": "https://example.test",
                "anthropic_api_key": "sk-test-backup-only",
                "anthropic_base_url": "https://backup.example.test",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["default_image_model"] == "gpt-image-2-test"
        assert body["openai_image_model"] == "gpt-image-2-test"
        assert body["gemini_image_model"] == "gemini-image-test"
        assert body["gemini_image_base_url"] == "https://gemini-image.example.test"
        assert body["gemini_image_api_key_configured"] is True
        assert body["default_llm_provider"] == "anthropic"
        assert body["default_llm_model"] == "kimi-for-coding-test"
        assert body["openai_llm_model"] == "gpt-5.5-test"
        assert body["kimi_llm_model"] == "kimi-for-coding-test"
        assert body["backup_llm_model"] == "gpt-5.5-test"
        assert body["default_llm_model"] != body["default_image_model"]
        assert body["image_work_intensity"] == "studio"
        assert body["openai_base_url"] == "https://example.test/v1"
        assert body["anthropic_base_url"] == "https://backup.example.test"
        assert body["openai_api_key_configured"] is True
        assert body["anthropic_api_key_configured"] is True
        assert "sk-test-runtime-only" not in response.text
        assert "sk-test-backup-only" not in response.text
        assert "sk-test-gemini-image-only" not in response.text
        env_text = settings.runtime_env_path.read_text(encoding="utf-8")
        assert "DEFAULT_IMAGE_PROVIDER=openai_gpt_image" in env_text
        assert "DEFAULT_IMAGE_MODEL=gpt-image-2-test" in env_text
        assert "DEFAULT_LLM_PROVIDER=anthropic" in env_text
        assert "DEFAULT_LLM_MODEL=kimi-for-coding-test" in env_text
        assert "BACKUP_LLM_PROVIDER=openai" in env_text
        assert "BACKUP_LLM_MODEL=gpt-5.5-test" in env_text
        assert "OPENAI_BASE_URL=https://example.test/v1" in env_text
        assert "GEMINI_IMAGE_BASE_URL=https://gemini-image.example.test" in env_text
        assert "ANTHROPIC_BASE_URL=https://backup.example.test" in env_text
        assert "sk-test-runtime-only" not in env_text
        assert "sk-test-backup-only" not in env_text
        assert "sk-test-gemini-image-only" not in env_text

        providers = client.get("/v1/providers").json()
        openai_caps = next(provider for provider in providers["image"] if provider["provider"] == "openai_gpt_image")
        gemini_caps = next(provider for provider in providers["image"] if provider["provider"] == "gemini_image")
        seedance_caps = next(provider for provider in providers["video"] if provider["provider"] == "seedance")
        assert openai_caps["models"] == ["gpt-image-2-test"]
        assert gemini_caps["models"] == ["gemini-image-test"]
        assert gemini_caps["configured"] is False
        assert seedance_caps["configured"] is False
    finally:
        settings.persist_runtime_settings = original_persist
        settings.runtime_env_path = original_runtime_env_path
        settings.default_image_model = original_model
        settings.default_llm_model = original_llm_model
        settings.default_image_provider = original_provider
        settings.default_llm_provider = original_llm_provider
        settings.openai_image_model = original_openai_image_model
        settings.gemini_image_model = original_gemini_image_model
        settings.gemini_image_base_url = original_gemini_image_base_url
        settings.gemini_image_api_key = original_gemini_image_api_key
        settings.openai_llm_model = original_openai_llm_model
        settings.kimi_llm_model = original_kimi_llm_model
        settings.image_work_intensity = original_intensity
        settings.openai_base_url = original_base_url
        settings.openai_api_key = original_key
        settings.backup_llm_provider = original_backup_provider
        settings.backup_llm_model = original_backup_model
        settings.anthropic_base_url = original_anthropic_base_url
        settings.anthropic_api_key = original_anthropic_api_key
        settings.anthropic_auth_token = original_anthropic_auth_token
