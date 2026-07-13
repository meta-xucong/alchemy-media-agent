import base64
from io import BytesIO
from pathlib import Path

import pytest

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
from app.providers.base import ProviderRuntimeError, ProviderNotConfiguredError


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


def _human_generation_request() -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_v3_human",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="direct-to-use portrait cover image",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_v3_human",
        asset_id=asset.asset_id,
        visual_prompt="East Asian summer portrait photo with clean cool daylight",
        negative_prompt="distorted face",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["realistic portrait", "clean daylight"],
        layout_notes=["portrait crop", "cover-safe framing"],
    )
    visual_cluster = {
        "human_photorealism_guidance": {
            "applies": True,
            "positive_prompt_fragments": [
                "natural human skin texture with subtle pores",
                "slight natural facial asymmetry",
            ],
            "negative_prompt_fragments": ["plastic skin", "over-smoothed skin", "AI beauty filter"],
            "reference_preserve_rules": ["keep broad face shape and recognizable identity cues"],
            "reference_do_not_inherit_rules": ["do not inherit over-smoothed skin from the reference"],
        },
        "strong_reference_closure_package": {
            "active": True,
            "reference_strength": "hard",
            "provider_reference_required_ids": ["selected_portrait_ref"],
            "identity_keep_rules": ["keep broad face shape and recognizable identity cues"],
            "allowed_variations": ["change expression, gaze, pose, and camera angle naturally"],
            "forbidden_drift": ["do not copy the exact same still or face angle"],
            "provider_prompt_rules": [
                "Use selected references as identity truth while allowing natural expression and pose variation."
            ],
            "negative_prompt_rules": ["same exact AI face repeated"],
        },
        "mode_quality_profile": {
            "mode": "selection_candidates",
            "user_visible_label": "Similar alternatives",
            "review_priorities": ["same subject direction", "small visible pose/expression/crop differences"],
            "pass_conditions": ["outputs feel comparable but not identical"],
            "prompt_guidance": ["create close alternatives for choosing the best image"],
            "negative_guidance": ["same exact still repeated"],
        },
    }
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_v3_human", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_v3_human",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_v3_human",
            "template_id": "general_creative",
            "scenario_id": "general_creative",
            "user_input": "Create an East Asian summer realistic portrait photo",
            "visual_cluster": visual_cluster,
            "shared_capabilities": {"visual_cluster": visual_cluster},
        },
    )


def test_uploaded_portrait_reference_gets_identity_priority_over_prompt(tmp_path) -> None:
    reference_path = _reference_image(tmp_path / "portrait_reference.png")
    request = _human_generation_request()
    request.metadata["uploaded_assets"] = [
        {
            "asset_id": "uploaded_portrait_ref",
            "role": "style_reference",
            "filename": reference_path.name,
            "mime_type": "image/png",
            "file_path": str(reference_path),
        }
    ]
    request.prompt_compilation.visual_prompt = (
        "Create a summer portrait in a different outfit and evening fountain scene with fresh beauty mood"
    )

    provider = ProductionImageGenerationProvider()
    reference_assets = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, reference_assets)  # noqa: SLF001
    prompt = provider._generation_prompt(request, reference_assets)  # noqa: SLF001

    constraints = " ".join(
        constraint
        for item in asset_plan["assets"]
        for constraint in item.get("prompt_constraints", [])
    )
    assert "same-person portrait identity reference" in constraints or "exact portrait identity truth" in constraints
    assert any(item.get("derivative_kind") == "portrait_identity_crop" for item in asset_plan["assets"])
    assert "Uploaded portrait reference priority" in prompt
    assert "higher priority for identity" in prompt
    assert "must not replace facial feature relationships" in prompt


