from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_pre_generation_export_has_publish_checks_but_no_invented_files() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create two Ozon images for this drink",
        product_profile={"product_category": "drink"}, uploaded_asset_ids=["drink_front"],
        scenario_parameters={"platform": "ozon", "requested_image_count": 2}, platform_profile=None, job_key="e6",
    )
    checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert checks["product_truth"]["status"] == "attention"
    assert checks["platform_profile"]["status"] == "attention"
    assert output.export_package.files == []
    assert output.export_package.metadata["creative_recipe_present"] is False
