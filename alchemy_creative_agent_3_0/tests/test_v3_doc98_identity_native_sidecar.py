import asyncio
import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    ProductionImageGenerationProvider,
)
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
from app.config import settings
from app.providers.base import ProviderCapabilityMismatchError, ProviderRuntimeError
from app.providers.identity_sidecar import IdentityNativeSidecarProvider
from app.schemas import ImageGenerationRequest, ImageGenerationResult, ImagePromptPlan


def _png_base64(width: int = 96, height: int = 96) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(94, 124, 143))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _reference(path: Path) -> Path:
    path.write_bytes(base64.b64decode(_png_base64()))
    return path


def _sidecar_request(path: Path) -> ImageGenerationRequest:
    asset_plan = {
        "assets": [
            {
                "asset_id": "portrait-root::portrait_identity_crop",
                "source_asset_id": "portrait-root",
                "role": "portrait_identity",
                "priority": 130,
                "provider_input_mode": "reference_image",
                "storage_path": str(path),
                "mime_type": "image/png",
                "reference_truth_layer": "portrait_identity_truth",
                "truth_layers": ["portrait_identity_truth"],
                "derivative_kind": "portrait_identity_crop",
            }
        ],
        "provider_input_plan": {
            "reference_truth_layers": [
                {
                    "asset_id": "portrait-root::portrait_identity_crop",
                    "source_asset_id": "portrait-root",
                    "truth_layer": "portrait_identity_truth",
                    "truth_layers": ["portrait_identity_truth"],
                }
            ]
        },
    }
    return ImageGenerationRequest(
        prompt_plan=ImagePromptPlan(
            main_subject="same person in a new portrait scene",
            negative_constraints=["identity drift", "plastic skin"],
            size="1024x1536",
            variables={"generation_prompt": "Keep the same person while changing the scene.", "asset_plan": asset_plan},
        ),
        asset_ids=["portrait-root::portrait_identity_crop"],
        asset_mode="advanced",
        asset_plan=asset_plan,
        provider_preference="identity_native_sidecar",
        idempotency_key="doc98-test",
        trace_id="trace-doc98",
    )


def _production_portrait_request(path: Path) -> GenerationRequest:
    visual_cluster = {
        "human_photorealism_guidance": {"applies": True},
        "subject_continuity_asset_package": {
            "applies": True,
            "subject_type": "character",
            "uploaded_root_truth_ids": ["portrait-root"],
            "provider_candidate_ids": ["portrait-root"],
        },
    }
    asset = AssetSpec(
        asset_id="asset-doc98-portrait",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="realistic portrait cover",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt-doc98",
            asset_id=asset.asset_id,
            visual_prompt="Same person in a clean daylight editorial portrait",
            negative_prompt="identity drift, plastic skin",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["realistic portrait"],
            layout_notes=["portrait crop"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition-doc98", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation-doc98",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job-doc98",
            "template_id": "general_creative",
            "user_input": "Create a realistic portrait of the same person in clean daylight",
            "uploaded_assets": [
                {
                    "asset_id": "portrait-root",
                    "role": "portrait_identity",
                    "filename": path.name,
                    "mime_type": "image/png",
                    "file_path": str(path),
                }
            ],
            "visual_cluster": visual_cluster,
            "shared_capabilities": {"visual_cluster": visual_cluster},
        },
    )


