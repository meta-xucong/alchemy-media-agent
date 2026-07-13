from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.category_profiles import resolve_category
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_common_product_descriptions_resolve_to_evidence_profiles() -> None:
    assert resolve_category("LED desk lamp").category_id == "home_kitchen"
    assert resolve_category("wireless keyboard").category_id == "electronics"
    assert resolve_category("hydrating face serum").category_id == "beauty"
    assert resolve_category("canvas shoulder bag").category_id == "apparel"


def test_category_context_does_not_promote_questions_to_required_output_roles() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon image set for this LED desk lamp",
        product_profile={"product_category": "desk lamp", "materials": ["metal"]}, uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": "amazon_us"}, platform_profile=None, job_key="e8",
    )
    assert output.creative_context is not None
    assert "size and space fit" in output.creative_context.category_evidence_questions
    assert output.recipes == []
