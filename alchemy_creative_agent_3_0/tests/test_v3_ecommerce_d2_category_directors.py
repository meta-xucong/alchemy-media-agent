import pytest

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.category_profiles import list_category_profiles
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(product_category: str, *, job_key: str) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input=f"Create an Amazon listing suite for this {product_category}.",
        product_profile={
            "product_category": product_category,
            "selling_points": ["One supplied product fact", "One distinct buyer proof"],
        },
        uploaded_asset_ids=[f"{job_key}_reference"],
        scenario_parameters={"platform": "amazon_us", "market": "US"},
        platform_profile=None,
        job_key=job_key,
    )


def test_first_wave_category_profiles_expose_the_completed_director_contract() -> None:
    profiles = {profile.category_id: profile for profile in list_category_profiles()}

    assert set(profiles) == {"apparel", "beauty", "electronics", "home_kitchen", "food_beverage"}
    for profile in profiles.values():
        assert profile.buyer_questions
        assert profile.required_evidence
        assert profile.default_slot_priority
        assert profile.human_presence_policy
        assert profile.text_roles
        assert profile.product_truth_fields
        assert profile.review_checks
        assert profile.slot_directors
        assert all(director.purpose and director.evidence and director.fact_channels for director in profile.slot_directors)


@pytest.mark.parametrize(
    ("product_category", "category_id", "feature_role_id"),
    [
        ("cropped cotton shirt", "apparel", "apparel_worn_front_fit"),
        ("hydrating face serum", "beauty", "beauty_texture_or_application"),
        ("wireless earbuds", "electronics", "electronics_ports_or_controls"),
        ("stainless kitchen organizer", "home_kitchen", "home_supported_function"),
        ("bottled tea", "food_beverage", "food_serving_or_contents"),
    ],
)
def test_every_first_wave_category_emits_distinct_slot_directors_and_export_lineage(
    product_category: str,
    category_id: str,
    feature_role_id: str,
) -> None:
    output = _plan(product_category, job_key=f"d2_{category_id}")
    recipes = {recipe.slot: recipe for recipe in output.recipes}
    export_files = {item["slot"]: item for item in output.export_package.files}

    assert output.metadata["category_id"] == category_id
    assert recipes["feature_image_1"].metadata["category_slot_guidance_id"] == feature_role_id
    assert all(recipe.metadata["category_slot_purpose"] for recipe in output.recipes)
    assert all(recipe.metadata["category_slot_fact_channels"] for recipe in output.recipes)
    assert all(recipe.metadata["category_slot_review_checks"] for recipe in output.recipes)
    assert len({recipe.metadata["category_slot_differentiation_key"] for recipe in output.recipes}) == len(output.recipes)
    assert all(
        set(recipe.metadata["category_slot_review_checks"]).issubset(recipe.review_checks)
        for recipe in output.recipes
    )
    assert export_files["feature_image_1"]["category_slot_role_id"] == feature_role_id
    assert export_files["feature_image_1"]["category_slot_purpose"] == recipes["feature_image_1"].metadata["category_slot_purpose"]
    assert output.export_package.metadata["category_slot_directors"]["feature_image_1"]["role_id"] == feature_role_id


def test_garment_directors_do_not_leak_to_bags_and_use_accessory_directors() -> None:
    output = _plan("leather handbag", job_key="d2_bag_isolation")

    assert output.metadata["category_id"] == "apparel"
    assert all(recipe.metadata["category_slot_guidance_id"].startswith("accessory_") for recipe in output.recipes)
    assert all("garment" not in recipe.metadata["category_slot_guidance"].lower() for recipe in output.recipes)
    assert output.export_package.metadata["category_slot_directors"]["main_image"]["role_id"] == "accessory_primary_form"


def test_category_priority_selects_the_highest_value_proof_roles_for_constrained_suite() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create three Amazon images for wireless earbuds.",
        product_profile={"product_category": "wireless earbuds", "selling_points": ["Compact charging case"]},
        uploaded_asset_ids=["d2_earbuds_reference"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 3},
        platform_profile=None,
        job_key="d2_electronics_short",
    )

    assert [recipe.slot for recipe in output.recipes] == ["main_image", "feature_image_1", "feature_image_2"]
    assert [recipe.metadata["category_slot_guidance_id"] for recipe in output.recipes] == [
        "electronics_product_silhouette",
        "electronics_ports_or_controls",
        "electronics_included_items",
    ]
