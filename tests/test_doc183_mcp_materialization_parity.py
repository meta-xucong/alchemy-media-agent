from __future__ import annotations

import base64
from io import BytesIO
import hashlib
from pathlib import Path
import threading

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord, V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    BrandProfile,
    CommercialAssetPack,
    CommercialBrief,
    ConditionPlan,
    CreativeJob,
    CreativePlan,
    GenerationPlan,
    IndustryCategory,
    LayoutPlan,
    LayoutRegion,
    PackagedAsset,
    Platform,
    PlanningResult,
    PromptCompilationResult,
    ProviderStrategy,
    SeriesPlan,
    TextRenderingMode,
)
from app.providers.base import ProviderRuntimeError
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS

from tests.test_doc130_codex_native_prompt_parity import _canonical_runtime_result


def _png_bytes() -> bytes:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(220, 235, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _provider_request() -> object:
    runtime_result = _canonical_runtime_result()
    plan = runtime_result.planning_result
    return build_provider_generation_request(
        asset_spec=plan.series_plan.assets[0],
        layout_plan=plan.layout_plans[0],
        prompt_compilation=plan.prompt_compilations[0],
        condition_plan=plan.condition_plans[0],
        generation_plan=plan.generation_plans[0],
        job_id=plan.creative_job.job_id,
    )


def _light_provider_request(*, generation_metadata: dict | None = None, metadata: dict | None = None) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc222",
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="character card validation image",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc222",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc222",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
    )
    condition = ConditionPlan(condition_plan_id="condition_doc222", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_doc222",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
        metadata=generation_metadata or {},
    )
    base_metadata = {
        "llm_brain": {
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "review_status": "approved",
                    "prompt": "same character card portrait",
                }
            ]
        }
    }
    base_metadata.update(metadata or {})
    return GenerationRequest(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt,
        condition_plan=condition,
        generation_plan=generation,
        metadata=base_metadata,
    )


class _CrashBeforeOutputStore(V3GeneratedOutputStore):
    def save_base64_output(self, **_kwargs):  # noqa: ANN001, ANN201
        raise RuntimeError("doc223 injected crash before output checkpoint")


def _minimal_generation_result_with_candidate(candidate, *, job_id: str) -> PlanningResult:  # noqa: ANN001
    asset = AssetSpec(
        asset_id=candidate.asset_id,
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="checkpoint fixture",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc223",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id=str(candidate.prompt_compilation_id or "prompt_doc223"),
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
    )
    condition = ConditionPlan(condition_plan_id=str(candidate.condition_plan_id or "condition_doc223"), asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_doc223",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
    )
    packaged = PackagedAsset(
        asset_id=asset.asset_id,
        asset_type=asset.asset_type,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        purpose=asset.purpose,
        file_path=candidate.file_path,
        uri=candidate.uri,
        layout_plan_id=layout.layout_plan_id,
        prompt_compilation_id=prompt.prompt_compilation_id,
        metadata={
            "selected_candidate_id": candidate.candidate_id,
            "candidate_metadata": dict(candidate.metadata),
        },
    )
    job = CreativeJob(job_id=job_id, raw_user_input="doc223 checkpoint")
    return PlanningResult(
        planning_result_id="planning_doc223",
        creative_job=job,
        commercial_brief=CommercialBrief(
            brief_id="brief_doc223",
            job_id=job_id,
            industry=IndustryCategory.UNKNOWN,
            scenario="checkpoint",
            business_goal="checkpoint",
            target_platforms=[Platform.XIAOHONGSHU],
        ),
        brand_profile=BrandProfile(brand_id="brand_doc223"),
        creative_plan=CreativePlan(
            creative_plan_id="plan_doc223",
            job_id=job_id,
            brief_id="brief_doc223",
            concept="checkpoint",
            visual_direction="checkpoint",
            composition_strategy="single subject",
        ),
        series_plan=SeriesPlan(series_plan_id="series_doc223", job_id=job_id, assets=[asset]),
        layout_plans=[layout],
        prompt_compilations=[prompt],
        condition_plans=[condition],
        generation_plans=[generation],
        evaluation_reports=[],
        asset_pack=CommercialAssetPack(
            asset_pack_id="asset_pack_doc223",
            job_id=job_id,
            assets=[packaged],
            planning_only=False,
        ),
        metadata={},
    )


