from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.contracts import ProductTruthLock
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.commerce_critic import CommerceCritic
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(product_profile: dict, *, parameters: dict | None = None) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon listing suite for this product.",
        product_profile=product_profile,
        uploaded_asset_ids=["product_reference"],
        scenario_parameters={"platform": "amazon_us", "market": "US", **(parameters or {})},
        platform_profile=None,
        job_key="d1_fact_ledger",
    )


def test_legacy_unverified_visual_facts_materialize_as_confirmation_records() -> None:
    output = _plan(
        {
            "product_category": "shirt",
            "visible_attributes": ["blue striped shirt", "collared neck"],
            "unverified_visual_facts": ["back pintuck detail"],
            "selling_points": ["relaxed fit"],
        }
    )

    fact = next(fact for fact in output.product_truth.fact_ledger if fact.value == "back pintuck detail")
    assert fact.source_type == "supplier_spec"
    assert fact.verification == "requires_confirmation"
    assert fact.review_requirement == "product_owner_confirmation"
    assert all("back pintuck detail" in recipe.required_product_facts for recipe in output.recipes)
    checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert checks["product_fact_confirmation"]["status"] == "attention"
    assert output.export_package.metadata["pending_product_facts"][0]["fact_id"] == fact.fact_id


def test_structured_facts_bind_to_slots_and_blocked_facts_stay_out_of_prompts_and_copy() -> None:
    blocked_fact = "clinically proven thermal protection"
    output = _plan(
        {
            "product_category": "shirt",
            "selling_points": [blocked_fact, "fine blue stripe"],
            "fact_ledger": [
                {
                    "fact_id": "stripe",
                    "label": "Fine blue vertical stripe",
                    "value": "fine blue vertical stripe",
                    "source_type": "reference_visible",
                    "verification": "verified",
                    "visual_channels": ["product", "material"],
                    "allowed_slot_ids": ["main_image", "detail_image"],
                    "claim_eligible": True,
                },
                {
                    "fact_id": "back_pintuck",
                    "label": "Back pintuck detail",
                    "value": "back pintuck detail",
                    "source_type": "supplier_spec",
                    "verification": "requires_confirmation",
                    "visual_channels": ["construction"],
                    "allowed_slot_ids": ["feature_image_2"],
                },
                {
                    "fact_id": "blocked_thermal_claim",
                    "label": "Unsupported thermal claim",
                    "value": blocked_fact,
                    "source_type": "derived_blocked",
                    "verification": "verified",
                    "visual_channels": ["copy"],
                    "claim_eligible": True,
                },
            ],
        },
        parameters={"overlay_copy": {"feature_image_1": blocked_fact}},
    )
    recipes = {recipe.slot: recipe for recipe in output.recipes}

    assert [fact.fact_id for fact in output.product_truth.fact_ledger] == [
        "stripe",
        "back_pintuck",
        "blocked_thermal_claim",
    ]
    assert output.product_truth.fact_ledger[2].verification == "blocked"
    assert output.product_truth.fact_ledger[2].claim_eligible is False
    assert output.product_truth.fact_ledger[0].claim_eligible is True
    assert recipes["main_image"].metadata["pending_product_fact_ids"] == []
    assert [fact["fact_id"] for fact in recipes["main_image"].metadata["product_fact_bindings"]] == ["stripe"]
    assert [fact["fact_id"] for fact in recipes["feature_image_2"].metadata["product_fact_bindings"]] == ["back_pintuck"]
    assert "back pintuck detail" not in recipes["main_image"].required_product_facts
    assert recipes["feature_image_1"].overlay_text is None
    assert recipes["feature_image_1"].metadata["copy_plan"]["policy"] == "text_blocked"
    assert all(blocked_fact not in " ".join([*recipe.required_product_facts, recipe.visual_scene]) for recipe in output.recipes)
    assert output.critic.metadata["blocked_fact_leak_slots"] == []
    assert output.critic.metadata["blocked_copy_slots"] == ["feature_image_1"]
    export_checks = {check["id"]: check for check in output.export_package.metadata["publish_checks"]}
    assert export_checks["product_fact_confirmation"]["status"] == "attention"
    assert export_checks["blocked_product_facts"]["status"] == "attention"
    assert all(
        binding["fact_id"] != "blocked_thermal_claim"
        for bindings in output.export_package.metadata["product_fact_bindings"].values()
        for binding in bindings
    )


def test_historical_product_truth_without_a_ledger_remains_readable() -> None:
    truth = ProductTruthLock.model_validate(
        {
            "product_category": "generic_product",
            "visible_attributes": ["legacy blue bottle"],
            "immutable_attributes": ["legacy blue bottle"],
        }
    )

    assert truth.fact_ledger == []


def test_critic_detects_a_blocked_fact_if_it_reaches_provider_native_copy() -> None:
    blocked_fact = "clinically proven thermal protection"
    output = _plan(
        {
            "product_category": "shirt",
            "fact_ledger": [
                {
                    "fact_id": "blocked_thermal_claim",
                    "label": "Unsupported thermal claim",
                    "value": blocked_fact,
                    "source_type": "derived_blocked",
                    "verification": "verified",
                    "visual_channels": ["copy"],
                    "claim_eligible": True,
                }
            ],
        }
    )
    leaking_recipe = output.recipes[1].model_copy(update={"provider_native_text": blocked_fact})
    recipes = [output.recipes[0], leaking_recipe, *output.recipes[2:]]

    report = CommerceCritic().review(
        truth=output.product_truth,
        brief=output.commerce_brief,
        marketplace_profile=output.marketplace_profile,
        recipes=recipes,
    )

    assert report.metadata["blocked_fact_leak_slots"] == [leaking_recipe.slot]


def test_relevant_global_facts_are_not_arbitrarily_truncated() -> None:
    fact_ledger = [
        {
            "fact_id": f"fact_{index}",
            "label": f"Verified fact {index}",
            "value": f"verified product fact {index}",
            "source_type": "user_confirmed",
            "verification": "verified",
        }
        for index in range(1, 10)
    ]
    output = _plan({"product_category": "shirt", "fact_ledger": fact_ledger})
    main_facts = next(recipe.required_product_facts for recipe in output.recipes if recipe.slot == "main_image")

    assert {f"verified product fact {index}" for index in range(1, 10)}.issubset(main_facts)


def test_supplier_fact_cannot_become_claim_eligible_without_a_confirmed_source() -> None:
    output = _plan(
        {
            "product_category": "shirt",
            "fact_ledger": [
                {
                    "fact_id": "supplier_material",
                    "label": "Supplier material specification",
                    "value": "100% recycled cotton",
                    "source_type": "supplier_spec",
                    "verification": "verified",
                    "claim_eligible": True,
                }
            ],
        }
    )

    assert output.product_truth.fact_ledger[0].claim_eligible is False
