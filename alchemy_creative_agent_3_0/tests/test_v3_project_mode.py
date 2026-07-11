import base64
from io import BytesIO

from alchemy_creative_agent_3_0.app.project_mode import (
    PersistentProjectStore,
    ProjectTemplateRegistry,
    TemplateActivationError,
)
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore, V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry


def _project_handlers_with_brand_store(tmp_path):
    brand_service = BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))
    product_service = V3ProductApiService(brand_profile_service=brand_service)
    product_service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    return V3ProductRouteHandlers(service=product_service), brand_service


def _project_handlers_with_output_store(tmp_path) -> V3ProductRouteHandlers:
    product_service = V3ProductApiService(
        output_store=V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    )
    product_service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    return V3ProductRouteHandlers(service=product_service)


def _png_base64() -> str:
    from PIL import Image

    image = Image.new("RGB", (16, 16), color=(220, 224, 230))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ready_upload(
    handlers: V3ProductRouteHandlers,
    tmp_path,
    *,
    role: str = "style_reference",
    filename: str = "reference.png",
) -> str:
    handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": 256,
            "role": role,
        }
    )
    handlers.put_upload_content(created["asset_id"], {"content_base64": _png_base64(), "mime_type": "image/png"})
    ready = handlers.post_upload_complete(created["asset_id"])
    assert ready["status"] == "ready"
    return created["asset_id"]


def _pending_upload(
    handlers: V3ProductRouteHandlers,
    tmp_path,
    *,
    role: str = "product_reference",
    filename: str = "reference.png",
) -> str:
    handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": 256,
            "role": role,
        }
    )
    return created["asset_id"]


def _save_project_output(
    handlers: V3ProductRouteHandlers,
    *,
    job_id: str,
    candidate_id: str,
    asset_id: str,
    owner_user_id: int | None = None,
    prompt: str = "clean commercial image",
    metadata_override: dict | None = None,
):
    metadata = {
        "final_provider_prompt": prompt,
        "compiled_visual_direction": "clean bright commercial direction",
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
    }
    if owner_user_id is not None:
        metadata["veyra_user_id"] = owner_user_id
    if metadata_override:
        metadata.update(metadata_override)
    return handlers.service.output_store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=asset_id,
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
        metadata=metadata,
    )


def _save_project_output_batch(
    handlers: V3ProductRouteHandlers,
    *,
    job_id: str,
    attempt: int,
    count: int,
    prefix: str,
) -> list[str]:
    output_ids = []
    for index in range(count):
        record = _save_project_output(
            handlers,
            job_id=job_id,
            candidate_id=f"{prefix}_candidate_{index}",
            asset_id=f"{prefix}_asset_{index}",
            metadata_override={
                "requested_image_count": count,
                "visual_auto_retry_attempt": attempt,
                "visual_retry_reason_codes": ["lower_right_mark_artifact"] if attempt else [],
            },
        )
        output_ids.append(record.output_id)
    return output_ids


def test_template_registry_contains_general_active() -> None:
    registry = ProjectTemplateRegistry()
    manifests = {manifest.template_id: manifest for manifest in registry.list_manifests()}
    cards = {card.template_id: card for card in registry.list_cards()}

    assert manifests["general_template"].status == "active"
    assert manifests["general_template"].scenario_pack_id == "general_creative"
    assert manifests["general_template"].context_write_policy.can_create_jobs is True
    assert cards["general_template"].project_can_create_jobs is True
    assert cards["general_template"].metadata["manifest_version"] == "project_template_manifest_v1"
    assert cards["general_template"].metadata["context_read_policy"]["reads_selected_outputs"] is True


def test_template_registry_contains_ecommerce_active_after_doc42() -> None:
    registry = ProjectTemplateRegistry()
    manifests = {manifest.template_id: manifest for manifest in registry.list_manifests()}
    cards = {card.template_id: card for card in registry.list_cards()}

    assert manifests["ecommerce_template"].status == "active"
    assert manifests["ecommerce_template"].scenario_pack_id == "ecommerce"
    assert manifests["ecommerce_template"].context_write_policy.can_create_jobs is True
    assert manifests["ecommerce_template"].required_inputs == []
    assert manifests["ecommerce_template"].optional_inputs[0].field_id == "product_image"
    assert manifests["ecommerce_template"].optional_inputs[0].required is False
    assert cards["ecommerce_template"].project_can_create_jobs is True
    assert cards["ecommerce_template"].ui_card["state"] == "active"
    assert cards["ecommerce_template"].metadata["project_mode_active_document"] == "42"


def test_general_template_maps_to_general_creative() -> None:
    registry = ProjectTemplateRegistry()

    manifest = registry.ensure_can_create_project_job("general_template")

    assert manifest.template_id == "general_template"
    assert manifest.scenario_pack_id == "general_creative"


def test_active_template_requires_existing_scenario_pack() -> None:
    registry = ProjectTemplateRegistry(scenario_registry=ScenarioPackRegistry(packs=[]))

    try:
        registry.ensure_can_create_project_job("general_template")
    except TemplateActivationError as exc:
        assert exc.code == "template_unavailable"
        assert exc.template_id == "general_template"
    else:
        raise AssertionError("active template must require an active Scenario Pack")


def test_placeholder_template_cannot_create_project_job() -> None:
    registry = ProjectTemplateRegistry()

    try:
        registry.ensure_can_create_project_job("new_media_template")
    except TemplateActivationError as exc:
        assert exc.code == "template_placeholder"
        assert exc.template_id == "new_media_template"
    else:
        raise AssertionError("placeholder templates must not create project jobs")


def test_project_mode_lists_templates_with_general_and_ecommerce_active() -> None:
    handlers = V3ProductRouteHandlers()

    payload = handlers.get_projects()

    templates = {item["template_id"]: item for item in payload["templates"]}
    assert payload["api_namespace"] == "/api/v3/creative-agent"
    assert templates["general_template"]["project_can_create_jobs"] is True
    assert templates["general_template"]["status"] == "active"
    assert templates["general_template"]["metadata"]["manifest_version"] == "project_template_manifest_v1"
    assert templates["ecommerce_template"]["project_can_create_jobs"] is True
    assert templates["ecommerce_template"]["status"] == "active"
    assert templates["ecommerce_template"]["metadata"]["requires_product_reference"] is False
    assert templates["ecommerce_template"]["metadata"]["supports_text_to_image_fallback"] is True
    assert templates["photographer_template"]["project_can_create_jobs"] is False
    assert templates["photographer_template"]["status"] == "placeholder"
    assert templates["new_media_template"]["project_can_create_jobs"] is False
    assert templates["new_media_template"]["status"] == "placeholder"
    assert payload["metadata"]["ecommerce_template_locked"] is False


def test_project_mode_creates_general_project_and_job_without_rewriting_product_api() -> None:
    handlers = V3ProductRouteHandlers()
    created = handlers.post_projects(
        {
            "user_goal": "帮我做一组清爽高级的夏季新品宣传图，适合小红书",
            "title": "夏季新品宣传",
        }
    )
    project = created["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "先做一张小红书封面", "template_id": "general_template"},
    )

    assert project["project_id"].startswith("project_")
    assert project["primary_template_id"] == "general_template"
    assert job["status"] == "planned"
    assert job["scenario"]["scenario_id"] == "general_creative"
    assert job["metadata"]["project_id"] == project["project_id"]
    assert job["metadata"]["template_id"] == "general_template"

    timeline = handlers.get_project_timeline(project["project_id"])
    assert [item["item_type"] for item in timeline["items"]] == ["project_created", "job_created"]


