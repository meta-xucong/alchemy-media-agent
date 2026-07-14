"""Doc114 Phase A garment-construction truth regressions."""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.product_truth import ProductTruthLockBuilder
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.apparel_construction import (
    APPAREL_CONSTRUCTION_CHANNELS,
    extract_apparel_construction_facts,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _profile() -> dict:
    return {
        "product_category": "apparel",
        "product_name": "blue layered occasion dress",
        "apparel_construction": {
            "silhouette_and_proportion": ["A-line knee-length silhouette", "fitted bodice with a soft skirt volume"],
            "print_or_pattern_registration": "small blue floral print stays registered across the bodice and skirt",
            "layer_order": ["printed lining", "two uneven tulle overlay layers"],
            "seam_hem_edge_trim_fastening": ["waist seam", "narrow scalloped hem trim", "back button fastening"],
            "material_weight_and_surface_response": "lightweight matte woven lining with translucent tulle",
            "fold_tension_gravity_and_drape": "soft gravity-driven folds, with irregular tulle edge separation",
        },
    }


def _provider_request(projection: dict) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="doc114-apparel-asset",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="3:4",
        purpose="faithful supplied apparel image",
    )
    plan = {
        "plan_id": "doc114-apparel-plan",
        "activation_mode": "enforced",
        "dependency_order": ["product_identity"],
    }
    envelope = {
        "envelope_id": "doc114-apparel-envelope",
        "activation_mode": "enforced",
        "activation_plan": plan,
        "active_capability_ids": ["product_identity"],
        "resolved_constraint_ledger": {
            "provider_projection": projection,
            "review_contracts": [],
            "hard_semantic_contract": True,
        },
    }
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="doc114-apparel-prompt",
            asset_id=asset.asset_id,
            visual_prompt="Create a faithful product-on-person image of the supplied dress.",
            negative_prompt="",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(condition_plan_id="doc114-apparel-condition", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="doc114-apparel-generation",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
            metadata={"capability_activation_plan": plan},
        ),
        metadata={
            "job_id": "doc114-apparel-job",
            "user_input": "Create a faithful product-on-person image of the supplied dress.",
            "capability_activation_plan": plan,
            "capability_execution_envelope": envelope,
        },
    )


def test_nested_apparel_construction_is_typed_hard_evidence_without_age_or_template_logic() -> None:
    facts = extract_apparel_construction_facts(_profile(), has_reference_evidence=False)

    assert facts.applies is True
    assert [fact.channel for fact in facts.facts] == list(APPAREL_CONSTRUCTION_CHANNELS)
    strengths = {fact.channel: fact.strength for fact in facts.facts}
    assert {strengths[channel] for channel in APPAREL_CONSTRUCTION_CHANNELS[:4]} == {"hard"}
    assert {strengths[channel] for channel in APPAREL_CONSTRUCTION_CHANNELS[4:]} == {"strong"}
    assert {fact.evidence_mode for fact in facts.facts} == {"declared_structured"}
    assert all(fact.source == "product_profile.apparel_construction" for fact in facts.facts)
    assert "fold_configuration" in facts.facts[-1].allowed_variation


def test_ecommerce_factual_context_carries_apparel_truth_without_creating_a_recipe() -> None:
    truth = ProductTruthLockBuilder().build(
        user_input="Create a faithful product-on-person ecommerce image.",
        product_profile=_profile(),
        uploaded_asset_ids=["dress-reference"],
        parameters={},
    )

    assert truth.apparel_construction is not None
    assert truth.apparel_construction.source_summary == "reference_backed_apparel_construction"
    assert {fact.channel for fact in truth.apparel_construction.facts} == set(APPAREL_CONSTRUCTION_CHANNELS)
    assert "Supplied garment silhouette" in " ".join(truth.review_obligations)
    assert "recipe" not in truth.model_dump_json().lower()


def test_runtime_projects_garment_facts_as_typed_ledger_entries_and_preserves_prompt_owned_channels(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider()))

    result = runtime.plan_job(
        {
            "user_input": "Create one faithful product-on-person image of the supplied dress, with a natural candid expression.",
            "scenario_selection": {"scenario_id": "ecommerce", "parameters": {"requested_image_count": 1}},
            "uploaded_assets": [{"asset_id": "dress-reference", "role": "product_reference"}],
            "product_profile": _profile(),
            "metadata": {"requested_image_count": 1},
        }
    )

    ledger = result.metadata["resolved_constraint_ledger"]
    entries = {entry["channel"]: entry for entry in ledger["entries"]}
    projection = ledger["provider_projection"]["apparel_construction"]

    assert set(APPAREL_CONSTRUCTION_CHANNELS).issubset(entries)
    assert {entries[channel]["strength"] for channel in APPAREL_CONSTRUCTION_CHANNELS[:4]} == {"hard"}
    assert {entries[channel]["strength"] for channel in APPAREL_CONSTRUCTION_CHANNELS[4:]} == {"strong"}
    assert {entries[channel]["provenance"][0]["evidence_mode"] for channel in APPAREL_CONSTRUCTION_CHANNELS} == {
        "reference_backed"
    }
    assert projection["applies"] is True
    assert {fact["channel"] for fact in projection["facts"]} == set(APPAREL_CONSTRUCTION_CHANNELS)
    assert not ({"pose", "expression", "camera", "scene", "lighting", "mood", "styling"} & set(entries))
    assert ledger["audit_summary"]["deliverable_owner"] == "ecommerce_template"


def test_provider_materializes_only_frozen_garment_truth_and_keeps_art_direction_prompt_owned() -> None:
    projection = {
        "protected_user_intent": "Create a faithful product-on-person image of the supplied dress.",
        "quality_guidance": [],
        "negative_guidance": [],
        "capability_projection": {},
        "apparel_construction": extract_apparel_construction_facts(_profile(), has_reference_evidence=True).provider_projection(),
    }
    prompt = ProductionImageGenerationProvider()._generation_prompt(_provider_request(projection), [])

    assert "Garment construction truth:" in prompt
    assert "A-line knee-length silhouette" in prompt
    assert "small blue floral print stays registered" in prompt
    assert "Keep materially consistent material weight and surface response" in prompt
    assert "current brief still owns pose, expression, camera, scene, lighting, mood, and styling" in prompt


def test_non_apparel_profile_has_no_garment_projection_or_provider_prompt_leakage() -> None:
    facts = extract_apparel_construction_facts(
        {"product_category": "ceramic mug", "material": "glazed ceramic"},
        has_reference_evidence=True,
    )
    projection = {
        "protected_user_intent": "Create a clean product image of a ceramic mug.",
        "quality_guidance": [],
        "negative_guidance": [],
        "capability_projection": {},
        "apparel_construction": facts.provider_projection(),
    }
    prompt = ProductionImageGenerationProvider()._generation_prompt(_provider_request(projection), [])

    assert facts.applies is False
    assert "Garment construction truth:" not in prompt
