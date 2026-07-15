from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.creative_core import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationProvider,
    GenerationRequest,
    GenerationResponse,
    GenerationRouter,
)
from alchemy_creative_agent_3_0.app.schemas import CandidateResult, ProviderStrategy


class RecordingImageProvider(GenerationProvider):
    provider_name = "recording_image_provider"

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.requests: list[dict] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        snapshot = request.model_dump(mode="json")
        self.requests.append(snapshot)
        index = len(self.requests)
        output_path = self.output_dir / f"generated_{index}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (96, 96), color=(120 + index, 180, 210)).save(output_path)
        candidate = CandidateResult(
            candidate_id=f"candidate_doc73_{index}",
            asset_id=request.generation_plan.asset_id,
            file_path=str(output_path),
            uri=f"mock://doc73/{index}",
            provider=self.provider_name,
            prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
            condition_plan_id=request.condition_plan.condition_plan_id,
            is_mock=False,
            metadata={
                "output_id": f"v3_output_doc73_{index}",
                "mime_type": "image/png",
                "mode_role_recipe": request.metadata.get("mode_role_recipe", {}),
                "reference_asset_count": len(request.metadata.get("reference_assets") or []),
            },
        )
        return GenerationResponse(candidates=[candidate], provider_metadata={"provider_name": self.provider_name})


def test_doc73_first_output_becomes_identity_anchor_when_user_has_no_reference(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    result = brain.run_generation_loop(
        "Create a summer cool East Asian beauty portrait set for a social cover campaign. "
        "The same young woman has subtle green-highlighted dark hair, white summer styling, and seaside daylight.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "llm_brain": {
                "visual_task_profile": {
                    "subject_entities": [
                        {"entity_id": "portrait_subject_1", "entity_type": "person", "confidence": 0.98}
                    ]
                }
            },
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is True
    assert first_metadata.get("reference_assets") == []
    assert second_metadata["auto_batch_identity_anchor_applied"] is True
    assert second_metadata["reference_assets"][0]["source_type"] == "generated_first_output"
    assert second_metadata["reference_assets"][0]["use_policy"] == "identity"
    assert second_metadata["reference_assets"][0]["strength"] == "hard"
    assert second_metadata["reference_assets"][0]["file_path"] == provider.requests[0]["metadata"].get(
        "auto_batch_identity_anchor_source_file_path",
        str(tmp_path / "outputs" / "generated_1.png"),
    )
    assert "eye shape and spacing" in second_metadata["reference_assets"][0]["lock_targets"]
    assert result.metadata["candidate_loop"] is True


def test_doc73_user_selected_reference_has_priority_over_auto_first_output(tmp_path) -> None:
    selected_reference = tmp_path / "selected_reference.png"
    Image.new("RGB", (96, 96), color=(220, 200, 180)).save(selected_reference)
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Create a summer cool East Asian beauty portrait set for a social cover campaign. "
        "Keep the same young woman but vary expression and crop.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "reference_assets": [
                {
                    "asset_id": "user_selected_identity_ref",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "role": "identity_anchor",
                    "strength": "hard",
                    "file_path": str(selected_reference),
                }
            ],
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert first_metadata["auto_batch_identity_anchor_policy"]["explicit_references_present"] is True
    assert second_metadata.get("auto_batch_identity_anchor_applied") is not True
    assert len(second_metadata["reference_assets"]) == 1
    assert second_metadata["reference_assets"][0]["asset_id"] == "user_selected_identity_ref"
    assert second_metadata["reference_assets"][0]["file_path"] == str(selected_reference)


def test_doc134_raw_person_or_cartoon_words_do_not_start_an_identity_chain_without_brain_evidence(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Photograph the same young woman wearing a real blue dress with a cartoon print.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
        },
    )

    assert len(provider.requests) >= 2
    assert provider.requests[0]["metadata"]["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert provider.requests[1]["metadata"].get("auto_batch_identity_anchor_applied") is not True


def test_doc73_product_profile_does_not_turn_a_no_reference_set_into_an_edit_chain(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Create a clean glass product model still-life set with three translucent spheres on a neutral surface.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "llm_brain": {
                "visual_task_profile": {
                    "subject_entities": [
                        {"entity_id": "product_1", "entity_type": "product", "confidence": 0.95}
                    ]
                }
            },
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert second_metadata.get("auto_batch_identity_anchor_applied") is not True
    assert not any(
        item.get("source_type") == "generated_first_output"
        for item in second_metadata.get("reference_assets", [])
    )
