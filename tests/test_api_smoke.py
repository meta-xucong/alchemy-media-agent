import base64
import json
import os
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient
import pytest

from app.config import settings
import app.main as main_module
import app.services.image_service as image_service_module
import app.services.alchemy_lab as alchemy_lab_module
import app.services.alchemy_lab_quality as alchemy_lab_quality_module
import app.services.alchemy_lab_intent_director as alchemy_lab_intent_module
from app.main import app
from app.providers.base import ProviderRuntimeError
from app.providers.mock_image import MockImageProvider
from app.repositories import repository
from app.services.alchemy_lab import lab_store
from app.storage import media_store


def count_cards(board: dict, status: str = "") -> int:
    return sum(
        1
        for group in board.get("groups", [])
        for card in group.get("cards", [])
        if not status or card.get("status") == status
    )


def tiny_png_b64(color=(220, 60, 70)) -> str:
    try:
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nG"
            "P4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )


@pytest.fixture(autouse=True)
def isolate_repository_and_media_store(tmp_path, monkeypatch):
    original_provider = settings.default_image_provider
    original_model = settings.default_image_model
    original_openai_model = settings.openai_image_model
    original_gemini_model = settings.gemini_image_model
    original_gemini_key = settings.gemini_image_api_key
    original_gemini_base_url = settings.gemini_image_base_url
    original_gemini_enabled = settings.gemini_image_generation_enabled
    original_mock_enabled = settings.mock_image_provider_enabled
    original_veyra_usage_path = settings.veyra_usage_path
    original_lab_llm_enabled = settings.lab_llm_enabled
    monkeypatch.setattr(media_store, "root", tmp_path)
    monkeypatch.setitem(image_service_module.registry.image_providers, "mock_image", MockImageProvider())
    settings.default_image_provider = "mock_image"
    settings.default_image_model = "mock-image"
    settings.mock_image_provider_enabled = True
    settings.openai_image_model = "gpt-image-2"
    settings.gemini_image_model = "gemini-3-pro-image-preview"
    settings.gemini_image_api_key = None
    settings.gemini_image_base_url = None
    settings.gemini_image_generation_enabled = False
    settings.veyra_usage_path = tmp_path / "veyra_usage.jsonl"
    settings.lab_llm_enabled = False
    repository.reset()
    lab_store.reset()
    yield
    repository.reset()
    lab_store.reset()
    settings.default_image_provider = original_provider
    settings.default_image_model = original_model
    settings.openai_image_model = original_openai_model
    settings.gemini_image_model = original_gemini_model
    settings.gemini_image_api_key = original_gemini_key
    settings.gemini_image_base_url = original_gemini_base_url
    settings.gemini_image_generation_enabled = original_gemini_enabled
    settings.mock_image_provider_enabled = original_mock_enabled
    settings.veyra_usage_path = original_veyra_usage_path
    settings.lab_llm_enabled = original_lab_llm_enabled


def _completed_image_job(client: TestClient, response, *, headers: dict[str, str] | None = None, max_attempts: int = 30) -> dict:
    assert response.status_code == 200
    body = response.json()
    for _ in range(max_attempts):
        if body["status"] != "generating":
            return body
        lookup = client.get(f"/v1/image/jobs/{body['id']}", headers=headers or {})
        assert lookup.status_code == 200
        body = lookup.json()
    raise AssertionError(f"Image job did not reach a terminal state: {body['id']}")


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
    image_body = _completed_image_job(client, image_job)
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
    revision_body = _completed_image_job(client, revision)
    assert revision_body["version_parent_id"] == image_body["outputs"][0]["id"]

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


def test_image_provider_errors_redact_api_keys(monkeypatch):
    secret = "sk-liveSECRET1234567890abcdef"
    masked_secret = "sk-liveS******************cdef"

    class SecretFailingProvider(MockImageProvider):
        async def generate(self, request):
            raise ProviderRuntimeError(
                f"Error code: 401 - Incorrect API key provided: {secret}. invalid_api_key",
                provider=self.name,
                detail={
                    "message": f"AuthenticationError: Incorrect API key provided: {secret}",
                    "nested": {"raw": f"provider said {secret}", "masked": f"provider said {masked_secret}"},
                },
            )

    monkeypatch.setitem(image_service_module.registry.image_providers, "mock_image", SecretFailingProvider())
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"project_id": "proj_test", "title": "Secret redaction"})
    assert session.status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={"session_id": session.json()["id"], "prompt": "测试密钥脱敏", "count": 1},
    )
    body = _completed_image_job(client, image_job)
    serialized = json.dumps(body, ensure_ascii=False)

    assert body["status"] == "failed"
    assert secret not in serialized
    assert masked_secret not in serialized
    assert "sk-***" in serialized


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


def test_alchemy_lab_lists_rare_style_presets():
    client = TestClient(app)

    response = client.get("/api/lab/rare-style-explorer/styles")

    assert response.status_code == 200
    body = response.json()
    assert body["limits"]["maxTotalImages"] == 12
    assert body["limits"]["maxImagesPerStyle"] == 4
    assert body["limits"]["maxGenerationIntervalSeconds"] == 60
    assert body["limits"]["styleLibrarySize"] >= 620
    assert len(body["styles"]) >= 620
    assert any(style["id"] == "M001" for style in body["styles"])
    assert {family["id"] for family in body["families"]} >= {"film", "fashion", "material"}
    assert {mode["id"] for mode in body["modes"]} >= {"minimal", "product", "character", "poster"}
    assert all(style["prompt_directives"] for style in body["styles"])


def test_alchemy_lab_semantic_style_search_ranks_and_scores():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/styles/search",
        json={"query_text": "端午节祝贺海报，中式节日，绿色粽子，竖版", "limit": 12},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] in {"local_scorer", "llm_rerank"}
    assert body["styles"]
    assert len(body["styles"]) <= 12
    assert all("score" in style for style in body["styles"])
    assert all("why_selected" in style for style in body["styles"])
    scores = [style["score"] for style in body["styles"]]
    assert scores == sorted(scores, reverse=True)
    assert body["styles"][0]["id"] == "G049"
    assert "食物饮品" in body["styles"][0]["why_selected"]
    combined = " ".join(" ".join([style["display_name"], style["short_description"], style["category"], style.get("why_selected", "")]) for style in body["styles"][:6])
    assert any(marker in combined for marker in ["海报", "节日", "工艺", "平面", "绿色", "传统"])


def test_alchemy_lab_semantic_style_search_handles_noise_and_long_queries():
    client = TestClient(app)

    nonsense = client.post(
        "/api/lab/rare-style-explorer/styles/search",
        json={"query_text": "!!!@@@ ### xyznotreal 𠀀𠮷", "limit": 12},
    )

    assert nonsense.status_code == 200
    nonsense_body = nonsense.json()
    assert nonsense_body["source"] == "local_scorer"
    assert nonsense_body["styles"] == []
    assert nonsense_body["query_features"] == []

    long_query = "端午节祝贺海报 中式绿色粽子 竖版 " * 80
    long_response = client.post(
        "/api/lab/rare-style-explorer/styles/search",
        json={"query_text": long_query, "limit": 12},
    )

    assert long_response.status_code == 200
    long_body = long_response.json()
    assert long_body["styles"]
    assert long_body["styles"][0]["id"] == "G049"
    assert len(long_body["ranking_explanation"]) < 700


def test_alchemy_lab_rejects_empty_idea_and_oversized_batch():
    client = TestClient(app)

    empty = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={"idea": "   ", "selected_style_ids": ["folk_horror_poster_photo"], "images_per_style": 1},
    )
    assert empty.status_code == 422

    too_large = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "复古咖啡馆吉祥物",
            "selected_style_ids": [
                "folk_horror_poster_photo",
                "chrome_y2k_fashion_editorial",
                "pastel_ceramic_toy_photo",
                "tropical_vhs_travelogue",
                "risograph_botanical_catalog",
                "brutalist_museum_product_plinth",
                "crt_pixel_interface_still_life",
            ],
            "images_per_style": 2,
        },
    )
    assert too_large.status_code == 400
    assert too_large.json()["detail"]["code"] == "invalid_exploration_request"

    too_many_raw_styles = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "复古咖啡馆吉祥物",
            "selected_style_ids": [
                "folk_horror_poster_photo",
                "chrome_y2k_fashion_editorial",
                "pastel_ceramic_toy_photo",
                "tropical_vhs_travelogue",
                "risograph_botanical_catalog",
                "brutalist_museum_product_plinth",
                "crt_pixel_interface_still_life",
                "hand_tinted_archive_portrait",
                "folk_horror_poster_photo",
            ],
            "style_family": "product",
            "images_per_style": 1,
        },
    )
    assert too_many_raw_styles.status_code == 400
    assert "no more than 8 styles" in too_many_raw_styles.json()["detail"]["message"]


def test_alchemy_lab_creates_comparison_board_and_persists_favorites():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "陶瓷猫香水瓶",
            "selected_style_ids": ["pastel_ceramic_toy_photo", "brutalist_museum_product_plinth"],
            "mode": "product",
            "images_per_style": 1,
            "aspect_ratio": "square",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session = payload["session"]
    board = payload["board"]
    assert session["status"] == "completed"
    assert board["status"] == "completed"
    assert len(board["groups"]) == 2
    first_card = board["groups"][0]["cards"][0]
    assert first_card["status"] == "succeeded"
    assert first_card["thumbnail_url"]
    assert "稀有风格方向" in first_card["prompt"]
    assert "避免泛化的现代极简风" in first_card["prompt"]
    assert first_card["quality"]["quality_enhancement_mode"] == "auto"
    assert first_card["quality"]["quality_enhancement_applied"] is True

    favorite = client.post(
        f"/api/lab/rare-style-explorer/sessions/{session['id']}/favorites",
        json={"variant_ids": [first_card["variant_id"]]},
    )
    assert favorite.status_code == 200
    favorite_board = favorite.json()["board"]
    assert favorite_board["favorites"] == [first_card["variant_id"]]
    assert favorite_board["groups"][0]["cards"][0]["is_favorite"] is True

    reload_response = client.get(f"/api/lab/rare-style-explorer/sessions/{session['id']}")
    assert reload_response.status_code == 200
    assert reload_response.json()["board"]["favorites"] == [first_card["variant_id"]]


def test_alchemy_lab_quality_off_preserves_base_prompt():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "万圣节南瓜海报，本周五18:30大学生活动中心",
            "selected_style_ids": ["C002"],
            "mode": "poster",
            "quality_enhancement": "off",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    session = response.json()["session"]
    prompt = session["prompts"][0]
    quality = prompt["prompt_metadata"]["quality_enhancement"]
    assert quality["mode"] == "off"
    assert quality["applied"] is False
    assert prompt["final_prompt"].startswith("万圣节南瓜海报")
    assert "用户创意与主体" not in prompt["final_prompt"]


def test_alchemy_lab_accepts_legacy_quality_mode_field():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "万圣节南瓜海报，本周五18:30大学生活动中心",
            "selected_style_ids": ["C002"],
            "mode": "poster",
            "quality_enhancement_mode": "off",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    session = response.json()["session"]
    assert session["prompts"][0]["prompt_metadata"]["quality_enhancement"]["mode"] == "off"


