import base64
import os
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient
import pytest

from app.config import settings
import app.main as main_module
from app.main import app
from app.repositories import repository
from app.storage import media_store


@pytest.fixture(autouse=True)
def isolate_repository_and_media_store(tmp_path, monkeypatch):
    original_provider = settings.default_image_provider
    original_model = settings.default_image_model
    original_openai_model = settings.openai_image_model
    original_gemini_model = settings.gemini_image_model
    original_gemini_key = settings.gemini_image_api_key
    original_gemini_base_url = settings.gemini_image_base_url
    monkeypatch.setattr(media_store, "root", tmp_path)
    settings.default_image_provider = "mock_image"
    settings.default_image_model = "mock-image"
    settings.openai_image_model = "gpt-image-2"
    settings.gemini_image_model = "gemini-3-pro-image-preview"
    settings.gemini_image_api_key = None
    settings.gemini_image_base_url = None
    repository.reset()
    yield
    repository.reset()
    settings.default_image_provider = original_provider
    settings.default_image_model = original_model
    settings.openai_image_model = original_openai_model
    settings.gemini_image_model = original_gemini_model
    settings.gemini_image_api_key = original_gemini_key
    settings.gemini_image_base_url = original_gemini_base_url


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


def test_v1_image_job_rejects_blank_prompt():
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"project_id": "proj_test", "title": "Blank Prompt"})
    assert session.status_code == 200

    response = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session.json()["id"],
            "prompt": "   ",
            "count": 1,
        },
    )

    assert response.status_code == 422


def test_asset_upload_rejects_non_image_materials():
    client = TestClient(app)

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "brief.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 128,
            "consent": {"rights_confirmed": True},
        },
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["upload_url"] == ""
    assert body["asset_id"].startswith("asset_")

    asset = client.get(f"/v1/assets/{body['asset_id']}")
    assert asset.status_code == 200
    assert asset.json()["status"] == "rejected"


