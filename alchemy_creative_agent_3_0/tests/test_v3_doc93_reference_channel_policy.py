import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain.fallback import _fallback_human_variation_contract
from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore, V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import (
    VISUAL_AUTO_RETRY_RETRYABLE_ISSUES,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    ReferenceChannelPolicyModule,
    StrongReferenceBinding,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    _inspection_reference_data_urls,
)


ANCIENT_PORTRAIT_PROMPT = (
    "Use the uploaded woman as the same person. Create an ancient-style realistic portrait with black loose hair, "
    "a red forehead ornament, silver-white silk costume, cool cyan and silver lighting, dark pear-blossom background, "
    "close elevated camera angle, shallow depth of field, quiet melancholic cinematic film style."
)


def _portrait_binding(source_id: str = "uploaded_face_truth") -> StrongReferenceBinding:
    return StrongReferenceBinding(
        binding_id=f"binding_{source_id}",
        source_type="uploaded",
        source_id=source_id,
        asset_id=source_id,
        file_path=f"D:/AI/{source_id}.png",
        role="generated_identity_reference",
        strength="hard",
        use_policy="identity",
        lock_targets=["face_identity", "body_identity_direction", "natural_complexion_direction"],
        provider_input_required=True,
        confidence=0.9,
    )


def _cluster(user_input: str = ANCIENT_PORTRAIT_PROMPT, metadata: dict | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc93",
            scenario_id="general_creative",
            user_input=user_input,
            metadata={
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "selection_candidates",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc93",
                    "template_id": "general_template",
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "uploaded_face_truth",
                            "asset_id": "uploaded_face_truth",
                            "file_path": "D:/AI/uploaded_face_truth.png",
                            "source_type": "uploaded",
                            "role": "face_reference",
                            "use_policy": "identity",
                        }
                    ],
                },
                **(metadata or {}),
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    return result.results[-1].facts["visual_capability_cluster"]


def _request_from_cluster(cluster: dict, *, reference_file: str | None = None) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc93",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person ancient-style portrait",
    )
    metadata = {
        "job_id": "job_doc93_provider",
        "template_id": "general_template",
        "scenario_id": "general_creative",
        "user_input": ANCIENT_PORTRAIT_PROMPT,
        "visual_cluster": cluster,
        "role_specific_generation_plan": cluster["role_specific_generation_plan"],
    }
    if reference_file:
        metadata["uploaded_assets"] = [
            {
                "asset_id": "uploaded_face_truth",
                "file_path": reference_file,
                "source_type": "uploaded",
                "role": "face_reference",
                "use_policy": "identity",
                "strength": "hard",
            }
        ]
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc93",
            asset_id=asset.asset_id,
            visual_prompt=ANCIENT_PORTRAIT_PROMPT,
            negative_prompt="different person, copied source lighting, copied source outfit",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["cool ancient-style cinematic portrait"],
            layout_notes=["vertical portrait"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc93", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc93",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata=metadata,
    )


def test_doc93_ordinary_portrait_keeps_identity_but_prompt_owns_ancient_styling() -> None:
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc93",
        job_id="job_doc93",
        user_input=ANCIENT_PORTRAIT_PROMPT,
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding()],
        advanced_reference_controls={"preserve_person_identity": True},
    )
    policy = package.policies[0]

    assert policy.identity_geometry == "hard"
    assert policy.body_identity == "medium"
    assert policy.natural_complexion_direction == "medium"
    assert policy.hair_direction == "prompt_owned"
    assert policy.makeup_style == "prompt_owned"
    assert policy.wardrobe_structure == "prompt_owned"
    assert policy.lighting_color == "prompt_owned"
    assert policy.scene_background == "prompt_owned"
    assert policy.camera_composition == "prompt_owned"
    assert policy.style_finish == "prompt_owned"
    assert package.effective_channel_owners["identity_geometry"].startswith("reference:uploaded_face_truth:hard")
    assert package.effective_channel_owners["wardrobe_structure"] == "current_prompt"

    prompt_silent_package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc93",
        job_id="job_doc93_prompt_silent_hair",
        user_input="Keep the same person in a clean professional portrait.",
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding()],
        advanced_reference_controls={"preserve_person_identity": True},
    )
    assert prompt_silent_package.policies[0].hair_direction == "prompt_owned"


def test_doc93_explicit_same_outfit_locks_only_appearance_channels() -> None:
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc93",
        job_id="job_doc93_outfit",
        user_input="Keep the same outfit and accessories, but use new cool lighting and a different garden scene.",
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding()],
        advanced_reference_controls={"preserve_person_identity": True},
    )
    policy = package.policies[0]

    assert policy.wardrobe_structure == "hard"
    assert policy.accessory_system == "medium"
    assert policy.lighting_color == "prompt_owned"
    assert policy.scene_background == "prompt_owned"
    assert policy.identity_geometry == "hard"


