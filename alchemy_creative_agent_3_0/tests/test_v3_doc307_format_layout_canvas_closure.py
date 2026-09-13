"""Doc307 regression tests for General format-layout output closure."""

from __future__ import annotations

import json

import pytest

from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.creative_core.context import PipelineContext
from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import ModeAwareRoleDirector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GENERAL_FORMAT_LAYOUT_AXIS_RENDER_SPECS,
    VariationExecutionContract,
)
from app.providers.base import ProviderRuntimeError


def _format_contract(count: int = 4) -> VariationExecutionContract:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307",
        job_id="job_doc307",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=count,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    contract = director.build_variation_execution_contract(
        role_plan=role_plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    return contract


def _format_request(
    output_index: int,
    *,
    provider_size: str | None = None,
    enforced: bool = True,
) -> GenerationRequest:
    contract = _format_contract()
    binding = {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
    }
    asset = AssetSpec(
        asset_id=f"asset_doc307_{output_index}",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="one complete visual output",
        priority=output_index + 1,
    )
    generation_metadata = {
        "output_index": output_index,
        "requested_image_size": "1024x1536",
    }
    if enforced:
        generation_metadata["capability_execution_envelope"] = {
            "activation_plan": {
                "activation_mode": "enforced",
                "dependency_order": ["suite_direction"],
            },
            "resolved_constraint_ledger": {
                "provider_projection": {
                    "capability_projection": {
                        "variation_execution_contract": contract.model_dump(mode="json"),
                        "variation_execution_contract_binding": binding,
                    }
                }
            },
        }
    else:
        # This marker and binding are intentionally insufficient without the
        # execution envelope; Provider must not treat them as canvas authority.
        generation_metadata.update(
            {
                "variation_execution_contract_enforced": True,
                "variation_execution_contract_binding": binding,
            }
        )
    if provider_size:
        generation_metadata["provider_image_options"] = {"size": provider_size}
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id=f"prompt_doc307_{output_index}",
            asset_id=asset.asset_id,
            visual_prompt="same approved visual idea with a format adaptation",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(condition_plan_id=f"condition_doc307_{output_index}", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id=f"generation_doc307_{output_index}",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            metadata=generation_metadata,
        ),
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "visual_cluster": {
                "variation_execution_contract": contract.model_dump(mode="json"),
            },
        },
    )


def test_format_contract_preserves_physical_targets_as_neutral_axes() -> None:
    contract = _format_contract()

    assert [list(output.variation_axes)[0] for output in contract.outputs] == [
        "format_vertical",
        "format_square",
        "format_horizontal",
        "format_tight",
    ]
    assert all(
        list(output.variation_axes)[0] in GENERAL_FORMAT_LAYOUT_AXIS_RENDER_SPECS
        for output in contract.outputs
    )
    assert contract.contract_digest == contract.computed_digest()


def test_central_brain_applies_the_same_format_target_to_layout_planning() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307",
        job_id="job_doc307",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    context = PipelineContext(
        user_input="same visual idea with format adaptations",
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "variation_execution_contract": _format_contract(count=2).model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": _format_contract(count=2).contract_version,
                "contract_digest": _format_contract(count=2).contract_digest,
            },
            "shared_capabilities": {
                "visual_cluster": {
                    "role_specific_generation_plan": role_plan.model_dump(mode="json"),
                    "mode_execution_policy": role_plan.policy.model_dump(mode="json"),
                }
            },
        },
    )
    asset = AssetSpec(
        asset_id="asset_doc307_layout",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="one complete visual output",
    )

    vertical = CentralCreativeBrain()._asset_with_mode_role(context, asset, 0)  # noqa: SLF001
    square = CentralCreativeBrain()._asset_with_mode_role(context, asset, 1)  # noqa: SLF001

    assert vertical.aspect_ratio == "2:3"
    assert square.aspect_ratio == "1:1"