def test_advanced_asset_mode_uploads_content_and_records_prompt_plan():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_advanced"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "style.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "style_reference",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True},
        },
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    assert upload.json()["upload_url"].endswith("/content")

    content = client.put(
        f"/v1/assets/{asset_id}/content",
        json={"content_base64": png_b64, "mime_type": "image/png"},
    )
    assert content.status_code == 200
    assert content.json()["status"] == "stored"

    completed = client.post(f"/v1/assets/{asset_id}/complete")
    assert completed.status_code == 200
    completed_body = completed.json()
    assert completed_body["status"] == "ready"
    assert completed_body["vision_profile"]["status"] == "ready"
    assert completed_body["vision_profile"]["image"]["width"] == 1
    assert "style_reference" in completed_body["material_brief"]["detected_roles"]

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张高级咖啡海报。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "style_reference",
                    "priority": 80,
                    "preservation": "loose",
                    "strength": 0.65,
                    "notes": "参考柔和光线和高级感",
                    "consent": {"user_confirmed_rights": True},
                },
                {
                    "asset_id": asset_id,
                    "role": "composition_reference",
                    "priority": 70,
                    "preservation": "medium",
                    "strength": 0.65,
                    "notes": "参考版式和主体位置",
                    "consent": {"user_confirmed_rights": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )
    assert image_job.status_code == 200
    body = image_job.json()
    assert body["status"] == "ready"
    assert body["asset_mode"] == "advanced"
    assert body["asset_plan"]["provider_requirements"]["needs_image_reference"] is True
    assert body["asset_plan"]["provider_input_plan"]["reference_image_count"] == 1
    assert body["asset_plan"]["assets"][0]["vision_profile_used"] is True
    assert body["prompt_plan"]["variables"]["asset_mode"] == "advanced"
    assert body["prompt_plan"]["variables"]["provider_input_plan"]["reference_image_count"] == 1
    assert body["prompt_plan"]["variables"]["asset_vision_profiles"][0]["status"] == "ready"
    assert "上传素材要求" in body["prompt_plan"]["variables"]["generation_prompt"]
    assert "素材画像" in body["prompt_plan"]["variables"]["generation_prompt"]
    assert "真实保真" not in body["prompt_plan"]["variables"]["generation_prompt"]
    assert "reference 输入" not in body["prompt_plan"]["variables"]["generation_prompt"]
    assert "provider" not in body["prompt_plan"]["variables"]["generation_prompt"]
    assert body["raw_response_summary"]["prompt_plan"]["original_prompt"] == "生成 1 张高级咖啡海报。"
    assert body["outputs"][0]["visual_review"]["review_status"] == "ready"
    assert body["outputs"][0]["visual_review"]["overall_score"] is not None

    history = client.get(f"/v1/image/history?session_id={session_id}")
    assert history.status_code == 200
    item = history.json()["items"][0]
    assert item["asset_mode"] == "advanced"
    assert item["original_prompt"] == "生成 1 张高级咖啡海报。"
    assert "上传素材要求" in item["final_prompt"]
    assert "真实保真" not in item["final_prompt"]
    assert "reference 输入" not in item["final_prompt"]
    assert {intent["role_label"] for intent in item["asset_intents"]} == {"风格参考", "构图参考"}
    assert item["asset_vision_profiles"][0]["status"] == "ready"
    assert item["provider_input_plan"]["reference_image_count"] == 1
    assert item["visual_review"]["review_status"] == "ready"


def test_chinese_corner_quote_text_is_preserved_in_prompt_plan():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_text"}).json()["id"]

    response = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张高级咖啡新品海报，画面中出现短文字「新品拿铁」。",
            "count": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_plan"]["text"]["required"] is True
    assert body["prompt_plan"]["text"]["content"] == "新品拿铁"
    assert "文字必须严格为“新品拿铁”" in body["prompt_plan"]["variables"]["generation_prompt"]
    assert "不要多余空格" in body["prompt_plan"]["variables"]["generation_prompt"]


def test_advanced_asset_vision_keeps_small_but_important_accent_colors():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_accent"}).json()["id"]
    png_b64 = _accent_reference_png_base64()

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "premium-green-gold-reference.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "style_reference",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True},
        },
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200

    completed = client.post(f"/v1/assets/{asset_id}/complete")
    assert completed.status_code == 200
    vision_style = completed.json()["vision_profile"]["style"]
    dark_accents = {item["hex"] for item in vision_style["dark_accent_colors"]}
    warm_accents = {item["hex"] for item in vision_style["warm_metal_colors"]}
    assert "#002000" in dark_accents
    assert "#ffa020" in warm_accents

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "参考上传图的高级感，生成 1 张冰拿铁海报，画面中出现短文字「新品拿铁」。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "style_reference",
                    "priority": 80,
                    "preservation": "strict",
                    "strength": 0.65,
                    "consent": {"user_confirmed_rights": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )
    assert image_job.status_code == 200
    prompt = image_job.json()["prompt_plan"]["variables"]["generation_prompt"]
    assert "深色强调 #002000" in prompt
    assert "暖金/琥珀点缀" in prompt
    assert "文字必须严格为“新品拿铁”" in prompt
    assert "asset_" not in prompt


def test_advanced_logo_mode_requires_logo_rights():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_logo"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "brand-logo.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "logo_overlay",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True},
        },
    )
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/v1/assets/{asset_id}/complete").status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张品牌海报。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "logo_overlay",
                    "priority": 100,
                    "preservation": "exact",
                    "strength": 1,
                    "consent": {"user_confirmed_rights": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )
    assert image_job.status_code == 200
    body = image_job.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "asset_consent_required"


