import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(*, scope: str | None = None, placement_context: str | None = None, legacy_scope: str | None = None) -> object:
    parameters = {"platform": "amazon_us", "market": "US"}
    if scope:
        parameters["delivery_scope"] = scope
    if placement_context:
        parameters["placement_context"] = placement_context
    if legacy_scope:
        parameters["suite_scope"] = legacy_scope
    return EcommerceScenarioPackPlanner().plan(
        user_input="Create an ecommerce package for this desk lamp.",
        product_profile={"product_category": "desk lamp", "selling_points": ["Adjustable lamp head"]},
        uploaded_asset_ids=["d3_lamp_reference"],
        scenario_parameters=parameters,
        platform_profile=None,
        job_key=f"d3_{scope or legacy_scope or 'default'}",
    )


def test_default_and_legacy_suite_scope_resolve_to_listing_only_without_losing_legacy_lineage() -> None:
    output = _plan(legacy_scope="listing_full")

    assert output.metadata["delivery_scope_id"] == "listing_only"
    assert output.metadata["delivery_scope_source"] == "legacy_suite_scope"
    assert output.metadata["legacy_suite_scope"] == "listing_full"
    assert output.metadata["text_pixel_delivery_promised"] is False
    assert all(not recipe.slot.startswith(("a_plus_", "content_", "storefront_")) for recipe in output.recipes)
    assert output.export_package.metadata["delivery_scope_id"] == "listing_only"
    assert output.export_package.metadata["legacy_suite_scope"] == "listing_full"


def test_a_plus_scope_requires_explicit_placement_context_instead_of_silently_using_listing_roles() -> None:
    output = _plan(scope="listing_plus_a_plus_planning")

    assert output.metadata["delivery_scope_id"] == "listing_plus_a_plus_planning"
    assert output.metadata["status"] == "needs_placement_context"
    assert output.recipes == []
    assert "merchant placement context" in output.metadata["missing_requirements"]
    assert any(check["id"] == "delivery_scope_context" and check["status"] == "attention" for check in output.critic.checks)
    checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert checks["delivery_scope_context"]["status"] == "attention"


def test_a_plus_scope_uses_distinct_module_roles_when_placement_context_is_explicit() -> None:
    output = _plan(
        scope="listing_plus_a_plus_planning",
        placement_context="Amazon US A+ standard comparison module",
    )

    assert output.metadata["status"] == "ready"
    assert [recipe.slot for recipe in output.recipes] == [
        "a_plus_brand_story",
        "a_plus_feature_proof",
        "a_plus_comparison_context",
    ]
    assert all(not recipe.slot.endswith(("main_image", "detail_image", "scenario_image")) for recipe in output.recipes)
    assert output.export_package.metadata["delivery_scope_text_pixel_delivery_promised"] is False


@pytest.mark.parametrize(
    ("scope", "placement_context", "expected_slots"),
    [
        ("content_assets", None, ["content_cover", "content_feature_hook", "content_creator_context"]),
        ("storefront_assets", "Shopify Dawn collection grid", ["storefront_hero", "storefront_collection", "storefront_feature"]),
    ],
)
def test_non_listing_scopes_use_their_own_deliverable_map(
    scope: str,
    placement_context: str | None,
    expected_slots: list[str],
) -> None:
    output = _plan(scope=scope, placement_context=placement_context)

    assert output.metadata["delivery_scope_id"] == scope
    assert output.metadata["status"] == "ready"
    assert [recipe.slot for recipe in output.recipes] == expected_slots
    assert output.export_package.metadata["delivery_scope_text_pixel_delivery_promised"] is False


def test_project_mode_forwards_scope_metadata_without_a_public_schema_change(tmp_path) -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Plan an A+ product package"})["project"]

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Plan A+ modules for this desk lamp",
            "commerce_profile_patch": {
                "product_category": "desk lamp",
                "target_platform": "amazon_us",
                "target_market": "US",
                "metadata": {
                    "delivery_scope": "listing_plus_a_plus_planning",
                    "a_plus_placement_context": "Amazon US A+ standard comparison module",
                },
            },
        },
    )

    assert job["metadata"]["scenario_parameters"]["ecommerce_delivery_scope"] == "listing_plus_a_plus_planning"
    assert job["metadata"]["scenario_parameters"]["placement_context"] == "Amazon US A+ standard comparison module"
    assert [recipe["slot"] for recipe in job["ecommerce"]["image_recipes"]] == [
        "a_plus_brand_story",
        "a_plus_feature_proof",
        "a_plus_comparison_context",
    ]