def test_central_brain_keeps_extended_format_roles_on_their_base_canvas() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307_extended",
        job_id="job_doc307_extended",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=5,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    context = PipelineContext(
        user_input="same visual idea with format adaptations",
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "variation_execution_contract": _format_contract(count=5).model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": _format_contract(count=5).contract_version,
                "contract_digest": _format_contract(count=5).contract_digest,
            },
            "shared_capabilities": {
                "visual_cluster": {
                    "role_specific_generation_plan": role_plan.model_dump(mode="json"),
                    "mode_execution_policy": role_plan.policy.model_dump(mode="json"),
                }
            },
        },
    )
    asset = AssetSpec(
        asset_id="asset_doc307_extended_layout",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="one complete visual output",
    )

    extended_vertical = CentralCreativeBrain()._asset_with_mode_role(context, asset, 4)  # noqa: SLF001

    assert extended_vertical.aspect_ratio == "2:3"


def test_central_brain_fails_closed_without_active_format_contract() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307_no_contract",
        job_id="job_doc307_no_contract",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    context = PipelineContext(
        user_input="same visual idea with format adaptations",
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "shared_capabilities": {
                "visual_cluster": {
                    "role_specific_generation_plan": role_plan.model_dump(mode="json"),
                }
            },
        },
    )
    asset = AssetSpec(
        asset_id="asset_doc307_no_contract",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="one complete visual output",
    )

    with pytest.raises(ValueError, match="execution contract is missing"):
        CentralCreativeBrain()._asset_with_mode_role(context, asset, 0)  # noqa: SLF001


def test_central_brain_fails_closed_for_explicit_single_format_mode_without_contract() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307_single_no_contract",
        job_id="job_doc307_single_no_contract",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=1,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    context = PipelineContext(
        user_input="same visual idea with format adaptations",
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "variation_mode_override": "format_layout_adaptation",
            "variation_mode_source": "manual",
            "shared_capabilities": {
                "visual_cluster": {
                    "role_specific_generation_plan": role_plan.model_dump(mode="json"),
                }
            },
        },
    )
    asset = AssetSpec(
        asset_id="asset_doc307_single_no_contract",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="one complete visual output",
    )

    with pytest.raises(ValueError, match="execution contract is missing"):
        CentralCreativeBrain()._asset_with_mode_role(context, asset, 0)  # noqa: SLF001


def test_non_format_general_modes_do_not_emit_format_axes() -> None:
    director = ModeAwareRoleDirector()

    for mode in ("selection_candidates", "delivery_suite", "creative_exploration"):
        role_plan = director.build(
            project_id="project_doc307_isolation",
            job_id=f"job_doc307_{mode}",
            user_input="same visual idea",
            mode=mode,
            requested_image_count=4,
            subject_type="character",
            scenario_id="general_creative",
            template_id="general_template",
            has_identity_anchor=False,
        )
        contract = director.build_variation_execution_contract(
            role_plan=role_plan,
            scenario_id="general_creative",
            template_id="general_template",
        )

        assert contract is not None
        assert not any(
            axis in GENERAL_FORMAT_LAYOUT_AXIS_RENDER_SPECS
            for output in contract.outputs
            for axis in output.variation_axes
        )


def test_provider_resolves_per_output_canvas_from_frozen_contract() -> None:
    provider = ProductionImageGenerationProvider()

    assert provider._size_for_request(_format_request(0)) == "1024x1536"  # noqa: SLF001
    assert provider._size_for_request(_format_request(1)) == "1024x1024"  # noqa: SLF001
    assert provider._size_for_request(_format_request(2)) == "1536x1024"  # noqa: SLF001
    # Tight framing is a crop duty, not an invented new canvas.
    assert provider._size_for_request(_format_request(3)) == "1024x1536"  # noqa: SLF001


def test_explicit_provider_size_remains_a_transport_override() -> None:
    provider = ProductionImageGenerationProvider()

    assert provider._size_for_request(_format_request(1, provider_size="2048x1152")) == "2048x1152"  # noqa: SLF001


def test_reference_edit_transport_cannot_replace_format_canvas_with_square(monkeypatch) -> None:
    from app.providers.openai_image import OpenAIGPTImageProvider

    monkeypatch.setattr(
        OpenAIGPTImageProvider,
        "_uses_square_b64_transport",
        lambda self, *, image_edit=False: bool(image_edit),
    )
    provider = ProductionImageGenerationProvider()

    size, adaptation = provider._resolve_provider_size(  # noqa: SLF001
        _format_request(0),
        [{"asset_id": "reference_doc307", "file_path": "memory://reference"}],
    )

    assert size == "1024x1536"
    assert adaptation == {}


