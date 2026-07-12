from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_export_package_collects_concise_publish_checks_from_existing_metadata() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create two Ozon images for this drink",
        product_profile={"product_category": "drink", "selling_points": ["Fresh summer refreshment"]},
        uploaded_asset_ids=["drink_front"],
        scenario_parameters={"platform": "ozon", "requested_image_count": 2},
        platform_profile=None,
        job_key="e6_ozon_publish",
    )

    checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert checks["product_truth"]["status"] == "attention"
    assert checks["platform_profile"]["status"] == "attention"
    assert "localized_copy" not in checks
    assert checks["category_evidence_coverage"]["status"] == "attention"
    assert output.export_package.review_status == "attention"
    assert "2 planned image(s)" in output.export_package.metadata["publish_summary"]


def test_publish_checks_include_claim_evidence_without_rewriting_copy() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon listing image set",
        product_profile={
            "product_category": "desk lamp",
            "selling_points": ["Adjustable angle"],
            "claims": ["100% eye protection"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "requested_image_count": 2,
            "overlay_copy": {"feature_image_1": "100% eye protection"},
        },
        platform_profile=None,
        job_key="e6_claim_publish",
    )

    checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert checks["claim_evidence"]["status"] == "attention"
    assert output.export_package.files[1]["overlay_text"] is None
    assert output.export_package.files[1]["provider_native_text"] == "100% eye protection"