def test_production_provider_persists_v3_owned_outputs(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        assert app_request.asset_mode == "advanced"
        assert app_request.asset_plan["provider_input_plan"]["reference_image_count"] >= 2
        constraints = " ".join(
            constraint
            for item in app_request.asset_plan["assets"]
            for constraint in item.get("prompt_constraints", [])
        )
        assert "strong product identity reference" in constraints or "exact product truth" in constraints
        assert any(
            item.get("truth_layer") == "product_identity_truth"
            for item in app_request.asset_plan["provider_input_plan"]["reference_truth_layers"]
        )
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
    assert candidate.metadata["compiled_visual_direction"] == "premium ecommerce product hero image on a clean bright background"
    assert "premium ecommerce product hero image on a clean bright background" in candidate.metadata["final_provider_prompt"]
    assert "Strong reference rules" in candidate.metadata["final_provider_prompt"]
    assert candidate.metadata["final_provider_prompt_chars"] == len(candidate.metadata["final_provider_prompt"])
    assert candidate.metadata["provider_prompt_target_chars"] == 15000
    assert candidate.metadata["provider_prompt_materialization"] == "v3_semantic_budget_user_direction_lossless"
    assert "fake text" in candidate.metadata["negative_constraints"]
    assert "distorted product" in candidate.metadata["negative_constraints"]
    assert Path(candidate.file_path).exists()
    assert Path(candidate.metadata["thumbnail_url"].replace("/api/v3/creative-agent/outputs/", "")).name != ""
    records = provider.output_store.list_by_job("job_v3_prod")
    assert records[0].metadata["compiled_visual_direction"] == candidate.metadata["compiled_visual_direction"]
    assert records[0].metadata["final_provider_prompt"] == candidate.metadata["final_provider_prompt"]
    assert records[0].metadata["final_provider_prompt_chars"] == candidate.metadata["final_provider_prompt_chars"]
    assert records[0].metadata["style_notes"] == ["premium", "clean"]


def test_production_provider_retries_wrapped_provider_timeout_with_fresh_request(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    old_failover = settings.openai_image_gateway_managed_failover
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    settings.openai_image_gateway_managed_failover = False
    calls = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        if len(calls) == 1:
            raise ProviderRuntimeError(
                "OpenAI image reference generation failed.",
                provider="openai_gpt_image",
                detail={"error_type": "TimeoutError", "message": "TimeoutError"},
            )
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    monkeypatch.setattr(ProductionImageGenerationProvider, "_app_provider_transient_cooldown_seconds", lambda self: 0.0)
    try:
        reference_path = _reference_image(tmp_path / "reference.png")
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(_generation_request(reference_path))
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider
        settings.openai_image_gateway_managed_failover = old_failover

    assert len(calls) == 2
    assert response.candidates
    summary = response.provider_metadata["provider_failure_retry"]
    assert summary["executed_count"] == 1
    assert summary["fresh_upstream_requests"] == 2
    assert summary["final_status"] == "succeeded"
    assert summary["attempts"][0]["classification"] == "retryable_provider_failure"
    assert response.candidates[0].metadata["provider_failure_retry"]["executed_count"] == 1


def test_production_provider_gateway_managed_failover_does_not_replay_terminal_failure(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    old_failover = settings.openai_image_gateway_managed_failover
    old_timeout = settings.openai_image_gateway_managed_failover_timeout_seconds
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    settings.openai_image_gateway_managed_failover = True
    settings.openai_image_gateway_managed_failover_timeout_seconds = 420.0
    calls = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        raise ProviderRuntimeError(
            "OpenAI image generation failed after gateway-managed failover.",
            provider="openai_gpt_image",
            detail={"error_type": "TimeoutError", "message": "TimeoutError"},
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    managed_timeout = None
    managed_attempts = None
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        with pytest.raises(ProviderRuntimeError) as error:
            provider.generate(_generation_request())
        managed_timeout = provider._app_provider_timeout_seconds([])  # noqa: SLF001
        managed_attempts = provider._app_provider_max_attempts()  # noqa: SLF001
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider
        settings.openai_image_gateway_managed_failover = old_failover
        settings.openai_image_gateway_managed_failover_timeout_seconds = old_timeout

    assert len(calls) == 1
    summary = error.value.provider_failure_retry
    assert summary["max_attempts"] == 1
    assert summary["fresh_upstream_requests"] == 1
    assert summary["execution_audit"] == {
        "gateway_managed_failover": True,
        "gateway_managed_failover_timeout_seconds": 420.0,
        "outer_timeout_seconds": 665.0,
        "outer_max_attempts": 1,
        "operation": "image_generate",
    }
    assert managed_timeout == 665.0
    assert managed_attempts == 1


def test_production_provider_retries_generic_reference_upstream_400_once(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    old_failover = settings.openai_image_gateway_managed_failover
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    settings.openai_image_gateway_managed_failover = False
    calls = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        if len(calls) == 1:
            raise ProviderRuntimeError(
                "OpenAI image reference generation failed. Error code: 400 - "
                "{'error': {'code': 'bad_response_status_code', 'message': 'openai_error'}}",
                provider="openai_gpt_image",
                detail={
                    "error_type": "bad_response_status_code",
                    "message": "openai_error",
                },
            )
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {
                    "b64_json": _png_base64(96, 72),
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 96,
                    "height": 72,
                }
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    monkeypatch.setattr(
        ProductionImageGenerationProvider,
        "_app_provider_transient_cooldown_seconds",
        lambda self: 0.0,
    )
    try:
        reference_path = _reference_image(tmp_path / "reference.png")
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(_generation_request(reference_path))
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider
        settings.openai_image_gateway_managed_failover = old_failover

    assert len(calls) == 2
    assert response.candidates
    summary = response.provider_metadata["provider_failure_retry"]
    assert summary["executed_count"] == 1
    assert summary["fresh_upstream_requests"] == 2
    assert summary["attempts"][0]["classification"] == "retryable_provider_failure"
    assert summary["provider_prompt_chars"] > 0


def test_production_provider_does_not_retry_non_retryable_configuration_failure(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    calls = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        raise ProviderNotConfiguredError("OPENAI_API_KEY is not configured.", provider="openai_gpt_image")

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        try:
            provider.generate(_generation_request())
        except ProviderNotConfiguredError:
            pass
        else:
            raise AssertionError("ProviderNotConfiguredError should propagate")
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert len(calls) == 1
    summary = provider._last_provider_failure_retry_summary  # noqa: SLF001
    assert summary["final_status"] == "failed"
    assert summary["attempts"][0]["classification"] == "non_retryable_provider_failure"


def test_production_provider_does_not_retry_transport_capability_mismatch(tmp_path, monkeypatch) -> None:
    from app.config import settings
    from app.providers.base import ProviderCapabilityMismatchError

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"
    calls: list[int] = []

    async def capability_mismatch(self, provider_name, app_request):  # noqa: ANN001, ARG001
        calls.append(1)
        raise ProviderCapabilityMismatchError(
            "Configured OpenAI image transport only supports 1024x1024 text-to-image generation.",
            provider="openai_gpt_image",
            detail={"transport_profile": "generation_only_square_b64"},
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", capability_mismatch)
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        with pytest.raises(ProviderCapabilityMismatchError):
            provider.generate(_generation_request())
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert len(calls) == 1
    summary = provider._last_provider_failure_retry_summary  # noqa: SLF001
    assert summary["final_status"] == "failed"
    assert summary["attempts"][0]["classification"] == "non_retryable_provider_failure"


def test_production_provider_respects_requested_size_without_multiplying_group_count(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        assert app_request.prompt_plan.count == 1
        assert app_request.prompt_plan.size == "1536x1024"
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    request = _generation_request()
    request.metadata["requested_image_count"] = 3
    request.metadata["requested_image_size"] = "1536x1024"
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(request)
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert len(response.candidates) == 3
    records = provider.output_store.list_by_job("job_v3_prod")
    assert len(records) == 3
    assert response.provider_metadata["requested_image_count"] == 3
    assert response.provider_metadata["requested_image_size"] == "1536x1024"
    assert "aspect ratio: 3:2" in response.candidates[0].metadata["final_provider_prompt"]


def test_production_provider_consumes_visual_retry_patch_and_uniques_candidate_id(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    observed_prompts: list[str] = []
    observed_negatives: list[list[str]] = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        observed_prompts.append(app_request.prompt_plan.variables["generation_prompt"])
        observed_negatives.append(list(app_request.prompt_plan.negative_constraints))
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        original = provider.generate(_generation_request())
        retry_request = _generation_request()
        retry_request.metadata.update(
            {
                "visual_auto_retry_attempt": 1,
                "visual_retry_reason_codes": ["visible_text_artifact"],
                "visual_retry_patch": {
                    "prompt_additions": ["make the result cleaner and more polished"],
                    "artifact_repair": ["remove visible text and watermark risk"],
                    "negative_additions": ["visible text", "watermark"],
                },
            }
        )
        retry = provider.generate(retry_request)
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert original.candidates[0].candidate_id != retry.candidates[0].candidate_id
    assert "Retry repair guidance" in observed_prompts[-1]
    assert "make the result cleaner and more polished" in observed_prompts[-1]
    assert "remove visible text and watermark risk" in observed_prompts[-1]
    assert "visible text" in observed_negatives[-1]
    assert "watermark" in observed_negatives[-1]
    assert retry.candidates[0].metadata["visual_auto_retry_attempt"] == 1


def test_production_provider_includes_human_photorealism_guidance(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    observed_prompts: list[str] = []
    observed_negatives: list[list[str]] = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        observed_prompts.append(app_request.prompt_plan.variables["generation_prompt"])
        observed_negatives.append(list(app_request.prompt_plan.negative_constraints))
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 128), "mime_type": "image/png", "format": "png", "width": 96, "height": 128},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(_human_generation_request())
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert response.candidates
    assert "Human realism contract" in observed_prompts[-1]
    assert "Selected reference closure" in observed_prompts[-1]
    assert "Mode quality contract" in observed_prompts[-1]
    assert "natural human skin texture" in observed_prompts[-1]
    assert "slight natural facial asymmetry" in observed_prompts[-1]
    assert "identity truth" in observed_prompts[-1]
    assert "plastic skin" in observed_negatives[-1]
    assert "over-smoothed skin" in observed_negatives[-1]
    assert "same exact AI face repeated" in observed_negatives[-1]
    assert response.provider_metadata["strong_reference_closure_package"]["active"] is True
    assert response.provider_metadata["mode_quality_profile"]["mode"] == "selection_candidates"


def test_production_provider_materializes_framework_without_losing_user_direction() -> None:
    request = _human_generation_request()
    user_direction = " ".join(
        [
            "East Asian summer beach portrait with natural fair skin, same person identity, premium real camera photography"
            for _ in range(8)
        ]
    )
    request.metadata["user_input"] = user_direction
    request.prompt_compilation.visual_prompt = " ".join(
        [
            "East Asian summer beach portrait with natural fair skin, same person identity, premium real camera photography"
            for _ in range(180)
        ]
    )
    request.prompt_compilation.negative_prompt = "distorted face, watermark, text, " * 80

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert len(final_prompt) <= ProductionImageGenerationProvider.provider_prompt_target_chars
    assert user_direction in final_prompt
    assert "Visual direction:" in final_prompt
    assert "Human realism contract" in final_prompt
    assert "Identity continuity" in final_prompt
    assert "Avoid:" in final_prompt
    assert "watermark" in final_prompt


def test_provider_prompt_removes_framework_duplicates_without_truncating_user_direction() -> None:
    request = _human_generation_request()
    user_direction = "A complete exact user visual direction with silver costume, pear blossoms, and cool cinematic light."
    request.prompt_compilation.visual_prompt = user_direction
    request.metadata["user_input"] = user_direction
    request.prompt_compilation.hard_constraints = [
        "Use the V3-owned generation strategy selected by the runtime.",
        "Do not render any final text, captions, or UI copy inside the image model output.",
        "A unique user constraint: keep the red forehead ornament visible.",
        "Avoid: beauty-app face",
    ]

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert user_direction in final_prompt
    assert "A unique user constraint: keep the red forehead ornament visible." in final_prompt
    assert "Use the V3-owned generation strategy" not in final_prompt
    assert "Hard constraints: Avoid:" not in final_prompt
    assert "Mode quality contract" in final_prompt
    assert "Review priorities:" not in final_prompt
    assert "Pass conditions:" not in final_prompt


def test_production_provider_can_apply_explicit_emergency_prompt_cap() -> None:
    request = _human_generation_request()
    request.prompt_compilation.visual_prompt = " ".join(
        [
            "East Asian summer beach portrait with natural fair skin, same person identity, premium real camera photography"
            for _ in range(180)
        ]
    )
    request.prompt_compilation.negative_prompt = "distorted face, watermark, text, " * 80
    provider = ProductionImageGenerationProvider()
    provider.max_provider_prompt_chars = 3200

    final_prompt = provider._generation_prompt(request, [])  # noqa: SLF001

    assert len(final_prompt) <= 3200
    assert "Visual direction:" in final_prompt
    assert "Human realism contract" in final_prompt
    assert "Identity continuity" in final_prompt
    assert "Avoid:" in final_prompt
    assert "watermark" in final_prompt


def test_production_provider_honors_transport_prompt_cap(monkeypatch) -> None:
    from app.config import settings

    request = _human_generation_request()
    user_direction = "Keep the desk lamp centered on a warm oak desk in clean morning light; no text."
    request.metadata["user_input"] = user_direction
    request.prompt_compilation.visual_prompt = " ".join(
        [
            "premium product atmosphere with honest material rendering, clean composition, and natural commercial lighting"
            for _ in range(80)
        ]
    )
    request.prompt_compilation.negative_prompt = "watermark, distorted product, clutter, " * 60
    monkeypatch.setattr(settings, "openai_image_transport_max_prompt_chars", 1800)

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert len(final_prompt) <= 1800
    assert user_direction in final_prompt
    assert "watermark" in final_prompt


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


def test_v3_output_store_reuses_cached_index_until_the_storage_revision_changes(tmp_path, monkeypatch) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first = store.save_base64_output(
        job_id="job_cached_outputs",
        candidate_id="candidate_cached_outputs",
        asset_id="asset_cached_outputs",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(96, 64),
    )
    scans = 0
    original_signature = store._record_paths_signature  # noqa: SLF001

    def observe_signature():
        nonlocal scans
        scans += 1
        return original_signature()

    monkeypatch.setattr(store, "_record_paths_signature", observe_signature)

    assert [record.output_id for record in store.list_by_job(first.job_id)] == [first.output_id]
    assert [record.output_id for record in store.list_by_job(first.job_id)] == [first.output_id]
    assert scans == 1

    second = store.save_base64_output(
        job_id="job_cached_outputs",
        candidate_id="candidate_cached_outputs_2",
        asset_id="asset_cached_outputs_2",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(96, 64),
    )

    assert {record.output_id for record in store.list_by_job(first.job_id)} == {first.output_id, second.output_id}
    assert scans == 2


def test_v3_output_store_observes_a_write_from_another_store_instance(tmp_path) -> None:
    root = tmp_path / "outputs"
    reader = V3GeneratedOutputStore(root)
    writer = V3GeneratedOutputStore(root)

    assert reader.list_outputs() == []
    record = writer.save_base64_output(
        job_id="job_external_output",
        candidate_id="candidate_external_output",
        asset_id="asset_external_output",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(96, 64),
    )

    assert [item.output_id for item in reader.list_by_job(record.job_id)] == [record.output_id]


def test_product_api_real_generation_uses_injected_output_store(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(128, 128), "mime_type": "image/png", "format": "png", "width": 128, "height": 128},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    store = V3GeneratedOutputStore(tmp_path / "product_api_outputs")
    service = V3ProductApiService(output_store=store)
    try:
        created = service.create_job(
            {
                "user_input": "Create a clean summer portrait social cover",
                "scenario_selection": {"scenario_id": "general_creative", "preset_id": "social_cover"},
                "metadata": {"requested_image_count": 1, "requested_image_size": "1024x1024"},
            }
        )
        generated = service.generate_job(
            created.job_id,
            {
                "quality_mode": "standard",
                "metadata": {"require_real_images": True, "requested_image_count": 1},
            },
        )
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    records = store.list_by_job(created.job_id)
    assert generated.status == "generated"
    assert len(records) == 1
    assert generated.asset_series[0].output_id == records[0].output_id
    assert Path(records[0].file_path).is_relative_to(tmp_path / "product_api_outputs")


def test_product_api_persisted_real_generation_requirement_cannot_downgrade_to_mock(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(128, 128), "mime_type": "image/png", "format": "png", "width": 128, "height": 128},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    store = V3GeneratedOutputStore(tmp_path / "product_api_outputs")
    service = V3ProductApiService(output_store=store)
    try:
        created = service.create_job(
            {
                "user_input": "Create a clean text-led poster",
                "scenario_selection": {"scenario_id": "general_creative", "preset_id": "social_cover"},
                "metadata": {
                    "require_real_images": True,
                    "requested_image_count": 1,
                    "requested_image_size": "1024x1024",
                },
            }
        )
        generated = service.generate_job(
            created.job_id,
            {
                "quality_mode": "standard",
                # This mirrors Project Mode's normal later generate request:
                # it cannot relax the frozen real-provider intent.
                "metadata": {"requested_image_count": 1, "require_real_images": False},
            },
        )
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    records = store.list_by_job(created.job_id)
    assert generated.status == "generated"
    assert len(records) == 1
    assert records[0].provider == "openai_gpt_image"
    assert records[0].metadata.get("mock_contract_fixture") is not True


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