def test_alchemy_lab_quality_balanced_uses_llm_text_hierarchy(monkeypatch):
    captured_kwargs = {}

    async def fake_json_plan(**kwargs):
        captured_kwargs.update(kwargs)
        return (
            {
                "subject_and_intent": "万圣节南瓜派对视觉主海报，南瓜灯为主视觉",
                "style_boundary": "民俗恐怖海报质感只作用于色彩、纸张和边框，不压住南瓜轮廓",
                "art_direction_summary": "让南瓜灯成为唯一视觉中心，背景留出呼吸感，画面像完成度高的活动主视觉。",
                "composition_guidance": "竖版居中构图，暖橙南瓜光和冷紫背景对比，底部保留干净信息区。",
                "finish_quality": "高级印刷海报质感，高细节、低噪声、清楚边界。",
                "text_hierarchy": {
                    "has_text_intent": True,
                    "text_strategy_summary": "活动信息只保留为短促邀请信息，避免长句占满画面。",
                    "text_roles": [
                        {
                            "role_name": "活动核心信息",
                            "content": "本周五18:30 大学生活动中心",
                            "importance": "secondary",
                            "rendering_policy": "exact",
                            "placement_intent": "放在画面下方安全信息区，与南瓜主视觉保持距离",
                            "reason": "用户需要观众知道时间和地点，但视觉中心仍应是南瓜",
                        }
                    ],
                    "avoid_text": ["邀请来参加晚会这种长句不要直接画成完整段落"],
                    "postprocess_recommendation": "如文字不够稳定，可保留信息区后期排版。",
                },
                "negative_guidance": ["避免随机文字", "避免固定信息槽模板感"],
            },
            {"llm_provider": "test_llm", "llm_model": "test-model", "fallback_used": False},
        )

    monkeypatch.setattr(alchemy_lab_quality_module, "plan_lab_json", fake_json_plan)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "帮我生成一个万圣节南瓜的海报，本周五18:30分，邀请来大学生活动中心参加晚会",
            "selected_style_ids": ["C002"],
            "mode": "poster",
            "quality_enhancement": "balanced",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    session = response.json()["session"]
    prompt = session["prompts"][0]
    quality = prompt["prompt_metadata"]["quality_enhancement"]
    assert quality["mode"] == "balanced"
    assert quality["applied"] is True
    assert quality["llm_provider"] == "test_llm"
    assert quality["text_hierarchy"]["text_roles"][0]["role_name"] == "活动核心信息"
    assert captured_kwargs["timeout_seconds"] == 90.0
    assert "用户创意与主体" in prompt["final_prompt"]
    assert "活动核心信息" in prompt["final_prompt"]
    assert "Title:" not in prompt["final_prompt"]
    assert "Time:" not in prompt["final_prompt"]
    assert "Location:" not in prompt["final_prompt"]


def test_alchemy_lab_quality_curated_allows_longer_llm_timeout(monkeypatch):
    captured_kwargs = {}

    async def fake_json_plan(**kwargs):
        captured_kwargs.update(kwargs)
        return (
            {
                "subject_and_intent": "高完成度南瓜派对海报",
                "style_boundary": "复古恐怖质感只服务南瓜灯和校园活动氛围",
                "art_direction_summary": "精致主视觉，明确前景南瓜灯，背景保留活动空间。",
                "composition_guidance": "竖版海报层级，橙色主光和深紫阴影形成节日对比。",
                "finish_quality": "商业级印刷质感，干净边缘和稳定图文区域。",
                "text_hierarchy": {
                    "has_text_intent": True,
                    "text_strategy_summary": "只保留短信息，避免文字喧宾夺主。",
                    "text_roles": [],
                    "avoid_text": [],
                    "postprocess_recommendation": "必要时后期排版精确活动信息。",
                },
                "negative_guidance": ["避免随机乱码"],
            },
            {"llm_provider": "test_llm", "llm_model": "test-model", "fallback_used": False},
        )

    monkeypatch.setattr(alchemy_lab_quality_module, "plan_lab_json", fake_json_plan)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "万圣节南瓜海报，本周五18:30大学生活动中心",
            "selected_style_ids": ["C015"],
            "mode": "poster",
            "quality_enhancement": "curated",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    assert captured_kwargs["reasoning_effort"] == "medium"
    assert captured_kwargs["timeout_seconds"] == 150.0
    quality = response.json()["session"]["prompts"][0]["prompt_metadata"]["quality_enhancement"]
    assert quality["source"] == "llm_quality_enhancement"


def test_alchemy_lab_quality_llm_failure_falls_back_without_formula(monkeypatch):
    async def fail_json_plan(**kwargs):
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(alchemy_lab_quality_module, "plan_lab_json", fail_json_plan)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "青柠薄荷气泡水包装设计，适合夏季便利店货架",
            "selected_style_ids": ["M001"],
            "mode": "product",
            "quality_enhancement": "balanced",
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    prompt = response.json()["session"]["prompts"][0]
    quality = prompt["prompt_metadata"]["quality_enhancement"]
    assert quality["applied"] is True
    assert quality["source"] == "local_quality_enhancement"
    assert quality["text_hierarchy"]["applied"] is False
    assert "Title:" not in prompt["final_prompt"]
    assert "Time:" not in prompt["final_prompt"]
    assert "Location:" not in prompt["final_prompt"]


def test_alchemy_lab_uses_beginner_default_styles_when_styles_omitted():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "甜品店开业海报",
            "mode": "poster",
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["request"]["selected_style_ids"] == []
    assert len(payload["board"]["groups"]) == 4
    assert all(group["cards"] for group in payload["board"]["groups"])


def test_alchemy_lab_auto_selects_by_family_and_seed():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "潮流饮料发布海报",
            "mode": "poster",
            "style_family": "graphic",
            "freshness": "high",
            "target_count": 6,
            "seed": 2594,
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["request"]["target_count"] == 6
    assert payload["session"]["request"]["style_family"] == "graphic"
    assert len(payload["board"]["groups"]) == 6
    assert {style["family"] for style in payload["session"]["style_presets"]} == {"graphic"}


