import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisionOutputInspector,
)
from app.schemas import ImageGenerationResult


def _png_base64(width: int = 96, height: int = 128, color: tuple[int, int, int] = (190, 160, 140)) -> str:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _image(path: Path, *, width: int = 96, height: int = 128, color: tuple[int, int, int] = (190, 160, 140)) -> Path:
    path.write_bytes(base64.b64decode(_png_base64(width, height, color)))
    return path


def _human_request(reference_path: Path, selected_path: Path | None = None) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc85_human",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person portrait continuation",
    )
    visual_cluster = {
        "human_photorealism_guidance": {
            "applies": True,
            "reference_preserve_rules": ["keep the same uploaded person"],
            "reference_do_not_inherit_rules": ["do not inherit bad retouching"],
        }
    }
    metadata = {
        "job_id": "job_doc85_human",
        "template_id": "general_template",
        "scenario_id": "general_creative",
        "user_input": "Create a realistic East Asian portrait with the same uploaded person",
        "visual_cluster": visual_cluster,
        "shared_capabilities": {"visual_cluster": visual_cluster},
        "uploaded_assets": [
            {
                "asset_id": "uploaded_portrait_truth",
                "role": "style_reference",
                "source_type": "uploaded",
                "use_policy": "identity",
                "filename": reference_path.name,
                "mime_type": "image/png",
                "file_path": str(reference_path),
            }
        ],
    }
    if selected_path is not None:
        metadata["reference_assets"] = [
            {
                "asset_id": "v3_output_selected_identity",
                "output_id": "v3_output_selected_identity",
                "role": "identity",
                "source_type": "selected_output",
                "use_policy": "identity",
                "filename": selected_path.name,
                "mime_type": "image/png",
                "file_path": str(selected_path),
            }
        ]
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc85_human",
            asset_id=asset.asset_id,
            visual_prompt="same-person portrait in a summer garden, natural expression and new camera angle",
            negative_prompt="generic AI beauty face, distorted face",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["real camera", "fresh daylight"],
            layout_notes=["portrait cover"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc85_human", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc85_human",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata=metadata,
    )


def _product_request(reference_path: Path) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc85_product",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="1:1",
        purpose="commercial product identity visual",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc85_product",
            asset_id=asset.asset_id,
            visual_prompt="premium ecommerce product hero image with the same uploaded product",
            negative_prompt="distorted product, fake label",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["premium", "clean"],
            layout_notes=["center product"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc85_product", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc85_product",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc85_product",
            "template_id": "ecommerce_template",
            "scenario_id": "ecommerce",
            "uploaded_assets": [
                {
                    "asset_id": "uploaded_product_truth",
                    "role": "product_reference",
                    "source_type": "uploaded",
                    "use_policy": "product_identity",
                    "filename": reference_path.name,
                    "mime_type": "image/png",
                    "file_path": str(reference_path),
                }
            ],
        },
    )


def test_doc85_uploaded_portrait_truth_beats_selected_generated_reference(tmp_path) -> None:
    uploaded = _image(tmp_path / "uploaded_portrait.png")
    selected = _image(tmp_path / "selected_generated.png", color=(90, 130, 160))
    request = _human_request(uploaded, selected)
    provider = ProductionImageGenerationProvider()

    references = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, references)  # noqa: SLF001
    prompt = provider._generation_prompt(request, references)  # noqa: SLF001
    truth_package = asset_plan["provider_input_plan"]["reference_truth_package"]

    assert truth_package["sources"]["uploaded_portrait_truth"]["truth_layers"][0] == "portrait_identity_truth"
    assert truth_package["sources"]["v3_output_selected_identity"]["truth_layers"] == ["style_context_truth"]
    assert "uploaded_portrait_truth::portrait_identity_crop" in asset_plan["provider_input_plan"]["reference_image_asset_ids"]
    assert any(item.get("derivative_kind") == "portrait_identity_crop" for item in asset_plan["assets"])
    assert "Reference truth layering contract" in prompt
    assert "Uploaded truth sources remain identity-critical" in prompt
    assert "generic AI beauty replacement" in prompt
    assert "Same-person identity is stricter than same archetype" in prompt
    assert "mouth scale" in prompt
    original_reference = next(
        item
        for item in asset_plan["assets"]
        if item.get("asset_id") == "uploaded_portrait_truth" and not item.get("provider_reference_derivative")
    )
    original_constraint = " ".join(original_reference["prompt_constraints"])
    assert "exact same-person portrait identity truth" in original_constraint
    assert "not as a whole-image style, lighting, scene" in original_constraint
    assert "beauty-template anchor" in original_constraint
    assert "strong identity and style anchor" not in original_constraint
    assert "lighting language" not in original_constraint


def test_doc85_product_truth_derivative_and_metadata_are_persisted(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    observed_plan = {}

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        observed_plan.update(app_request.asset_plan["provider_input_plan"])
        assert provider_name == "openai_gpt_image"
        assert app_request.asset_plan["provider_input_plan"]["reference_image_count"] >= 2
        assert any(
            item.get("truth_layer") == "product_identity_truth" and item.get("provider_reference_derivative")
            for item in app_request.asset_plan["provider_input_plan"]["reference_truth_layers"]
        )
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="gpt-image-2",
            outputs=[
                {
                    "b64_json": _png_base64(128, 128, (80, 120, 150)),
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 128,
                    "height": 128,
                    "api_operation": "images.edit",
                }
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        reference = _image(tmp_path / "product_reference.png", width=140, height=100)
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(_product_request(reference))
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert observed_plan["reference_truth_package"]["sources"]["uploaded_product_truth"]["truth_layers"][0] == "product_identity_truth"
    metadata = response.candidates[0].metadata
    assert metadata["provider_reference_image_count"] >= 2
    assert metadata["api_operation"] == "images.edit"
    assert metadata["provider_input_plan"]["reference_truth_package"]["truth_source_ids"] == ["uploaded_product_truth"]
    assert any(item["truth_layer"] == "product_identity_truth" for item in metadata["provider_reference_assets"])


def test_doc85_retry_patch_mentions_exact_reference_truth_sources() -> None:
    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc85",
            project_id="project_doc85",
            job_id="job_doc85",
            candidate_id="candidate_doc85",
            output_id="output_doc85",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": ["identity_drift", "reference_guard_ignored", "product_identity_drift"]},
    )
    patch_text = " ".join(
        [
            *report.retry_patch["identity_reinforcement"],
            *report.retry_patch["product_reinforcement"],
            *report.retry_patch["negative_additions"],
        ]
    )
    assert "exact uploaded portrait identity truth" in patch_text
    assert "selected generated references only as continuation support" in patch_text
    assert "same instance" in patch_text
    assert "changed reference subject" in patch_text

    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(  # noqa: SLF001
        ["identity_drift", "product_identity_drift"]
    )
    api_text = " ".join([*api_patch["identity_reinforcement"], *api_patch["product_reinforcement"]])
    assert "exact uploaded portrait identity truth" in api_text
    assert "same instance" in api_text