def test_ecommerce_project_memory_summary_uses_ecommerce_template_default_chip() -> None:
    handlers = V3ProductRouteHandlers()
    created = handlers.post_projects(
        {
            "user_goal": "Create an Ozon-ready wireless-earbud image suite",
            "primary_template_id": "ecommerce_template",
        }
    )
    project = created["project"]
    recent = handlers.get_projects(limit=10)
    summary = next(item for item in recent["projects"] if item["project_id"] == project["project_id"])

    assert project["primary_template_id"] == "ecommerce_template"
    assert project["memory_summary"]["active_template_label"] == "电商模板"
    assert project["memory_summary"]["confirmed_style_chips"] == ["电商模板"]
    assert summary["active_template_label"] == "电商模板"
    assert summary["confirmed_style_chips"] == ["电商模板"]


def test_general_project_job_preserves_variation_mode_contract() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects(
        {
            "user_goal": "生成同一个东方夏日人物的多张相似备选写真",
            "title": "夏日人物备选",
        }
    )["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "user_input": "同一个人物，小幅变化姿势，多给几张相似备选",
            "template_id": "general_template",
            "metadata": {
                "variation_mode": "selection_candidates",
                "effective_variation_mode": "selection_candidates",
                "variation_mode_source": "manual",
            },
        },
    )

    assert job["scenario"]["scenario_id"] == "general_creative"
    assert job["metadata"]["scenario_parameters"]["variation_mode"] == "selection_candidates"
    assert job["metadata"]["scenario_parameters"]["effective_variation_mode"] == "selection_candidates"
    assert job["metadata"]["scenario_parameters"]["continuation_mode"] == "selection_candidates"
    assert job["metadata"]["scenario_parameters"]["variation_mode_source"] == "manual"
    assert job["metadata"]["variation_mode"] == "selection_candidates"
    assert job["metadata"]["effective_variation_mode"] == "selection_candidates"


def test_project_generation_adds_visual_review_and_retry_timeline_items() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects(
        {
            "user_goal": "生成一组清爽高级的夏日人物写真",
            "title": "夏日人物写真",
        }
    )["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "先做一张干净明亮的社媒封面", "template_id": "general_template"},
    )

    generated = handlers.post_project_job_generate(
        project["project_id"],
        job["job_id"],
        {
            "quality_mode": "standard",
            "metadata": {
                "post_generation_fake_issue_codes": ["visible_text_artifact"],
                "max_visual_retry_attempts": 1,
            },
        },
    )
    timeline = handlers.get_project_timeline(project["project_id"])
    item_types = [item["item_type"] for item in timeline["items"]]

    assert generated["metadata"]["post_generation_review"]["inspections"][0]["status"] == "fail_retryable"
    assert generated["metadata"]["visual_auto_retry"]["executed_count"] == 1
    assert "visual_review" in item_types
    assert "visual_retry" in item_types
    assert timeline["items"][-2]["title"] == "V3 检查了生成结果"
    assert timeline["items"][-1]["title"] == "V3 自动补做了一次"


def test_project_mode_scopes_same_user_input_jobs_by_project() -> None:
    handlers = V3ProductRouteHandlers()
    first = handlers.post_projects({"user_goal": "Create a clean summer drink campaign", "title": "Drink A"})["project"]
    second = handlers.post_projects({"user_goal": "Create a clean summer drink campaign variation", "title": "Drink B"})["project"]

    first_job = handlers.post_project_job(first["project_id"], {"user_input": "Generate a clean summer drink poster"})
    second_job = handlers.post_project_job(second["project_id"], {"user_input": "Generate a clean summer drink poster"})

    assert first_job["job_id"] != second_job["job_id"]
    assert first_job["metadata"]["project_id"] == first["project_id"]
    assert second_job["metadata"]["project_id"] == second["project_id"]
    assert first_job["metadata"]["project_job_sequence"] == 1
    assert second_job["metadata"]["project_job_sequence"] == 1


def test_project_archive_hides_project_from_recent_list_but_keeps_detail() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a launch poster", "title": "Launch"})["project"]
    second = handlers.post_projects({"user_goal": "Create a cafe poster", "title": "Cafe"})["project"]

    archived = handlers.post_project_archive(project["project_id"])
    projects = handlers.get_projects(limit=10)
    detail = handlers.get_project(project["project_id"])
    timeline = handlers.get_project_timeline(project["project_id"])

    listed_ids = [item["project_id"] for item in projects["projects"]]
    assert archived["project"]["status"] == "archived"
    assert project["project_id"] not in listed_ids
    assert second["project_id"] in listed_ids
    assert detail["project"]["project_id"] == project["project_id"]
    assert detail["project"]["status"] == "archived"
    assert timeline["items"][-1]["item_type"] == "project_archived"
    assert "归档" in timeline["items"][-1]["title"]


def test_project_mode_allows_ecommerce_project_job_without_product_reference() -> None:
    handlers = V3ProductRouteHandlers()
    created = handlers.post_projects({"user_goal": "帮我做一个产品宣传项目"})
    project_id = created["project"]["project_id"]

    job = handlers.post_project_job(
        project_id,
        {"template_id": "ecommerce_template", "user_input": "做电商套图"},
    )

    assert job["status"] == "planned"
    assert job["scenario"]["scenario_id"] == "ecommerce"
    assert job["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert job["metadata"]["has_product_reference"] is False


def test_project_mode_rejects_ecommerce_project_job_with_fake_uploaded_asset_id() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]

    try:
        handlers.post_project_job(
            project["project_id"],
            {
                "template_id": "ecommerce_template",
                "user_input": "Create an ecommerce image set",
                "uploaded_asset_ids": ["product_reference"],
            },
        )
    except ValueError as exc:
        assert "商品图" in str(exc)
    else:
        raise AssertionError("ecommerce_template must reject arbitrary product-reference strings")


def test_project_mode_rejects_ecommerce_project_job_with_non_product_upload(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    style_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="style.png")
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]

    try:
        handlers.post_project_job(
            project["project_id"],
            {
                "template_id": "ecommerce_template",
                "user_input": "Create an ecommerce image set",
                "uploaded_asset_ids": [style_asset_id],
            },
        )
    except ValueError as exc:
        assert "商品图" in str(exc)
    else:
        raise AssertionError("ecommerce_template must reject explicit non-product uploads")


def test_project_mode_rejects_ecommerce_project_job_with_pending_product_upload(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    pending_asset_id = _pending_upload(handlers, tmp_path, role="product_reference", filename="pending-product.png")
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]

    try:
        handlers.post_project_job(
            project["project_id"],
            {
                "template_id": "ecommerce_template",
                "user_input": "Create an ecommerce image set",
                "uploaded_asset_ids": [pending_asset_id],
            },
        )
    except ValueError as exc:
        assert "商品图" in str(exc)
    else:
        raise AssertionError("ecommerce_template must reject product uploads that are not ready")


def test_project_mode_rejects_fake_saved_product_reference() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]

    try:
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": "v3_asset_fake00000000",
                "source_type": "uploaded",
                "use_policy": "product",
            },
        )
    except ValueError as exc:
        assert "上传记录" in str(exc)
    else:
        raise AssertionError("saved product references must point at a real V3 upload")


def test_project_mode_ignores_fake_project_create_product_asset_and_falls_back_to_text() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects(
        {
            "user_goal": "Create a product launch image suite",
            "primary_template_id": "ecommerce_template",
            "uploaded_asset_ids": ["v3_asset_deadbeefdeadbeef"],
        }
    )["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {"template_id": "ecommerce_template", "user_input": "Create an ecommerce image set"},
    )

    assert job["status"] == "planned"
    assert job["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert job["metadata"]["has_product_reference"] is False


def test_project_mode_uses_ready_project_create_product_asset(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="desk-lamp.png")
    project = handlers.post_projects(
        {
            "user_goal": "Create a product launch image suite",
            "primary_template_id": "ecommerce_template",
            "uploaded_asset_ids": [product_asset_id],
        }
    )["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {"template_id": "ecommerce_template", "user_input": "Create an ecommerce image set"},
    )

    assert job["status"] == "planned"
    assert job["ecommerce"]["product_truth"]["evidence_sources"] == [f"uploaded_asset:{product_asset_id}"]


def test_project_mode_accepts_ready_saved_product_reference(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="desk-lamp.png")
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_asset_id,
            "source_type": "uploaded",
            "use_policy": "product",
            "label": "Desk lamp product photo",
        },
    )

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a direct-to-use ecommerce image set for this desk lamp",
            "commerce_profile_patch": {"product_category": "desk lamp"},
        },
    )

    assert job["status"] == "planned"
    assert job["scenario"]["scenario_id"] == "ecommerce"
    assert job["ecommerce"]["product_truth"]["evidence_sources"] == [f"uploaded_asset:{product_asset_id}"]