def _enable_sidecar(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(settings, "v3_identity_sidecar_enabled", True)
    monkeypatch.setattr(settings, "v3_identity_sidecar_base_url", "https://identity.test")
    monkeypatch.setattr(settings, "v3_identity_sidecar_api_key", "sidecar-key")
    monkeypatch.setattr(settings, "v3_identity_sidecar_provider", "pulid")
    monkeypatch.setattr(settings, "v3_identity_sidecar_model", "pulid-test")
    monkeypatch.setattr(settings, "v3_identity_sidecar_health_ttl_seconds", 0.0)
    monkeypatch.setattr(settings, "v3_identity_sidecar_max_references", 3)


def test_identity_sidecar_requires_live_identity_capability(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    reference = _reference(tmp_path / "portrait.png")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/capabilities"
        return httpx.Response(200, json={"capabilities": {"multi_reference": True}})

    provider = IdentityNativeSidecarProvider(transport=httpx.MockTransport(handler))
    try:
        asyncio.run(provider.generate(_sidecar_request(reference)))
    except ProviderCapabilityMismatchError as exc:
        assert "identity_conditioning=true" in str(exc)
    else:
        raise AssertionError("A sidecar without identity_conditioning must be rejected")


def test_identity_sidecar_sends_multipart_and_records_actual_capabilities(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    reference = _reference(tmp_path / "portrait.png")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "capabilities": {
                        "identity_conditioning": True,
                        "multi_reference": True,
                        "identity_native_local_repair": True,
                    },
                },
            )
        body = request.read()
        assert request.url.path == "/v1/identity/generate"
        assert request.headers["authorization"] == "Bearer sidecar-key"
        assert b'name="manifest"' in body
        assert b'name="reference_0"' in body
        assert b"doc98-v1" in body
        return httpx.Response(
            200,
            json={
                "provider": "pulid",
                "model": "pulid-test",
                "outputs": [
                    {
                        "b64_json": _png_base64(),
                        "mime_type": "image/png",
                        "format": "png",
                        "width": 96,
                        "height": 96,
                    }
                ],
            },
        )

    provider = IdentityNativeSidecarProvider(transport=httpx.MockTransport(handler))
    result = asyncio.run(provider.generate(_sidecar_request(reference)))

    assert len(requests) == 2
    assert result.provider == "identity_native_sidecar:pulid"
    assert result.outputs[0]["identity_native_provider"] is True
    assert result.outputs[0]["identity_native_local_repair_capable"] is True
    assert result.raw_response_summary["identity_native_local_repair"] is True
    assert result.raw_response_summary["contract_version"] == "doc98-v1"


def test_identity_sidecar_local_repair_sends_canvas_and_mask(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    reference = _reference(tmp_path / "portrait.png")
    canvas = _reference(tmp_path / "canvas.png")
    mask = _reference(tmp_path / "mask.png")
    request_payload = _sidecar_request(reference)
    request_payload.prompt_plan.variables["identity_repair_canvas_path"] = str(canvas)
    request_payload.prompt_plan.variables["identity_repair_mask_path"] = str(mask)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "capabilities": {
                        "identity_conditioning": True,
                        "identity_native_local_repair": True,
                    }
                },
            )
        body = request.read()
        assert b'name="canvas"' in body
        assert b'name="mask"' in body
        assert b'"active": true' in body
        return httpx.Response(
            200,
            json={
                "provider": "pulid",
                "outputs": [{"b64_json": _png_base64(), "mime_type": "image/png"}],
            },
        )

    provider = IdentityNativeSidecarProvider(transport=httpx.MockTransport(handler))
    result = asyncio.run(provider.generate(request_payload))

    assert result.outputs[0]["identity_local_repair"] is True
    assert result.outputs[0]["identity_native_local_repair_capable"] is True