def test_alchemy_lab_reference_product_auto_uses_curated_showcase_sampling():
    client = TestClient(app)
    upload = client.post(
        "/api/lab/uploads",
        json={
            "filename": "reference-bottle.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "role": "product_reference",
            "constraint_strength": "strong",
            "intended_use": "保持产品主体，探索高端海报风格。",
            "consent": {"user_confirmed_rights": True, "commercial_use_allowed": True},
        },
    )
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/api/lab/uploads/{asset_id}/content", json={"content_base64": tiny_png_b64(), "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/api/lab/uploads/{asset_id}/complete").status_code == 200

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "以参考图中的白色工业瓶为主体，生成高端产品海报。",
            "mode": "product",
            "target_count": 4,
            "images_per_style": 1,
            "seed": 20260619,
            "provider_preference": "mock_image",
            "reference_assets": [{"asset_id": asset_id, "role": "product_reference", "constraint_strength": "strong"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    families = [style["family"] for style in payload["session"]["style_presets"]]
    assert len(set(families)) >= 3
    assert set(families) - {"product", "material"}
    first_quality = payload["session"]["prompts"][0]["prompt_metadata"]["quality_enhancement"]
    assert first_quality["mode"] == "auto"
    assert first_quality["strategy"] == "curated"
    assert first_quality["applied"] is True


def test_alchemy_lab_auto_mode_target_count_is_exact_total():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "甜品店新品海报",
            "target_count": 5,
            "style_family": "graphic",
            "images_per_style": 3,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["request"]["images_per_style"] == 3
    assert len(payload["board"]["groups"]) == 2
    assert sum(len(group["cards"]) for group in payload["board"]["groups"]) == 5


def test_alchemy_lab_distributes_target_count_remainder_to_last_style():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "甜品店新品海报",
            "target_count": 5,
            "style_family": "graphic",
            "images_per_style": 2,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    groups = response.json()["board"]["groups"]
    assert len(groups) == 3
    assert [len(group["cards"]) for group in groups] == [2, 2, 1]
    assert sum(len(group["cards"]) for group in groups) == 5


def test_alchemy_lab_rejects_manual_styles_when_target_exceeds_capacity():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "手选两个风格但要求太多图",
            "selected_style_ids": ["M001", "C002"],
            "target_count": 9,
            "images_per_style": 4,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 400
    assert "Choose more styles" in response.json()["detail"]["message"]


def test_alchemy_lab_deduplicates_selected_styles():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "重复风格边界测试",
            "selected_style_ids": ["M001", "M001", "folk_horror_poster_photo", "C002"],
            "images_per_style": 2,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    board = response.json()["board"]
    assert [group["style_preset_id"] for group in board["groups"]] == ["M001", "C002"]
    assert sum(len(group["cards"]) for group in board["groups"]) == 4


def test_alchemy_lab_manual_styles_are_not_filtered_by_family():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "手选风格不应被族筛选误删",
            "selected_style_ids": ["M001", "C002"],
            "style_family": "graphic",
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    board = response.json()["board"]
    assert [group["style_preset_id"] for group in board["groups"]] == ["M001", "C002"]
    assert sum(len(group["cards"]) for group in board["groups"]) == 2


def test_alchemy_lab_generation_interval_is_applied(monkeypatch):
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(alchemy_lab_module.asyncio, "sleep", fake_sleep)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "复古电子表广告海报",
            "selected_style_ids": ["pastel_ceramic_toy_photo", "crt_pixel_interface_still_life"],
            "mode": "poster",
            "images_per_style": 1,
            "generation_interval_seconds": 0.25,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    assert delays == [0.25]


def test_alchemy_lab_live_provider_returns_async_session_and_serializes(monkeypatch):
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    class LiveLikeMockProvider(MockImageProvider):
        name = "openai_gpt_image"

    monkeypatch.setitem(image_service_module.registry.image_providers, "openai_gpt_image", LiveLikeMockProvider())
    monkeypatch.setattr(alchemy_lab_module.asyncio, "sleep", fake_sleep)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "串行节奏测试海报",
            "selected_style_ids": ["M001", "C002"],
            "target_count": 3,
            "images_per_style": 2,
            "generation_interval_seconds": 0.5,
            "provider_preference": "openai_gpt_image",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["session"]["id"]
    assert payload["async"] is True
    assert payload["session"]["status"] == "queued"
    assert count_cards(payload["board"]) == 3
    assert all(card["status"] == "queued" for group in payload["board"]["groups"] for card in group["cards"])

    for _ in range(10):
        poll = client.get(f"/api/lab/rare-style-explorer/sessions/{session_id}")
        assert poll.status_code == 200
        board = poll.json()["board"]
        if board["status"] == "completed":
            break
    else:
        pytest.fail("Lab async session did not complete.")

    assert board["status"] == "completed"
    assert count_cards(board, "succeeded") == 3
    assert sleeps == [0.5, 0.5]


def test_alchemy_lab_schema_matches_real_api_responses():
    jsonschema = pytest.importorskip("jsonschema")
    client = TestClient(app)
    schema = json.loads(Path("specs/alchemy_lab/rare_style_explorer.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    styles_response = client.get("/api/lab/rare-style-explorer/styles")
    assert styles_response.status_code == 200
    validator.validate(styles_response.json())

    session_response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "孔版印刷风格咖啡豆包装",
            "mode": "product",
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )
    assert session_response.status_code == 200
    validator.validate(session_response.json())


def test_alchemy_lab_reference_upload_lifecycle_and_history_redaction():
    client = TestClient(app)

    upload = client.post(
        "/api/lab/uploads",
        json={
            "filename": "secret-product.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "role": "product_reference",
            "constraint_strength": "strong",
            "intended_use": "保持产品包装外观",
            "consent": {
                "user_confirmed_rights": True,
                "logo_or_trademark_allowed": True,
                "commercial_use_allowed": True,
            },
        },
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    assert upload.json()["upload_url"].startswith("/api/lab/uploads/")

    stored = client.put(
        f"/api/lab/uploads/{asset_id}/content",
        json={"content_base64": tiny_png_b64(), "mime_type": "image/png"},
    )
    assert stored.status_code == 200
    assert stored.json()["status"] == "stored"

    completed = client.post(f"/api/lab/uploads/{asset_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "ready"
    assert completed.json()["source_url"].startswith("/api/lab/uploads/")

    session_response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "端午节礼盒海报",
            "selected_style_ids": ["M001"],
            "target_count": 1,
            "images_per_style": 1,
            "provider_preference": "mock_image",
            "reference_assets": [
                {
                    "asset_id": asset_id,
                    "role": "product_reference",
                    "constraint_strength": "strong",
                    "notes": "保持礼盒外形和主色",
                }
            ],
        },
    )
    assert session_response.status_code == 200
    payload = session_response.json()
    prompt = payload["session"]["prompts"][0]["final_prompt"]
    assert "参考图约束" in prompt
    assert "稀有风格仍然是主要视觉变量" in prompt
    assert payload["board"]["groups"][0]["cards"][0]["reference"]["summary"].startswith("参考图")

    job_id = payload["session"]["variants"][0]["asset"]["job_id"]
    job = repository.get_job(job_id)
    assert job is not None
    assert job.asset_mode == "lab_reference"
    assert job.asset_plan["asset_mode"] == "lab_reference"
    assert job.asset_plan["provider_input_plan"]["reference_image_count"] == 1

    lab_history = client.get("/api/lab/history?limit=10&include_mock=true")
    assert lab_history.status_code == 200
    item = lab_history.json()["items"][0]
    serialized = json.dumps(item, ensure_ascii=False)
    assert item["reference_summary"].startswith("参考图")
    assert "secret-product.png" not in serialized
    assert asset_id not in serialized
    assert "source_url" not in serialized
    assert "storage_path" not in serialized


def test_alchemy_lab_intent_director_guides_text_only_auto_styles(monkeypatch):
    async def fake_intent_plan(**kwargs):
        return (
            {
                "target_use": "product",
                "subject_kind": "product",
                "main_subject": "青柠薄荷气泡水",
                "user_goal_summary": "判断为产品包装方向，优先产品和材质相关稀有风格。",
                "confidence": "high",
                "reference_directives": [],
                "style_routing": {
                    "auto_selection_scope": "compatible_families",
                    "preferred_families": ["product", "material"],
                    "avoid_families": [],
                    "style_strength_guidance": "保留产品识别，让风格改变光线、材质和陈列方式。",
                    "reason": "用户描述包含包装与货架语义。",
                },
                "prompt_constraints": {
                    "must_keep": ["产品包装识别", "青柠薄荷清爽感"],
                    "may_change": ["背景", "陈列材质"],
                    "avoid": ["随机无关文字"],
                    "director_summary": "产品识别优先，稀有风格只改变呈现语言。",
                },
            },
            {"llm_provider": "lab_test", "llm_model": "test-vision", "fallback_used": False, "vision_used": False},
        )

    monkeypatch.setattr(alchemy_lab_intent_module, "plan_lab_json", fake_intent_plan)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "青柠薄荷气泡水包装设计，适合夏季便利店货架",
            "target_count": 3,
            "images_per_style": 1,
            "provider_preference": "mock_image_live_intent",
            "quality_enhancement": "off",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    families = {style["family"] for style in payload["session"]["style_presets"]}
    assert families <= {"product", "material"}
    prompt = payload["session"]["prompts"][0]
    assert "智能意图约束" in prompt["final_prompt"]
    assert prompt["prompt_metadata"]["intent_director"]["target_use"] == "product"
    assert payload["board"]["groups"][0]["cards"][0]["intent"]["summary"].startswith("判断为产品包装方向")


def test_alchemy_lab_intent_director_off_keeps_prompt_random(monkeypatch):
    async def fail_if_called(**kwargs):
        raise AssertionError("intent director LLM should not run when intent_director is off")

    monkeypatch.setattr(alchemy_lab_intent_module, "plan_lab_json", fail_if_called)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "青柠薄荷气泡水产品包装设计，随机探索稀有视觉风格",
            "target_count": 3,
            "images_per_style": 1,
            "provider_preference": "mock_image_live_intent",
            "quality_enhancement": "off",
            "intent_director": "off",
            "seed": 20260620,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["request"]["intent_director"] == "off"
    assert payload["session"]["intent_plan"]["source"] == "disabled"
    prompt = payload["session"]["prompts"][0]
    assert "智能意图约束" not in prompt["final_prompt"]
    assert prompt["prompt_metadata"]["intent_director"]["summary"] is None
    assert payload["board"]["groups"][0]["cards"][0]["intent"]["summary"] is None


def test_alchemy_lab_intent_director_does_not_replace_manual_styles(monkeypatch):
    async def fake_intent_plan(**kwargs):
        return (
            {
                "target_use": "product",
                "user_goal_summary": "产品方向",
                "confidence": "high",
                "reference_directives": [],
                "style_routing": {"preferred_families": ["product"], "avoid_families": ["graphic"]},
                "prompt_constraints": {"must_keep": ["主体"], "may_change": [], "avoid": [], "director_summary": "保持主体"},
            },
            {"llm_provider": "lab_test", "llm_model": "test", "fallback_used": False, "vision_used": False},
        )

    monkeypatch.setattr(alchemy_lab_intent_module, "plan_lab_json", fake_intent_plan)
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "一张活动海报",
            "selected_style_ids": ["C002", "G001"],
            "target_count": 2,
            "images_per_style": 1,
            "provider_preference": "mock_image_live_intent",
            "quality_enhancement": "off",
        },
    )

    assert response.status_code == 200
    assert [style["id"] for style in response.json()["session"]["style_presets"]] == ["C002", "G001"]


def test_alchemy_lab_intent_director_can_recommend_reference_role(monkeypatch):
    async def fake_intent_plan(**kwargs):
        assets = kwargs["user_payload"]["reference_assets"]
        asset_id = assets[0]["asset_id"]
        return (
            {
                "target_use": "product",
                "subject_kind": "packaging",
                "main_subject": "白色工业瓶",
                "user_goal_summary": "参考图判断为产品瓶身，应固定瓶型和白色工业质感。",
                "confidence": "high",
                "reference_directives": [
                    {
                        "asset_id": asset_id,
                        "recommended_role": "product_reference",
                        "recommended_strength": "required",
                        "lock_constraints": ["白色瓶身比例", "工业包装识别点"],
                        "allow_transformations": ["背景", "布光", "稀有风格媒介"],
                        "forbidden_changes": ["改成非瓶装产品"],
                        "provider_input_requirement": "required",
                        "compatibility_note": "产品图必须作为输入图保留。",
                    }
                ],
                "style_routing": {"preferred_families": ["product"], "avoid_families": []},
                "prompt_constraints": {
                    "must_keep": ["白色瓶身比例"],
                    "may_change": ["背景"],
                    "avoid": ["主体漂移"],
                    "director_summary": "保持产品，风格只改呈现方式。",
                },
            },
            {"llm_provider": "lab_test", "llm_model": "test-vision", "fallback_used": False, "vision_used": True},
        )

    monkeypatch.setattr(alchemy_lab_intent_module, "plan_lab_json", fake_intent_plan)
    client = TestClient(app)
    upload = client.post(
        "/api/lab/uploads",
        json={
            "filename": "white-bottle.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "consent": {"user_confirmed_rights": True},
        },
    )
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/api/lab/uploads/{asset_id}/content", json={"content_base64": tiny_png_b64(), "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/api/lab/uploads/{asset_id}/complete").status_code == 200

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "把参考图做成高端产品摄影",
            "selected_style_ids": ["M001"],
            "target_count": 1,
            "images_per_style": 1,
            "provider_preference": "mock_image_live_intent",
            "quality_enhancement": "off",
            "reference_assets": [{"asset_id": asset_id}],
        },
    )

    assert response.status_code == 200
    prompt = response.json()["session"]["prompts"][0]
    role = prompt["prompt_metadata"]["reference_asset_roles"][0]
    assert role["role"] == "product_reference"
    assert role["constraint_strength"] == "required"
    assert "智能判断需保留" in prompt["final_prompt"]
    serialized = json.dumps(response.json(), ensure_ascii=False)
    assert "white-bottle.png" not in serialized
    assert "storage_path" not in serialized


def test_alchemy_lab_upload_rejects_invalid_requests():
    client = TestClient(app)

    no_rights = client.post(
        "/api/lab/uploads",
        json={
            "filename": "portrait.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "consent": {"user_confirmed_rights": False},
        },
    )
    assert no_rights.status_code == 200
    assert no_rights.json()["upload_url"] == ""

    wrong_type = client.post(
        "/api/lab/uploads",
        json={
            "filename": "notes.txt",
            "mime_type": "text/plain",
            "size_bytes": 12,
            "consent": {"user_confirmed_rights": True},
        },
    )
    assert wrong_type.status_code == 200
    assert wrong_type.json()["upload_url"] == ""

    invalid_asset = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "参考图缺失测试",
            "selected_style_ids": ["M001"],
            "target_count": 1,
            "provider_preference": "mock_image",
            "reference_assets": [{"asset_id": "lab_asset_missing", "role": "subject_reference"}],
        },
    )
    assert invalid_asset.status_code == 400


def test_alchemy_lab_uses_existing_generation_without_v2_bridge_history():
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "AI 知识库应用图标",
            "selected_style_ids": ["crt_pixel_interface_still_life"],
            "mode": "poster",
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    session = response.json()["session"]
    variant = session["variants"][0]
    assert variant["status"] == "succeeded"
    output_id = variant["asset"]["output_id"]
    job_id = variant["asset"]["job_id"]
    job = repository.get_job(job_id)
    assert job is not None
    assert job.session_id.startswith(f"ses_{session['id']}")
    assert job.idempotency_key.startswith("lab:")
    assert not job.idempotency_key.startswith("v2:")

    history = client.get(f"/v1/image/history?session_id={job.session_id}")
    assert history.status_code == 200
    assert all(item["id"] != output_id for item in history.json()["items"])

    lab_history = client.get("/api/lab/history?limit=10&include_mock=true")
    assert lab_history.status_code == 200
    lab_items = lab_history.json()["items"]
    assert any(item["id"] == output_id for item in lab_items)
    legacy_lab_history = client.get("/api/lab/rare-style-explorer/history?limit=10&include_mock=true")
    assert legacy_lab_history.status_code == 200
    assert any(item["id"] == output_id for item in legacy_lab_history.json()["items"])
    item = next(item for item in lab_items if item["id"] == output_id)
    assert item["module"] == "rare-style-explorer"
    assert item["module_label"] == "Rare Style Explorer"
    assert item["title"].startswith("Rare Style Explorer")
    assert item["style_name"]
    assert item["mode"] == "poster"
    assert item["mode_label"] == "海报封面"
    assert item["keywords"]
    assert item["idea"] == "AI 知识库应用图标"
    assert item["final_prompt"]
    assert "AI 知识库应用图标" in item["final_prompt"]
    assert "稀有风格方向：" in item["final_prompt"]


def test_alchemy_lab_preserves_partial_failures(monkeypatch):
    class PartiallyFailingProvider(MockImageProvider):
        async def generate(self, request):
            prompt_text = request.prompt_plan.variables.get("generation_prompt", "")
            if "CRT荧光屏拍摄" in prompt_text:
                raise ProviderRuntimeError("Injected Lab style failure", provider=self.name)
            return await super().generate(request)

    monkeypatch.setitem(image_service_module.registry.image_providers, "mock_image", PartiallyFailingProvider())
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "复古电子表广告海报",
            "selected_style_ids": ["pastel_ceramic_toy_photo", "crt_pixel_interface_still_life"],
            "mode": "poster",
            "images_per_style": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    board = response.json()["board"]
    statuses = [card["status"] for group in board["groups"] for card in group["cards"]]
    assert board["status"] == "partial_success"
    assert statuses == ["succeeded", "failed"]
    failed_cards = [card for group in board["groups"] for card in group["cards"] if card["status"] == "failed"]
    assert failed_cards[0]["error"]["code"] == "provider_error"
    assert "Injected Lab style failure" in failed_cards[0]["error"]["message"]