def test_project_mode_creates_ecommerce_project_job_through_template_registry(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="desk-lamp.png")
    project = handlers.post_projects({"user_goal": "Create a product launch image suite"})["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a direct-to-use ecommerce image set for this desk lamp",
            "uploaded_asset_ids": [product_asset_id],
            "commerce_profile_patch": {
                "product_category": "desk lamp",
                "target_platform": "amazon_us",
                "target_market": "US",
                "target_audience": "home office users",
                "core_selling_points": ["Adjustable angle"],
                "must_keep_facts": ["black metal body"],
                "keywords": ["desk lamp"],
            },
            "suite_slot_request": ["main_image", "feature_image_1", "scenario_image"],
            "metadata": {"selected_preset_id": "marketplace_listing_set"},
        },
    )
    loaded = handlers.get_project(project["project_id"])

    assert job["status"] == "planned"
    assert job["scenario"]["scenario_id"] == "ecommerce"
    assert job["scenario"]["selected_preset_id"] == "marketplace_listing_set"
    assert job["metadata"]["template_id"] == "ecommerce_template"
    assert job["metadata"]["project_id"] == project["project_id"]
    assert job["metadata"]["project_context_snapshot"]["template_id"] == "ecommerce_template"
    assert job["metadata"]["project_context_snapshot"]["metadata"]["commerce_profile"]["product_category"] == "desk lamp"
    assert job["ecommerce"]["platform"] == "amazon"
    assert job["ecommerce"]["target_audience"][0] == "home office users"
    assert job["ecommerce"]["image_recipes"]
    assert loaded["project"]["primary_template_id"] == "ecommerce_template"
    assert loaded["project"]["commerce_profile"]["product_category"] == "desk lamp"
    assert loaded["project"]["commerce_profile"]["target_audience"] == "home office users"
    assert loaded["project"]["commerce_profile"]["suite_slots_requested"] == [
        "main_image",
        "feature_image_1",
        "scenario_image",
    ]


def test_project_mode_passes_ecommerce_requested_count_to_pack(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="summer-drink.png")
    project = handlers.post_projects({"user_goal": "Create a compact marketplace lifestyle set"})["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create realistic lifestyle ecommerce images for this summer drink bottle",
            "uploaded_asset_ids": [product_asset_id],
            "commerce_profile_patch": {
                "product_category": "drink",
                "target_platform": "amazon_us",
                "core_selling_points": ["Fresh summer refreshment"],
            },
            "suite_slot_request": ["main_image", "scenario_image", "ad_cover"],
            "metadata": {"requested_image_count": 2},
        },
    )

    assert job["metadata"]["scenario_parameters"]["requested_image_count"] == 2
    assert len(job["ecommerce"]["image_recipes"]) == 2
    assert [recipe["slot"] for recipe in job["ecommerce"]["image_recipes"]] == ["main_image", "scenario_image"]
    assert job["ecommerce"]["image_recipes"][1]["metadata"]["lifestyle_realism_required"] is True


def test_project_mode_forwards_ecommerce_copy_metadata_to_existing_slot_safe_planner(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="desk-lamp-copy.png")
    project = handlers.post_projects({"user_goal": "Create listing images with approved product copy"})["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create an Amazon listing set for this adjustable desk lamp",
            "uploaded_asset_ids": [product_asset_id],
            "commerce_profile_patch": {
                "product_category": "desk lamp",
                "target_platform": "amazon_us",
                "metadata": {
                    "copy_locale": "en-US",
                    "overlay_copy": {"feature_image_1": "Adjustable angle"},
                },
            },
            "suite_slot_request": ["main_image", "feature_image_1"],
        },
    )

    assert job["metadata"]["scenario_parameters"]["copy_locale"] == "en-US"
    assert job["metadata"]["scenario_parameters"]["overlay_copy"] == {"feature_image_1": "Adjustable angle"}
    recipes = {recipe["slot"]: recipe for recipe in job["ecommerce"]["image_recipes"]}
    assert recipes["main_image"]["overlay_text"] is None
    assert recipes["feature_image_1"]["overlay_text"] == "Adjustable angle"


def test_selected_ecommerce_output_enters_project_context_without_brand_memory_auto_write(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    product_asset_id = _ready_upload(handlers, tmp_path, role="product_reference", filename="desk-lamp.png")
    project = handlers.post_projects({"user_goal": "Create a marketplace image suite"})["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Generate a six-image ecommerce suite for this desk lamp",
            "uploaded_asset_ids": [product_asset_id],
            "commerce_profile_patch": {
                "product_category": "desk lamp",
                "target_platform": "amazon_us",
                "core_selling_points": ["Adjustable angle"],
            },
        },
    )

    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"], "apply_memory_update": True},
    )
    context = handlers.get_project_context(project["project_id"])
    timeline = handlers.get_project_timeline(project["project_id"])

    assert generated["status"] == "generated"
    assert generated["scenario"]["scenario_id"] == "ecommerce"
    assert generated["metadata"]["template_id"] == "ecommerce_template"
    assert generated["asset_series"]
    assert generated["ecommerce"]["image_recipes"]
    assert selected["selected_result"]["memory_update_applied"] is False
    assert selected["metadata"]["brand_memory_auto_applied"] is False
    assert selected["project"]["selected_output_refs"]
    assert context["selected_output_assets"]
    assert context["metadata"]["commerce_profile"]["product_category"] == "desk lamp"
    assert context["selected_visual_references"][0]["use_policy"] == "product_identity"
    assert context["strong_reference_bindings"][0]["use_policy"] == "product_identity"
    assert context["identity_lock_profiles"][0]["subject_type"] == "product"
    item_types = [item["item_type"] for item in timeline["items"]]
    assert item_types[:4] == ["project_created", "job_created", "job_generated", "visual_review"]
    assert "candidate_selected" in item_types
    assert item_types.index("candidate_selected") > item_types.index("job_generated")


def test_legacy_ecommerce_jobs_remain_compatible_outside_project_mode() -> None:
    handlers = V3ProductRouteHandlers()

    legacy = handlers.post_jobs(
        {
            "user_input": "Create a legacy ecommerce planning job",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "product_profile": {"product_category": "desk lamp"},
        }
    )
    assert legacy["scenario"]["scenario_id"] == "ecommerce"


def test_template_job_creation_requires_project_id() -> None:
    handlers = V3ProductRouteHandlers()

    try:
        handlers.post_project_job("", {"template_id": "general_template", "user_input": "Create a poster"})
    except KeyError:
        pass
    else:
        raise AssertionError("Project Mode template jobs must be created inside an existing project")


def test_project_selection_updates_project_context_without_brand_memory_auto_apply() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "帮我做一组清爽高级的活动图"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "生成第一张活动图"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})

    selected = handlers.post_project_job_select(project["project_id"], generated["job_id"], {})

    assert selected["status"] == "selected"
    assert selected["selected_result"]["memory_update_applied"] is False
    assert selected["metadata"]["brand_memory_auto_applied"] is False
    assert selected["project"]["selected_output_refs"]
    assert selected["context"]["selected_output_assets"]
    assert selected["context"]["metadata"]["unselected_candidates_excluded"] is True


