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

from app.config import settings
from app.providers.images.registry import get_v2_image_provider
import app.main as main_module
from app.main import app
from app.repositories import repository
from app.schemas import CreateImageJobRequest, ImagePromptPlan, PromptCase, PromptCaseSummary
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_intelligence import build_case_profile
import app.services.claude_orchestrator as claude_orchestrator_service
import app.services.generation as generation_service
from app.services.prompting import compose_prompt_plan
import app.services.queue_worker as queue_worker_service
import app.services.task_queue as task_queue_service
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
    object.__setattr__(settings, "gemini_api_key", "sk-test-gemini")
    object.__setattr__(settings, "persist_image_history", False)
    object.__setattr__(settings, "sync_github_on_startup", False)
    object.__setattr__(settings, "claude_orchestrator_enabled", False)
    object.__setattr__(settings, "claude_orchestrator_model", None)
    object.__setattr__(settings, "claude_orchestrator_fallback_model", None)
    object.__setattr__(settings, "claude_orchestrator_timeout_seconds", 240.0)
    object.__setattr__(settings, "claude_orchestrator_max_output_tokens", 32000)
    object.__setattr__(settings, "claude_orchestrator_effort", "low")
    object.__setattr__(settings, "claude_orchestrator_tools", "none")
    object.__setattr__(settings, "claude_checkpoint_orchestrator_enabled", False)
    object.__setattr__(settings, "claude_checkpoint_max_stage_retries", 2)
    object.__setattr__(settings, "claude_checkpoint_stage_timeout_seconds", 180.0)
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


def upload_test_asset(client: TestClient, *, role: str = "subject_reference", color=(32, 96, 180)) -> str:
    image_bytes = BytesIO()
    Image.new("RGB", (320, 240), color).save(image_bytes, format="PNG")
    return upload_image_asset(client, image_bytes.getvalue(), role=role, filename=f"{role}.png")