def test_production_router_uses_sidecar_only_for_doc97_portrait_package(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    monkeypatch.setattr(settings, "openai_api_key", "fallback-key")
    reference = _reference(tmp_path / "portrait.png")
    provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    request = _production_portrait_request(reference)

    app_request, provider_name, references = provider._build_app_request(request)  # noqa: SLF001

    assert references
    assert provider_name == "identity_native_sidecar"
    assert app_request.provider_preference == "identity_native_sidecar"

    request.metadata["visual_cluster"]["subject_continuity_asset_package"]["subject_type"] = "product"
    app_request, provider_name, _ = provider._build_app_request(request)  # noqa: SLF001
    assert provider_name == "openai_gpt_image"
    assert app_request.provider_preference == "openai_gpt_image"


def test_sidecar_failure_falls_back_and_never_claims_identity_native_delivery(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    monkeypatch.setattr(settings, "openai_api_key", "fallback-key")
    monkeypatch.setattr(settings, "default_image_provider", "openai_gpt_image")
    reference = _reference(tmp_path / "portrait.png")
    calls: list[str] = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        if provider_name == "identity_native_sidecar":
            raise ProviderRuntimeError(
                "Identity sidecar capability probe failed.",
                provider=provider_name,
                detail={"message": "503 service unavailable", "retryable": True},
            )
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="gpt-image-test",
            outputs=[
                {
                    "b64_json": _png_base64(),
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 96,
                    "height": 96,
                }
            ],
            raw_response_summary={"output_count": 1},
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    monkeypatch.setattr(ProductionImageGenerationProvider, "_app_provider_transient_cooldown_seconds", lambda self: 0.0)
    provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    response = provider.generate(_production_portrait_request(reference))

    assert calls == ["identity_native_sidecar", "openai_gpt_image"]
    audit = response.provider_metadata["identity_native_routing"]
    assert audit["attempted"] is True
    assert audit["delivered"] is False
    assert audit["fallback_used"] is True
    assert audit["capability_evidence_source"] == "none"
    assert response.provider_metadata["provider_failure_retry"]["final_provider"] == "openai_gpt_image"
    assert response.candidates[0].metadata["identity_native_provider"] is False


def test_sidecar_and_fallback_failure_preserve_the_full_attempt_audit(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    monkeypatch.setattr(settings, "openai_api_key", "fallback-key")
    monkeypatch.setattr(settings, "default_image_provider", "openai_gpt_image")
    reference = _reference(tmp_path / "portrait.png")
    calls: list[str] = []

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        calls.append(provider_name)
        raise ProviderRuntimeError(
            "Upstream 503 service unavailable.",
            provider=provider_name,
            detail={"message": "503 service unavailable", "retryable": True},
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    monkeypatch.setattr(ProductionImageGenerationProvider, "_app_provider_transient_cooldown_seconds", lambda self: 0.0)
    provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    try:
        provider.generate(_production_portrait_request(reference))
    except ProviderRuntimeError as exc:
        summary = getattr(exc, "provider_failure_retry")
    else:
        raise AssertionError("The final fallback error should propagate")

    assert calls == ["identity_native_sidecar", "openai_gpt_image", "openai_gpt_image"]
    assert summary["final_status"] == "failed"
    assert summary["identity_sidecar_attempted"] is True
    assert summary["identity_sidecar_fallback"] is True
    assert len(summary["attempts"]) == 3
    assert summary["attempts"][0]["provider"] == "identity_native_sidecar"
    assert summary["attempts"][-1]["provider"] == "openai_gpt_image"


def test_sidecar_success_is_audited_as_capability_backed_delivery(tmp_path, monkeypatch) -> None:
    _enable_sidecar(monkeypatch)
    monkeypatch.setattr(settings, "openai_api_key", "fallback-key")
    reference = _reference(tmp_path / "portrait.png")

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "identity_native_sidecar"
        return ImageGenerationResult(
            provider="identity_native_sidecar:photomaker",
            model="photomaker-test",
            outputs=[
                {
                    "b64_json": _png_base64(),
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 96,
                    "height": 96,
                    "identity_native_provider": True,
                    "identity_conditioning": True,
                    "identity_native_local_repair_capable": False,
                }
            ],
            raw_response_summary={
                "identity_native_provider": True,
                "identity_conditioning": True,
                "identity_native_local_repair": False,
                "multi_reference": True,
                "backend_family": "photomaker",
            },
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    response = provider.generate(_production_portrait_request(reference))

    audit = response.provider_metadata["identity_native_routing"]
    assert audit == {
        "doc": "98",
        "attempted": True,
        "delivered": True,
        "requested_provider": "identity_native_sidecar",
        "actual_provider": "identity_native_sidecar:photomaker",
        "fallback_used": False,
        "identity_conditioning": True,
        "identity_native_local_repair": False,
        "multi_reference": True,
        "backend_family": "photomaker",
        "capability_evidence_source": "live_sidecar_response",
    }
    assert response.candidates[0].metadata["identity_native_provider"] is True


def test_local_repair_gate_accepts_only_delivered_sidecar_capability_evidence(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job-doc98-repair",
        candidate_id="candidate-doc98-repair",
        asset_id="asset-doc98-repair",
        provider="identity_native_sidecar:pulid",
        model="pulid-test",
        encoded_image=_png_base64(),
        metadata={
            "identity_native_local_repair_capable": True,
            "identity_native_routing": {
                "delivered": True,
                "identity_native_local_repair": True,
                "capability_evidence_source": "live_sidecar_response",
            },
        },
    )
    service = object.__new__(V3ProductApiService)
    service.output_store = store
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "inspections": [{"output_id": record.output_id}]
            }
        }
    )

    assert service._result_has_identity_native_local_repair_capability(result) is True  # noqa: SLF001

    store.update_metadata(
        record.output_id,
        {
            "identity_native_local_repair_capable": False,
            "identity_native_routing": {
                "delivered": False,
                "identity_native_local_repair": True,
                "capability_evidence_source": "none",
            },
        },
    )
    assert service._result_has_identity_native_local_repair_capability(result) is False  # noqa: SLF001