def test_persistent_project_store_survives_service_restart(tmp_path) -> None:
    store_root = tmp_path / "v3_projects"
    first = V3ProductRouteHandlers(project_store=PersistentProjectStore(store_root))
    project = first.post_projects(
        {
            "user_goal": "Create a clean premium product launch visual chain",
            "title": "Launch Visual Chain",
        }
    )["project"]
    job = first.post_project_job(project["project_id"], {"user_input": "Create the first launch poster"})
    generated = first.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = first.post_project_job_select(project["project_id"], generated["job_id"], {})

    assert selected["project"]["selected_output_refs"]
    assert (store_root / project["project_id"] / "project.json").exists()
    assert (store_root / project["project_id"] / "timeline.json").exists()

    second = V3ProductRouteHandlers(project_store=PersistentProjectStore(store_root))
    loaded = second.get_project(project["project_id"])
    timeline = second.get_project_timeline(project["project_id"])
    projects = second.get_projects(limit=5)

    assert loaded["project"]["project_id"] == project["project_id"]
    assert loaded["project"]["selected_output_refs"]
    assert loaded["context"]["selected_output_assets"]
    item_types = [item["item_type"] for item in timeline["items"]]
    assert item_types[:4] == ["project_created", "job_created", "job_generated", "visual_review"]
    assert "candidate_selected" in item_types
    assert item_types.index("candidate_selected") > item_types.index("job_generated")
    assert projects["projects"][0]["project_id"] == project["project_id"]
    assert projects["projects"][0]["selected_asset_count"] > 0


def test_project_summary_restores_generated_output_thumbnail_after_restart(tmp_path) -> None:
    project_store_root = tmp_path / "v3_projects"
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    first_service = V3ProductApiService(output_store=output_store)
    first = V3ProductRouteHandlers(
        service=first_service,
        project_store=PersistentProjectStore(project_store_root),
    )
    project = first.post_projects(
        {
            "user_goal": "Create a bright summer drink social cover",
            "title": "Drink Cover",
        }
    )["project"]
    job = first.post_project_job(project["project_id"], {"user_input": "Create the first drink image"})
    record = output_store.save_base64_output(
        job_id=job["job_id"],
        candidate_id="candidate_persisted_output",
        asset_id="asset_persisted_output",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )

    second_service = V3ProductApiService(output_store=output_store)
    second = V3ProductRouteHandlers(
        service=second_service,
        project_store=PersistentProjectStore(project_store_root),
    )

    loaded = second.get_project(project["project_id"])
    projects = second.get_projects(limit=5)
    restored_job = second.get_job(job["job_id"])

    assert loaded["project"]["memory_summary"]["latest_thumbnail_urls"] == [record.thumbnail_url]
    assert projects["projects"][0]["latest_thumbnail_urls"] == [record.thumbnail_url]
    assert restored_job["status"] == "generated"
    assert restored_job["candidates"][0]["output_id"] == record.output_id

    selected = second.post_project_job_select(
        project["project_id"],
        job["job_id"],
        {"selected_candidate_id": "candidate_persisted_output"},
    )
    selected_refs = selected["project"]["selected_output_refs"]
    active_references = selected["project"]["reference_assets"]

    assert selected["status"] == "selected"
    assert selected["job_status"]["metadata"]["selected_from_restored_outputs"] is True
    assert selected_refs[0]["candidate_id"] == "candidate_persisted_output"
    assert selected_refs[0]["asset_id"] == "asset_persisted_output"
    assert selected_refs[0]["output_id"] == record.output_id
    assert selected["context"]["selected_output_assets"][0]["output_id"] == record.output_id
    assert active_references[0]["source_type"] == "generated_selected"
    assert active_references[0]["created_from_output_id"] == record.output_id


def test_old_project_record_loads_with_default_context_fields(tmp_path) -> None:
    store_root = tmp_path / "v3_projects"
    project_dir = store_root / "project_legacydoc39"
    project_dir.mkdir(parents=True)
    (project_dir / "project.json").write_text(
        """
        {
          "project_id": "project_legacydoc39",
          "title": "Legacy Project",
          "status": "active",
          "primary_template_id": "general_template",
          "allowed_template_ids": ["general_template"],
          "linked_brand_id": null,
          "user_goal": "Create a clean launch poster",
          "short_summary": "Create a clean launch poster",
          "confirmed_style_summary": null,
          "selected_output_refs": [],
          "uploaded_asset_refs": [],
          "rejected_direction_notes": [],
          "timeline_refs": [],
          "job_ids": [],
          "latest_context": null,
          "memory_summary": null,
          "created_at": "2026-06-29T00:00:00+00:00",
          "updated_at": "2026-06-29T00:00:00+00:00",
          "metadata": {}
        }
        """,
        encoding="utf-8",
    )

    loaded = PersistentProjectStore(store_root).get_project("project_legacydoc39")

    assert loaded is not None
    assert loaded.reference_assets == []
    assert loaded.feedback_records == []
    assert loaded.selected_output_states == []
    assert loaded.schema_version.startswith("project_mode_")


def test_uploaded_reference_can_be_saved_to_project_and_used_in_context(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="style-board.png")
    project = handlers.post_projects({"user_goal": "Create a fresh cafe poster"})["project"]

    reference = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": reference_asset_id,
            "source_type": "uploaded",
            "label": "清爽风格参考",
            "user_note": "保持明亮留白",
            "use_policy": "style",
        },
    )
    context = handlers.get_project_context(project["project_id"])

    assert reference["reference"]["source_type"] == "uploaded"
    assert reference["reference"]["status"] == "active"
    assert context["uploaded_reference_assets"][0]["asset_ref_id"] == reference_asset_id
    assert context["metadata"]["active_reference_count"] == 1


def test_removed_uploaded_reference_exits_project_context(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="style-board.png")
    project = handlers.post_projects({"user_goal": "Create a fresh cafe poster"})["project"]
    reference = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": reference_asset_id, "source_type": "uploaded", "label": "Style", "use_policy": "style"},
    )["reference"]

    removed = handlers.post_project_reference_remove(
        project["project_id"],
        reference["reference_id"],
        {"plain_text": "不再参考这张图"},
    )
    context = handlers.get_project_context(project["project_id"])
    timeline = handlers.get_project_timeline(project["project_id"])

    assert removed["reference"]["status"] == "inactive"
    assert removed["context"]["uploaded_reference_assets"] == []
    assert context["uploaded_reference_assets"] == []
    assert timeline["items"][-1]["item_type"] == "reference_removed"


