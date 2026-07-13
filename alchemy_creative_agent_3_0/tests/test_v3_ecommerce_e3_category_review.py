from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_category_evidence_is_sent_as_questions_and_not_scored_against_fixed_slots() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="为无线耳机创建三张商品图",
        product_profile={"product_category": "wireless earbuds", "selling_points": ["Compact case"]},
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 3},
        platform_profile=None,
        job_key="e3_electronics",
    )
    assert output.creative_context is not None
    assert "ports or functional structure" in output.creative_context.category_evidence_questions
    assert all(check["id"] != "category_evidence_coverage" for check in output.critic.checks)
    assert output.recipes == []
