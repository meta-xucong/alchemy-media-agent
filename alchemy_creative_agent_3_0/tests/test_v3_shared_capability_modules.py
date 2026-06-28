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


def _input(tmp_path, assets=None, product_profile=None, brand_context=None, scenario_id="general_creative") -> CapabilityInput:
    return CapabilityInput(
        job_id="job_shared_test",
        scenario_id=scenario_id,
        user_input="Create a clean social campaign cover for a premium product launch",
        uploaded_assets=assets or [],
        product_profile=product_profile or {},
        brand_context=brand_context or {},
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


def test_case_library_excludes_ecommerce_cases_from_general_creative() -> None:
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
    assert "case_ecommerce_product_hero" not in general_case_ids
    assert "case_ecommerce_product_hero" in ecommerce_case_ids


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