def test_project_generation_blocked_records_provider_retry_timeline() -> None:
    class BlockingProductService(V3ProductApiService):
        def generate_job(self, job_id, request=None):  # noqa: ANN001
            status = super().get_job(job_id)
            metadata = dict(status.metadata or {})
            metadata["provider_failure_retry"] = {
                "executed_count": 1,
                "max_attempts": 2,
                "fresh_upstream_requests": 2,
                "final_status": "failed",
                "attempts": [
                    {
                        "attempt": 1,
                        "status": "failed",
                        "classification": "retryable_provider_failure",
                        "message": "TimeoutError",
                    },
                    {
                        "attempt": 2,
                        "status": "failed",
                        "classification": "retryable_provider_failure",
                        "message": "TimeoutError",
                    },
                ],
            }
            return status.model_copy(
                update={
                    "status": ProductJobStatusValue.BLOCKED,
                    "warnings": ["V3 real image generation failed via openai_gpt_image (provider_error): TimeoutError"],
                    "metadata": metadata,
                    "asset_series": [],
                    "candidates": [],
                }
            )

    handlers = V3ProductRouteHandlers(service=BlockingProductService())
    project = handlers.post_projects({"user_goal": "Create a product image", "primary_template_id": "ecommerce_template"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create Ozon style ecommerce image", "template_id": "ecommerce_template"})

    blocked = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    timeline = handlers.get_project_timeline(project["project_id"])

    item_types = [item["item_type"] for item in timeline["items"]]
    assert blocked["status"] == "blocked"
    assert "provider_retry" in item_types
    assert "job_blocked" in item_types
    assert timeline["items"][-1]["summary"].startswith("上游生图暂时超时")
    assert timeline["items"][-1]["metadata"]["provider_failure_retry"]["executed_count"] == 1


def test_selected_output_creates_active_generated_reference_and_selection_state() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a premium social cover"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate first cover"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})

    selected = handlers.post_project_job_select(project["project_id"], generated["job_id"], {})

    refs = selected["project"]["reference_assets"]
    states = selected["project"]["selected_output_states"]
    assert refs
    assert refs[0]["source_type"] == "generated_selected"
    assert refs[0]["status"] == "active"
    assert states[0]["selection_state"] == "selected"
    assert selected["context"]["selected_output_assets"]
    assert selected["context"]["selected_reference_assets"]


def test_portrait_selection_becomes_strong_identity_reference(tmp_path) -> None:
    project_store_root = tmp_path / "v3_projects"
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    first_service = V3ProductApiService(output_store=output_store)
    first = V3ProductRouteHandlers(
        service=first_service,
        project_store=PersistentProjectStore(project_store_root),
    )
    project = first.post_projects({"user_goal": "Create a fresh summer portrait of an East Asian woman"})["project"]
    job = first.post_project_job(project["project_id"], {"user_input": "Generate the first clean bright portrait"})
    record = output_store.save_base64_output(
        job_id=job["job_id"],
        candidate_id="candidate_identity_output",
        asset_id="asset_identity_output",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    second_service = V3ProductApiService(output_store=output_store)
    handlers = V3ProductRouteHandlers(
        service=second_service,
        project_store=PersistentProjectStore(project_store_root),
    )

    selected = handlers.post_project_job_select(
        project["project_id"],
        job["job_id"],
        {"selected_candidate_id": "candidate_identity_output"},
    )
    context = selected["context"]

    assert context["selected_visual_references"][0]["use_policy"] == "identity"
    assert context["selected_visual_references"][0]["file_path"]
    assert context["selected_visual_references"][0]["output_id"] == record.output_id
    assert context["selected_output_assets"][0]["metadata"]["file_path"] == record.file_path
    assert context["strong_reference_bindings"][0]["use_policy"] == "identity"
    assert context["strong_reference_bindings"][0]["provider_input_required"] is True
    assert context["identity_lock_profiles"][0]["subject_type"] == "character"
    assert context["project_identity_anchors"][0]["subject_type"] == "character"
    assert context["project_identity_anchors"][0]["provider_reference_required"] is True
    assert context["strong_reference_continuation_plan"]["active_anchor_ids"]
    assert context["batch_identity_diversity_review"]["applies"] is True
    assert "face_identity" in context["strong_reference_bindings"][0]["lock_targets"]

    continuation = handlers.post_project_job(project["project_id"], {"user_input": "Continue this as a second same-style portrait"})
    continuation_status = handlers.post_project_job_generate(
        project["project_id"],
        continuation["job_id"],
        {"quality_mode": "standard"},
    )
    reference_assets = continuation_status["metadata"]["project_context_snapshot"]["strong_reference_bindings"]
    assert any(item.get("use_policy") == "identity" and item.get("file_path") for item in reference_assets)
    assert continuation_status["metadata"]["project_context_snapshot"]["project_identity_anchors"][0]["subject_type"] == "character"
    assert continuation_status["metadata"]["project_context_snapshot"]["strong_reference_continuation_plan"]["reference_mode"] == "provider_image_reference"
    cluster_results = [
        item
        for item in continuation_status["metadata"]["shared_capabilities"]["results"]
        if item["module_id"] == "visual_capability_cluster"
    ]
    assert cluster_results[0]["facts"]["visual_capability_cluster"]["identity_lock_profiles"][0]["subject_type"] == "character"
    assert cluster_results[0]["facts"]["visual_capability_cluster"]["project_identity_anchors"]
    assert cluster_results[0]["facts"]["visual_capability_cluster"]["general_suite_role_plan"]["roles"]


def test_chinese_portrait_goal_uses_identity_reference_policy() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects(
        {"user_goal": "\u751f\u6210\u590f\u65e5\u6e05\u51c9\u4e1c\u65b9\u7f8e\u5973\u5199\u771f"}
    )["project"]
    project_record = ProjectRecord.model_validate(project)

    assert handlers.project_service._looks_like_character_project(project_record) is True
    assert handlers.project_service._generated_output_use_policy(project_record).value == "identity"


def test_uploaded_portrait_reference_is_promoted_and_kept_before_selected_output(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    upload_id = _ready_upload(handlers, tmp_path, role="face_reference", filename="prototype-face.png")
    project = handlers.post_projects(
        {"user_goal": "\u751f\u6210\u540c\u4e00\u4f4d\u4e1c\u65b9\u7f8e\u5973\u7684\u590f\u65e5\u5199\u771f"}
    )["project"]
    saved = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": upload_id, "source_type": "uploaded", "use_policy": "general"},
    )["reference"]

    assert saved["use_policy"] == "identity"

    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate a bright portrait variation"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )
    context = selected["context"]

    assert context["selected_visual_references"][0]["source_type"] == "uploaded"
    assert context["selected_visual_references"][0]["asset_ref_id"] == upload_id
    assert context["selected_visual_references"][0]["use_policy"] == "identity"
    assert any(item.get("source_type") == "selected_output" for item in context["selected_visual_references"])
    assert context["strong_reference_bindings"][0]["source_type"] == "uploaded"
    assert context["strong_reference_bindings"][0]["use_policy"] == "identity"


def test_uploaded_portrait_job_asset_enters_context_before_generation(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    upload_id = _ready_upload(handlers, tmp_path, role="face_reference", filename="prototype-face.png")
    project = handlers.post_projects(
        {"user_goal": "\u751f\u6210\u540c\u4e00\u4f4d\u4e1c\u65b9\u7f8e\u5973\u7684\u590f\u65e5\u5199\u771f"}
    )["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use the uploaded prototype face as the identity source", "uploaded_asset_ids": [upload_id]},
    )
    snapshot = job["metadata"]["project_context_snapshot"]

    assert any(item.get("asset_ref_id") == upload_id and item.get("use_policy") == "identity" for item in snapshot["uploaded_reference_assets"])
    assert snapshot["selected_visual_references"][0]["asset_ref_id"] == upload_id
    assert snapshot["strong_reference_bindings"][0]["source_type"] == "uploaded"
    assert snapshot["identity_lock_profiles"][0]["subject_type"] == "character"


def test_identity_only_portrait_does_not_misapply_structured_appearance_lock(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    upload_id = _ready_upload(handlers, tmp_path, role="face_reference", filename="appearance-anchor.png")
    project = handlers.post_projects(
        {
            "user_goal": (
                "Create a same-person portrait suite with one layered translucent ceremonial outfit, "
                "embroidered pattern family, sash structure, sleeve shape, collar direction, and trim placement."
            )
        }
    )["project"]
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": upload_id, "source_type": "uploaded", "use_policy": "general"},
    )

    context = handlers.get_project_context(project["project_id"])

    assert context["identity_lock_profiles"][0]["subject_type"] == "character"
    assert context["identity_lock_profiles"][0]["metadata"]["structured_appearance_lock"] is False
    keep_rules = " ".join(context["identity_lock_profiles"][0]["keep_rules"]).lower()
    assert "pattern family" not in keep_rules
    assert "accessory placement" not in keep_rules
    plan_additions = " ".join(context["strong_reference_continuation_plan"]["prompt_additions"]).lower()
    assert "appearance asset structure" not in plan_additions
    policy = context["resolved_reference_policy_package"]["policies"][0]
    assert policy["identity_geometry"] == "hard"
    assert policy["wardrobe_structure"] == "prompt_owned"


def test_portrait_project_create_marks_uploaded_asset_as_face_reference() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects(
        {
            "user_goal": "\u751f\u6210\u540c\u4e00\u4f4d\u4e1c\u65b9\u7f8e\u5973\u7684\u590f\u65e5\u5199\u771f",
            "uploaded_asset_ids": ["v3_asset_feedfacefeedface"],
        }
    )["project"]

    assert project["uploaded_asset_refs"][0]["role"] == "face_reference"


def test_removed_generated_reference_unselects_output_context() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a premium social cover"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate first cover"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )
    reference_id = selected["project"]["reference_assets"][0]["reference_id"]

    removed = handlers.post_project_reference_remove(project["project_id"], reference_id, {"plain_text": "不沿用这张"})
    context = handlers.get_project_context(project["project_id"])

    assert removed["reference"]["status"] == "inactive"
    assert removed["project"]["selected_output_refs"] == []
    assert removed["project"]["selected_output_states"][0]["selection_state"] == "unselected"
    assert context["selected_output_assets"] == []
    assert context["selected_reference_assets"] == []