def test_advanced_logo_on_scene_surface_uses_reference_image_not_canvas_overlay():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_logo_surface"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "alcoen-logo.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "logo_overlay",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True, "logo_or_trademark_allowed": True},
        },
    )
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/v1/assets/{asset_id}/complete").status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "设计一款高端深绿色 POLO 衫海报，品牌 ALCOEN，上传的 Logo 要印在衣服胸口。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "logo_overlay",
                    "priority": 100,
                    "preservation": "exact",
                    "strength": 1,
                    "notes": "Logo 贴到衣服胸口，不要放在海报下方或角落。",
                    "placement": {"anchor": "bottom_right", "width_ratio": 0.18},
                    "consent": {"user_confirmed_rights": True, "logo_or_trademark_allowed": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )

    assert image_job.status_code == 200
    body = image_job.json()
    assert body["status"] == "ready"
    asset = body["asset_plan"]["assets"][0]
    assert asset["provider_input_mode"] == "reference_image"
    assert asset["placement_intent"]["mode"] == "scene_surface"
    assert "衣服" in asset["placement_intent"]["target_label"]
    assert body["asset_plan"]["provider_requirements"]["needs_image_reference"] is True
    assert body["asset_plan"]["provider_requirements"]["needs_postprocess"] is False
    assert body["asset_plan"]["provider_input_plan"]["reference_image_count"] == 1
    assert body["asset_plan"]["provider_input_plan"]["postprocess_asset_ids"] == []
    assert body["postprocess_steps"] == []
    final_prompt = body["prompt_plan"]["variables"]["generation_prompt"]
    assert "衣服胸口" in final_prompt or "服装表面" in final_prompt
    assert "不要把 Logo 放到海报下方" in final_prompt
    visual_review = body["outputs"][0]["visual_review"]
    assert visual_review["review_status"] == "ready"
    assert not any(issue["code"] == "logo_overlay_missing" for issue in visual_review["issues"])


def test_advanced_logo_canvas_badge_still_uses_postprocess_overlay():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_logo_badge"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "brand-logo-badge.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "logo_overlay",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True, "logo_or_trademark_allowed": True},
        },
    )
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/v1/assets/{asset_id}/complete").status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "生成 1 张品牌海报，Logo 作为右下角角标。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "logo_overlay",
                    "priority": 100,
                    "preservation": "exact",
                    "strength": 1,
                    "notes": "仅作为右下角角标。",
                    "placement": {"anchor": "bottom_right", "width_ratio": 0.18},
                    "consent": {"user_confirmed_rights": True, "logo_or_trademark_allowed": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )

    assert image_job.status_code == 200
    body = image_job.json()
    assert body["status"] == "ready"
    asset = body["asset_plan"]["assets"][0]
    assert asset["provider_input_mode"] == "postprocess_only"
    assert asset["placement_intent"]["mode"] == "canvas_overlay"
    assert body["asset_plan"]["provider_requirements"]["needs_postprocess"] is True
    assert body["asset_plan"]["provider_input_plan"]["reference_image_count"] == 0
    assert body["asset_plan"]["provider_input_plan"]["postprocess_asset_ids"] == [asset_id]
    assert body["postprocess_steps"]
    assert body["postprocess_steps"][0]["type"] == "logo_overlay"