def test_doc93_product_truth_does_not_own_source_scene_or_light() -> None:
    binding = StrongReferenceBinding(
        binding_id="binding_product",
        source_type="uploaded",
        source_id="uploaded_product_truth",
        asset_id="uploaded_product_truth",
        role="product_identity_reference",
        strength="hard",
        use_policy="product_identity",
        provider_input_required=True,
    )
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_product",
        job_id="job_product",
        user_input="Put the same product in a bright outdoor lifestyle scene with warm afternoon light.",
        subject_type="product",
        template_id="ecommerce_template",
        strong_bindings=[binding],
        advanced_reference_controls={"preserve_product_appearance": True},
    )
    policy = package.policies[0]

    assert policy.product_identity == "hard"
    assert policy.scene_background == "prompt_owned"
    assert policy.lighting_color == "prompt_owned"
    assert policy.identity_geometry == "off"


def test_doc93_uploaded_identity_beats_selected_output_and_new_prompt_beats_selected_style() -> None:
    selected = StrongReferenceBinding(
        binding_id="binding_selected",
        source_type="selected_output",
        source_id="selected_output_1",
        asset_id="selected_output_1",
        output_id="selected_output_1",
        role="generated_identity_reference",
        strength="medium",
        use_policy="identity",
        provider_input_required=True,
        metadata={"selected_output_anchor": True},
    )
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc93",
        job_id="job_doc93_selected",
        user_input="Keep the same person but use a new silver costume, cool cyan light, and a dark blossom scene.",
        subject_type="character",
        template_id="general_template",
        strong_bindings=[selected, _portrait_binding()],
        selected_outputs=[{"output_id": "selected_output_1"}],
        advanced_reference_controls={"preserve_person_identity": True},
    )

    assert package.effective_channel_owners["identity_geometry"].startswith("reference:uploaded_face_truth:hard")
    assert package.effective_channel_owners["wardrobe_structure"] == "current_prompt"
    selected_policy = next(policy for policy in package.policies if policy.source_asset_id == "selected_output_1")
    assert selected_policy.wardrobe_structure == "prompt_owned"
    assert selected_policy.style_finish in {"medium", "prompt_owned"}


def test_doc93_cluster_and_provider_remove_coarse_hair_wardrobe_light_lock(tmp_path) -> None:
    from PIL import Image

    cluster = _cluster()
    package = cluster["resolved_reference_policy_package"]
    identity_lock = cluster["identity_lock_profiles"][0]
    reference_path = tmp_path / "uploaded_face_truth.png"
    Image.new("RGB", (64, 64), (220, 205, 195)).save(reference_path)
    provider = ProductionImageGenerationProvider()
    request = _request_from_cluster(cluster, reference_file=str(reference_path))
    reference_assets = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, reference_assets)  # noqa: SLF001
    final_prompt = provider._generation_prompt(request, reference_assets)  # noqa: SLF001
    truth_sources = asset_plan["provider_input_plan"]["reference_truth_package"]["sources"]

    assert "reference_channel_policy" in cluster["child_module_ids"]
    assert package["applies"] is True
    assert identity_lock["hair_lock"]["preserve"] is False
    assert identity_lock["wardrobe_lock"]["preserve"] is False
    assert identity_lock["appearance_structure_lock"] == {}
    assert truth_sources["uploaded_face_truth"]["truth_layers"] == ["portrait_identity_truth"]
    assert "Reference channel policy:" in final_prompt
    assert "Current prompt owns its explicit visual channels" in final_prompt
    assert "broad hair or wardrobe direction, and light" not in final_prompt
    assert "identity and style anchor" not in final_prompt
    assert "Do not copy the reference image's original lighting" in final_prompt


