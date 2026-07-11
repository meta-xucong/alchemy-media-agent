from pathlib import Path

from PIL import Image, ImageDraw

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
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
    ReferenceChannelPolicyModule,
    StrongReferenceBinding,
    reference_channel_retry_patch,
)
from app.services.provider_reference import prepare_reference_truth_derivatives


def _portrait_binding(path: Path) -> StrongReferenceBinding:
    return StrongReferenceBinding(
        binding_id="binding_doc103",
        source_type="uploaded",
        source_id="uploaded_doc103",
        asset_id="uploaded_doc103",
        file_path=str(path),
        role="face_reference",
        strength="hard",
        use_policy="identity",
        provider_input_required=True,
        confidence=0.95,
    )


def _policy(path: Path, prompt: str):
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc103",
        job_id="job_doc103",
        user_input=prompt,
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding(path)],
        advanced_reference_controls={"preserve_person_identity": True},
    )
    return package, package.policies[0]


def _colored_portrait(path: Path) -> Path:
    image = Image.new("RGB", (720, 720), (30, 180, 230))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 20, 640, 560), fill=(20, 180, 60))
    draw.ellipse((205, 95, 515, 610), fill=(222, 178, 155))
    draw.ellipse((275, 280, 315, 310), fill=(35, 28, 26))
    draw.ellipse((405, 280, 445, 310), fill=(35, 28, 26))
    draw.rectangle((326, 390, 394, 404), fill=(150, 65, 70))
    image.save(path)
    return path


def _channel_range(pixel: tuple[int, int, int]) -> int:
    return max(pixel) - min(pixel)


def test_prompt_owned_portrait_evidence_reduces_outer_color_without_flattening_face(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "portrait.png")
    package, policy = _policy(
        source,
        "Keep the same woman but use long natural black hair, neutral makeup, a white shirt, and a cool gray studio.",
    )

    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="uploaded_doc103",
        truth_layers=["portrait_identity_truth"],
        reference_policy=policy.model_dump(mode="json"),
    )

    assert package.effective_channel_owners["identity_geometry"].startswith("reference:")
    assert package.effective_channel_owners["hair_direction"] == "current_prompt"
    assert len(derivatives) == 2
    assert all(item["identity_channel_isolation_applied"] is True for item in derivatives)
    assert all(item["identity_channel_isolation_profile"] == "prompt_owned_channel_isolation_v1" for item in derivatives)
    assert all("hair_direction" in item["identity_prompt_owned_channels"] for item in derivatives)
    for item in derivatives:
        with Image.open(item["path"]).convert("RGB") as evidence:
            outer = evidence.getpixel((max(2, evidence.width // 18), max(2, evidence.height // 5)))
            center = evidence.getpixel((evidence.width // 2, int(evidence.height * 0.58)))
        assert _channel_range(outer) < _channel_range(center)
        assert item["identity_outer_context_softened"] is True
        assert item["identity_outer_color_retention"] <= 0.12


def test_explicit_same_hair_lock_preserves_assigned_hair_evidence(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "portrait.png")
    _, policy = _policy(source, "Keep the same person and preserve the exact same hair, but move her to a new studio.")

    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="uploaded_doc103",
        truth_layers=["portrait_identity_truth"],
        reference_policy=policy.model_dump(mode="json"),
    )

    assert policy.hair_direction == "medium"
    assert all(item["identity_channel_isolation_applied"] is False for item in derivatives)
    assert all(item["identity_channel_isolation_profile"] == "assigned_channel_preservation_v1" for item in derivatives)


def test_explicit_prompt_channels_compile_non_authoritative_reference_rules(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "portrait.png")
    package, _ = _policy(
        source,
        "Use the same woman with natural black hair, clean neutral makeup, a navy suit, window light, and a modern office.",
    )
    rules = " ".join(package.provider_prompt_rules)

    assert "Hair is current-prompt-owned" in rules
    assert "conflicting hair pixels" in rules
    assert "Makeup is current-prompt-owned" in rules
    assert "Wardrobe is current-prompt-owned" in rules
    assert "Lighting and color are current-prompt-owned" in rules
    assert "Scene and background are current-prompt-owned" in rules


def test_channel_retry_patch_repairs_only_reported_reference_channel() -> None:
    hair = reference_channel_retry_patch(["source_hair_overinherited"])
    scene = reference_channel_retry_patch(["source_scene_overinherited"])
    hair_text = " ".join([*hair["prompt_additions"], *hair["negative_additions"]])
    scene_text = " ".join([*scene["prompt_additions"], *scene["negative_additions"]])

    assert "hair color" in hair_text
    assert "source scene" not in hair_text
    assert "exact current prompt scene" in scene_text
    assert "source hair" not in scene_text


def test_common_photography_light_language_is_owned_by_current_prompt(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "portrait.png")
    package, policy = _policy(
        source,
        "Keep the same woman outdoors in natural-light open shade with a quiet park background.",
    )

    assert policy.lighting_color == "prompt_owned"
    assert "lighting_color" in package.prompt_ownership.explicit_channels
    assert any("Lighting and color are current-prompt-owned" in item for item in package.provider_prompt_rules)


def test_non_portrait_truth_derivatives_do_not_receive_identity_isolation(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "object.png")
    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="uploaded_object",
        truth_layers=["product_identity_truth"],
        reference_policy={"source_role": "product_identity_reference", "scene_background": "prompt_owned"},
    )

    assert len(derivatives) == 1
    assert derivatives[0]["derivative_kind"] == "product_truth_crop"
    assert derivatives[0]["identity_channel_isolation_applied"] is False


def test_provider_receives_isolated_identity_evidence_and_prompt_owned_rules(tmp_path) -> None:
    source = _colored_portrait(tmp_path / "portrait.png")
    prompt = "Keep the same woman with natural black hair, neutral makeup, a navy suit, and cool office window light."
    package, policy = _policy(source, prompt)
    asset = AssetSpec(
        asset_id="asset_doc103",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person modern editorial portrait",
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc103",
            asset_id=asset.asset_id,
            visual_prompt=prompt,
            negative_prompt="different person, copied source hair, copied source lighting",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["modern realistic editorial portrait"],
            layout_notes=["vertical portrait"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc103", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc103",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc103_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": prompt,
            "uploaded_assets": [
                {
                    "asset_id": "uploaded_doc103",
                    "file_path": str(source),
                    "source_type": "uploaded",
                    "role": "face_reference",
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "visual_cluster": {
                "resolved_reference_policy_package": package.model_dump(mode="json"),
                "role_specific_generation_plan": {"slots": []},
            },
            "role_specific_generation_plan": {"slots": []},
        },
    )
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, references)  # noqa: SLF001
    final_prompt = provider._generation_prompt(request, references)  # noqa: SLF001
    input_plan = asset_plan["provider_input_plan"]

    assert policy.identity_geometry == "hard"
    assert input_plan["reference_image_count"] == 2
    assert input_plan["suppressed_full_frame_identity_asset_ids"] == ["uploaded_doc103"]
    assert all(item["identity_channel_isolation_applied"] for item in asset_plan["assets"])
    assert all(item["identity_channel_isolation_profile"] == "prompt_owned_channel_isolation_v1" for item in asset_plan["assets"])
    assert all("hair_direction" in item["identity_prompt_owned_channels"] for item in asset_plan["assets"])
    assert "Hair is current-prompt-owned" in final_prompt
    assert "Lighting and color are current-prompt-owned" in final_prompt