def upload_image_asset(client: TestClient, image_content: bytes, *, role: str, filename: str = "uploaded.png") -> str:
    upload = client.post(
        "/api/v2/uploads",
        json={
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(image_content),
            "role": role,
            "constraint_strength": "required",
        },
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
        assert image.width <= 360
        assert image.height <= 450


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

    monkeypatch.setattr(claude_orchestrator_service.subprocess, "run", fake_run)
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
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
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
        candidate = json.loads((workspace / "candidate_cases.json").read_text(encoding="utf-8"))[0]["case_id"]
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
    assert calls == ["intent", "visual_strategy", "generation_decision", "generation_decision_micro_retry_1"]
    assert decision["provider"] == "claude-code"
    assert decision["invocation_status"] == "checkpoint_success"
    assert len(decision["final_prompt"]) <= 180
    assert "deterministic" not in decision["provider"]


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
    assert calls == ["intent", "visual_strategy", "generation_decision", "generation_decision_micro_retry_1"]
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
    assert calls == ["intent", "intent_micro_retry_1"]
    assert decision["provider"] == "deterministic-fallback"
    assert decision["invocation_status"] == "checkpoint_fallback"
    assert decision["fallback_reason"] == "claude_checkpoint_missing_decision"
    assert decision["attempts"] == 2


def test_checkpoint_stage_uses_prompt_contract_without_cli_schema_by_default(monkeypatch, tmp_path: Path) -> None:
    fresh_client()
    object.__setattr__(settings, "claude_checkpoint_cli_schema_enabled", False)
    object.__setattr__(settings, "claude_orchestrator_timeout_seconds", 240.0)
    object.__setattr__(settings, "claude_checkpoint_stage_timeout_seconds", 123.0)
    object.__setattr__(settings, "claude_checkpoint_soft_stage_timeout_seconds", 60.0)
    captured: dict[str, object] = {}

    def fake_run(command_line, **kwargs):
        captured["command_line"] = command_line
        captured["env"] = kwargs["env"]
        captured["timeout"] = kwargs["timeout"]
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

    monkeypatch.setattr(claude_orchestrator_service.subprocess, "run", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed["stage"] == "intent"
    assert "--json-schema" not in captured["command_line"]
    assert captured["env"]["MAX_STRUCTURED_OUTPUT_RETRIES"] == "0"
    assert captured["timeout"] == 60.0
    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("intent_micro_retry_1") == 61.5
    assert claude_orchestrator_service._checkpoint_stage_timeout_seconds("intent_ultra_micro_retry_2") == 60.0


def test_checkpoint_stage_accepts_safe_micro_alias_and_confidence_label(monkeypatch, tmp_path: Path) -> None:
    fresh_client()

    def fake_run(command_line, **kwargs):
        result = json.dumps(
            {
                "stage": "intent_micro",
                "mode": "smart_enhance",
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

    monkeypatch.setattr(claude_orchestrator_service.subprocess, "run", fake_run)

    parsed = claude_orchestrator_service._invoke_claude_stage_json(
        command=["claude"],
        workspace=tmp_path,
        stage_name="intent_micro_retry_1",
        prompt="Return JSON.",
        schema=claude_orchestrator_service.CLAUDE_INTENT_CHECKPOINT_SCHEMA,
    )

    assert parsed["stage"] == "intent"
    assert parsed["confidence"] == 0.9
    assert parsed["risk_notes"] == ["no specific product identity supplied"]


def test_checkpoint_stage_rejects_missing_required_fields(monkeypatch, tmp_path: Path) -> None:
    fresh_client()

    def fake_run(command_line, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": json.dumps({"stage": "intent"})}), stderr="")

    monkeypatch.setattr(claude_orchestrator_service.subprocess, "run", fake_run)

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
    assert "Think fully" not in prompt
    assert "bounded internal" in claude_orchestrator_service._checkpoint_system_prompt()
    assert len(prompt) < 2100


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
    assert payload["checkpoints"]["intent"]["primary_subject"].endswith("...")
    assert payload["checkpoints"]["visual_strategy"]["composition"].endswith("...")
    assert len(prompt) < 3500


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
    assert body["claude_checkpoint_orchestrator_enabled"] is True
    assert body["case_intelligence_provider"] == "claude-code"
    assert body["case_intelligence_model"] == "claude-sonnet-test"

    status = client.get("/api/v2/orchestrator/status")
    assert status.status_code == 200
    assert status.json()["model"] == "claude-sonnet-test"
    assert status.json()["timeout_seconds"] == settings.claude_orchestrator_timeout_seconds
    assert status.json()["max_output_tokens"] == settings.claude_orchestrator_max_output_tokens
    assert status.json()["checkpoint_enabled"] is True

    profile = client.get("/api/v2/case-profiles/case_github_evolinkai_ad_0001")
    assert profile.status_code == 200
    assert profile.json()["source"] == "rules"


def test_runtime_model_settings_accepts_gemini_image_provider() -> None:
    client = fresh_client()

    response = client.post("/api/v2/runtime/model-settings", json={"image_generation_provider": "gemini_image"})

    assert response.status_code == 200
    assert response.json()["image_generation_provider"] == "gemini_image"
    assert settings.image_generation_provider == "gemini_image"


def test_v2_auto_provider_hint_inherits_gemini_setting() -> None:
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
    assert output.metadata["input_images"][0]["asset_id"] == asset_id
    assert output.metadata["input_images"][0]["role"] == "logo_reference"
    assert "logo_overlay" not in str(output.metadata)
    assert Path(output.metadata["storage_path"]).exists()


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
    assert "TEMPLATE LOCK: use the hand-selected template 'Pastel Jellyfish Room Goods Poster'" in prompt
    assert "soft dreamy lavender jellyfish aesthetic" in run["prompt_plan"]["prompt"]
    assert "let the template win" in run["prompt_plan"]["prompt"]
    assert "Generic minimal studio portrait" in run["prompt_plan"]["prompt"]
    negative_terms = {term.strip().lower() for term in run["prompt_plan"]["negative_prompt"].split(",")}
    assert "text" not in negative_terms
    assert "highest-priority visual anchor" in run["prompt_plan"]["risk_notes"][0]


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
    assert run["prompt_plan"]["prompt"] == run["orchestrator_decision"]["final_prompt"]
    assert run["prompt_plan"]["user_variables"]["prompt_source"] == "claude_final_prompt"
    assert run["prompt_plan"]["provider_parameters"]["aspect_ratio"] == "4:5"
    assert run["prompt_plan"]["provider_parameters"]["provider_hint"] == "mock_image"
    assert "avoid crowded background" in run["prompt_plan"]["negative_prompt"]
    assert "unlicensed third-party logos" in run["prompt_plan"]["negative_prompt"]
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
    assert history["items"][0]["metadata"]["original_prompt"] == "Minimal clean ecommerce product listing image."
    assert history["items"][0]["metadata"]["final_prompt"] == history["items"][0]["prompt"]
    assert history["items"][0]["metadata"]["native_v2"] is True
    assert history["items"][0]["metadata"]["native_v2_storage"] is True


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