def _accent_reference_png_base64() -> str:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (96, 96), (224, 192, 160))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 18, 66, 78), fill=(0, 32, 0))
    draw.rectangle((30, 18, 66, 27), fill=(255, 160, 32))
    draw.rectangle((30, 69, 66, 78), fill=(255, 160, 32))
    draw.ellipse((10, 10, 30, 30), fill=(192, 160, 96))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_frontend_static_app_is_served():
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert "Alchemy Media Agent" in index.text
    assert "/static/app.js" in index.text
    assert 'href="/h5"' in index.text
    assert "手机 H5" in index.text
    assert "window.location.replace(`/h5${window.location.search}${window.location.hash}`)" in index.text
    assert 'params.get("desktop") === "1"' in index.text
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
    assert "Kimi 思考模型" in index.text
    assert "Kimi Base URL" in index.text
    assert "geminiImageBaseUrlInput" in index.text
    assert "geminiImageApiKeyInput" in index.text
    assert "openaiImageModelInput" in index.text
    assert "geminiImageModelInput" in index.text
    assert "openaiLlmModelInput" in index.text
    assert "agentLlmModelInput" in index.text
    assert "anthropicBaseUrlInput" in index.text
    assert "heroHistoryCarousel" in index.text
    assert "lightboxPromptPanel" in index.text
    assert "lightboxPromptText" in index.text
    assert "aspect-segmented" in index.text
    assert "v2-result-prompt" in index.text
    assert "v2-result-block" in index.text
    assert "Your Work" not in index.text
    assert "assetPreview" in index.text
    assert 'accept="image/*"' in index.text
    assert "仅支持图片素材" in index.text
    assert "图片、PDF、文档或表格" not in index.text
    assert "advanced-role-checks" in index.text
    assert 'rows="1"' in index.text
    assert "已确认素材授权" not in index.text
    assert "确认拥有 Logo" not in index.text
    assert "确认拥有人物肖像授权" not in index.text
    assert "模型与 API" in index.text
    assert "高级调度" in index.text
    assert "外接 Provider" in index.text
    assert "v2ImageActiveLabel" in index.text
    assert "v2OpenaiImageState" in index.text
    assert "v2BrainModelState" in index.text
    assert "v2AgentModelInput" in index.text
    assert "v2ClaudeModelInput" in index.text
    assert "v2CaseIntelligenceProviderInput" in index.text
    assert "v2ModelApplyBtn" in index.text
    assert "v2SearchThinking" in index.text
    assert "大模型思考中" in index.text
    assert index.text.find("生图 V2.0 AGENT", index.text.find('id="v2Tab"')) > index.text.find("外接 Provider")
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
    assert "v2-model-control-grid" in styles.text
    assert "thinking-spinner" in styles.text
    assert "spinThinking" in styles.text
    assert "segmented.quality" in styles.text
    assert "segmented.aspect-segmented" in styles.text
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in styles.text
    assert "grid-template-areas:" in styles.text
    assert "height: clamp(260px, 34vh, 430px)" in styles.text
    assert "overscroll-behavior: contain" in styles.text
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
    assert "resetV2Session" in script.text
    assert 'if (activeTabName === "v2")' in script.text
    assert 'setSize("")' in script.text
    assert 'const defaultImageCount = "1"' in script.text
    assert "openSampleGuide" in script.text
    assert "applyCoffeeSample" in script.text
    assert "refreshHistory" in script.text
    assert "openImageLightbox" in script.text
    assert "toggleLightboxPrompt" in script.text
    assert "promptTextFromJob" in script.text
    assert "素材视觉理解" in script.text
    assert "图片输入链路" in script.text
    assert "视觉复检" in script.text
    assert "providerInputSummaryFromJob" in script.text
    assert "图片编辑接口" in script.text
    assert "renderHeroHistory" in script.text
    assert "openActiveHeroHistorySlide" in script.text
    assert "state.heroHistoryItems[activeIndex]" in script.text
    assert "deleteHistoryItem" in script.text
    assert "compareHistoryItems" in script.text
    assert "historyTime" in script.text
    assert "const historyPageSize = 24" in script.text
    assert "const v2HistoryPageSize = 24" in script.text
    assert "/v1/image/history/" in script.text
    assert 'method: "DELETE"' in script.text
    assert "v2PromptTextFromHistory" in script.text
    assert "Claude 思考后的最终提示词" in script.text
    assert "selectedQuality" in script.text
    assert "openaiLlmModelInput" in script.text
    assert "agentLlmModelInput" in script.text
    assert "anthropicBaseUrlInput" in script.text
    assert "default_llm_provider" in script.text
    assert "selectedAssetRoles" in script.text
    assert "asset_intents: roles.map" in script.text
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
    assert "/runtime/model-settings" in script.text
    assert "applyV2ModelSettings" in script.text
    assert "function v2RequestedImageProvider" in script.text
    assert "const selected = els.v2ImageProviderInput?.value" in script.text
    assert "const imageProvider = v2RequestedImageProvider(v2State.modelSettings || {})" in script.text
    assert "v2CaseIntelligenceSourceLabel" in script.text
    assert "setV2CaseSearchThinking" in script.text
    assert "后台仍在运行，页面会持续刷新" in script.text
    assert "openV2HistoryLightbox" in script.text
    assert "v2PromptTextFromJob" in script.text
    assert "生成修改版本" in script.text
    assert "后续接入" not in script.text