def test_unselected_output_exits_positive_context_but_remains_history() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a clean campaign visual"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate first visual"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )
    output_id = selected["project"]["selected_output_refs"][0]["output_id"]

    unselected = handlers.post_project_output_unselect(project["project_id"], output_id, {})
    context = handlers.get_project_context(project["project_id"])

    assert unselected["project"]["selected_output_refs"] == []
    assert unselected["project"]["selected_output_states"][0]["selection_state"] == "unselected"
    assert unselected["project"]["reference_assets"][0]["status"] == "inactive"
    assert context["selected_output_assets"] == []
    assert context["metadata"]["unselected_candidates_excluded"] is True


def test_rejected_output_adds_negative_context() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a warm product style visual"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate visual"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )
    output_id = selected["project"]["selected_output_refs"][0]["output_id"]

    rejected = handlers.post_project_output_reject(
        project["project_id"],
        output_id,
        {"plain_text": "不要暗色背景，保持明亮干净", "reason_tags": ["dark_background"]},
    )
    context = handlers.get_project_context(project["project_id"])

    assert rejected["project"]["selected_output_states"][0]["selection_state"] == "rejected"
    assert rejected["feedback"]["feedback_type"] == "avoid_direction"
    assert "不要暗色背景" in context["negative_direction_notes"][0]
    assert context["selected_output_assets"] == []


def test_unselected_candidate_does_not_enter_context() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a minimal event poster"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate options"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})

    context = handlers.get_project_context(project["project_id"])

    assert generated["candidates"]
    assert context["selected_output_assets"] == []
    assert context["selected_reference_assets"] == []
    assert context["metadata"]["unselected_candidates_excluded"] is True


def test_project_job_creation_reads_enriched_project_context(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="mood.png")
    project = handlers.post_projects({"user_goal": "Create a bright summer campaign"})["project"]
    reference = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": reference_asset_id,
            "source_type": "uploaded",
            "label": "Mood board",
            "use_policy": "mood",
        },
    )["reference"]
    handlers.post_project_feedback(
        project["project_id"],
        {"feedback_type": "avoid_direction", "plain_text": "避免拥挤背景", "reason_tags": ["clutter"]},
    )

    job = handlers.post_project_job(project["project_id"], {"user_input": "继续同风格做封面"})
    status = handlers.get_job(job["job_id"])

    project_context = status["metadata"]["project_context_snapshot"]
    assert project_context["uploaded_reference_assets"][0]["reference_id"] == reference["reference_id"]
    assert "避免拥挤背景" in project_context["negative_direction_notes"][0]
    assert project_context["continuation_instruction"] == "继续同风格做封面"


def test_project_timeline_uses_plain_language_events(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="clean-style.png")
    project = handlers.post_projects({"user_goal": "Create a clean poster"})["project"]
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": reference_asset_id, "source_type": "uploaded", "label": "Clean style"},
    )
    handlers.post_project_feedback(
        project["project_id"],
        {"feedback_type": "note", "plain_text": "希望整体更清爽", "reason_tags": []},
    )

    timeline = handlers.get_project_timeline(project["project_id"])
    visible_text = " ".join(f"{item['title']} {item['summary']}" for item in timeline["items"])

    assert "provider" not in visible_text.lower()
    assert "job id" not in visible_text.lower()
    assert "manifest" not in visible_text.lower()
    assert any(item["item_type"] == "reference_uploaded" for item in timeline["items"])
    assert any(item["item_type"] == "note_added" for item in timeline["items"])


def test_brand_memory_proposal_does_not_write_brand(tmp_path) -> None:
    handlers, brand_service = _project_handlers_with_brand_store(tmp_path)
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="cafe-style.png")
    project = handlers.post_projects({"user_goal": "Create a bright cafe poster", "title": "Cafe Style"})["project"]
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": reference_asset_id, "source_type": "uploaded", "label": "Cafe style"},
    )

    proposal = handlers.post_project_brand_memory_proposal(project["project_id"], {"mode": "create"})

    assert proposal["proposal"]["project_id"] == project["project_id"]
    assert proposal["proposal"]["reference_asset_ids"] == [reference_asset_id]
    assert proposal["metadata"]["brand_memory_written"] is False
    assert brand_service.store.list_brand_ids() == []


def test_brand_memory_confirm_creates_new_brand(tmp_path) -> None:
    handlers, brand_service = _project_handlers_with_brand_store(tmp_path)
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="clean-drink.png")
    project = handlers.post_projects({"user_goal": "Create a clean beverage campaign", "title": "Clean Drink"})["project"]
    handlers.post_project_reference(project["project_id"], {"asset_ref_id": reference_asset_id, "source_type": "uploaded"})
    proposal = handlers.post_project_brand_memory_proposal(project["project_id"], {"mode": "create"})["proposal"]

    confirmed = handlers.post_project_brand_memory_confirm(
        project["project_id"],
        {
            "proposal_id": proposal["proposal_id"],
            "edited_brand_name": "Clean Drink Brand",
            "edited_style_summary": "Bright clean drink visuals",
            "edited_keep_notes": ["bright natural light", "clear product focus"],
            "edited_avoid_notes": ["dark clutter"],
            "edited_usage_scenes": ["social cover"],
        },
    )

    brand = brand_service.load_profile(confirmed["brand_id"])
    timeline = handlers.get_project_timeline(project["project_id"])
    assert confirmed["memory_update_applied"] is True
    assert brand is not None
    assert brand.brand_name == "Clean Drink Brand"
    assert "Bright clean drink visuals" in brand.visual_tone
    assert reference_asset_id in brand.successful_asset_ids
    assert "dark clutter" in brand.rejected_style_tags
    assert timeline["items"][-1]["item_type"] == "brand_memory_confirmed"