def test_handoff_is_nonce_hash_reference_and_one_time_safe(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "Remote Brain final prompt"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    contract = {"renderer": "codex_builtin_imagegen", "model": "gpt-image-2", "output_format": "png", "count": 1}
    pending = store.ensure_pending(
        operation_id="project:face.front:1",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[],
        rendering_contract=contract,
    )
    assert pending["status"] == "pending"
    assert store.public_view(pending["handoff_id"])["canonical_prompt"] == prompt
    with pytest.raises(McpMaterializationError, match="nonce"):
        store.submit(
            pending["handoff_id"],
            nonce="wrong",
            prompt_sha256=prompt_hash,
            reference_asset_hashes=[],
            artifact_bytes=_png_bytes(),
        )
    submitted = store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_hash,
        reference_asset_hashes=[],
        artifact_bytes=_png_bytes(),
    )
    assert submitted["status"] == "submitted"
    artifact = store.consume(pending["handoff_id"])
    assert artifact["artifact_format"] == "png"
    assert store.get(pending["handoff_id"])["status"] == "consumed_uncheckpointed"
    replayed = store.consume(pending["handoff_id"])
    assert replayed["artifact_sha256"] == artifact["artifact_sha256"]


def test_handoff_rejects_format_and_reference_mismatch(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "same prompt"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    pending = store.ensure_pending(
        operation_id="op-2",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[{"asset_id": "root", "sha256": "a" * 64}],
        rendering_contract={"output_format": "png"},
    )
    with pytest.raises(McpMaterializationError, match="reference"):
        store.submit(
            pending["handoff_id"],
            nonce=pending["nonce"],
            prompt_sha256=prompt_hash,
            reference_asset_hashes=["b" * 64],
            artifact_bytes=_png_bytes(),
        )
    with pytest.raises(McpMaterializationError, match="readable"):
        store.submit(
            pending["handoff_id"],
            nonce=pending["nonce"],
            prompt_sha256=prompt_hash,
            reference_asset_hashes=["a" * 64],
            artifact_bytes=b"not-an-image",
        )


def test_doc222_handoff_store_round_trips_character_card_reference_semantics(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    references = [
        {
            "asset_id": "front_output",
            "output_id": "front_output",
            "sha256": "1" * 64,
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_evidence_scope": "card_framing",
        },
        {
            "asset_id": "front_output",
            "output_id": "front_output",
            "sha256": "2" * 64,
            "derivative_kind": "portrait_identity_crop",
            "identity_evidence_scope": "feature_detail",
        },
        {
            "asset_id": "front_output",
            "output_id": "front_output",
            "sha256": "3" * 64,
            "derivative_kind": "portrait_identity_pose_geometry_crop",
            "identity_evidence_scope": "head_geometry",
        },
    ]

    pending = store.ensure_pending(
        operation_id="doc222-full-frame-first",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={"output_format": "png"},
    )
    readback = store.get(pending["handoff_id"])

    assert readback is not None
    assert readback["reference_assets"][0]["derivative_kind"] == (
        "character_card_full_frame_framing_reference"
    )
    assert readback["reference_assets"][0]["identity_evidence_scope"] == "card_framing"
    assert ProductApiAnchorPackPreparationHost._character_card_expression_handoff_reference_order_current(  # noqa: SLF001
        readback
    )


def test_doc222_handoff_semantic_fingerprint_separates_same_bytes_different_roles(
    tmp_path: Path,
) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    base = [
        {
            "asset_id": "front_output",
            "sha256": "a" * 64,
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_evidence_scope": "card_framing",
        },
        {
            "asset_id": "front_output",
            "sha256": "a" * 64,
            "derivative_kind": "portrait_identity_crop",
            "identity_evidence_scope": "feature_detail",
        },
    ]
    swapped = [dict(base[1]), dict(base[0])]

    first = store.ensure_pending(
        operation_id="doc222-same-bytes",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=base,
        rendering_contract={"output_format": "png"},
    )
    second = store.ensure_pending(
        operation_id="doc222-same-bytes",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=swapped,
        rendering_contract={"output_format": "png"},
    )

    assert first["handoff_id"] != second["handoff_id"]
    assert first["reference_asset_hashes"] == second["reference_asset_hashes"]
    assert first["reference_semantic_fingerprint"] != second["reference_semantic_fingerprint"]


def test_doc222_rendering_contract_mismatch_creates_new_pending_revision(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    references = [{"asset_id": "front_output", "sha256": "1" * 64}]
    first = store.ensure_pending(
        operation_id="doc222-rendering",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={"size": "24x24", "quality": "high", "output_format": "png"},
    )
    second = store.ensure_pending(
        operation_id="doc222-rendering",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={"size": "1536x1024", "quality": "high", "output_format": "png"},
    )

    assert first["handoff_id"] != second["handoff_id"]
    assert first["revision"] == 1
    assert second["revision"] == 2
    assert first["reference_asset_hashes"] == second["reference_asset_hashes"]
    assert first["rendering_contract_fingerprint"] != second["rendering_contract_fingerprint"]


def test_doc222_submitted_rendering_contract_mismatch_fails_closed(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    references = [{"asset_id": "front_output", "sha256": "1" * 64}]
    pending = store.ensure_pending(
        operation_id="doc222-submitted-rendering",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={"size": "24x24", "quality": "high", "output_format": "png"},
    )
    store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=prompt_hash,
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    with pytest.raises(McpMaterializationError, match="contract_mismatch"):
        store.ensure_pending(
            operation_id="doc222-submitted-rendering",
            prompt=prompt,
            prompt_sha256=prompt_hash,
            reference_assets=references,
            rendering_contract={"size": "32x32", "quality": "high", "output_format": "png"},
        )


def test_doc223_handoff_store_uses_unique_temp_files_under_concurrent_writes(
    tmp_path: Path,
) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    errors: list[BaseException] = []

    def _write(index: int) -> None:
        try:
            store.ensure_pending(
                operation_id=f"doc223-concurrent-{index}",
                prompt=prompt,
                prompt_sha256=prompt_hash,
                reference_assets=[{"asset_id": f"front_{index}", "sha256": f"{index:064x}"}],
                rendering_contract={"size": "1024x1536", "output_format": "png"},
            )
        except BaseException as exc:  # pragma: no cover - assertion reports collected exceptions.
            errors.append(exc)

    threads = [threading.Thread(target=_write, args=(index + 1,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(list(tmp_path.glob("mcp_handoff_*.json"))) == 8
    assert list(tmp_path.glob("*.json.tmp")) == []


def test_doc222_handoff_order_current_supports_suffix_fallback_but_rejects_degraded_contract(
    tmp_path: Path,
) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    suffix_only = store.ensure_pending(
        operation_id="doc222-suffix-only",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {"asset_id": "front_output", "sha256": "1" * 64},
            {"asset_id": "front_output::portrait_identity_crop", "sha256": "2" * 64},
            {"asset_id": "front_output::portrait_identity_geometry_crop", "sha256": "3" * 64},
        ],
        rendering_contract={"output_format": "png"},
    )
    degraded = store.ensure_pending(
        operation_id="doc222-degraded",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {"asset_id": "front_output", "sha256": "1" * 64},
            {"asset_id": "front_output", "sha256": "2" * 64},
            {"asset_id": "front_output", "sha256": "3" * 64},
        ],
        rendering_contract={"output_format": "png"},
    )

    assert ProductApiAnchorPackPreparationHost._character_card_expression_handoff_reference_order_current(  # noqa: SLF001
        store.get(suffix_only["handoff_id"]) or {}
    )
    assert not ProductApiAnchorPackPreparationHost._character_card_expression_handoff_reference_order_current(  # noqa: SLF001
        store.get(degraded["handoff_id"]) or {}
    )


def test_doc222_crop_first_handoff_round_trip_remains_rejected(tmp_path: Path) -> None:
    store = McpMaterializationHandoffStore(tmp_path)
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    pending = store.ensure_pending(
        operation_id="doc222-crop-first",
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=[
            {
                "asset_id": "front_output",
                "sha256": "2" * 64,
                "derivative_kind": "portrait_identity_crop",
                "identity_evidence_scope": "feature_detail",
            },
            {
                "asset_id": "front_output",
                "sha256": "3" * 64,
                "derivative_kind": "portrait_identity_pose_geometry_crop",
                "identity_evidence_scope": "head_geometry",
            },
            {
                "asset_id": "front_output",
                "sha256": "1" * 64,
                "derivative_kind": "character_card_full_frame_framing_reference",
                "identity_evidence_scope": "card_framing",
            },
        ],
        rendering_contract={"output_format": "png"},
    )

    assert not ProductApiAnchorPackPreparationHost._character_card_expression_handoff_reference_order_current(  # noqa: SLF001
        store.get(pending["handoff_id"]) or {}
    )


def test_mcp_and_provider_materializers_share_prompt_reference_and_rendering_contract() -> None:
    request = _light_provider_request()
    web = ProductionImageGenerationProvider(output_store=object())
    mcp = McpMaterializationProvider(output_store=object(), handoff_store=McpMaterializationHandoffStore())
    web_materialization = web.materialize_final_prompt(request)
    mcp_request = request.model_copy(
        update={"metadata": {**request.metadata, "generation_channel": "mcp", "mcp_operation_id": "parity-op"}}
    )
    mcp_app_request, _provider_name, _references = mcp._build_app_request(mcp_request)
    variables = mcp_app_request.prompt_plan.variables
    assert variables["generation_prompt"] == web_materialization.generation_prompt
    assert variables["provider_prompt_sha256"] == web_materialization.prompt_sha256
    assert variables["mcp_materialization_context"]["rendering_contract"] == {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": mcp_app_request.prompt_plan.size,
        "quality": mcp_app_request.prompt_plan.quality,
        "output_format": mcp_app_request.prompt_plan.output_format,
        "count": 1,
        "api_operation": "image_generate",
        "input_fidelity": None,
        "input_fidelity_required": False,
        "size_normalization": "white_matte_contain_to_contract_size",
    }


def test_doc222_provider_recovers_handoff_from_generation_plan_metadata_only(tmp_path: Path) -> None:
    provider = McpMaterializationProvider(
        output_store=object(),
        handoff_store=McpMaterializationHandoffStore(tmp_path / "handoffs"),
    )
    operation_id = "doc222-generation-plan-only"
    planning_only_request = _light_provider_request(
        generation_metadata={"mcp_operation_id": operation_id},
        metadata={},
    )
    app_request, _provider_name, reference_assets = provider._build_app_request(planning_only_request)
    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    handoff = provider.handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=context["canonical_prompt"],
        prompt_sha256=context["prompt_sha256"],
        reference_assets=reference_assets,
        rendering_contract=context["rendering_contract"],
    )
    resume_request = planning_only_request.model_copy(
        update={
            "generation_plan": planning_only_request.generation_plan.model_copy(
                update={
                    "metadata": {
                        **dict(planning_only_request.generation_plan.metadata or {}),
                        "mcp_materialization": {
                            "handoff_id": handoff["handoff_id"],
                            "status": "pending",
                            "generation_channel": "mcp",
                        },
                    }
                }
            ),
            "metadata": {
                key: value
                for key, value in dict(planning_only_request.metadata or {}).items()
                if key not in {"mcp_operation_id", "mcp_materialization"}
            },
        }
    )

    resumed_app_request, _provider_name, _references = provider._build_app_request(resume_request)
    variables = resumed_app_request.prompt_plan.variables

    assert variables["provider_prompt_materialization"] == "v3_mcp_frozen_handoff_resume"
    assert variables["mcp_materialization_context"]["handoff_id"] == handoff["handoff_id"]


def test_doc222_provider_pending_resume_checks_reference_semantic_fingerprint(tmp_path: Path) -> None:
    provider = McpMaterializationProvider(
        output_store=object(),
        handoff_store=McpMaterializationHandoffStore(tmp_path / "handoffs"),
    )
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    operation_id = "doc222-provider-semantic"
    crop_first = [
        {
            "asset_id": "front_output",
            "sha256": "a" * 64,
            "derivative_kind": "portrait_identity_crop",
            "identity_evidence_scope": "feature_detail",
        },
        {
            "asset_id": "front_output",
            "sha256": "a" * 64,
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_evidence_scope": "card_framing",
        },
    ]
    full_frame_first = [dict(crop_first[1]), dict(crop_first[0])]
    rendering_contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
    }
    handoff = provider.handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=crop_first,
        rendering_contract=rendering_contract,
    )
    request = _light_provider_request(
        metadata={
            "mcp_operation_id": operation_id,
            "mcp_materialization": {
                "handoff_id": handoff["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
            },
        }
    )

    assert (
        provider._existing_mcp_handoff_context(  # noqa: SLF001
            request,
            current_context={
                "operation_id": operation_id,
                "canonical_prompt": prompt,
                "prompt_sha256": prompt_hash,
            },
            current_reference_assets=full_frame_first,
            current_rendering_contract=rendering_contract,
        )
        is None
    )


def test_doc222_provider_pending_resume_checks_full_rendering_fingerprint(tmp_path: Path) -> None:
    provider = McpMaterializationProvider(
        output_store=object(),
        handoff_store=McpMaterializationHandoffStore(tmp_path / "handoffs"),
    )
    prompt = "expression laugh handoff"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    operation_id = "doc222-provider-rendering"
    references = [{"asset_id": "front_output", "sha256": "a" * 64}]
    handoff = provider.handoff_store.ensure_pending(
        operation_id=operation_id,
        prompt=prompt,
        prompt_sha256=prompt_hash,
        reference_assets=references,
        rendering_contract={
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
            "input_fidelity": "high",
        },
    )
    request = _light_provider_request(
        metadata={
            "mcp_operation_id": operation_id,
            "mcp_materialization": {
                "handoff_id": handoff["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
            },
        }
    )

    assert (
        provider._existing_mcp_handoff_context(  # noqa: SLF001
            request,
            current_context={
                "operation_id": operation_id,
                "canonical_prompt": prompt,
                "prompt_sha256": prompt_hash,
            },
            current_reference_assets=references,
            current_rendering_contract={
                "renderer": "codex_builtin_imagegen",
                "model": "gpt-image-2",
                "size": "1024x1536",
                "quality": "high",
                "output_format": "png",
                "count": 1,
                "api_operation": "image_edit",
                "input_fidelity": "low",
            },
        )
        is None
    )


def test_doc223a_resume_after_consume_before_output_checkpoint_uses_same_handoff_and_output(
    tmp_path: Path,
) -> None:
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    operation_id = "doc223a-consume-before-output"
    request = _light_provider_request(metadata={"generation_channel": "mcp", "mcp_operation_id": operation_id})
    failing_provider = McpMaterializationProvider(
        output_store=_CrashBeforeOutputStore(tmp_path / "crash-outputs"),
        handoff_store=handoffs,
    )
    with pytest.raises(ProviderRuntimeError) as pending:
        failing_provider.generate(request)
    handoff_id = pending.value.detail["handoff_id"]
    public = handoffs.public_view(handoff_id)
    handoffs.submit(
        handoff_id,
        nonce=public["nonce"],
        prompt_sha256=public["prompt_sha256"],
        reference_asset_hashes=public["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    with pytest.raises(RuntimeError, match="injected crash"):
        failing_provider.generate(request)
    consumed = handoffs.get(handoff_id)
    assert consumed is not None
    assert consumed["status"] == "consumed_uncheckpointed"
    expected_output_id = consumed["mcp_checkpoint"]["output_id"]

    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    recovery_provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    response = recovery_provider.generate(request)
    recovered = handoffs.get(handoff_id)

    assert len(response.candidates) == 1
    assert response.candidates[0].metadata["output_id"] == expected_output_id
    assert recovered is not None
    assert recovered["status"] == "output_checkpointed"
    assert recovered["output_checkpoint"]["output_id"] == expected_output_id
    assert len(outputs.list_outputs()) == 1


def test_doc223a_resume_after_output_checkpoint_is_idempotent_and_does_not_duplicate_output(
    tmp_path: Path,
) -> None:
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    operation_id = "doc223a-output-before-job"
    request = _light_provider_request(metadata={"generation_channel": "mcp", "mcp_operation_id": operation_id})
    with pytest.raises(ProviderRuntimeError) as pending:
        provider.generate(request)
    handoff_id = pending.value.detail["handoff_id"]
    public = handoffs.public_view(handoff_id)
    handoffs.submit(
        handoff_id,
        nonce=public["nonce"],
        prompt_sha256=public["prompt_sha256"],
        reference_asset_hashes=public["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )

    first = provider.generate(request)
    checkpointed = handoffs.get(handoff_id)
    assert checkpointed is not None
    assert checkpointed["status"] == "output_checkpointed"
    first_output_id = first.candidates[0].metadata["output_id"]
    assert len(outputs.list_outputs()) == 1

    second = provider.generate(request)
    assert second.candidates[0].metadata["output_id"] == first_output_id
    assert len(outputs.list_outputs()) == 1
    assert handoffs.get(handoff_id)["status"] == "output_checkpointed"


def test_doc223a_product_job_checkpoint_advances_handoff_after_generation_result_save(
    tmp_path: Path,
) -> None:
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    operation_id = "doc223a-job-checkpoint"
    request = _light_provider_request(
        metadata={
            "generation_channel": "mcp",
            "mcp_operation_id": operation_id,
            "job_id": "job_doc223a_checkpoint",
        }
    )
    with pytest.raises(ProviderRuntimeError) as pending:
        provider.generate(request)
    handoff_id = pending.value.detail["handoff_id"]
    public = handoffs.public_view(handoff_id)
    handoffs.submit(
        handoff_id,
        nonce=public["nonce"],
        prompt_sha256=public["prompt_sha256"],
        reference_asset_hashes=public["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    response = provider.generate(request)
    candidate = response.candidates[0]
    generation_result = _minimal_generation_result_with_candidate(
        candidate,
        job_id="job_doc223a_checkpoint",
    )
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="doc223 checkpoint"),
        status=ProductJobStatusValue.FINALIZING,
        job_id_value="job_doc223a_checkpoint",
        generation_result=generation_result,
    )
    service = V3ProductApiService(
        output_store=outputs,
        mcp_materialization_store=handoffs,
    )

    assert service._checkpoint_mcp_generation_result(record, generation_result) is None  # noqa: SLF001
    checkpointed = handoffs.get(handoff_id)
    assert checkpointed is not None
    assert checkpointed["status"] == "job_checkpointed"
    assert checkpointed["job_checkpoint"]["job_id"] == "job_doc223a_checkpoint"
    assert checkpointed["job_checkpoint"]["output_id"] == candidate.metadata["output_id"]


def test_mcp_pending_is_not_a_provider_retry_and_success_uses_shared_output_store(tmp_path: Path) -> None:
    request = _light_provider_request(metadata={"generation_channel": "mcp", "mcp_operation_id": "resume-op"})
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    with pytest.raises(ProviderRuntimeError) as caught:
        provider.generate(request)
    assert caught.value.detail["failure_code"] == "mcp_materialization_pending"
    assert provider._classify_provider_failure(caught.value) == "non_retryable_provider_failure"
    handoff_id = caught.value.detail["handoff_id"]
    handoff = handoffs.public_view(handoff_id)
    artifact = _png_bytes()
    handoffs.submit(
        handoff_id,
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=artifact,
    )
    response = provider.generate(request)
    assert len(response.candidates) == 1
    record = outputs.get_output(response.candidates[0].metadata["output_id"])
    assert record is not None
    assert record.metadata["generation_channel"] == "mcp"
    assert record.provider == "codex_builtin_imagegen"
    assert record.metadata["provider_prompt_sha256"] == handoff["prompt_sha256"]


def test_mcp_tools_expose_explicit_handoff_without_web_credentials() -> None:
    names = [tool["name"] for tool in TOOL_SCHEMAS]
    assert names[:2] == ["prepare_shared_mcp_materialization", "submit_shared_mcp_materialization"]
    submit = TOOL_SCHEMAS[1]["inputSchema"]
    assert "api_key" not in submit["properties"]
    assert "cookie" not in submit["properties"]
    assert "provider_id" not in submit["properties"]


def test_character_card_frontend_exposes_channel_switch_without_creating_a_second_flow() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "src_skeleton" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="v3CharacterCardGenerationChannelInput"' in html
    assert 'value="provider"' in html and 'value="mcp"' in html
    assert "generation_channel" in javascript
    assert "mcp_materialization" not in javascript
