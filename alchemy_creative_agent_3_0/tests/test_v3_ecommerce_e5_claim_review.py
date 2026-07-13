from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.product_truth import claim_review_required


def test_claim_risk_helper_flags_sensitive_claim_language() -> None:
    assert claim_review_required("100% eye protection") is True
    assert claim_review_required("FDA certified treatment") is True
    assert claim_review_required("Compact matte black case") is False


def test_risky_approved_copy_is_preserved_as_context_and_requires_review() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon image set",
        product_profile={"product_category": "desk lamp", "claims": ["100% eye protection"]},
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": "amazon_us", "approved_literal_copy": "100% eye protection"},
        platform_profile=None,
        job_key="e5",
    )
    assert output.creative_context is not None
    assert output.creative_context.approved_literal_copy == "100% eye protection"
    assert output.creative_context.claim_risk_warnings
    assert any(check["id"] == "approved_copy_claim_risk" and check["status"] == "attention" for check in output.critic.checks)
    assert output.recipes == []