def test_mobile_h5_app_is_served_independently():
    client = TestClient(app)

    h5 = client.get("/h5")
    mobile = client.get("/mobile")

    assert h5.status_code == 200
    assert mobile.status_code == 200
    assert "/mobile-static/mobile.css" in h5.text
    assert "/mobile-static/mobile.js" in h5.text
    assert "生图 V1.0 基础版" in h5.text
    assert "生图 V2.0 AGENT" in h5.text
    assert "生视频（DEMO）" in h5.text
    assert 'href="/?desktop=1"' in h5.text
    assert "桌面版" in h5.text
    assert "基础版" in h5.text
    assert "高级版" in h5.text
    assert "继续修改" in h5.text
    assert "模型与 API" in h5.text
    assert "案例展示区" in h5.text
    assert "AI Agent 生图区" in h5.text
    assert "外接 Provider" in h5.text
    assert "/static/app.js" not in h5.text
    assert "/static/showcase" not in h5.text
    assert "/mobile-static/showcase" in h5.text
    assert mobile.text == h5.text

    mobile_styles = client.get("/mobile-static/mobile.css")
    assert mobile_styles.status_code == 200
    assert "safe-area-inset-bottom" in mobile_styles.text
    assert "background-size: contain" in mobile_styles.text
    assert "--sage-deep" in mobile_styles.text
    assert "--champagne" in mobile_styles.text
    assert ".h5-advanced-panel" in mobile_styles.text
    assert ".h5-quick-guide" in mobile_styles.text

    mobile_script = client.get("/mobile-static/mobile.js")
    assert mobile_script.status_code == 200
    assert "/creative/runs/async" in mobile_script.text
    assert "/v1/image/jobs" in mobile_script.text
    assert "setupH5AdvancedPanels" in mobile_script.text
    assert "createH5AdvancedPanel" in mobile_script.text
    assert "参数、素材、修图、历史、模型/API 和事件" not in mobile_script.text
    assert "中枢输出、历史、Provider 和调度" not in mobile_script.text
    assert "runV2Creative" in mobile_script.text
    assert "function v2RequestedImageProvider" in mobile_script.text
    assert "const imageProvider = v2RequestedImageProvider(v2State.modelSettings || {})" in mobile_script.text
    assert "imageAssetPayload" in mobile_script.text
    assert "const historyPageSize = 24" in mobile_script.text
    assert "const v2HistoryPageSize = 24" in mobile_script.text
    assert "deleteV2HistoryItem" in mobile_script.text
    assert "share-poster-download" not in mobile_script.text
    assert "长按图片保存" in mobile_script.text
    assert "复制原图链接" in mobile_script.text


def test_image_share_landing_page_has_wechat_friendly_metadata():
    client = TestClient(app)

    response = client.get(
        "/share/image",
        params={
            "image": "/v1/outputs/out_share/download",
            "thumb": "/v1/outputs/out_share/thumbnail",
            "title": "轻食海报 <script>",
            "desc": "分享给微信好友",
        },
    )

    assert response.status_code == 200
    assert 'property="og:title"' in response.text
    assert "轻食海报 &lt;script&gt;" in response.text
    assert "<script>" not in response.text
    assert 'property="og:image"' in response.text
    assert "http://testserver/share/poster?" in response.text
    assert "打开 Alchemy" in response.text
    assert "下载分享图" in response.text
    assert "长按分享图保存，扫码直接查看原图。" in response.text