def test_alchemy_lab_reports_invalid_provider_key_without_leaking_secret(monkeypatch):
    secret = "sk-liveSECRET1234567890abcdef"
    masked_secret = "sk-liveS******************cdef"

    class InvalidKeyProvider(MockImageProvider):
        async def generate(self, request):
            raise ProviderRuntimeError(
                f"Error code: 401 - Incorrect API key provided: {secret}. invalid_api_key",
                provider="openai_gpt_image",
                detail={
                    "error_type": "AuthenticationError",
                    "message": f"AuthenticationError: Incorrect API key provided: {masked_secret}; invalid_api_key",
                },
            )

    monkeypatch.setitem(image_service_module.registry.image_providers, "mock_image", InvalidKeyProvider())
    client = TestClient(app)

    response = client.post(
        "/api/lab/rare-style-explorer/sessions",
        json={
            "idea": "本地 key 诊断",
            "target_count": 1,
            "provider_preference": "mock_image",
        },
    )

    assert response.status_code == 200
    board = response.json()["board"]
    failed_card = board["groups"][0]["cards"][0]
    serialized = json.dumps(board, ensure_ascii=False)
    assert board["status"] == "failed"
    assert failed_card["error"]["message"] == "OpenAI 生图通道 API Key 无效，请到“模型与 API”更新后再试。"
    assert secret not in serialized
    assert masked_secret not in serialized
    assert "sk-***" in serialized


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


def test_asset_upload_rejects_oversized_declared_and_actual_content():
    client = TestClient(app)
    original_limit = settings.max_asset_upload_bytes
    settings.max_asset_upload_bytes = 4
    try:
        upload = client.post(
            "/v1/assets/upload-url",
            json={
                "filename": "large.png",
                "mime_type": "image/png",
                "size_bytes": 5,
                "consent": {"rights_confirmed": True},
            },
        )
        assert upload.status_code == 200
        oversized_asset_id = upload.json()["asset_id"]
        assert upload.json()["upload_url"] == ""
        oversized_asset = client.get(f"/v1/assets/{oversized_asset_id}")
        assert oversized_asset.status_code == 200
        assert oversized_asset.json()["status"] == "rejected"
        assert oversized_asset.json()["error"]["code"] == "asset_too_large"

        accepted = client.post(
            "/v1/assets/upload-url",
            json={
                "filename": "small-declared.png",
                "mime_type": "image/png",
                "size_bytes": 4,
                "consent": {"rights_confirmed": True},
            },
        )
        assert accepted.status_code == 200
        asset_id = accepted.json()["asset_id"]
        content = client.put(
            f"/v1/assets/{asset_id}/content",
            json={"content_base64": base64.b64encode(b"12345").decode("ascii"), "mime_type": "image/png"},
        )
        assert content.status_code == 400
        assert content.json()["detail"]["code"] == "asset_too_large"
    finally:
        settings.max_asset_upload_bytes = original_limit


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
    body = _completed_image_job(client, image_job)
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


def test_v1_prototype_reference_preserves_visible_information_in_asset_prompt():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_prototype_asset"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    upload = client.post(
        "/v1/assets/upload-url",
        json={
            "filename": "prototype.png",
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(png_b64)),
            "declared_role": "composition_reference",
            "intended_use": "image_generation",
            "consent": {"user_confirmed_rights": True},
        },
    )
    assert upload.status_code == 200
    asset_id = upload.json()["asset_id"]
    assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200
    assert client.post(f"/v1/assets/{asset_id}/complete").status_code == 200

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "以这张图为原型，生成一张极具商业化风格的海报。",
            "asset_mode": "advanced",
            "asset_intents": [
                {
                    "asset_id": asset_id,
                    "role": "composition_reference",
                    "priority": 80,
                    "preservation": "strict",
                    "strength": 0.8,
                    "notes": "用户把上传图作为原型/模板参考；只改变用户明确要求改变的部分。",
                    "consent": {"user_confirmed_rights": True},
                }
            ],
            "provider_preference": "mock_image",
        },
    )
    body = _completed_image_job(client, image_job)
    final_prompt = body["prompt_plan"]["variables"]["generation_prompt"]

    assert body["status"] == "ready"
    assert "仅替换用户明确要求改变的内容" in final_prompt
    assert "文字、标识、包装、界面" in final_prompt
    assert "主体内容按用户需求替换" not in final_prompt


