from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)


def _request(active_ids, composed, *, text="clean visual", asset_type=AssetType.SINGLE_IMAGE):
    asset = AssetSpec(
        asset_id="asset",
        asset_type=asset_type,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="direct image",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt",
        asset_id="asset",
        visual_prompt=text,
        negative_prompt="",
        text_policy="do_not_render_final_text_in_image_model",
    )
    plan = {
        "plan_id": "plan",
        "activation_mode": "enforced",
        "dependency_order": active_ids,
    }
    cluster = {
        "capability_activation_plan_summary": plan,
        "composed_visual_contribution": {
            "activation_plan_id": "plan",
            "active_capability_ids": active_ids,
            **composed,
        },
        # Deliberately stale legacy data. Enforced mode must ignore it.
        "human_photorealism_guidance": {
            "applies": True,
            "positive_prompt_fragments": ["STALE SKIN RULE"],
            "negative_prompt_fragments": ["STALE FACE RULE"],
        },
        "portrait_bone_structure_lock": {"applies": True, "prompt_rules": ["STALE IDENTITY RULE"]},
    }
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition", asset_id="asset"),
        generation_plan=GenerationPlan(
            generation_plan_id="generation",
            asset_id="asset",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
            metadata={"capability_activation_plan": plan},
        ),
        metadata={
            "job_id": "job",
            "user_input": text,
            "capability_activation_plan": plan,
            "visual_cluster": cluster,
        },
    )


def test_product_only_prompt_ignores_stale_human_and_portrait_fields() -> None:
    request = _request(
        ["visual_grammar", "universal_visual_quality", "product_identity"],
        {
            "prompt_additions": ["KEEP PRODUCT SHAPE"],
            "negative_additions": ["AVOID PRODUCT REPLACEMENT"],
        },
        text="premium product hero",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
    )
    prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])
    assert "KEEP PRODUCT SHAPE" in prompt
    assert "STALE SKIN RULE" not in prompt
    assert "STALE IDENTITY RULE" not in prompt
    assert "Human realism contract" not in prompt


def test_illustration_prompt_ignores_stale_product_and_human_fields() -> None:
    request = _request(
        ["visual_grammar", "universal_visual_quality"],
        {"prompt_additions": ["ILLUSTRATION GRAMMAR"], "negative_additions": []},
        text="anime illustration",
    )
    prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])
    assert "ILLUSTRATION GRAMMAR" in prompt
    assert "STALE SKIN RULE" not in prompt
    assert "commercial product image" not in prompt


def test_human_rules_are_read_when_human_capability_is_active() -> None:
    request = _request(
        ["visual_grammar", "universal_visual_quality", "human_realism"],
        {"prompt_additions": ["ACTIVE HUMAN REALISM"], "negative_additions": ["ACTIVE AI FACE AVOID"]},
        text="real woman portrait",
    )
    prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])
    assert "ACTIVE HUMAN REALISM" in prompt
    assert "Human realism contract" in prompt