def test_image_share_poster_returns_downloadable_png():
    client = TestClient(app)

    response = client.get(
        "/share/poster",
        params={
            "image": "/v1/outputs/out_missing/download",
            "thumb": "/v1/outputs/out_missing/thumbnail",
            "title": "轻食海报",
            "desc": "微信扫码查看完整图片",
            "url": "http://testserver/share/image?image=/static/showcase/city-poster.jpg",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(response.content) > 10_000


def test_image_share_poster_qr_defaults_to_direct_image_url(monkeypatch):
    client = TestClient(app)
    captured = {}

    def fake_render_share_poster(**kwargs):
        captured["share_url"] = kwargs["share_url"]
        return b"\x89PNG\r\n\x1a\nfake"

    monkeypatch.setattr(main_module, "_render_share_poster", fake_render_share_poster)

    response = client.get(
        "/share/poster",
        params={
            "image": "/v1/outputs/out_share/download",
            "thumb": "/v1/outputs/out_share/thumbnail",
        },
    )

    assert response.status_code == 200
    assert captured["share_url"] == "http://testserver/v1/outputs/out_share/download"


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
    assert "创作目标：" in body["items"][0]["prompt"]
    assert client.get(output_url).status_code == 200
    assert client.get(body["items"][0]["thumbnail_url"]).status_code == 200

    delete = client.delete(f"/v1/image/history/{body['items'][0]['id']}")
    assert delete.status_code == 200
    assert delete.json()["ok"] is True

    after_delete = client.get("/v1/image/history")
    assert after_delete.status_code == 200
    assert after_delete.json()["total"] == 0
    assert client.get(output_url).status_code == 404


def test_image_history_recovers_generated_files_missing_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    client = TestClient(app)

    manifest_id = "out_manifest123456"
    manifest_path = media_store.output_path(job_id="job_manifest123456", output_id=manifest_id, output_format="png")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    media_store.save_history_record(
        {
            "id": manifest_id,
            "job_id": "job_manifest123456",
            "url": f"/v1/outputs/{manifest_id}/download",
            "thumbnail_url": f"/v1/outputs/{manifest_id}/thumbnail",
            "format": "png",
            "provider": "mock_image",
            "model": "mock-image-v1",
            "prompt": "manifest record",
            "created_at": "2026-01-01T09:00:00+00:00",
            "updated_at": "2026-01-01T09:00:00+00:00",
        }
    )

    recovered_id = "out_recovered123456"
    recovered_path = media_store.output_path(job_id="job_recovered123456", output_id=recovered_id, output_format="png")
    recovered_path.parent.mkdir(parents=True, exist_ok=True)
    recovered_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    os.utime(recovered_path, (2000000000, 2000000000))

    response = client.get("/v1/image/history?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [recovered_id, manifest_id]
    assert body["items"][0]["source"] == "filesystem"
    assert "从本地输出目录恢复" in body["items"][0]["prompt"]
    assert client.get(body["items"][0]["url"]).status_code == 200
    assert client.get(body["items"][0]["thumbnail_url"]).status_code == 200


def test_image_history_excludes_v2_bridge_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "alchemy_v2_bridge"}).json()["id"]

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "V2 bridge generated image should stay out of V1 history.",
            "count": 1,
            "provider_preference": "mock_image",
            "idempotency_key": "v2:run_test:plan_test",
        },
    )
    assert image_job.status_code == 200

    history = client.get("/v1/image/history")
    assert history.status_code == 200
    assert history.json()["total"] == 0

    repository.reset()
    output_path = media_store.output_path(job_id="job_bridge_manifest", output_id="out_bridge_manifest", output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    media_store.save_history_record(
        {
            "id": "out_bridge_manifest",
            "job_id": "job_bridge_manifest",
            "session_id": session_id,
            "url": "/v1/outputs/out_bridge_manifest/download",
            "thumbnail_url": "/v1/outputs/out_bridge_manifest/thumbnail",
            "format": "png",
            "provider": "mock_image",
            "model": "mock-image-v1",
            "source_app": "alchemy_v2_bridge",
            "idempotency_key": "v2:run_manifest:plan_manifest",
            "prompt": "bridge manifest",
            "created_at": "2026-04-01T09:00:00+00:00",
            "updated_at": "2026-04-01T09:00:00+00:00",
        }
    )

    manifest_history = client.get("/v1/image/history")
    assert manifest_history.status_code == 200
    assert manifest_history.json()["total"] == 0


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
    assert "高级创意指导" in variables["generation_prompt"]
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
        assert gemini_caps["configured"] is True
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