def test_v1_advanced_job_accepts_multiple_uploaded_reference_images():
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "proj_multi_asset"}).json()["id"]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    asset_ids = []
    for index, role in enumerate(["style_reference", "subject_reference"], start=1):
        upload = client.post(
            "/v1/assets/upload-url",
            json={
                "filename": f"reference-{index}.png",
                "mime_type": "image/png",
                "size_bytes": len(base64.b64decode(png_b64)),
                "declared_role": role,
                "intended_use": "image_generation",
                "consent": {"user_confirmed_rights": True},
            },
        )
        assert upload.status_code == 200
        asset_id = upload.json()["asset_id"]
        assert client.put(f"/v1/assets/{asset_id}/content", json={"content_base64": png_b64, "mime_type": "image/png"}).status_code == 200
        assert client.post(f"/v1/assets/{asset_id}/complete").status_code == 200
        asset_ids.append(asset_id)

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "结合两张上传图，生成 1 张高级咖啡产品海报。",
            "asset_mode": "advanced",
            "asset_intents": [
                {"asset_id": asset_ids[0], "role": "style_reference", "priority": 80, "consent": {"user_confirmed_rights": True}},
                {"asset_id": asset_ids[1], "role": "subject_reference", "priority": 90, "consent": {"user_confirmed_rights": True}},
            ],
            "provider_preference": "mock_image",
        },
    )

    body = _completed_image_job(client, image_job)
    assert body["status"] == "ready"
    provider_plan = body["asset_plan"]["provider_input_plan"]
    assert provider_plan["reference_image_count"] == 2
    assert set(provider_plan["reference_image_asset_ids"]) == set(asset_ids)
    assert len(body["prompt_plan"]["variables"]["asset_vision_profiles"]) == 2


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

    body = _completed_image_job(client, response)
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
    body = _completed_image_job(client, image_job)
    prompt = body["prompt_plan"]["variables"]["generation_prompt"]
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
    body = _completed_image_job(client, image_job)
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

    body = _completed_image_job(client, image_job)
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

    body = _completed_image_job(client, image_job)
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
    assert "Verya Alchemy" in index.text
    assert "/static/app.js" in index.text
    assert "20260621-progress-share-fix" in index.text
    assert '<body data-active-module="image">' in index.text
    assert 'href="/h5"' in index.text
    assert "Alchemy Lab" in index.text
    assert 'id="labTab"' in index.text
    assert "Rare Style Explorer" in index.text
    assert "labStyleGrid" in index.text
    assert "labComparisonGrid" in index.text
    lab_home_pos = index.text.find('id="labHomePanel"')
    lab_detail_pos = index.text.find('id="rareStyleExplorerPanel"')
    lab_history_pos = index.text.find('id="labHistoryGrid"')
    assert lab_home_pos != -1
    assert lab_detail_pos != -1
    assert lab_history_pos != -1
    assert lab_home_pos < lab_detail_pos < lab_history_pos
    lab_section = index.text[index.text.find('id="labTab"') : index.text.find('id="videoTab"')]
    assert "批次" not in lab_section
    assert "Provider" not in lab_section
    assert "data-lab-module-open=\"rare-style-explorer\"" in index.text
    assert "labHomePanel" in index.text
    assert "rareStyleExplorerPanel" in index.text
    assert "labTargetCountInput" in index.text
    assert "labIntervalInput" in index.text
    assert "labModeInput" in index.text
    assert "labFamilyInput" in index.text
    assert "labStyleSearchInput" in index.text
    assert "labStyleSearchBtn" in index.text
    assert "labStyleSearchThinking" in index.text
    assert "智能匹配" in index.text
    assert "labStyleLibraryPanel" in index.text
    assert "labStyleLibraryToggleBtn" not in index.text
    assert "labReferenceToggleBtn" not in index.text
    assert "labReferenceInput" in index.text
    assert "labReferenceConsentInput" not in index.text
    assert "我确认有权使用这些图片" not in index.text
    assert "labIntentSummary" in index.text
    assert "智能判断" in index.text
    assert "参考图" in index.text
    assert "点开上传图片，用于锁定人物、产品、Logo、构图或配色。" not in index.text
    lab_reference_section = index.text[index.text.find('id="labReferencePanel"') : index.text.find('id="labReferenceList"')]
    assert 'value="style_material_reference"' in lab_reference_section
    assert 'value="required"' in lab_reference_section
    assert 'value="soft"' in lab_reference_section
    assert 'value="style_reference"' not in lab_reference_section
    assert 'value="medium"' not in lab_reference_section
    assert 'value="light"' not in lab_reference_section
    assert 'id="labReferencePanel" class="lab-reference-panel" hidden' not in index.text
    assert 'id="labStyleLibraryPanel" class="lab-library-panel" hidden' not in index.text
    assert "搜索 620 个风格名" in index.text
    assert "每种风格最多" in index.text
    assert "生视频（DEMO）" in index.text
    assert "<p class=\"video-state\">coming soon</p>" in index.text
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
    assert 'data-v2-ratio="" type="button" title="自动画幅' in index.text
    assert "自动画幅不锁尺寸" in index.text
    assert "探索模式也会保持该画幅" in index.text
    assert "v2-result-prompt" in index.text
    assert "v2-result-block" in index.text
    assert "Your Work" not in index.text
    assert "assetPreview" in index.text
    assert 'accept="image/*"' in index.text
    assert "multiple" in index.text
    assert "支持多图，单次最多 6 张" in index.text
    assert "图片、PDF、文档或表格" not in index.text
    assert "advanced-role-checks" in index.text
    assert 'rows="1"' in index.text
    assert "已确认素材授权" not in index.text
    assert "确认拥有 Logo" not in index.text
    assert "确认拥有人物肖像授权" not in index.text
    assert "模型与 API" in index.text
    assert "高级调度" in index.text
    assert "外接 Provider" not in index.text
    assert "05 / Model Status" in index.text
    assert "模型状态" in index.text
    assert "生图通道" in index.text
    assert "v2ImageActiveLabel" in index.text
    assert "v2OpenaiImageState" in index.text
    assert "v2BrainModelState" in index.text
    assert "v2AgentModelInput" in index.text
    assert "v2ClaudeModelInput" in index.text
    assert "v2CaseIntelligenceProviderInput" in index.text
    assert "v2ModelApplyBtn" in index.text
    assert "v2SearchThinking" in index.text
    assert "大模型思考中" in index.text
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
    assert "lab-style-grid" in styles.text
    assert "lab-nav-dropdown" in styles.text
    assert "lab-module-card" in styles.text
    assert "lab-reference-head" in styles.text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in styles.text
    assert "height: clamp(900px, 84vh, 980px)" in styles.text
    assert "max-height: none" in styles.text
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in styles.text
    assert "grid-template-columns: repeat(6, minmax(0, 1fr))" in styles.text
    assert "lab-library-toggle" not in styles.text
    assert ".lab-library-panel[hidden]" in styles.text
    assert "lab-library-details" not in styles.text
    assert "lab-style-more-note" in styles.text
    assert "lab-search-thinking" in styles.text
    assert "lab-style-score" in styles.text
    assert "lab-comparison-grid" in styles.text
    assert "lab-card-quality" in styles.text
    assert "lab-reference-box" in styles.text
    assert "lab-reference-toggle" not in styles.text
    assert "lab-reference-list" in styles.text
    assert ".lab-card-grid" in styles.text
    assert ".lab-favorite-btn.active" in styles.text
    assert "thinking-spinner" in styles.text
    assert "spinThinking" in styles.text
    assert "segmented.quality" in styles.text
    assert "segmented.aspect-segmented" in styles.text
    assert "v2-aspect-hint" in styles.text
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
    assert "const ticketAccepted = await handleVeyraTicketFromUrl();" in script.text
    assert "hydrateV2AspectButtons" in script.text
    assert "v2AspectDisplay" in script.text
    assert "自动画幅" in script.text
    assert 'lab: "探索各种创意玩法"' in script.text
    assert "labHistoryGrid" in index.text
    assert "Alchemy Lab History" in index.text
    assert "探索各种创意玩法" in index.text
    assert "稀有风格探索器" in index.text
    assert "返回实验室" in index.text
    assert "function loadLabHistory" in script.text
    assert "function renderLabHistory" in script.text
    assert 'className = "v2-history-card lab-history-card"' in script.text
    assert "data-lab-history-card" in script.text
    assert "/api/lab/history" in script.text
    assert "function loadLabStyles" in script.text
    assert "function openLabModule" in script.text
    assert "function restoreInitialModuleRoute" in script.text
    assert "function canUseLabDropdown" in script.text
    assert "const shouldOpenLabMenu = !labState.navOpen" in script.text
    assert "setLabNavOpen(canUseLabDropdown() && shouldOpenLabMenu)" in script.text
    assert 'params.get("module") || params.get("tab") || window.location.hash' in script.text
    assert 'if (route === "rare-style-explorer")' in script.text
    assert 'openLabModule("rare-style-explorer");' in script.text
    assert "openLabHome();" in script.text
    assert "function handleLabReferenceFiles" in script.text
    assert "function uploadLabReferenceFile" in script.text
    assert "function labReferencePayload" in script.text
    assert "/api/lab/uploads" in script.text
    assert "/api/v2/uploads" not in script.text
    assert "reference_assets: labReferencePayload()" in script.text
    assert 'reference_mode: labState.referenceAssets.length ? "guided" : "off"' in script.text
    assert "labIntentDirectorInput" in index.text
    assert "labIntentDirectorInput" in script.text
    assert 'value="off">纯随机' in index.text
    assert 'intent_director: labState.intentDirector || "auto"' in script.text
    assert "不调用智能判断收束风格族" in script.text
    assert "调用智能判断理解文字和参考图用途" in script.text
    assert "不会覆盖手动选择的风格" in script.text
    assert "上传参考图" in index.text
    assert "renderLabIntentSummary" in script.text
    assert "function labIntentMetaText" in script.text
    assert "function filteredLabStyles" in script.text
    assert "function searchLabStyles" in script.text
    assert "function setLabStyleSearchThinking" in script.text
    assert "function renderLabSearchEmptyNotice" in script.text
    assert "function clearLabStyleSearchInput" in script.text
    assert "已清空选择和搜索条件" in script.text
    assert "/api/lab/rare-style-explorer/styles/search" in script.text
    assert "相关度" in script.text
    assert "data-lab-load-more-styles" in script.text
    assert "点击加载更多" in script.text
    assert "target_count" in script.text
    assert "最后一种承接余数" in script.text
    assert "generation_interval_seconds" in script.text
    assert "labDefaultGenerationIntervalSeconds = 8" in script.text
    assert "function scheduleLabPolling" in script.text
    assert "等待串行生成" in script.text
    assert 'value="8"' in index.text
    assert "quality_enhancement" in script.text
    assert "labQualityEnhancementInput" in index.text
    assert "labQualityEnhancementInput" in script.text
    assert "function labQualityMetaText" in script.text
    assert "智能文案层级已规划" in script.text
    assert "/api/lab/rare-style-explorer/styles" in script.text
    assert "/api/lab/rare-style-explorer/sessions" in script.text
    assert "function runLabExploration" in script.text
    assert "function renderLabBoard" in script.text
    assert "function handleLabComparisonClick" in script.text
    assert "function labProviderPreference" in script.text
    assert "if (hadVeyraTicket && !ticketAccepted) return;" in script.text
    assert "/v1/image/jobs" in script.text
    assert "/v1/image/history" in script.text
    assert "output.thumbnail_url || output.url" in script.text
    assert 'image.loading = "lazy"' in script.text
    assert "noticeBar" in script.text
    assert "生成中" in script.text
    assert "scrollIntoView" in script.text
    assert "function scrollV2HomeResultsIntoView(run)" in script.text
    assert "scrollV2HomeResultsIntoView(run);" in script.text
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
    assert 'const v2ApiBase = window.ALCHEMY_V2_API_BASE || `${window.location.origin}/api/v2`;' in script.text
    assert "v2LocalApiBase" not in script.text
    assert "Claude 思考后的最终提示词" in script.text
    assert "selectedQuality" in script.text
    assert "openaiLlmModelInput" in script.text
    assert "agentLlmModelInput" in script.text
    assert "anthropicBaseUrlInput" in script.text
    assert "default_llm_provider" in script.text
    assert "selectedAssetRoles" in script.text
    assert "asset_intents: state.assetIds.flatMap" in script.text
    assert "default_llm_model" in script.text
    assert "openai_image_model" in script.text
    assert "doubao_image_model" in script.text
    assert "gemini_image_model" in script.text
    assert "openai_llm_model" in script.text
    assert "kimi_llm_model" in script.text
    assert "anthropic_api_key" in script.text
    assert "gemini_image_base_url" in script.text
    assert "gemini_image_api_key" in script.text
    assert "doubaoImageModelInput" in script.text
    assert "doubaoImageApiKeyInput" in script.text
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
    assert 'const selected = safeImageProviderPreference(els.v2ImageProviderInput?.value || "", "auto")' in script.text
    assert "isGeminiImageTemporarilyDisabled(requested)" in script.text
    assert "const imageProvider = v2RequestedImageProvider(v2State.modelSettings || {})" in script.text
    assert "v2CaseIntelligenceSourceLabel" in script.text
    assert "setV2CaseSearchThinking" in script.text
    assert "后台仍在运行，页面会持续刷新" in script.text
    assert 'v2: "智能中枢统筹创意策略，案例体系赋能品牌视觉升级。"' in script.text
    assert 'video: "coming soon"' in script.text
    assert "document.body.dataset.activeModule" in script.text
    assert "encodeV2CaseAssetPath" in script.text
    assert "fallbackV2CaseImageToPreview" in script.text
    assert "if (url.startsWith(\"/api/v2/\")) return v2MediaUrl(url);" in script.text
    assert "if (url?.startsWith(\"/api/v2/\")) return v2MediaUrl(url);" in script.text
    assert "/case-thumbnails/" in script.text
    assert "/case-assets/" in script.text
    assert "openV2HistoryLightbox" in script.text
    assert "v2PromptTextFromJob" in script.text
    assert "mergeAccountHistory" in script.text
    assert "account_history_source" in script.text
    assert "mergeVeyraUsage" in script.text
    assert "veyraTemplateHistoryList" in index.text
    assert "历史使用模板" in index.text
    assert "buildVeyraTemplateHistory" in script.text
    assert "v2HistoryTemplateCaseId" in script.text
    assert "/v1/veyra/usage?limit=100" in script.text
    assert "refreshVeyraAccountPanelAfterHistoryChange" in script.text
    assert script.text.count("await refreshVeyraAccountPanelAfterHistoryChange();") >= 3
    assert "function refreshV1GenerationSideEffects" in script.text
    assert "await refreshV1GenerationSideEffects();" in script.text
    assert "/veyra/history?limit=1000" in script.text
    assert "管理员可见全部账户" in script.text
    assert "当前账户与旧版生图记录" in script.text
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
    assert "20260621-progress-share-fix" in h5.text
    assert '<body data-active-module="image">' in h5.text
    assert "V1 基础" in h5.text
    assert "V2 Agent" in h5.text
    assert "Alchemy Lab" in h5.text
    assert "<small>实验室</small>" not in h5.text
    assert 'id="labTab"' in h5.text
    assert "Rare Style Explorer" in h5.text
    assert "labStyleGrid" in h5.text
    assert "labComparisonGrid" in h5.text
    lab_home_pos = h5.text.find('id="labHomePanel"')
    lab_detail_pos = h5.text.find('id="rareStyleExplorerPanel"')
    lab_history_pos = h5.text.find('id="labHistoryGrid"')
    assert lab_home_pos != -1
    assert lab_detail_pos != -1
    assert lab_history_pos != -1
    assert lab_home_pos < lab_detail_pos < lab_history_pos
    assert "labHomePanel" in h5.text
    assert "rareStyleExplorerPanel" in h5.text
    assert "data-lab-module-open=\"rare-style-explorer\"" in h5.text
    assert "lab-tab" in h5.text
    assert "探索各种创意玩法" in h5.text
    assert "稀有风格探索器" in h5.text
    assert 'data-mobile-open="lab-history"' in h5.text
    assert "查看所有实验室模块生成的图片" in h5.text
    assert "返回实验室" in h5.text
    assert "labTargetCountInput" in h5.text
    assert "labIntervalInput" in h5.text
    assert "labModeInput" in h5.text
    assert "labFamilyInput" in h5.text
    assert "labQualityEnhancementInput" in h5.text
    assert "labStyleSearchInput" in h5.text
    assert "labStyleSearchBtn" in h5.text
    assert "labStyleSearchThinking" in h5.text
    assert "智能匹配" in h5.text
    assert "labStyleLibraryPanel" in h5.text
    assert "labStyleLibraryToggleBtn" not in h5.text
    assert "labReferenceToggleBtn" not in h5.text
    assert "labReferenceInput" in h5.text
    assert "labReferenceConsentInput" not in h5.text
    assert "我确认有权使用这些图片" not in h5.text
    assert "labIntentSummary" in h5.text
    assert "智能判断" in h5.text
    assert "点开上传图片，用于锁定人物、产品、Logo、构图或配色。" not in h5.text
    assert "labMobileActionPanel" in h5.text
    assert "mobileLabRunSummary" in h5.text
    assert "mobileLabExploreSummary" in h5.text
    assert "mobileLabReferenceSummary" in h5.text
    assert "mobileLabStyleSummary" in h5.text
    h5_lab_reference_section = h5.text[h5.text.find('id="labReferencePanel"') : h5.text.find('id="labReferenceList"')]
    assert 'value="style_material_reference"' in h5_lab_reference_section
    assert 'value="required"' in h5_lab_reference_section
    assert 'value="soft"' in h5_lab_reference_section
    assert 'value="style_reference"' not in h5_lab_reference_section
    assert 'value="medium"' not in h5_lab_reference_section
    assert 'value="light"' not in h5_lab_reference_section
    assert 'id="labReferencePanel" class="lab-reference-panel" hidden' not in h5.text
    assert 'id="labStyleLibraryPanel" class="lab-library-panel" hidden' not in h5.text
    assert "搜索 620 个风格名" in h5.text
    assert "每种风格最多" in h5.text
    lab_section = h5.text[h5.text.find('id="labTab"') : h5.text.find('id="videoTab"')]
    assert "批次" not in lab_section
    assert "Provider" not in lab_section
    assert "生视频（DEMO）" in h5.text
    assert "<p class=\"video-state\">coming soon</p>" in h5.text
    assert "coming soon" in h5.text
    assert 'href="/?desktop=1"' in h5.text
    assert "桌面版" in h5.text
    assert "mobileHeaderAccountBtn" in h5.text
    assert "accountModule" in h5.text
    assert "历史使用模板" in h5.text
    assert "基础版" in h5.text
    assert "高级版" in h5.text
    assert "继续修改" in h5.text
    assert "模型与 API" in h5.text
    assert "案例展示区" in h5.text
    assert "AI Agent 生图区" in h5.text
    assert "外接 Provider" not in h5.text
    assert "06 / Model Status" in h5.text
    assert "模型状态" in h5.text
    assert "生图通道" in h5.text
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
    assert "lab-style-grid" in mobile_styles.text
    assert ".lab-home-panel[hidden]" in mobile_styles.text
    assert "lab-module-card" in mobile_styles.text
    assert "lab-mobile-action-panel" in mobile_styles.text
    assert "lab-reference-head" in mobile_styles.text
    assert "lab-library-toggle" not in mobile_styles.text
    assert ".lab-library-panel[hidden]" in mobile_styles.text
    assert "lab-library-details" not in mobile_styles.text
    assert "lab-style-more-note" in mobile_styles.text
    assert "lab-search-thinking" in mobile_styles.text
    assert "lab-style-score" in mobile_styles.text
    assert "lab-comparison-grid" in mobile_styles.text
    assert "lab-history-grid" in mobile_styles.text
    assert "lab-card-quality" in mobile_styles.text
    assert "lab-reference-box" in mobile_styles.text
    assert "lab-reference-toggle" not in mobile_styles.text
    assert "lab-reference-list" in mobile_styles.text
    assert ".lab-card-grid" in mobile_styles.text
    assert ".lab-favorite-btn.active" in mobile_styles.text
    assert "v2-template-actions" in mobile_styles.text
    assert ".v2-template-card:focus-visible" in mobile_styles.text
    assert ".mobile-entry-card" in mobile_styles.text
    assert "max-width: 108px" in mobile_styles.text
    assert ".module-tabs .tab.lab-tab" in mobile_styles.text

    mobile_script = client.get("/mobile-static/mobile.js")
    assert mobile_script.status_code == 200
    assert "const ticketAccepted = await handleVeyraTicketFromUrl();" in mobile_script.text
    assert 'lab: "探索各种创意玩法"' in mobile_script.text
    assert "labHistoryGrid" in h5.text
    assert "Alchemy Lab History" in h5.text
    assert "function loadLabHistory" in mobile_script.text
    assert "function renderLabHistory" in mobile_script.text
    assert "/api/lab/history" in mobile_script.text
    assert "function loadLabStyles" in mobile_script.text
    assert "function openLabModule" in mobile_script.text
    assert "function restoreInitialModuleRoute" in mobile_script.text
    assert 'params.get("module") || params.get("tab") || window.location.hash' in mobile_script.text
    assert 'if (route === "rare-style-explorer")' in mobile_script.text
    assert 'openLabModule("rare-style-explorer");' in mobile_script.text
    assert "openLabHome();" in mobile_script.text
    assert "function setLabStyleLibraryOpen" in mobile_script.text
    assert "function renderLabStyleLibraryState" in mobile_script.text
    assert "function createMobileLabArchitecture" in mobile_script.text
    assert "function updateMobileLabSummaries" in mobile_script.text
    assert "lab-run-params" in mobile_script.text
    assert "lab-explore-settings" in mobile_script.text
    assert "lab-reference" in mobile_script.text
    assert "lab-style-library" in mobile_script.text
    assert "lab-history" in mobile_script.text
    assert 'openMobileSurface("lab-history", historyCard);' in mobile_script.text
    assert 'state.heroHistorySource === "lab" || activePanel === "lab"' in mobile_script.text
    assert 'button.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" })' in mobile_script.text
    assert "function handleLabReferenceFiles" in mobile_script.text
    assert "function uploadLabReferenceFile" in mobile_script.text
    assert "function labReferencePayload" in mobile_script.text
    assert "/api/lab/uploads" in mobile_script.text
    assert "/api/v2/uploads" not in mobile_script.text
    assert "reference_assets: labReferencePayload()" in mobile_script.text
    assert 'reference_mode: labState.referenceAssets.length ? "guided" : "off"' in mobile_script.text
    assert "labIntentDirectorInput" in h5.text
    assert "labIntentDirectorInput" in mobile_script.text
    assert 'value="off">纯随机' in h5.text
    assert 'intent_director: labState.intentDirector || "auto"' in mobile_script.text
    assert "不调用智能判断收束风格族" in mobile_script.text
    assert "调用智能判断理解文字和参考图用途" in mobile_script.text
    assert "不会覆盖手动选择的风格" in mobile_script.text
    assert "上传参考图" in h5.text
    assert "renderLabIntentSummary" in mobile_script.text
    assert "function labIntentMetaText" in mobile_script.text
    assert "function filteredLabStyles" in mobile_script.text
    assert "function searchLabStyles" in mobile_script.text
    assert "function setLabStyleSearchThinking" in mobile_script.text
    assert "function renderLabSearchEmptyNotice" in mobile_script.text
    assert "function clearLabStyleSearchInput" in mobile_script.text
    assert "已清空选择和搜索条件" in mobile_script.text
    assert "/api/lab/rare-style-explorer/styles/search" in mobile_script.text
    assert "相关度" in mobile_script.text
    assert "data-lab-load-more-styles" in mobile_script.text
    assert "点击加载更多" in mobile_script.text
    assert "target_count" in mobile_script.text
    assert "lab-rare-style-explorer" not in mobile_script.text
    assert "openLabModuleSurface" not in mobile_script.text
    assert "最后一种承接余数" in mobile_script.text
    assert "generation_interval_seconds" in mobile_script.text
    assert "labDefaultGenerationIntervalSeconds = 8" in mobile_script.text
    assert "function scheduleLabPolling" in mobile_script.text
    assert "等待串行生成" in mobile_script.text
    assert 'value="8"' in h5.text
    assert "quality_enhancement" in mobile_script.text
    assert "labQualityEnhancementInput" in mobile_script.text
    assert "function labQualityMetaText" in mobile_script.text
    assert "智能文案层级已规划" in mobile_script.text
    assert "/api/lab/rare-style-explorer/styles" in mobile_script.text
    assert "/api/lab/rare-style-explorer/sessions" in mobile_script.text
    assert "function runLabExploration" in mobile_script.text
    assert "function renderLabBoard" in mobile_script.text
    assert "function handleLabComparisonClick" in mobile_script.text
    assert "function labProviderPreference" in mobile_script.text
    assert "if (hadVeyraTicket && !ticketAccepted) return;" in mobile_script.text
    assert "/creative/runs/async" in mobile_script.text
    assert "/v1/image/jobs" in mobile_script.text
    assert "setupH5AdvancedPanels" in mobile_script.text
    assert "createH5AdvancedPanel" in mobile_script.text
    assert "参数、素材、修图、历史、模型/API 和事件" not in mobile_script.text
    assert "中枢输出、历史、Provider 和调度" not in mobile_script.text
    assert "Provider & Kernel" not in mobile_script.text
    assert "Provider Prompt Preview" not in mobile_script.text
    assert "Provider Input" not in mobile_script.text
    assert "最终提示词预览" in mobile_script.text
    assert "生成输入" in mobile_script.text
    assert "runV2Creative" in mobile_script.text
    assert "hydrateV2AspectButtons" in mobile_script.text
    assert "v2AspectDisplay" in mobile_script.text
    assert "自动画幅" in mobile_script.text
    assert "card.dataset.v2TemplateId" in mobile_script.text
    assert "selectTemplate();" in mobile_script.text
    assert "data-v2-preview-action" in mobile_script.text
    assert "选择模板" in mobile_script.text
    assert "function v2RequestedImageProvider" in mobile_script.text
    assert "const imageProvider = v2RequestedImageProvider(v2State.modelSettings || {})" in mobile_script.text
    assert "imageAssetPayload" in mobile_script.text
    assert "const historyPageSize = 24" in mobile_script.text
    assert "const v2HistoryPageSize = 24" in mobile_script.text
    assert "const veyraTokenStorageKey" in mobile_script.text
    assert "const veyraAccountStorageKey" in mobile_script.text
    assert "createMobileAccountArchitecture" in mobile_script.text
    assert "mobileAccountSummary" in mobile_script.text
    assert "buildVeyraTemplateHistory" in mobile_script.text
    assert "v2HistoryTemplateCaseId" in mobile_script.text
    assert 'const v2ApiBase = window.ALCHEMY_V2_API_BASE || `${window.location.origin}/api/v2`;' in mobile_script.text
    assert "v2LocalApiBase" not in mobile_script.text
    assert 'v2: "智能中枢统筹创意策略，案例体系赋能品牌视觉升级。"' in mobile_script.text
    assert 'video: "coming soon"' in mobile_script.text
    assert "document.body.dataset.activeModule" in mobile_script.text
    assert "encodeV2CaseAssetPath" in mobile_script.text
    assert "fallbackV2CaseImageToPreview" in mobile_script.text
    assert "if (url.startsWith(\"/api/v2/\")) return v2MediaUrl(url);" in mobile_script.text
    assert "if (url?.startsWith(\"/api/v2/\")) return v2MediaUrl(url);" in mobile_script.text
    assert "scrollV2HomeResultsIntoView(run);" in mobile_script.text
    assert "loadV2HistoryResponse" in mobile_script.text
    assert "/veyra/history?limit=1000" in mobile_script.text
    assert "/v1/veyra/usage?limit=100" in mobile_script.text
    assert "await refreshVeyraAccountPanelAfterHistoryChange();" in mobile_script.text
    assert "deleteV2HistoryItem" in mobile_script.text
    assert "share-poster-download" not in mobile_script.text
    assert "长按保存，扫码打开。" in mobile_script.text
    assert "微信内请用右上角分享" in mobile_script.text
    assert "分享链接" in mobile_script.text


