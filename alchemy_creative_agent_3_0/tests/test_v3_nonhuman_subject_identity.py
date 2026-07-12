from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest, GenerateJobRequest, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    build_task_profile_and_intent,
    general_capability_policy,
)
from app.config import settings
from app.providers.base import ProviderCapabilityMismatchError
from app.providers.openai_image import OpenAIGPTImageProvider


def _reference_image(path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (48, 36), color=(79, 106, 132)).save(path)
    return path


def _generation_request(reference_path: Path) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_nonhuman_identity",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:2",
        purpose="reference-conditioned subject image",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_nonhuman_identity",
            asset_id=asset.asset_id,
            visual_prompt="Create a low-angle blue-hour scene with a new habitat and clear subject separation.",
            negative_prompt="generic replacement subject, copied source frame",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_nonhuman_identity", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_nonhuman_identity",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_nonhuman_identity",
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "uploaded_assets": [
                {
                    "asset_id": "v3_asset_nonhuman_identity",
                    "role": "nonhuman_identity_reference",
                    "use_policy": "nonhuman_subject_identity",
                    "filename": reference_path.name,
                    "mime_type": "image/png",
                    "file_path": str(reference_path),
                }
            ],
            "capability_activation_plan": {
                "activation_mode": "enforced",
                "dependency_order": ["nonhuman_subject_identity"],
            },
        },
    )


@pytest.mark.parametrize(
    "user_input",
    [
        "Place the same individual in a windswept shoreline at blue hour with a low camera angle.",
        "Show the same individual moving through a misty forest at dawn with a long lens.",
        "Create a clean architectural-studio portrait of the same individual with directional side light.",
    ],
)
def test_typed_nonhuman_identity_evidence_activates_scene_neutral_shared_capability(user_input: str) -> None:
    profile, intent = build_task_profile_and_intent(
        user_input=user_input,
        job_id="job_nonhuman_activation",
        project_id="project_nonhuman_activation",
        template_id="general_template",
        scenario_id="general_creative",
        uploaded_assets=[{"asset_id": "v3_asset_nonhuman_identity", "role": "nonhuman_identity_reference"}],
        reference_assets=[],
        product_profile={},
        metadata={},
        template_policy=general_capability_policy(),
    )

    requested = {item.capability_id: item for item in intent.requested_capabilities}
    preservation = next(item for item in profile.preservation_targets if item.target_type == "nonhuman_subject_identity")

    assert requested["nonhuman_subject_identity"].requested_profile == "reference_truth"
    assert requested["nonhuman_subject_identity"].confidence == 0.95
    assert "portrait_identity" not in requested
    assert "human_realism" not in requested
    assert preservation.allowed_changes == ["habitat", "action", "camera", "lighting", "color", "finish"]


def test_runtime_freezes_nonhuman_plan_and_composes_native_reference_requirement(tmp_path) -> None:
    reference = _reference_image(tmp_path / "individual.png")
    runtime = ScenarioRuntime()

    result = runtime.plan_job(
        {
            "user_input": "Create a fresh habitat and a new camera angle while preserving the individual reference subject.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "v3_asset_nonhuman_identity",
                    "role": "nonhuman_identity_reference",
                    "file_path": str(reference),
                    "filename": reference.name,
                    "mime_type": "image/png",
                }
            ],
            "metadata": {"template_id": "general_template"},
        }
    )

    plan = result.metadata["capability_activation_plan"]
    cluster = result.metadata["shared_capabilities"]["visual_cluster"]
    composed = cluster["composed_visual_contribution"]

    assert "nonhuman_subject_identity" in plan["dependency_order"]
    assert "portrait_identity" not in plan["dependency_order"]
    assert "nonhuman_subject_identity" in composed["active_capability_ids"]
    assert composed["provider_input_requirements"] == [
        {"requirement": "native_nonhuman_identity_reference", "input_fidelity": "high", "on_unsupported": "block"}
    ]


def test_provider_materializes_native_truth_without_source_style_inheritance(tmp_path, monkeypatch) -> None:
    request = _generation_request(_reference_image(tmp_path / "individual.png"))
    provider = ProductionImageGenerationProvider()
    monkeypatch.setattr(provider, "_select_provider", lambda _references: "openai_gpt_image")

    references = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, references)  # noqa: SLF001
    app_request, _provider_name, _references = provider._build_app_request(request)  # noqa: SLF001
    constraints = " ".join(
        value for item in asset_plan["assets"] for value in item.get("prompt_constraints", [])
    )

    assert references[0]["role"] == "nonhuman_identity_reference"
    assert provider._input_fidelity_for_asset_plan(asset_plan) == "high"  # noqa: SLF001
    assert provider._input_fidelity_is_required(asset_plan) is True  # noqa: SLF001
    assert app_request.prompt_plan.variables["input_fidelity_required"] is True
    assert any(
        item["truth_layer"] == "nonhuman_subject_identity_truth"
        for item in asset_plan["provider_input_plan"]["reference_truth_layers"]
    )
    assert "stable morphology" in constraints
    assert "whole-image style as an unrequested template" in constraints
    assert not any(item.get("derivative_kind") == "portrait_identity_crop" for item in asset_plan["assets"])


def test_missing_typed_reference_and_unsupported_high_fidelity_transport_block_without_text_fallback(tmp_path, monkeypatch) -> None:
    missing_request = _generation_request(tmp_path / "does-not-exist.png")
    production = ProductionImageGenerationProvider()
    with pytest.raises(ProviderCapabilityMismatchError, match="cannot fall back to text-only"):
        production._build_app_request(missing_request)  # noqa: SLF001

    transport = OpenAIGPTImageProvider(model="gpt-image-2")
    plan = SimpleNamespace(
        variables={"input_fidelity": "high", "input_fidelity_required": True},
        size="1024x1024",
        quality=None,
        output_format="png",
    )
    monkeypatch.setattr(settings, "openai_image_transport_profile", "square_b64_reference_edit")
    with pytest.raises(ProviderCapabilityMismatchError, match="requires native high-fidelity"):
        asyncio.run(transport._generate_one_with_references(None, "test", plan, [], index=0))  # noqa: SLF001


def test_nonhuman_review_ownership_uses_one_bounded_shared_retry_and_never_face_local_repair() -> None:
    service = V3ProductApiService()
    issue_codes = ["nonhuman_subject_identity_drift", "nonhuman_reference_used_as_style"]
    patch = service._visual_retry_patch_from_issues(issue_codes)  # noqa: SLF001

    assert service._review_issue_capability_owner("nonhuman_subject_marking_drift") == "nonhuman_subject_identity"  # noqa: SLF001
    assert "stable morphology" in " ".join(patch["identity_reinforcement"])
    assert "copied source habitat or lighting" in patch["negative_additions"]
    assert service._visual_auto_retry_max_attempts(GenerateJobRequest(quality_mode="strict")) == 2  # noqa: SLF001
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(
            user_input="Preserve the typed individual reference.",
            metadata={"capability_activation_plan": {"dependency_order": ["nonhuman_subject_identity"]}},
        ),
        status=ProductJobStatusValue.PLANNED,
        job_id_value="job_nonhuman_retry",
    )
    assert service._visual_auto_retry_limit_for_record(record, GenerateJobRequest(quality_mode="strict")) == 1  # noqa: SLF001