def test_bare_raw_cluster_contract_cannot_create_a_provider_canvas_authority() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1, enforced=False)

    assert provider._size_for_request(request) == "1024x1536"  # noqa: SLF001


def test_provider_rejects_missing_output_index_in_active_format_contract() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1)
    request.generation_plan.metadata.pop("output_index")

    with pytest.raises(ProviderRuntimeError, match="output index is unavailable"):
        provider._size_for_request(request)  # noqa: SLF001


def test_provider_rejects_missing_active_format_contract() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1)
    request.generation_plan.metadata.update(
        {
            "requested_image_count": 4,
            "variation_execution_mode": "format_layout_adaptation",
        }
    )
    projection = request.generation_plan.metadata["capability_execution_envelope"][
        "resolved_constraint_ledger"
    ]["provider_projection"]["capability_projection"]
    projection.pop("variation_execution_contract")
    projection.pop("variation_execution_contract_binding")

    with pytest.raises(ProviderRuntimeError, match="execution contract is missing"):
        provider._size_for_request(request)  # noqa: SLF001


def test_provider_rejects_missing_contract_for_explicit_single_format_mode() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(0)
    request.generation_plan.metadata["variation_execution_mode"] = "format_layout_adaptation"
    request.generation_plan.metadata["requested_image_count"] = 1
    projection = request.generation_plan.metadata["capability_execution_envelope"][
        "resolved_constraint_ledger"
    ]["provider_projection"]["capability_projection"]
    projection.pop("variation_execution_contract")
    projection.pop("variation_execution_contract_binding")

    with pytest.raises(ProviderRuntimeError, match="execution contract is missing"):
        provider._size_for_request(request)  # noqa: SLF001


def test_provider_rejects_partial_or_ambiguous_active_format_contract() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1)
    contract = _format_contract()
    outputs = list(contract.outputs)
    outputs[1] = outputs[1].model_copy(update={"variation_axes": ("layout",)})
    invalid = VariationExecutionContract(
        contract_version=contract.contract_version,
        mode=contract.mode,
        requested_image_count=contract.requested_image_count,
        preserve_subject=contract.preserve_subject,
        preserve_style=contract.preserve_style,
        outputs=tuple(outputs),
    ).bind_digest()
    projection = request.generation_plan.metadata["capability_execution_envelope"][
        "resolved_constraint_ledger"
    ]["provider_projection"]["capability_projection"]
    projection["variation_execution_contract"] = invalid.model_dump(mode="json")
    projection["variation_execution_contract_binding"] = {
        "contract_version": invalid.contract_version,
        "contract_digest": invalid.contract_digest,
    }

    with pytest.raises(ProviderRuntimeError, match="cannot authorize a physical canvas"):
        provider._size_for_request(request)  # noqa: SLF001


def test_provider_rejects_two_physical_targets_in_one_active_format_row() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1)
    contract = _format_contract()
    outputs = list(contract.outputs)
    outputs[0] = outputs[0].model_copy(
        update={"variation_axes": ("format_vertical", "format_square")}
    )
    invalid = VariationExecutionContract(
        contract_version=contract.contract_version,
        mode=contract.mode,
        requested_image_count=contract.requested_image_count,
        preserve_subject=contract.preserve_subject,
        preserve_style=contract.preserve_style,
        outputs=tuple(outputs),
    ).bind_digest()
    projection = request.generation_plan.metadata["capability_execution_envelope"][
        "resolved_constraint_ledger"
    ]["provider_projection"]["capability_projection"]
    projection["variation_execution_contract"] = invalid.model_dump(mode="json")
    projection["variation_execution_contract_binding"] = {
        "contract_version": invalid.contract_version,
        "contract_digest": invalid.contract_digest,
    }

    with pytest.raises(ProviderRuntimeError, match="cannot authorize a physical canvas"):
        provider._size_for_request(request)  # noqa: SLF001