def test_v1_frontend_generation_success_is_not_overridden_by_refresh_failures():
    client = TestClient(app)
    desktop_script = client.get("/static/app.js")
    mobile_script = client.get("/mobile-static/mobile.js")

    for script in (desktop_script, mobile_script):
        assert script.status_code == 200
        text = script.text
        assert "function v1ImageJobDeferred" in text
        assert "polling_deferred: true" in text
        assert "状态查询暂时中断" in text
        assert "return deferV1ImageJob(job" in text
        assert "function refreshV1GenerationSideEffects" in text
        assert "V1 post-generation" in text
        assert "scrollV1GalleryIntoView();" in text
        assert "else if (v1ImageJobDeferred(completedJob))" in text
        assert "finishSimpleProgress(\"v1\", \"generating\", message, \"warning\")" in text


def test_veyra_ui_gate_enters_return_router_before_login():
    original_auth_enabled = settings.veyra_auth_enabled
    original_require_ui_auth = settings.veyra_require_ui_auth
    original_login_base_url = settings.veyra_login_base_url
    settings.veyra_auth_enabled = True
    settings.veyra_require_ui_auth = True
    settings.veyra_login_base_url = "https://aiself.vip/"
    try:
        client = TestClient(app)
        desktop = client.get("/", follow_redirects=False)
        mobile = client.get("/h5", follow_redirects=False)

        assert desktop.status_code == 307
        assert desktop.headers["location"] == "https://aiself.vip/_veyra/return?target=alchemy"
        assert "/login?" not in desktop.headers["location"]
        assert mobile.status_code == 307
        assert mobile.headers["location"] == "https://aiself.vip/_veyra/return?target=alchemy-mobile"
        assert "/login?" not in mobile.headers["location"]
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_require_ui_auth = original_require_ui_auth
        settings.veyra_login_base_url = original_login_base_url


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
    assert "http://testserver/share/save-image?" in response.text
    assert "http://testserver/share/poster?" not in response.text
    assert "打开 Alchemy" in response.text
    assert "查看原图" in response.text
    assert "下载分享图" not in response.text
    assert "长按保存 · 右上角分享" in response.text
    assert "分享海报" not in response.text