def test_brand_memory_confirm_appends_existing_brand(tmp_path) -> None:
    handlers, brand_service = _project_handlers_with_brand_store(tmp_path)
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="launch-style.png")
    handlers.post_brands(
        {
            "brand_id": "brand_existing_doc40",
            "brand_name": "Existing Brand",
            "visual_tone": ["existing tone"],
            "color_palette": ["#ffffff"],
        }
    )
    project = handlers.post_projects({"user_goal": "Continue a premium launch style"})["project"]
    handlers.post_project_reference(project["project_id"], {"asset_ref_id": reference_asset_id, "source_type": "uploaded"})
    proposal = handlers.post_project_brand_memory_proposal(
        project["project_id"],
        {"mode": "append", "target_brand_id": "brand_existing_doc40"},
    )["proposal"]

    handlers.post_project_brand_memory_confirm(
        project["project_id"],
        {
            "proposal_id": proposal["proposal_id"],
            "edited_brand_name": "Existing Brand",
            "edited_style_summary": "Premium launch direction",
            "edited_keep_notes": ["premium spacing"],
            "edited_avoid_notes": ["cheap props"],
            "edited_usage_scenes": ["launch poster"],
        },
    )

    brand = brand_service.load_profile("brand_existing_doc40")
    assert brand is not None
    assert "existing tone" in brand.visual_tone
    assert "Premium launch direction" in brand.visual_tone
    assert reference_asset_id in brand.successful_asset_ids
    assert "cheap props" in brand.rejected_style_tags


def test_unselected_outputs_excluded_from_brand_proposal(tmp_path) -> None:
    handlers, _brand_service = _project_handlers_with_brand_store(tmp_path)
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="active-style.png")
    project = handlers.post_projects({"user_goal": "Create a minimal project style"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Generate options"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})
    selected = handlers.post_project_job_select(
        project["project_id"],
        generated["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )
    output_id = selected["project"]["selected_output_refs"][0]["output_id"]
    handlers.post_project_output_unselect(project["project_id"], output_id, {})
    handlers.post_project_reference(project["project_id"], {"asset_ref_id": reference_asset_id, "source_type": "uploaded"})

    proposal = handlers.post_project_brand_memory_proposal(project["project_id"], {"mode": "create"})["proposal"]

    assert output_id not in proposal["reference_output_ids"]
    assert proposal["reference_asset_ids"] == [reference_asset_id]


def test_rejected_feedback_enters_avoid_notes_only_after_confirmation(tmp_path) -> None:
    handlers, brand_service = _project_handlers_with_brand_store(tmp_path)
    reference_asset_id = _ready_upload(handlers, tmp_path, role="style_reference", filename="clean-campaign.png")
    project = handlers.post_projects({"user_goal": "Create a clean campaign"})["project"]
    handlers.post_project_reference(project["project_id"], {"asset_ref_id": reference_asset_id, "source_type": "uploaded"})
    handlers.post_project_feedback(
        project["project_id"],
        {"feedback_type": "avoid_direction", "plain_text": "avoid dark clutter"},
    )

    proposal = handlers.post_project_brand_memory_proposal(project["project_id"], {"mode": "create"})["proposal"]
    assert "avoid dark clutter" in proposal["avoid_notes"]
    assert brand_service.store.list_brand_ids() == []

    confirmed = handlers.post_project_brand_memory_confirm(
        project["project_id"],
        {
            "proposal_id": proposal["proposal_id"],
            "edited_brand_name": "Clean Campaign Brand",
            "edited_style_summary": "Clean campaign style",
            "edited_keep_notes": ["clean spacing"],
            "edited_avoid_notes": proposal["avoid_notes"],
            "edited_usage_scenes": ["campaign poster"],
        },
    )

    brand = brand_service.load_profile(confirmed["brand_id"])
    assert brand is not None
    assert "avoid dark clutter" in brand.rejected_style_tags


def test_project_outputs_append_across_jobs_and_delete_hides_only_selected_image(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "Create a clean social campaign", "title": "Clean Campaign"})[
        "project"
    ]
    first_job = handlers.post_project_job(project["project_id"], {"user_input": "Create the first cover"})
    first_record = _save_project_output(
        handlers,
        job_id=first_job["job_id"],
        candidate_id="candidate_first_output",
        asset_id="asset_first_output",
        prompt="clean summer cover, bright product lighting",
    )
    second_job = handlers.post_project_job(project["project_id"], {"user_input": "Continue with a matching story image"})
    second_record = _save_project_output(
        handlers,
        job_id=second_job["job_id"],
        candidate_id="candidate_second_output",
        asset_id="asset_second_output",
        prompt="matching summer story image, same clean style",
    )

    detail_outputs = handlers.get_project(project["project_id"])["metadata"]["project_outputs"]
    history_outputs = handlers.get_project_outputs(limit=10)["items"]
    detail_ids = {item["output_id"] for item in detail_outputs}
    history_ids = {item["output_id"] for item in history_outputs if item["project_id"] == project["project_id"]}

    assert first_record.output_id in detail_ids
    assert second_record.output_id in detail_ids
    assert first_record.output_id in history_ids
    assert second_record.output_id in history_ids

    removed = handlers.post_project_output_unselect(project["project_id"], first_record.output_id, {})
    visible_ids_after_delete = {item["output_id"] for item in removed["metadata"]["project_outputs"]}
    history_ids_after_delete = {
        item["output_id"]
        for item in handlers.get_project_outputs(limit=10)["items"]
        if item["project_id"] == project["project_id"]
    }
    state_map = {item["output_id"]: item["selection_state"] for item in removed["project"]["selected_output_states"]}

    assert first_record.output_id not in visible_ids_after_delete
    assert second_record.output_id in visible_ids_after_delete
    assert first_record.output_id not in history_ids_after_delete
    assert second_record.output_id in history_ids_after_delete
    assert state_map[first_record.output_id] == "unselected"


def test_project_outputs_mark_retry_superseded_and_final_delivery_group(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "Create four portrait alternatives", "title": "Portrait Batch"})[
        "project"
    ]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create 4 matching portraits"})

    original_ids = _save_project_output_batch(
        handlers,
        job_id=job["job_id"],
        attempt=0,
        count=4,
        prefix="original",
    )
    retry_ids = _save_project_output_batch(
        handlers,
        job_id=job["job_id"],
        attempt=1,
        count=4,
        prefix="retry",
    )

    outputs = [
        item
        for item in handlers.get_project_outputs(limit=20, compact=True)["items"]
        if item["project_id"] == project["project_id"]
    ]
    final_outputs = [item for item in outputs if item["delivery_state"] == "final_delivery"]
    superseded_outputs = [item for item in outputs if item["delivery_state"] == "superseded"]

    assert len(outputs) == 8
    assert {item["output_id"] for item in final_outputs} == set(retry_ids)
    assert {item["output_id"] for item in superseded_outputs} == set(original_ids)
    assert {item["metadata"]["delivery_requested_image_count"] for item in outputs} == {4}
    assert all(item["metadata"]["delivery_final_attempt_index"] == 1 for item in outputs)
    assert all(item["metadata"]["retry_superseded"] is True for item in superseded_outputs)
    assert all(item["metadata"]["retry_superseded"] is False for item in final_outputs)


def test_project_outputs_keep_complete_original_when_retry_is_incomplete(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "Create four complete images", "title": "Incomplete Retry"})[
        "project"
    ]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create 4 complete images"})

    original_ids = _save_project_output_batch(
        handlers,
        job_id=job["job_id"],
        attempt=0,
        count=4,
        prefix="complete_original",
    )
    retry_record = _save_project_output(
        handlers,
        job_id=job["job_id"],
        candidate_id="incomplete_retry_candidate",
        asset_id="incomplete_retry_asset",
        metadata_override={
            "requested_image_count": 4,
            "visual_auto_retry_attempt": 1,
            "visual_retry_reason_codes": ["provider_partial_retry"],
        },
    )

    outputs = [
        item
        for item in handlers.get_project_outputs(limit=20, compact=True)["items"]
        if item["project_id"] == project["project_id"]
    ]
    final_outputs = [item for item in outputs if item["delivery_state"] == "final_delivery"]
    process_outputs = [item for item in outputs if item["delivery_state"] == "process_only"]

    assert {item["output_id"] for item in final_outputs} == set(original_ids)
    assert [item["output_id"] for item in process_outputs] == [retry_record.output_id]
    assert all(item["metadata"]["delivery_final_attempt_index"] == 0 for item in outputs)


def test_doc95_project_outputs_honor_reviewed_original_over_worse_complete_retry(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "Create two reviewed portraits", "title": "Reviewed Batch"})[
        "project"
    ]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create two matching portraits"})
    original_ids = _save_project_output_batch(
        handlers,
        job_id=job["job_id"],
        attempt=0,
        count=2,
        prefix="reviewed_original",
    )
    retry_ids = _save_project_output_batch(
        handlers,
        job_id=job["job_id"],
        attempt=1,
        count=2,
        prefix="worse_retry",
    )
    for output_id in original_ids:
        handlers.service.output_store.update_metadata(output_id, {"delivery_preferred_output": True})
    for output_id in retry_ids:
        handlers.service.output_store.update_metadata(output_id, {"delivery_preferred_output": False})

    outputs = [
        item
        for item in handlers.get_project_outputs(limit=20, compact=True)["items"]
        if item["project_id"] == project["project_id"]
    ]
    final_ids = {item["output_id"] for item in outputs if item["delivery_state"] == "final_delivery"}
    superseded_ids = {item["output_id"] for item in outputs if item["delivery_state"] == "superseded"}

    assert final_ids == set(original_ids)
    assert superseded_ids == set(retry_ids)
    assert all(item["metadata"]["reviewed_best_attempt"] is True for item in outputs)