def test_historical_format_contract_without_physical_axes_keeps_job_canvas() -> None:
    provider = ProductionImageGenerationProvider()
    request = _format_request(1)
    contract = _format_contract()
    generic_axes = ("layout", "framing", "placement", "detail")
    historical_outputs = tuple(
        output.model_copy(update={"variation_axes": (generic_axes[index],)})
        for index, output in enumerate(contract.outputs)
    )
    historical = VariationExecutionContract(
        contract_version=contract.contract_version,
        mode=contract.mode,
        requested_image_count=contract.requested_image_count,
        preserve_subject=contract.preserve_subject,
        preserve_style=contract.preserve_style,
        outputs=historical_outputs,
    ).bind_digest()
    projection = request.generation_plan.metadata["capability_execution_envelope"][
        "resolved_constraint_ledger"
    ]["provider_projection"]["capability_projection"]
    projection["variation_execution_contract"] = historical.model_dump(mode="json")
    projection["variation_execution_contract_binding"] = {
        "contract_version": historical.contract_version,
        "contract_digest": historical.contract_digest,
    }

    assert provider._size_for_request(request) == "1024x1536"  # noqa: SLF001


def test_review_verifies_nested_provider_metadata_and_actual_pixels() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc307_review",
        job_id="job_doc307_review",
        user_input="same visual idea with format adaptations",
        mode="format_layout_adaptation",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    contract = _format_contract(count=2)
    binding = {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
    }
    candidates = [
        {
            "mode_role_key": role_plan.role_recipes[index].role_key,
            "metadata": {
                "output_index": index + 1,
                "width": 1024,
                "height": 1536 if index == 0 else 1024,
                "general_format_layout": {
                    "target": "vertical" if index == 0 else "square",
                    "aspect_ratio": "2:3" if index == 0 else "1:1",
                    "size": "1024x1536" if index == 0 else "1024x1024",
                    "requested_size": "1024x1536" if index == 0 else "1024x1024",
                    "frozen_job_size": "1024x1536",
                    "size_source": "format_layout_contract",
                },
            },
        }
        for index in range(2)
    ]

    review = director.review(
        project_id="project_doc307_review",
        job_id="job_doc307_review",
        role_plan=role_plan,
        generated_candidates=candidates,
        variation_execution_contract=contract,
        variation_execution_contract_binding=binding,
        validate_rendered_canvas=True,
    )

    assert review.status == "pass"
    assert not review.issue_codes
    assert len(review.metadata["format_canvas_review"]) == 2

    candidates[1]["metadata"]["height"] = 1536
    rejected = director.review(
        project_id="project_doc307_review",
        job_id="job_doc307_review_retry",
        role_plan=role_plan,
        generated_candidates=candidates,
        variation_execution_contract=contract,
        variation_execution_contract_binding=binding,
        validate_rendered_canvas=True,
    )

    assert rejected.status == "retry_recommended"
    assert "format_layout_pixel_dimensions_mismatch" in rejected.issue_codes


def test_brain_payload_explains_format_axes_without_exposing_role_recipes() -> None:
    contract = _format_contract(count=2)
    binding = {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
    }
    payload = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="Create two format adaptations of the same visual idea.",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=2,
                metadata={
                    "require_real_images": True,
                    "variation_execution_contract_enforced": True,
                    "variation_execution_contract_binding": binding,
                },
                shared_capabilities={
                    "visual_cluster": {
                        "variation_execution_contract": contract.model_dump(mode="json"),
                    }
                },
            )
        )
    )

    instruction = payload["variation_execution_contract_instructions"]
    assert "format_vertical" in instruction
    assert "format_square" in instruction
    assert "2:3" in instruction and "1:1" in instruction
    assert "role_key" not in json.dumps(payload, ensure_ascii=True)
    assert "crop_rule" not in json.dumps(payload, ensure_ascii=True)


def test_brain_finalizer_contract_requires_format_axis_meaning_and_receipt() -> None:
    contract = _format_contract(count=2)
    binding = {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
    }
    context = {
        "variation_execution_contract": contract.model_dump(mode="json"),
        "variation_execution_contract_required": True,
        "variation_execution_semantic_evidence_required": True,
        "frozen_binding": {"variation_execution_contract": binding},
    }
    payload = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="Create two format adaptations of the same visual idea.",
                stage="provider_prompt_finalize",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=2,
                metadata={"canonical_prompt_context": context},
            )
        )
    )

    contract_text = payload["remote_response_contract"]
    receipt_schema = payload["return_schema"]["canonical_provider_prompts"][0]["variation_execution_receipt"]
    assert "format_vertical" in contract_text and "format_square" in contract_text
    assert "semantic_output_purpose" in receipt_schema
    assert "semantic_variation_axes" in receipt_schema
