import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import ReferenceInputAdmissionError
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
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
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioSelection
from alchemy_creative_agent_3_0.app.shared_capabilities import (
    AssetBindingPlanner,
    AssetRole,
    CapabilityInput,
    UploadedAssetInfo,
)


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (96, 72), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    path.write_bytes(_png_bytes(color))
    return path


def _reference(
    *,
    asset_id: str,
    role: str,
    path: Path,
) -> dict[str, object]:
    metadata = {
        "provider_input_required": True,
        "codex_native_reference_channel": (
            "product_truth" if role == "product_reference" else "portrait_identity"
        ),
    }
    return {
        "asset_id": asset_id,
        "role": role,
        "file_path": str(path),
        "filename": path.name,
        "mime_type": "image/png",
        "provider_input_required": True,
        "metadata": metadata,
    }


def _template_plan(
    *,
    selected_product_ids: list[str] | None,
    pool_product_ids: list[str],
) -> dict[str, object]:
    deliverable_metadata: dict[str, object] = {
        "product_truth_pool_asset_ids": list(pool_product_ids),
    }
    if selected_product_ids is not None:
        deliverable_metadata.update(
            {
                "product_truth_selection_role": "lifestyle_primary_product_view",
                "selected_product_truth_asset_ids": list(selected_product_ids),
                "admitted_product_truth_asset_ids": list(selected_product_ids),
                "max_product_truth_source_refs_per_output": 2,
                "product_truth_selection_source": (
                    "remote_brain_image_set_plan.evidence_dimensions_by_output"
                ),
            }
        )
    return {
        "plan_id": "template_plan_ecommerce_truth_scope",
        "template_id": "ecommerce_template",
        "scenario_id": "ecommerce",
        "owner": "ecommerce_scenario_pack",
        "creative_direction_owner": "remote_v3_llm_brain",
        "requested_image_count": 1,
        "effective_image_count": 1,
        "deliverables": [
            {
                "deliverable_id": "deliverable_1",
                "output_index": 1,
                "image_intent": "show the product faithfully",
                "source": "remote_v3_llm_brain",
                "factual_acceptance": ["product_truth"],
                "metadata": deliverable_metadata,
            }
        ],
        "provenance": [],
    }


def _generation_request(
    *,
    references: list[dict[str, object]],
    selected_product_ids: list[str] | None,
    pool_product_ids: list[str],
) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_ecommerce_truth_scope",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="1:1",
        purpose="professional ecommerce product image",
        priority=1,
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_ecommerce_truth_scope",
            asset_id=asset.asset_id,
            visual_prompt="professional product image",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(
            condition_plan_id="condition_ecommerce_truth_scope",
            asset_id=asset.asset_id,
        ),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_ecommerce_truth_scope",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "uploaded_assets": references,
            "professional_product_truth_required": True,
            "professional_ecommerce_product_truth_pool_asset_ids": list(pool_product_ids),
            "template_deliverable_plan": _template_plan(
                selected_product_ids=selected_product_ids,
                pool_product_ids=pool_product_ids,
            ),
        },
    )


def test_professional_ecommerce_truth_pool_suppresses_only_product_role_conflict(tmp_path) -> None:
    product_a = _image(tmp_path / "product-a.png", (220, 70, 70))
    product_b = _image(tmp_path / "product-b.png", (70, 160, 220))
    face = _image(tmp_path / "face.png", (200, 170, 150))
    planner = AssetBindingPlanner()

    result = planner.execute(
        CapabilityInput(
            job_id="job_ecommerce_truth_pool",
            scenario_id="ecommerce",
            user_input="Create a professional ecommerce product image.",
            uploaded_assets=[
                UploadedAssetInfo(
                    asset_id="product_a",
                    role=AssetRole.PRODUCT_REFERENCE,
                    file_path=str(product_a),
                    filename=product_a.name,
                ),
                UploadedAssetInfo(
                    asset_id="product_b",
                    role=AssetRole.PRODUCT_REFERENCE,
                    file_path=str(product_b),
                    filename=product_b.name,
                ),
                UploadedAssetInfo(
                    asset_id="face_reference",
                    role=AssetRole.FACE_REFERENCE,
                    file_path=str(face),
                    filename=face.name,
                ),
            ],
            metadata={
                "professional_product_truth_required": True,
                "professional_ecommerce_product_truth_pool_asset_ids": ["product_a", "product_b"],
            },
        )
    )

    assert not any(
        warning.code == "asset_binding_role_conflict"
        and warning.metadata.get("asset_ids") == ["product_a", "product_b"]
        for warning in result.warnings
    )


