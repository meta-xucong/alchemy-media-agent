from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.shared_capabilities import (
    AssetRole,
    CapabilityInput,
    CapabilityRunStatus,
    CapabilityStatus,
    SharedCapabilityRegistry,
    UploadedAssetInfo,
)


def _image(path: Path, size=(400, 300), color=(32, 180, 96)) -> Path:
    image = Image.new("RGB", size, color)
    image.save(path)
    return path


def _input(
    tmp_path,
    assets=None,
    product_profile=None,
    brand_context=None,
    scenario_id="general_creative",
    metadata=None,
    user_input="Create a clean social campaign cover for a premium product launch",
) -> CapabilityInput:
    return CapabilityInput(
        job_id="job_shared_test",
        scenario_id=scenario_id,
        user_input=user_input,
        uploaded_assets=assets or [],
        product_profile=product_profile or {},
        brand_context=brand_context or {},
        metadata=metadata or {},
    )


def test_asset_role_analyzer_detects_image_metadata_and_product_role(tmp_path) -> None:
    product_path = _image(tmp_path / "product_reference.png")
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            assets=[
                UploadedAssetInfo(
                    asset_id="asset_product",
                    file_path=str(product_path),
                    filename="product_reference.png",
                )
            ],
        ),
        module_ids=["asset_role_analyzer"],
    )

    assert result.status == CapabilityRunStatus.COMPLETE
    analysis = result.results[0].facts["asset_analyses"][0]
    assert analysis["role"] == AssetRole.PRODUCT_REFERENCE.value
    assert analysis["width"] == 400
    assert analysis["height"] == 300
    assert analysis["composition"]["orientation"] == "landscape"
    assert result.results[0].constraints[0].constraint_type == "product_identity_preservation"


def test_unknown_uploaded_asset_becomes_face_reference_for_human_task(tmp_path) -> None:
    portrait_path = _image(tmp_path / "uploaded_reference.png", size=(360, 480), color=(210, 190, 176))
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            user_input="Create a same-person East Asian summer portrait photo set with different poses",
            assets=[
                UploadedAssetInfo(
                    asset_id="asset_uploaded_person",
                    role=AssetRole.UNKNOWN_REFERENCE,
                    file_path=str(portrait_path),
                    filename="uploaded_reference.png",
                )
            ],
        ),
        module_ids=["asset_role_analyzer", "asset_binding_planner"],
    )

    analysis = result.results[0].facts["asset_analyses"][0]
    binding = result.results[1].facts["asset_binding_plan"]["bindings"][0]
    assert analysis["role"] == AssetRole.FACE_REFERENCE.value
    assert analysis["provider_input_required"] is True
    assert any(item.constraint_type == "portrait_identity_preservation" for item in result.results[0].constraints)
    assert binding["constraint_strength"] == "strong"
    assert binding["provider_input_required"] is True


def test_asset_binding_planner_prioritizes_product_and_warns_logo_conflicts(tmp_path) -> None:
    product_path = _image(tmp_path / "product.png")
    logo_a = _image(tmp_path / "logo_a.png", size=(300, 300), color=(250, 250, 250))
    logo_b = _image(tmp_path / "logo_b.png", size=(300, 300), color=(20, 20, 20))
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            assets=[
                UploadedAssetInfo(asset_id="product", file_path=str(product_path), filename="product.png"),
                UploadedAssetInfo(asset_id="logo_a", file_path=str(logo_a), filename="logo_a.png"),
                UploadedAssetInfo(asset_id="logo_b", file_path=str(logo_b), filename="logo_b.png"),
            ],
        ),
        module_ids=["asset_role_analyzer", "asset_binding_planner"],
    )

    binding = result.results[1]
    bindings = binding.facts["asset_binding_plan"]["bindings"]
    assert bindings[0]["role"] == AssetRole.PRODUCT_REFERENCE.value
    assert bindings[0]["constraint_strength"] == "strong"
    assert any(warning.code == "asset_binding_role_conflict" for warning in binding.warnings)


def test_case_library_has_no_ecommerce_delivery_recipe_in_shared_foundation() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    general = registry.run(
        _input(Path("."), product_profile={"category": "product listing"}),
        module_ids=["case_library_retriever"],
    )
    ecommerce = registry.run(
        _input(Path("."), product_profile={"category": "product listing"}, scenario_id="ecommerce"),
        module_ids=["case_library_retriever"],
    )

    general_case_ids = [case["case_id"] for case in general.results[0].facts["selected_cases"]]
    ecommerce_case_ids = [case["case_id"] for case in ecommerce.results[0].facts["selected_cases"]]
    assert all("ecommerce" not in case_id for case_id in general_case_ids)
    assert all("ecommerce" not in case_id for case_id in ecommerce_case_ids)


def test_visual_grammar_and_prompt_compiler_produce_deduped_constraints(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(tmp_path, product_profile={"category": "social campaign"}),
        module_ids=["case_library_retriever", "visual_grammar_lock", "prompt_constraint_compiler"],
    )

    assert result.status == CapabilityRunStatus.COMPLETE
    grammar = result.results[1].facts["visual_grammar_lock"]
    compiled = result.results[2].facts["compiled_constraints"]
    assert grammar["locked_visual_grammar"]
    assert compiled["layout_constraints"]
    assert compiled["prompt_constraints"]


