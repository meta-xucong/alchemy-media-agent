from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.product_truth import claim_review_required


def test_claim_risk_helper_flags_sensitive_claim_language() -> None:
    assert claim_review_required("100% eye protection") is True
    assert claim_review_required("FDA certified treatment") is True
    assert claim_review_required("Compact matte black case") is False
    assert claim_review_required("Best daily companion", ["best daily companion"]) is True


def test_risky_user_overlay_copy_requires_review_without_being_deleted() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon listing image set",
        product_profile={
            "product_category": "desk lamp",
            "selling_points": ["Adjustable angle", "Stable metal base"],
            "claims": ["100% eye protection"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "requested_image_count": 2,
            "overlay_copy": {"feature_image_1": "100% eye protection"},
        },
        platform_profile=None,
        job_key="e5_risky_copy",
    )

    feature = output.recipes[1]
    assert feature.overlay_text == "100% eye protection"
    assert feature.metadata["copy_plan"]["claim_review_required"] is True
    assert output.critic.metadata["claim_review_slots"] == ["feature_image_1"]
    assert any(check["id"] == "overlay_claim_review" and check["status"] == "attention" for check in output.critic.checks)
    assert any("claim review" in warning for warning in output.warnings)
    assert output.export_package.review_status == "attention"
    assert output.export_package.files[1]["claim_review_required"] is True
    assert output.export_package.metadata["claim_review_required"] is True


def test_safe_overlay_copy_remains_exportable_at_metadata_stage() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon listing image set",
        product_profile={"product_category": "desk lamp", "selling_points": ["Adjustable angle", "Stable metal base"]},
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "requested_image_count": 2,
            "overlay_copy": {"feature_image_1": "Adjustable angle"},
        },
        platform_profile=None,
        job_key="e5_safe_copy",
    )

    assert output.recipes[1].metadata["copy_plan"]["claim_review_required"] is False
    assert output.critic.metadata["claim_review_slots"] == []
    assert output.export_package.metadata["claim_review_required"] is False