def test_project_output_history_is_scoped_by_account_owner(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    first_project = handlers.post_projects(
        {
            "user_goal": "Create account one campaign",
            "title": "Account One",
            "metadata": {"veyra_user_id": 101},
        }
    )["project"]
    second_project = handlers.post_projects(
        {
            "user_goal": "Create account two campaign",
            "title": "Account Two",
            "metadata": {"veyra_user_id": 202},
        }
    )["project"]
    first_job = handlers.post_project_job(first_project["project_id"], {"user_input": "Create first user image"})
    second_job = handlers.post_project_job(second_project["project_id"], {"user_input": "Create second user image"})
    first_record = _save_project_output(
        handlers,
        job_id=first_job["job_id"],
        candidate_id="candidate_owner_one",
        asset_id="asset_owner_one",
        owner_user_id=101,
    )
    second_record = _save_project_output(
        handlers,
        job_id=second_job["job_id"],
        candidate_id="candidate_owner_two",
        asset_id="asset_owner_two",
        owner_user_id=202,
    )

    first_projects = handlers.get_projects(limit=10, owner_user_id=101)["projects"]
    first_outputs = handlers.get_project_outputs(limit=10, owner_user_id=101)["items"]
    second_outputs = handlers.get_project_outputs(limit=10, owner_user_id=202)["items"]

    assert [item["project_id"] for item in first_projects] == [first_project["project_id"]]
    assert {item["output_id"] for item in first_outputs} == {first_record.output_id}
    assert {item["output_id"] for item in second_outputs} == {second_record.output_id}


def test_project_timeline_reconciles_outputs_written_after_background_disconnect(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Generate a marketplace product suite",
            "title": "Recovered product suite",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Make one clean ecommerce image", "template_id": "ecommerce_template"},
    )
    record = _save_project_output(
        handlers,
        job_id=job["job_id"],
        candidate_id="candidate_recovered_1",
        asset_id="asset_recovered_1",
        prompt="clean marketplace product image",
    )

    timeline = handlers.get_project_timeline(project["project_id"])
    generated_items = [
        item for item in timeline["items"] if item["item_type"] == "job_generated" and item["job_id"] == job["job_id"]
    ]
    review_items = [
        item for item in timeline["items"] if item["item_type"] == "visual_review" and item["job_id"] == job["job_id"]
    ]
    outputs = timeline["metadata"]["project_outputs"]

    assert len(generated_items) == 1
    assert generated_items[0]["metadata"]["restored_from_output_store"] is True
    assert generated_items[0]["metadata"]["output_ids"] == [record.output_id]
    assert len(review_items) == 1
    assert review_items[0]["metadata"]["restored_from_output_store"] is True
    assert [item["job_id"] for item in outputs] == [job["job_id"]]

    timeline_again = handlers.get_project_timeline(project["project_id"])
    generated_again = [
        item for item in timeline_again["items"] if item["item_type"] == "job_generated" and item["job_id"] == job["job_id"]
    ]
    review_again = [
        item for item in timeline_again["items"] if item["item_type"] == "visual_review" and item["job_id"] == job["job_id"]
    ]

    assert len(generated_again) == 1
    assert len(review_again) == 1


def test_project_outputs_compact_mode_omits_heavy_prompt_metadata(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create compact history payload",
            "title": "Compact History",
        }
    )["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create a clean image"})
    record = _save_project_output(
        handlers,
        job_id=job["job_id"],
        candidate_id="candidate_compact",
        asset_id="asset_compact",
        prompt="very long provider prompt that should not be sent to the V3 home history",
    )

    full = handlers.get_project_outputs(limit=10, compact=False)["items"][0]
    compact = handlers.get_project_outputs(limit=10, compact=True)
    compact_item = compact["items"][0]

    assert full["output_id"] == record.output_id
    assert full["metadata"]["final_provider_prompt"]
    assert compact["metadata"]["compact"] is True
    assert compact_item["output_id"] == record.output_id
    assert compact_item["thumbnail_url"]
    assert compact_item["preview_url"]
    assert "final_provider_prompt" not in compact_item["metadata"]
    assert "compiled_visual_direction" not in compact_item["metadata"]
    assert compact_item["metadata"]["compact"] is True


def test_ownerless_v3_projects_and_outputs_are_visible_to_all_accounts(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    public_project = handlers.post_projects(
        {
            "user_goal": "Create public V3 validation images",
            "title": "Public V3 Validation",
        }
    )["project"]
    private_project = handlers.post_projects(
        {
            "user_goal": "Create private account images",
            "title": "Private V3 Validation",
            "metadata": {"veyra_user_id": 202},
        }
    )["project"]
    public_job = handlers.post_project_job(public_project["project_id"], {"user_input": "Create shared image"})
    private_job = handlers.post_project_job(private_project["project_id"], {"user_input": "Create private image"})
    public_record = _save_project_output(
        handlers,
        job_id=public_job["job_id"],
        candidate_id="candidate_public",
        asset_id="asset_public",
        owner_user_id=None,
    )
    private_record = _save_project_output(
        handlers,
        job_id=private_job["job_id"],
        candidate_id="candidate_private",
        asset_id="asset_private",
        owner_user_id=202,
    )

    first_projects = {item["project_id"] for item in handlers.get_projects(limit=10, owner_user_id=101)["projects"]}
    first_outputs = {item["output_id"] for item in handlers.get_project_outputs(limit=10, owner_user_id=101)["items"]}
    second_projects = {item["project_id"] for item in handlers.get_projects(limit=10, owner_user_id=202)["projects"]}
    second_outputs = {item["output_id"] for item in handlers.get_project_outputs(limit=10, owner_user_id=202)["items"]}

    assert public_project["project_id"] in first_projects
    assert public_project["project_id"] in second_projects
    assert private_project["project_id"] not in first_projects
    assert private_project["project_id"] in second_projects
    assert public_record.output_id in first_outputs
    assert public_record.output_id in second_outputs
    assert private_record.output_id not in first_outputs
    assert private_record.output_id in second_outputs


def test_general_project_job_preserves_requested_image_count_and_size() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a bright summer portrait set"})["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "user_input": "Continue with three same-style portraits",
            "template_id": "general_template",
            "metadata": {
                "requested_image_count": 3,
                "requested_image_size": "1024x1536",
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
            },
        },
    )

    assert job["metadata"]["scenario_parameters"]["requested_image_count"] == 3
    assert job["metadata"]["scenario_parameters"]["requested_image_size"] == "1024x1536"