def test_visual_capability_cluster_collects_project_context_and_child_modules(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            metadata={
                "project_context_snapshot": {
                    "project_id": "project_visual_cluster",
                    "context_version": "context_v1",
                    "confirmed_visual_tone": ["fresh", "premium"],
                    "selected_output_assets": [
                        {"output_id": "v3_output_keep", "selection_reason": "best summer portrait style"}
                    ],
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "v3_output_keep",
                            "source_type": "generated_selected",
                            "use_policy": "style",
                        }
                    ],
                    "negative_direction_notes": ["avoid dark clutter"],
                    "metadata": {
                        "positive_context_from_selected_outputs_only": True,
                        "unselected_candidates_excluded": True,
                    },
                }
            },
        ),
        module_ids=[
            "case_library_retriever",
            "visual_grammar_lock",
            "prompt_constraint_compiler",
            "visual_capability_cluster",
        ],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    snapshot = cluster["project_snapshot"]
    profile = cluster["profile"]
    guard = cluster["consistency_guard"]
    binding_profile = cluster["reference_binding_profile"]
    assert result.results[-1].module_id == "visual_capability_cluster"
    assert snapshot["project_id"] == "project_visual_cluster"
    assert snapshot["positive_anchor_output_ids"] == ["v3_output_keep"]
    assert snapshot["continuity_strength"] == "strong"
    assert "avoid dark clutter" in profile["negative_rules"]
    assert binding_profile["strong_bindings"]
    assert cluster["identity_lock_profiles"]
    assert cluster["quality_review_reports"]
    assert cluster["auto_retry_decisions"]
    assert cluster["commercial_output_selection"]["selection_id"]
    assert cluster["template_consistency_policy"]["policy_id"]
    assert cluster["project_identity_anchors"]
    assert cluster["strong_reference_continuation_plan"]["active_anchor_ids"]
    assert cluster["general_suite_role_plan"]["roles"]
    assert cluster["batch_identity_diversity_review"]["applies"] is True
    assert "planned distinct image roles for this set" in cluster["user_visible_summary"]
    assert guard["positive_context_from_selected_outputs_only"] is True
    assert guard["unselected_candidates_excluded"] is True


def test_visual_capability_cluster_adds_human_natural_variation_plan(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            user_input="Create three same-model East Asian summer portrait alternatives with small pose changes",
            metadata={
                "project_context_snapshot": {
                    "project_id": "project_human_variation",
                    "selected_output_assets": [
                        {"output_id": "selected_model_frame", "selection_reason": "best recognizable model"}
                    ],
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "selected_model_frame",
                            "source_type": "generated_selected",
                            "use_policy": "identity",
                        }
                    ],
                },
                "requested_image_count": 3,
                "variation_mode": "selection_candidates",
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    plan = cluster["human_natural_variation_plan"]
    anchor = cluster["human_identity_anchor_profile"]

    assert plan["applies"] is True
    assert plan["variation_mode"] == "selection_candidates"
    assert any("expression" in item for item in plan["per_image_variation_axes"])
    assert any("same exact expression" in item for item in plan["negative_additions"])
    assert anchor["applies"] is True
    assert "body type and proportions" in anchor["locked_traits"]


def test_human_natural_variation_policy_detects_chinese_person_requests(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            user_input="夏日清凉东方美女写真，同一个人物，两张图姿势自然变化",
            metadata={"requested_image_count": 2, "variation_mode": "selection_candidates"},
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]

    assert cluster["human_natural_variation_plan"]["applies"] is True
    assert cluster["human_identity_anchor_profile"]["applies"] is True


def test_information_integrity_flags_unsupported_claims_and_preserves_text(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            product_profile={
                "required_text": ["Summer Launch"],
                "facts": ["matte black finish"],
                "claims": ["100% guaranteed medical-grade result"],
            },
        ),
        module_ids=["information_integrity_lock", "prompt_constraint_compiler"],
    )

    integrity = result.results[0]
    compiled = result.results[1].facts["compiled_constraints"]
    assert integrity.status == CapabilityStatus.WARNING
    assert integrity.facts["information_integrity"]["unsupported_claims"]
    assert any(warning.code == "unsupported_claim_requires_evidence" for warning in integrity.warnings)
    assert compiled["negative_constraints"]


def test_output_review_and_history_reference_are_metadata_safe(tmp_path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        _input(
            tmp_path,
            product_profile={"facts": ["red package"]},
            brand_context={
                "visual_tone": ["clean", "fresh"],
                "successful_asset_ids": ["asset_old"],
                "rejected_style_tags": ["dark clutter"],
                "reference_assets": [{"asset_id": "ref_old"}],
            },
        ),
        module_ids=[
            "information_integrity_lock",
            "prompt_constraint_compiler",
            "output_review",
            "history_reference",
        ],
    )

    review = result.results[2]
    history = result.results[3]
    assert review.status == CapabilityStatus.WARNING
    assert review.facts["output_review"]["evaluation_check_count"] == 1
    assert history.status == CapabilityStatus.SUCCESS
    assert history.facts["history_reference"]["rejected_style_tags"] == ["dark clutter"]
    assert any(constraint.constraint_type == "avoid_rejected_history_styles" for constraint in history.constraints)
