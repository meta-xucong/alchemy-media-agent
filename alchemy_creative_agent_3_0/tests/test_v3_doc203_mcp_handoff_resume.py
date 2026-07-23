from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import (
    McpMaterializationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    LayoutPlan,
    LayoutRegion,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
    TextRenderingMode,
)


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 48), color=(224, 236, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _request_metadata(
    *,
    operation_id: str = "doc203-operation",
    materialization: dict | None = None,
) -> dict:
    metadata = {
        "mock_profile": "balanced",
        "requested_image_size": "1024x1536",
        "generation_channel": "mcp",
        "mcp_operation_id": operation_id,
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": "same character card portrait, clean reference-card framing",
                    "review_status": "approved",
                }
            ],
            "audit": {
                "remote_canonical_provider_prompts_received": True,
                "canonical_provider_prompt_stage": "provider_prompt_finalize",
            },
        },
    }
    if materialization is not None:
        metadata["mcp_materialization"] = materialization
    return metadata


def _minimal_request(*, metadata: dict | None = None):
    asset = AssetSpec(
        asset_id="asset_doc203",
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="2:3",
        purpose="character card validation image",
    )
    layout = LayoutPlan(
        layout_plan_id="layout_doc203",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.NO_TEXT,
        visual_hierarchy=["subject"],
        product_area=LayoutRegion(name="subject_area", position="center"),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc203",
        asset_id=asset.asset_id,
        visual_prompt="same character card portrait",
        negative_prompt="no watermark",
        text_policy="no_text",
        style_notes=[],
        layout_notes=[],
        provider_notes={},
    )
    condition = ConditionPlan(condition_plan_id="condition_doc203", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_doc203",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        candidate_count=1,
        max_refine_rounds=0,
        metadata=metadata or _request_metadata(),
    )
    return build_provider_generation_request(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt,
        condition_plan=condition,
        generation_plan=generation,
        job_id="job_doc203",
    )


def test_doc203_provider_request_preserves_explicit_mcp_materialization_handoff() -> None:
    explicit_handoff = {
        "handoff_id": "mcp_handoff_doc203_current",
        "status": "pending",
        "generation_channel": "mcp",
        "resume_required": True,
    }

    request = _minimal_request(
        metadata=_request_metadata(
            operation_id="doc203-explicit-operation",
            materialization=explicit_handoff,
        )
    )

    assert request.metadata["generation_channel"] == "mcp"
    assert request.metadata["mcp_operation_id"] == "doc203-explicit-operation"
    assert request.metadata["mcp_materialization"] == explicit_handoff


def test_doc203_mcp_provider_consumes_explicit_handoff_not_stale_same_operation(tmp_path: Path) -> None:
    operation_id = "doc203-same-operation"
    request = _minimal_request(metadata=_request_metadata(operation_id=operation_id))
    handoffs = McpMaterializationHandoffStore(tmp_path / "handoffs")
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = McpMaterializationProvider(output_store=outputs, handoff_store=handoffs)
    app_request, _provider_name, _references = provider._build_app_request(request)
    contract = app_request.prompt_plan.variables["mcp_materialization_context"]["rendering_contract"]

    stale_prompt = "stale submitted handoff"
    current_prompt = "current explicitly requested handoff"
    stale = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=stale_prompt,
        prompt_sha256=hashlib.sha256(stale_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    current = handoffs.ensure_pending(
        operation_id=operation_id,
        prompt=current_prompt,
        prompt_sha256=hashlib.sha256(current_prompt.encode()).hexdigest(),
        reference_assets=[],
        rendering_contract=contract,
    )
    for handoff in (stale, current):
        handoffs.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
        )

    explicit_request = _minimal_request(
        metadata=_request_metadata(
            operation_id=operation_id,
            materialization={
                "handoff_id": current["handoff_id"],
                "status": "pending",
                "generation_channel": "mcp",
                "resume_required": True,
            },
        )
    )

    response = provider.generate(explicit_request)

    record = outputs.get_output(response.candidates[0].metadata["output_id"])
    assert record is not None
    assert record.metadata["provider_raw_summary"]["mcp_handoff_id"] == current["handoff_id"]
    assert handoffs.get(current["handoff_id"])["status"] == "consumed"
    assert handoffs.get(stale["handoff_id"])["status"] == "submitted"