def test_doc93_identity_only_provider_input_is_deduplicated_focused_and_color_neutral(tmp_path) -> None:
    from PIL import Image

    first_path = tmp_path / "uploaded-face-a.png"
    second_path = tmp_path / "uploaded-face-b.png"
    Image.new("RGB", (256, 256), (20, 210, 45)).save(first_path)
    second_path.write_bytes(first_path.read_bytes())
    cluster = _cluster()
    request = _request_from_cluster(cluster, reference_file=str(first_path))
    request.metadata["uploaded_assets"].append(
        {
            "asset_id": "uploaded_face_duplicate",
            "file_path": str(second_path),
            "source_type": "uploaded",
            "role": "identity",
            "use_policy": "identity",
            "strength": "hard",
        }
    )
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    asset_plan = provider._asset_plan(request, references)  # noqa: SLF001
    provider_assets = asset_plan["assets"]
    input_plan = asset_plan["provider_input_plan"]

    assert len(references) == 1
    assert references[0]["metadata"]["doc93_content_role_deduplicated"] is True
    assert references[0]["metadata"]["deduplicated_source_asset_ids"] == ["uploaded_face_duplicate"]
    assert input_plan["reference_image_count"] == 2
    assert input_plan["suppressed_full_frame_identity_asset_ids"] == ["uploaded_face_truth"]
    assert input_plan["identity_evidence_scopes"] == ["feature_detail", "head_geometry"]
    assert input_plan["provider_reference_total_bytes"] <= 960_000
    assert len(provider_assets) == 2
    assert provider_assets[0]["derivative_kind"] == "portrait_identity_crop"
    assert provider_assets[1]["derivative_kind"] == "portrait_identity_geometry_crop"
    assert provider_assets[0]["identity_color_neutralized"] is True
    assert provider_assets[0]["identity_channel_isolation_profile"] == "prompt_owned_channel_isolation_v2"
    assert provider_assets[0]["identity_outer_context_neutralized"] is True
    assert provider_assets[0]["identity_background_neutralized"] is False
    assert provider_assets[0]["identity_context_reduced_by_tight_crop"] is True
    assert provider_assets[0]["identity_gateway_min_edge_px"] == 512
    assert provider_assets[0]["identity_evidence_scope"] == "feature_detail"
    assert provider_assets[1]["identity_evidence_scope"] == "head_geometry"
    assert provider_assets[0]["identity_color_retention"] == 0.90
    assert provider_assets[1]["identity_color_retention"] == 0.65
    assert provider_assets[0]["identity_evidence_group_id"] == "portrait_identity::uploaded_face_truth"
    assert provider_assets[1]["identity_evidence_group_id"] == "portrait_identity::uploaded_face_truth"
    assert provider_assets[0]["priority"] > provider_assets[1]["priority"]
    assert provider_assets[0]["provider_reference_bytes"] <= 480_000
    assert provider_assets[1]["provider_reference_bytes"] <= 480_000
    assert Path(provider_assets[0]["storage_path"]).read_bytes() != Path(
        provider_assets[1]["storage_path"]
    ).read_bytes()
    with Image.open(provider_assets[0]["storage_path"]).convert("RGB") as focused:
        assert min(focused.size) == 512
        corner = focused.getpixel((0, 0))
        red, green, blue = focused.getpixel((focused.width // 2, focused.height // 2))
    assert corner != (128, 128, 128)
    assert max(corner) - min(corner) <= 12
    assert 20 < max(red, green, blue) - min(red, green, blue) < 180

    prompt_with_evidence = provider._generation_prompt(  # noqa: SLF001
        request,
        references,
        asset_plan=asset_plan,
    )
    assert "complementary crops of one single uploaded person" in prompt_with_evidence
    assert "Primary operation: identity-preserving portrait edit" in prompt_with_evidence
    assert "Use the feature-detail crop for brow-eye" in prompt_with_evidence
    assert "Use the head-geometry crop for face width/length" in prompt_with_evidence
    assert prompt_with_evidence.index("Primary operation:") < prompt_with_evidence.index("Visual direction:")
    assert len(prompt_with_evidence) <= 15_000


def test_doc93_reference_conditioned_real_generation_defaults_to_live_review() -> None:
    service = V3ProductApiService()
    metadata = {
        "require_real_images": True,
        "project_context_snapshot": {
            "uploaded_reference_assets": [{"asset_id": "uploaded_face_truth"}],
            "resolved_reference_policy_package": {"applies": True},
        },
    }

    assert service._reference_conditioned_real_review_required(metadata, quality_mode="standard") is True  # noqa: SLF001
    assert service._reference_conditioned_real_review_required(metadata, quality_mode="strict") is True  # noqa: SLF001
    assert service._reference_conditioned_real_review_required(metadata, quality_mode="explore") is False  # noqa: SLF001
    assert service._reference_conditioned_real_review_required(  # noqa: SLF001
        {**metadata, "disable_real_vision_inspection": True},
        quality_mode="standard",
    ) is False
    assert service._reference_conditioned_real_review_required(  # noqa: SLF001
        {**metadata, "vision_inspection_mode": "metadata_only"},
        quality_mode="standard",
    ) is False


def test_doc93_channel_issue_codes_flow_through_review_and_retry() -> None:
    codes = [
        "source_hair_overinherited",
        "source_makeup_overinherited",
        "source_color_grade_overinherited",
        "source_camera_overinherited",
        "source_whole_style_overinherited",
        "prompt_owned_channel_ignored",
        "selected_anchor_overrode_current_prompt",
        "structured_appearance_lock_misapplied",
    ]
    assert set(codes).issubset(VISUAL_AUTO_RETRY_RETRYABLE_ISSUES)
    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc93",
            project_id="project_doc93",
            job_id="job_doc93",
            candidate_id="candidate_doc93",
            output_id="output_doc93",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": codes[:3]},
    )
    patch_text = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["identity_reinforcement"],
        ]
    )
    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(codes)  # noqa: SLF001
    api_text = " ".join(
        [
            *api_patch["prompt_additions"],
            *api_patch["negative_additions"],
            *api_patch["identity_reinforcement"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "Doc93 channel repair" in patch_text
    assert "Doc93 channel repair" in api_text
    assert "do not increase whole-image reference strength" in patch_text


def test_doc93_legacy_fallback_and_retry_do_not_restore_coarse_style_inheritance() -> None:
    anchor, _ = _fallback_human_variation_contract(
        request=SimpleNamespace(requested_image_count=2),
        variation_mode="selection_candidates",
        allow_product_language=False,
        human_subject_evidenced=True,
    )
    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc93_legacy",
            project_id="project_doc93",
            job_id="job_doc93_legacy",
            candidate_id="candidate_doc93_legacy",
            output_id="output_doc93_legacy",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": ["hair_or_outfit_drift", "camera_distance_drift"]},
    )
    retry_text = " ".join(
        [
            *report.retry_patch["identity_reinforcement"],
            *report.retry_patch["composition_repair"],
        ]
    )

    assert anchor["metadata"]["doc93_reference_channel_safe"] is True
    assert "same broad hair and styling direction" not in " ".join(anchor["locked_traits"])
    assert "current prompt owns hair, makeup, wardrobe" in " ".join(anchor["locked_traits"])
    assert "only when that exact channel is assigned" in retry_text
    assert "current prompt's requested camera distance" in retry_text
    assert "preserve broad hair direction and outfit category" not in retry_text


def test_doc93_real_review_receives_compressed_reference_evidence(tmp_path) -> None:
    from PIL import Image

    reference_path = tmp_path / "large-reference.png"
    Image.new("RGB", (1800, 1400), (205, 188, 172)).save(reference_path)
    metadata = {
        "user_input": ANCIENT_PORTRAIT_PROMPT,
        "project_context_snapshot": {
            "uploaded_reference_assets": [
                {
                    "asset_id": "uploaded_face_truth",
                    "file_path": str(reference_path),
                    "source_type": "uploaded",
                    "use_policy": "identity",
                }
            ],
            "resolved_reference_policy_package": {
                "applies": True,
                "package_id": "package_doc93",
                "effective_channel_owners": {
                    "identity_geometry": "reference:uploaded_face_truth:hard",
                    "wardrobe_structure": "current_prompt",
                },
            },
        },
    }
    data_urls = _inspection_reference_data_urls(metadata)
    prompt = _inspection_prompt(metadata)

    assert len(data_urls) == 1
    assert data_urls[0].startswith("data:image/jpeg;base64,")
    assert len(base64.b64decode(data_urls[0].split(",", 1)[1])) < reference_path.stat().st_size
    assert "Following images are reference truth/context images" in prompt
    assert "Resolved reference policy" in prompt


def test_doc93_project_context_persists_channel_policy(tmp_path) -> None:
    from PIL import Image

    product_service = V3ProductApiService(
        output_store=V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    )
    product_service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    handlers = V3ProductRouteHandlers(service=product_service)
    image = Image.new("RGB", (32, 32), (215, 205, 198))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    uploaded = handlers.post_uploads(
        {"filename": "portrait.png", "mime_type": "image/png", "size_bytes": len(buffer.getvalue()), "role": "face_reference"}
    )
    handlers.put_upload_content(uploaded["asset_id"], {"content_base64": encoded, "mime_type": "image/png"})
    handlers.post_upload_complete(uploaded["asset_id"])
    project = handlers.post_projects({"user_goal": ANCIENT_PORTRAIT_PROMPT})["project"]
    response = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": uploaded["asset_id"], "source_type": "uploaded", "use_policy": "identity"},
    )
    package = response["context"]["resolved_reference_policy_package"]

    assert package["applies"] is True
    assert package["policies"][0]["identity_geometry"] == "hard"
    assert package["policies"][0]["wardrobe_structure"] == "prompt_owned"
    assert response["context"]["metadata"]["reference_policy_package_id"] == package["package_id"]