def test_image_share_save_image_returns_lightweight_jpeg():
    client = TestClient(app)

    response = client.get(
        "/share/save-image",
        params={"image": "/static/showcase/city-poster.jpg"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content.startswith(b"\xff\xd8")
    assert len(response.content) > 10_000


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


def test_image_share_poster_reads_v2_local_output(tmp_path, monkeypatch):
    from PIL import Image

    storage_root = tmp_path / "v2_storage"
    output_id = "out_v2_share"
    output_dir = storage_root / "outputs" / "job_v2_share"
    output_dir.mkdir(parents=True)
    source_path = output_dir / f"{output_id}.png"
    Image.new("RGB", (640, 640), (20, 120, 220)).save(source_path)
    thumbnail_dir = storage_root / "thumbnails"
    thumbnail_dir.mkdir(parents=True)
    Image.new("RGB", (320, 320), (20, 120, 220)).save(thumbnail_dir / f"{output_id}.webp")
    monkeypatch.setenv("V2_STORAGE_DIR", str(storage_root))
    captured = {}

    def fake_render_share_poster(**kwargs):
        image = main_module._load_share_preview_image(kwargs["request"], kwargs["image_value"])
        captured["pixel"] = image.convert("RGB").getpixel((0, 0))
        return b"\x89PNG\r\n\x1a\nfake"

    monkeypatch.setattr(main_module, "_render_share_poster", fake_render_share_poster)
    client = TestClient(app)

    response = client.get(
        "/share/poster",
        params={
            "image": f"/api/v2/outputs/{output_id}/download",
            "thumb": f"/api/v2/image/history/{output_id}/thumbnail",
        },
    )

    assert response.status_code == 200
    assert all(abs(actual - expected) <= 4 for actual, expected in zip(captured["pixel"], (20, 120, 220)))


def test_image_share_poster_qr_defaults_to_share_landing_page(monkeypatch):
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
    assert captured["share_url"].startswith("http://testserver/share/image?")
    assert "image=http%3A%2F%2Ftestserver%2Fv1%2Foutputs%2Fout_share%2Fdownload" in captured["share_url"]


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
    image_body = _completed_image_job(client, image_job)
    output_url = image_body["outputs"][0]["url"]

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


def test_image_history_excludes_alchemy_lab_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "alchemy_lab_rare_style_explorer"}).json()["id"]

    image_job = client.post(
        "/v1/image/jobs",
        json={
            "session_id": session_id,
            "prompt": "Alchemy Lab image should stay out of V1 history.",
            "count": 1,
            "provider_preference": "mock_image",
            "idempotency_key": "lab:session:variant:attempt:0",
        },
    )
    assert image_job.status_code == 200

    history = client.get("/v1/image/history")
    assert history.status_code == 200
    assert history.json()["total"] == 0

    repository.reset()
    output_path = media_store.output_path(job_id="job_lab_manifest", output_id="out_lab_manifest", output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    media_store.save_history_record(
        {
            "id": "out_lab_manifest",
            "job_id": "job_lab_manifest",
            "session_id": session_id,
            "url": "/v1/outputs/out_lab_manifest/download",
            "thumbnail_url": "/v1/outputs/out_lab_manifest/thumbnail",
            "format": "png",
            "provider": "mock_image",
            "model": "mock-image-v1",
            "source_app": "alchemy_lab_rare_style_explorer",
            "idempotency_key": "lab:manifest:variant:attempt:0",
            "prompt": "lab manifest",
            "created_at": "2026-04-01T09:00:00+00:00",
            "updated_at": "2026-04-01T09:00:00+00:00",
            "alchemy_lab": {
                "idea": "测试 Lab 历史",
                "style_name": "CRT 像素界面静物",
                "style_family": "digital",
                "mode": "poster",
                "mode_label": "海报封面",
                "keywords": ["crt", "pixel"],
            },
        }
    )

    manifest_history = client.get("/v1/image/history")
    assert manifest_history.status_code == 200
    assert manifest_history.json()["total"] == 0

    lab_history = client.get("/api/lab/history?include_mock=true")
    assert lab_history.status_code == 200
    body = lab_history.json()
    assert body["total"] >= 1
    item = next(item for item in body["items"] if item["id"] == "out_lab_manifest")
    assert item["module_label"] == "Rare Style Explorer"
    assert item["style_name"] == "CRT 像素界面静物"
    legacy_lab_history = client.get("/api/lab/rare-style-explorer/history?include_mock=true")
    assert legacy_lab_history.status_code == 200
    assert "out_lab_manifest" in {item["id"] for item in legacy_lab_history.json()["items"]}


def test_alchemy_lab_history_hides_mock_outputs_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    client = TestClient(app)
    output_path = media_store.output_path(job_id="job_lab_mock", output_id="out_lab_mock", output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    media_store.save_history_record(
        {
            "id": "out_lab_mock",
            "job_id": "job_lab_mock",
            "session_id": "ses_lab_mock",
            "url": "/v1/outputs/out_lab_mock/download",
            "thumbnail_url": "/v1/outputs/out_lab_mock/thumbnail",
            "format": "png",
            "provider": "mock_image",
            "model": "mock-image-v1",
            "source_app": "alchemy_lab_rare_style_explorer",
            "idempotency_key": "lab:mock:variant:attempt:0",
            "prompt": "mock lab image",
            "created_at": "2026-04-01T09:00:00+00:00",
            "updated_at": "2026-04-01T09:00:00+00:00",
            "alchemy_lab": {"idea": "mock", "style_name": "Mock Style"},
        }
    )

    public_history = client.get("/api/lab/history")
    assert public_history.status_code == 200
    assert public_history.json()["total"] == 0

    debug_history = client.get("/api/lab/history?include_mock=true")
    assert debug_history.status_code == 200
    assert "out_lab_mock" in {item["id"] for item in debug_history.json()["items"]}


def test_v2_local_proxy_target_uses_same_origin_shell():
    assert main_module._v2_proxy_target_url("health", "x=1").endswith("/api/v2/health?x=1")
    assert main_module._v2_proxy_target_url("/templates/page").endswith("/api/v2/templates/page")


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


def test_v1_account_history_filters_user_public_and_admin_records(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"

    async def fake_load_account(user_id: int):
        role = "admin" if user_id == 99 else "user"
        return type("Account", (), {"user_id": user_id, "role": role})()

    monkeypatch.setattr(main_module, "load_account", fake_load_account)

    from app.services.veyra_auth import verify_session_token

    try:
        client = TestClient(app)
        user_token = _issue_test_veyra_session_token(42)
        admin_token = _issue_test_veyra_session_token(99)
        assert verify_session_token(user_token) == 42
        session_response = client.post(
            "/v1/sessions",
            json={"project_id": "proj_account_history"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["id"]

        user_id = "out_user_account"
        user_path = media_store.output_path(job_id="job_user_account", output_id=user_id, output_format="png")
        user_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": user_id,
                "job_id": "job_user_account",
                "session_id": session_id,
                "url": f"/v1/outputs/{user_id}/download",
                "thumbnail_url": f"/v1/outputs/{user_id}/thumbnail",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "user owned image",
                "veyra_user_id": 42,
                "created_at": "2026-06-11T00:00:00+00:00",
                "updated_at": "2026-06-11T00:00:00+00:00",
            }
        )

        other_id = "out_other_account"
        other_path = media_store.output_path(job_id="job_other_account", output_id=other_id, output_format="png")
        other_path.parent.mkdir(parents=True, exist_ok=True)
        other_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": other_id,
                "job_id": "job_other_account",
                "session_id": session_id,
                "url": f"/v1/outputs/{other_id}/download",
                "thumbnail_url": f"/v1/outputs/{other_id}/thumbnail",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "other account image",
                "veyra_user_id": 77,
                "created_at": "2026-06-11T00:01:00+00:00",
                "updated_at": "2026-06-11T00:01:00+00:00",
            }
        )
        public_id = "out_public_before_accounts"
        public_path = media_store.output_path(job_id="job_public_before_accounts", output_id=public_id, output_format="png")
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": public_id,
                "job_id": "job_public_before_accounts",
                "session_id": session_id,
                "url": f"/v1/outputs/{public_id}/download",
                "thumbnail_url": f"/v1/outputs/{public_id}/thumbnail",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "public image before accounts",
                "created_at": "2026-06-11T00:02:00+00:00",
                "updated_at": "2026-06-11T00:02:00+00:00",
            }
        )

        user_history = client.get("/v1/image/history?limit=10", headers={"Authorization": f"Bearer {user_token}"})
        admin_history = client.get("/v1/image/history?limit=10", headers={"Authorization": f"Bearer {admin_token}"})

        assert user_history.status_code == 200
        user_ids = {item["id"] for item in user_history.json()["items"]}
        assert public_id in user_ids
        assert other_id not in user_ids
        assert user_id in user_ids
        assert admin_history.status_code == 200
        admin_ids = {item["id"] for item in admin_history.json()["items"]}
        assert {user_id, other_id, public_id}.issubset(admin_ids)
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_alchemy_lab_history_and_images_are_shared_across_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"

    async def fake_load_account(user_id: int):
        return type("Account", (), {"user_id": user_id, "role": "user"})()

    monkeypatch.setattr(main_module, "load_account", fake_load_account)

    try:
        client = TestClient(app)
        owner_token = _issue_test_veyra_session_token(42)
        other_token = _issue_test_veyra_session_token(77)
        lab_id = "out_lab_shared_account"
        lab_path = media_store.output_path(job_id="job_lab_shared_account", output_id=lab_id, output_format="png")
        lab_path.parent.mkdir(parents=True, exist_ok=True)
        lab_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": lab_id,
                "job_id": "job_lab_shared_account",
                "session_id": "ses_lab_shared_account",
                "url": f"/v1/outputs/{lab_id}/download",
                "thumbnail_url": f"/v1/outputs/{lab_id}/download",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "shared lab image",
                "source_app": "alchemy_lab_rare_style_explorer",
                "veyra_user_id": 42,
                "alchemy_lab": {
                    "idea": "共享 Lab 历史",
                    "style_name": "Cinematic",
                    "mode": "poster",
                    "keywords": ["shared", "lab"],
                },
                "created_at": "2026-06-11T00:03:00+00:00",
                "updated_at": "2026-06-11T00:03:00+00:00",
            }
        )
        v1_id = "out_v1_private_account"
        v1_path = media_store.output_path(job_id="job_v1_private_account", output_id=v1_id, output_format="png")
        v1_path.parent.mkdir(parents=True, exist_ok=True)
        v1_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        media_store.save_history_record(
            {
                "id": v1_id,
                "job_id": "job_v1_private_account",
                "session_id": "ses_v1_private_account",
                "url": f"/v1/outputs/{v1_id}/download",
                "thumbnail_url": f"/v1/outputs/{v1_id}/download",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "private v1 image",
                "veyra_user_id": 42,
                "created_at": "2026-06-11T00:04:00+00:00",
                "updated_at": "2026-06-11T00:04:00+00:00",
            }
        )

        lab_history = client.get("/api/lab/history?limit=10&include_mock=true", headers={"Authorization": f"Bearer {other_token}"})
        legacy_lab_history = client.get("/api/lab/rare-style-explorer/history?limit=10&include_mock=true", headers={"Authorization": f"Bearer {other_token}"})
        v1_history = client.get("/v1/image/history?limit=10", headers={"Authorization": f"Bearer {other_token}"})
        lab_download = client.get(f"/v1/outputs/{lab_id}/download", headers={"Authorization": f"Bearer {other_token}"})
        v1_download = client.get(f"/v1/outputs/{v1_id}/download", headers={"Authorization": f"Bearer {other_token}"})
        owner_download = client.get(f"/v1/outputs/{lab_id}/download", headers={"Authorization": f"Bearer {owner_token}"})
        other_delete = client.delete(f"/v1/image/history/{lab_id}", headers={"Authorization": f"Bearer {other_token}"})

        assert lab_history.status_code == 200
        assert lab_id in {item["id"] for item in lab_history.json()["items"]}
        assert legacy_lab_history.status_code == 200
        assert lab_id in {item["id"] for item in legacy_lab_history.json()["items"]}
        assert v1_history.status_code == 200
        assert v1_id not in {item["id"] for item in v1_history.json()["items"]}
        assert lab_download.status_code == 200
        assert owner_download.status_code == 200
        assert v1_download.status_code == 403
        assert other_delete.status_code == 403
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_v1_revise_rejects_other_account_history_output(monkeypatch):
    repository.reset()
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"

    async def fake_load_account(user_id: int):
        return type("Account", (), {"user_id": user_id, "role": "user"})()

    monkeypatch.setattr(main_module, "load_account", fake_load_account)

    try:
        client = TestClient(app)
        owner_token = _issue_test_veyra_session_token(42)
        other_token = _issue_test_veyra_session_token(77)
        session_id = client.post(
            "/v1/sessions",
            json={"project_id": "proj_revise_isolation"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]
        output_id = "out_revise_account_owner"
        job_id = "job_revise_account_owner"
        output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(tiny_png_b64()))
        media_store.save_history_record(
            {
                "id": output_id,
                "job_id": job_id,
                "session_id": session_id,
                "url": f"/v1/outputs/{output_id}/download",
                "thumbnail_url": f"/v1/outputs/{output_id}/thumbnail",
                "format": "png",
                "provider": "mock_image",
                "model": "mock-image-v1",
                "prompt": "owner image",
                "veyra_user_id": 42,
                "created_at": "2026-06-11T00:05:00+00:00",
                "updated_at": "2026-06-11T00:05:00+00:00",
            }
        )

        blocked = client.post(
            f"/v1/image/jobs/{job_id}/revise",
            json={"output_id": output_id, "feedback": "换成咖啡"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        allowed = client.post(
            f"/v1/image/jobs/{job_id}/revise",
            json={"output_id": output_id, "feedback": "换成咖啡", "provider_preference": "mock_image"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert blocked.status_code == 403
        assert allowed.status_code == 200
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_v1_asset_uploads_are_bound_to_current_veyra_account(monkeypatch):
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"
    try:
        client = TestClient(app)
        owner_token = _issue_test_veyra_session_token(42)
        other_token = _issue_test_veyra_session_token(77)

        upload = client.post(
            "/v1/assets/upload-url",
            json={
                "filename": "owned.png",
                "mime_type": "image/png",
                "size_bytes": 4,
                "consent": {"rights_confirmed": True},
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert upload.status_code == 200
        asset_id = upload.json()["asset_id"]
        assert repository.get_asset(asset_id).veyra_user_id == 42

        owner_lookup = client.get(f"/v1/assets/{asset_id}", headers={"Authorization": f"Bearer {owner_token}"})
        other_lookup = client.get(f"/v1/assets/{asset_id}", headers={"Authorization": f"Bearer {other_token}"})
        assert owner_lookup.status_code == 200
        assert other_lookup.status_code == 403

        session = client.post(
            "/v1/sessions",
            json={"project_id": "proj_asset_owner"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert session.status_code == 200
        blocked_job = client.post(
            "/v1/image/jobs",
            json={
                "session_id": session.json()["id"],
                "prompt": "尝试使用其他账号上传的素材。",
                "asset_mode": "advanced",
                "asset_intents": [
                    {
                        "asset_id": asset_id,
                        "role": "style_reference",
                        "consent": {"rights_confirmed": True},
                    }
                ],
            },
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert blocked_job.status_code == 403
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_v1_advanced_asset_request_enforces_asset_count_limit():
    client = TestClient(app)
    original_limit = settings.max_asset_upload_count
    settings.max_asset_upload_count = 1
    try:
        session = client.post("/v1/sessions", json={"project_id": "proj_asset_count"})
        assert session.status_code == 200
        response = client.post(
            "/v1/image/jobs",
            json={
                "session_id": session.json()["id"],
                "prompt": "用多张参考图生成商品海报。",
                "asset_mode": "advanced",
                "asset_intents": [
                    {"asset_id": "asset_a", "role": "style_reference", "consent": {"rights_confirmed": True}},
                    {"asset_id": "asset_b", "role": "subject_reference", "consent": {"rights_confirmed": True}},
                ],
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "asset_count_exceeded"
    finally:
        settings.max_asset_upload_count = original_limit


def test_v1_veyra_usage_filters_current_user(monkeypatch):
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"
    settings.veyra_usage_path.write_text(
        "\n".join(
            [
                '{"user_id":42,"amount":1.2,"balance_after":8.8,"idempotency_key":"v1:user","reference_id":"job_user","source":"alchemy:v1","created_at":"2026-06-11T00:00:00+00:00"}',
                '{"user_id":77,"amount":9.9,"balance_after":1,"idempotency_key":"v1:other","reference_id":"job_other","source":"alchemy:v1","created_at":"2026-06-11T00:01:00+00:00"}',
            ]
        ),
        encoding="utf-8",
    )

    try:
        client = TestClient(app)
        token = _issue_test_veyra_session_token(42)
        response = client.get("/v1/veyra/usage?limit=10", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["reference_id"] == "job_user"
        assert body["items"][0]["amount"] == 1.2
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_v1_logged_in_generation_appears_in_account_history_and_usage(monkeypatch):
    original_auth_enabled = settings.veyra_auth_enabled
    original_internal_token = settings.veyra_internal_token
    original_session_secret = settings.veyra_session_secret
    settings.veyra_auth_enabled = True
    settings.veyra_internal_token = "bridge-secret"
    settings.veyra_session_secret = "session-secret"

    async def fake_load_account(user_id: int):
        return type("Account", (), {"user_id": user_id, "role": "user", "balance": 100})()

    async def fake_load_billing_rule(rule_key: str | None = None):
        return type("Rule", (), {"key": rule_key or "alchemy:v1", "enabled": True, "charge_amount": 2.5, "source": "alchemy:v1"})()

    async def fake_ensure_sufficient_balance(*, user_id: int, amount: float):
        return type("Account", (), {"user_id": user_id, "role": "user", "balance": 100})()

    async def fake_debit_balance(*, user_id: int, amount: float, idempotency_key: str, source: str, reference_id: str):
        return type(
            "Debit",
            (),
            {
                "user_id": user_id,
                "amount": amount,
                "balance_after": 97.5,
                "idempotency_key": idempotency_key,
                "source": source,
                "replayed": False,
            },
        )()

    monkeypatch.setattr(main_module, "load_account", fake_load_account)
    monkeypatch.setattr(image_service_module, "load_billing_rule", fake_load_billing_rule)
    monkeypatch.setattr(image_service_module, "ensure_sufficient_balance", fake_ensure_sufficient_balance)
    monkeypatch.setattr(image_service_module, "debit_balance", fake_debit_balance)

    try:
        client = TestClient(app)
        token = _issue_test_veyra_session_token(42)
        session = client.post(
            "/v1/sessions",
            json={"project_id": "proj_v1_account_generation"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert session.status_code == 200
        session_id = session.json()["id"]

        image_job = client.post(
            "/v1/image/jobs",
            json={
                "session_id": session_id,
                "prompt": "生成一张账户历史测试图。",
                "count": 1,
                "provider_preference": "mock_image",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        job = _completed_image_job(client, image_job, headers={"Authorization": f"Bearer {token}"})
        assert job["status"] == "ready"
        output_id = job["outputs"][0]["id"]
        assert job["outputs"][0]["metadata"]["veyra_user_id"] == 42

        history = client.get("/v1/image/history?limit=10", headers={"Authorization": f"Bearer {token}"})
        assert history.status_code == 200
        history_items = history.json()["items"]
        assert any(item["id"] == output_id and item["veyra_user_id"] == 42 for item in history_items)

        usage = client.get("/v1/veyra/usage?limit=10", headers={"Authorization": f"Bearer {token}"})
        assert usage.status_code == 200
        usage_items = usage.json()["items"]
        assert any(item["reference_id"] == job["id"] and item["amount"] == 2.5 for item in usage_items)
    finally:
        settings.veyra_auth_enabled = original_auth_enabled
        settings.veyra_internal_token = original_internal_token
        settings.veyra_session_secret = original_session_secret


def test_v1_local_generation_skips_remote_billing_when_veyra_disabled(monkeypatch):
    original_auth_enabled = settings.veyra_auth_enabled
    settings.veyra_auth_enabled = False

    async def fail_if_billing_rule_loaded(rule_key: str | None = None):
        raise AssertionError("local generation must not call remote billing settings when Veyra auth is disabled")

    monkeypatch.setattr(image_service_module, "load_billing_rule", fail_if_billing_rule_loaded)

    try:
        client = TestClient(app)
        session = client.post("/v1/sessions", json={"project_id": "proj_local_no_billing"})
        assert session.status_code == 200
        response = client.post(
            "/v1/image/jobs",
            json={
                "session_id": session.json()["id"],
                "prompt": "生成一张本地免计费测试图。",
                "count": 1,
                "provider_preference": "mock_image",
            },
        )

        job = _completed_image_job(client, response)
        assert job["status"] == "ready"
        assert job["outputs"]
    finally:
        settings.veyra_auth_enabled = original_auth_enabled


def _issue_test_veyra_session_token(user_id: int) -> str:
    import hashlib
    import hmac
    import json
    import time

    secret = str(settings.veyra_session_secret or settings.veyra_internal_token).encode("utf-8")
    now = int(time.time())
    payload = {"user_id": int(user_id), "iat": now, "exp": now + 3600}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).decode("ascii").rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
    return raw + "." + signature


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

    body = _completed_image_job(client, response)
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

    body = _completed_image_job(client, response)
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
    image_body = _completed_image_job(client, image_response)
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
    original_doubao_image_model = settings.doubao_image_model
    original_doubao_image_base_url = settings.doubao_image_base_url
    original_doubao_image_api_key = settings.doubao_image_api_key
    original_gemini_image_model = settings.gemini_image_model
    original_gemini_image_base_url = settings.gemini_image_base_url
    original_gemini_image_api_key = settings.gemini_image_api_key
    original_gemini_image_enabled = settings.gemini_image_generation_enabled
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
                "doubao_image_model": "doubao-seedream-test",
                "doubao_image_api_key": "sk-test-doubao-image-only",
                "doubao_image_base_url": "https://doubao-image.example.test",
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
        assert body["doubao_image_model"] == "doubao-seedream-test"
        assert body["doubao_image_base_url"] == "https://doubao-image.example.test/v1"
        assert body["doubao_image_api_key_configured"] is True
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
        assert "sk-test-doubao-image-only" not in response.text
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
        assert "DOUBAO_IMAGE_MODEL=doubao-seedream-test" in env_text
        assert "DOUBAO_IMAGE_BASE_URL=https://doubao-image.example.test/v1" in env_text
        assert "GEMINI_IMAGE_BASE_URL=https://gemini-image.example.test" in env_text
        assert "ANTHROPIC_BASE_URL=https://backup.example.test" in env_text
        assert "sk-test-runtime-only" not in env_text
        assert "sk-test-doubao-image-only" not in env_text
        assert "sk-test-backup-only" not in env_text
        assert "sk-test-gemini-image-only" not in env_text

        providers = client.get("/v1/providers").json()
        openai_caps = next(provider for provider in providers["image"] if provider["provider"] == "openai_gpt_image")
        doubao_caps = next(provider for provider in providers["image"] if provider["provider"] == "doubao_image")
        gemini_caps = next(provider for provider in providers["image"] if provider["provider"] == "gemini_image")
        seedance_caps = next(provider for provider in providers["video"] if provider["provider"] == "seedance")
        assert openai_caps["models"] == ["gpt-image-2-test"]
        assert doubao_caps["models"] == ["doubao-seedream-test"]
        assert doubao_caps["configured"] is True
        assert doubao_caps["limits"]["supports_reference_images"] is False
        assert gemini_caps["models"] == ["gemini-image-test"]
        assert gemini_caps["configured"] is False
        assert gemini_caps["limits"]["temporarily_disabled"] is True
        assert seedance_caps["configured"] is False
    finally:
        settings.persist_runtime_settings = original_persist
        settings.runtime_env_path = original_runtime_env_path
        settings.default_image_model = original_model
        settings.default_llm_model = original_llm_model
        settings.default_image_provider = original_provider
        settings.default_llm_provider = original_llm_provider
        settings.openai_image_model = original_openai_image_model
        settings.doubao_image_model = original_doubao_image_model
        settings.doubao_image_base_url = original_doubao_image_base_url
        settings.doubao_image_api_key = original_doubao_image_api_key
        settings.gemini_image_model = original_gemini_image_model
        settings.gemini_image_base_url = original_gemini_image_base_url
        settings.gemini_image_api_key = original_gemini_image_api_key
        settings.gemini_image_generation_enabled = original_gemini_image_enabled
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


def test_runtime_provider_settings_apply_when_persistence_fails(monkeypatch):
    client = TestClient(app)
    original_intensity = settings.image_work_intensity

    def fail_persist():
        raise OSError("runtime env is read-only")

    try:
        monkeypatch.setattr(main_module, "persist_runtime_settings_to_env", fail_persist)
        response = client.post(
            "/v1/runtime/provider-settings",
            json={"image_work_intensity": "atelier"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["image_work_intensity"] == "atelier"
        assert body["runtime_persistence_warning"]
        assert "写入 .env 失败" in body["runtime_persistence_warning"]
        assert settings.image_work_intensity == "atelier"
    finally:
        settings.image_work_intensity = original_intensity