def test_provider_emits_selected_product_truth_and_preserves_non_product_references(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    product_c = _reference(
        asset_id="product_c",
        role="product_reference",
        path=_image(tmp_path / "product-c.png", (80, 210, 110)),
    )
    face = _reference(
        asset_id="face_reference",
        role="face_reference",
        path=_image(tmp_path / "face.png", (200, 170, 150)),
    )
    request = _generation_request(
        references=[product_a, product_b, product_c, face],
        selected_product_ids=["product_b"],
        pool_product_ids=["product_a", "product_b", "product_c"],
    )

    assets = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == ["product_b", "face_reference"]
    assert request.metadata["professional_ecommerce_product_truth_projection"] == {
        "output_index": 1,
        "selected_product_truth_asset_ids": ["product_b"],
        "suppressed_product_truth_asset_ids": ["product_a", "product_c"],
    }


def test_mcp_provider_uses_the_same_professional_ecommerce_truth_scope(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    face = _reference(
        asset_id="face_reference",
        role="face_reference",
        path=_image(tmp_path / "face.png", (200, 170, 150)),
    )
    request = _generation_request(
        references=[product_a, product_b, face],
        selected_product_ids=["product_a"],
        pool_product_ids=["product_a", "product_b"],
    )

    assets = McpMaterializationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == ["product_a", "face_reference"]


def test_professional_ecommerce_truth_scope_fails_closed_without_frozen_selection(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    request = _generation_request(
        references=[product_a, product_b],
        selected_product_ids=None,
        pool_product_ids=["product_a", "product_b"],
    )

    with pytest.raises(ReferenceInputAdmissionError, match="selection"):
        ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001


def test_product_truth_scope_keeps_five_image_cap_after_selection(tmp_path) -> None:
    products = [
        _reference(
            asset_id=f"product_{index}",
            role="product_reference",
            path=_image(tmp_path / f"product-{index}.png", (120 + index, 80, 150)),
        )
        for index in range(3)
    ]
    faces = [
        _reference(
            asset_id=f"face_{index}",
            role="face_reference",
            path=_image(tmp_path / f"face-{index}.png", (190, 150 + index, 130)),
        )
        for index in range(5)
    ]
    request = _generation_request(
        references=[*products, *faces],
        selected_product_ids=["product_1"],
        pool_product_ids=["product_0", "product_1", "product_2"],
    )

    with pytest.raises(ReferenceInputAdmissionError, match="cannot accept all declared"):
        ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert request.metadata["provider_reference_resolution_audit"]["capacity_exceeded"] == {
        "reference_count": 6,
        "maximum_reference_images": 5,
    }


def test_product_api_issues_product_truth_pool_only_for_trusted_professional_binding(tmp_path) -> None:
    service = V3ProductApiService()
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_ids = []
    for index in range(2):
        upload = service.create_uploaded_asset(
            {
                "filename": f"product-{index}.png",
                "mime_type": "image/png",
                "size_bytes": len(_png_bytes((120 + index, 80, 150))),
                "role": "product_reference",
            }
        )
        service.store_uploaded_asset_content(
            upload.asset_id,
            {
                "content_base64": base64.b64encode(_png_bytes((120 + index, 80, 150))).decode(
                    "ascii"
                ),
                "mime_type": "image/png",
            },
        )
        service.complete_uploaded_asset(upload.asset_id)
        asset_ids.append(upload.asset_id)

    request = CreateCreativeJobRequest(
        user_input="Create a professional ecommerce product image.",
        scenario_selection=ScenarioSelection(scenario_id="ecommerce"),
        uploaded_asset_ids=asset_ids,
        metadata={
            "template_id": "ecommerce_template",
            "frozen_visual_asset_binding_set": {"state": "empty"},
        },
    )
    service._prepare_ecommerce_creative_context(request)  # noqa: SLF001

    assert request.metadata["professional_product_truth_required"] is True
    assert request.metadata["professional_ecommerce_product_truth_pool_asset_ids"] == asset_ids
    assert request.metadata["ecommerce_creative_context"]["provider_reference_budget"] == {
        "max_product_truth_source_refs_per_output": 2
    }


def test_public_product_truth_scope_marker_cannot_be_forged() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Create an ecommerce product image.",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {"professional_product_truth_required": True},
            }
        )


def test_central_planning_preserves_product_truth_scope_for_provider_materialization() -> None:
    result = CentralCreativeBrain().run_creative_planning(
        user_input="Create a professional ecommerce product image.",
        optional_template_id="ecommerce_template",
        runtime_metadata=_central_ecommerce_product_truth_metadata(),
    )

    metadata = result.generation_plans[0].metadata

    _assert_central_generation_metadata_preserves_product_truth_scope(metadata)


def test_central_generation_loop_preserves_product_truth_scope_for_provider_materialization() -> None:
    result = CentralCreativeBrain().run_generation_loop(
        user_input="Create a professional ecommerce product image.",
        optional_template_id="ecommerce_template",
        runtime_metadata=_central_ecommerce_product_truth_metadata(),
    )

    metadata = result.generation_plans[0].metadata

    _assert_central_generation_metadata_preserves_product_truth_scope(metadata)


def _central_ecommerce_product_truth_metadata() -> dict[str, object]:
    return {
        "scenario_id": "ecommerce",
        "template_id": "ecommerce_template",
        "requested_image_count": 1,
        "uploaded_assets": [
            {
                "asset_id": "product_a",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
            {
                "asset_id": "product_b",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
        ],
        "reference_assets": [],
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "image_set_plan": {
                "image_count": 1,
                "shot_plan": ["show the product faithfully"],
            },
        },
        "ecommerce_creative_context": {
            "provider_reference_budget": {
                "max_product_truth_source_refs_per_output": 2
            }
        },
        "professional_product_truth_required": True,
        "professional_ecommerce_product_truth_pool_asset_ids": ["product_a", "product_b"],
    }


def _assert_central_generation_metadata_preserves_product_truth_scope(metadata: dict[str, object]) -> None:
    assert metadata["professional_product_truth_required"] is True
    assert metadata["professional_ecommerce_product_truth_pool_asset_ids"] == [
        "product_a",
        "product_b",
    ]
    assert metadata["ecommerce_creative_context"]["provider_reference_budget"] == {
        "max_product_truth_source_refs_per_output": 2
    }
