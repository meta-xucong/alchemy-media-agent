import base64
from io import BytesIO
from pathlib import Path

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
from app.schemas import ImageGenerationResult


def _png_base64(width: int = 96, height: int = 72) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(66, 109, 134))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _reference_image(path: Path) -> Path:
    path.write_bytes(base64.b64decode(_png_base64()))
    return path


def _generation_request(reference_path: Path | None = None) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_v3_prod",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="1:1",
        purpose="direct-to-use ecommerce main image",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_v3_prod",
        asset_id=asset.asset_id,
        visual_prompt="premium ecommerce product hero image on a clean bright background",
        negative_prompt="fake text, distorted product",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["premium", "clean"],
        layout_notes=["center product", "reserve clean text area"],
    )
    uploaded_assets = []
    if reference_path is not None:
        uploaded_assets.append(
            {
                "asset_id": "v3_asset_reference",
                "role": "product_reference",
                "filename": reference_path.name,
                "mime_type": "image/png",
                "file_path": str(reference_path),
            }
        )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_v3_prod", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_v3_prod",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER if uploaded_assets else ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={"job_id": "job_v3_prod", "uploaded_assets": uploaded_assets, "quality_mode": "standard"},
    )


def test_production_provider_persists_v3_owned_outputs(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        assert app_request.asset_mode == "advanced"
        assert app_request.asset_plan["provider_input_plan"]["reference_image_count"] == 1
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {
                    "b64_json": _png_base64(),
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 96,
                    "height": 72,
                }
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        reference_path = _reference_image(tmp_path / "reference.png")
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(_generation_request(reference_path))
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert response.candidates
    candidate = response.candidates[0]
    assert candidate.is_mock is False
    assert candidate.metadata["output_id"].startswith("v3_output_")
    assert candidate.metadata["download_url"].startswith("/api/v3/creative-agent/outputs/")
    assert Path(candidate.file_path).exists()
    assert Path(candidate.metadata["thumbnail_url"].replace("/api/v3/creative-agent/outputs/", "")).name != ""


def test_v3_output_store_creates_preview_thumbnail_and_download(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_v3_output",
        candidate_id="candidate_v3_output",
        asset_id="asset_v3_output",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(140, 100),
        mime_type="image/png",
        output_format="png",
    )

    assert Path(record.file_path).exists()
    assert Path(record.preview_path).exists()
    assert Path(record.thumbnail_path).exists()
    assert store.file_for_variant(record.output_id, "download")[1] == "image/png"
    assert store.file_for_variant(record.output_id, "preview")[1] == "image/png"
    assert store.file_for_variant(record.output_id, "thumbnail")[1] == "image/png"


def test_product_api_restores_generated_history_from_output_store(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_restored_from_outputs",
        candidate_id="candidate_restored_from_outputs",
        asset_id="asset_restored_from_outputs",
        provider="openai_gpt_image",
        model="gpt-image-2",
        encoded_image=_png_base64(128, 128),
        mime_type="image/png",
        output_format="png",
    )
    service = V3ProductApiService(output_store=store)

    status = service.get_job("job_restored_from_outputs")
    history = service.list_history(limit=5)

    assert status.status == "generated"
    assert status.asset_series[0].output_id == record.output_id
    assert status.asset_series[0].thumbnail_url.endswith("/thumbnail")
    assert status.candidates[0].metadata["output_id"] == record.output_id
    assert status.metadata["restored_from_output_store"] is True
    assert history.items[0].job_id == "job_restored_from_outputs"
    assert history.items[0].metadata["restored_from_output_store"] is True
