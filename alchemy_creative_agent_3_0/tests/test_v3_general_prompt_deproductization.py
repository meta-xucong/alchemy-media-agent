import json
from base64 import b64encode
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.creative_core.prompt_language import product_language_allowed
from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    LayoutPlan,
    LayoutRegion,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
    TextRenderingMode,
)


GENERAL_SUMMER_PORTRAIT_PROMPT = (
    "\u521b\u5efa\u4e00\u7ec4\u4e1c\u4e9a\u5e74\u8f7b\u5973\u6027\u7684"
    "\u590f\u65e5\u6e05\u51c9\u5199\u771f\uff0c\u8981\u6c42\u6e05\u723d\u3001"
    "\u9ad8\u7ea7\u3001\u901a\u900f\u3002\u5934\u53d1\u4e3a\u9ed1\u53d1"
    "\u672c\u8272\uff0c\u67d3\u8272\u6210\u7684\u7eff\u8272\uff0c\u4e0e"
    "\u590f\u65e5\u3001\u6e05\u51c9\u7684\u98ce\u683c\u642d\u914d"
)
STRUCTURED_APPEARANCE_PORTRAIT_PROMPT = (
    "Create a same-person portrait suite for social cover use. "
    "The woman wears one layered translucent ceremonial outfit with visible collar direction, "
    "sleeve shape, sash structure, embroidered pattern family, and trim placement that must stay "
    "consistent across the set. Keep it real-camera, clean, and atmospheric."
)


PRODUCT_TERMS = (
    "product",
    "center product",
    "product label",
    "product facts",
    "product identity",
    "product claims",
    "product category",
    "packaging",
    "bottle",
    "jar",
)

GENERAL_AD_COPY_TERMS = (
    "commercial",
    "commercial goal",
    "copy tone",
    "clear offer",
    "cta",
    "final offer text",
)

def _tiny_png_base64() -> str:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buffer, format="PNG")
    return b64encode(buffer.getvalue()).decode("ascii")


def _provider_prompt_for_planning_result(result) -> str:  # noqa: ANN001
    request = GenerationRequest(
        asset_spec=result.series_plan.assets[0],
        layout_plan=result.layout_plans[0],
        prompt_compilation=result.prompt_compilations[0],
        condition_plan=result.condition_plans[0],
        generation_plan=result.generation_plans[0],
        metadata={**result.generation_plans[0].metadata},
    )
    provider = ProductionImageGenerationProvider()
    return provider._generation_prompt(request, [])  # noqa: SLF001


def test_general_template_final_prompt_stays_subject_focused_not_product_ad() -> None:
    result = run_creative_planning(
        GENERAL_SUMMER_PORTRAIT_PROMPT,
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )

    prompt = result.prompt_compilations[0]
    layout = result.layout_plans[0]
    final_provider_prompt = _provider_prompt_for_planning_result(result)
    model_facing_text = " ".join(
        [
            prompt.visual_prompt,
            prompt.negative_prompt or "",
            " ".join(prompt.hard_constraints),
            " ".join(prompt.layout_notes),
            " ".join(layout.visual_hierarchy),
            layout.product_area.name,
            layout.product_area.position,
            result.brand_profile.layout_preference or "",
            final_provider_prompt,
        ]
    ).lower()

    assert prompt.metadata["product_language_allowed"] is False
    assert layout.metadata["product_language_allowed"] is False
    assert result.brand_profile.layout_preference == "LLM/provider-directed subject presentation responsive to the creative brief"
    assert "main_subject" in layout.visual_hierarchy
    assert "subject_area" in layout.product_area.name
    for term in PRODUCT_TERMS:
        assert term not in model_facing_text
    for term in GENERAL_AD_COPY_TERMS:
        assert term not in final_provider_prompt.lower()
    assert "output goal:" in final_provider_prompt.lower()
    assert "no literal copy is preselected" in final_provider_prompt.lower()
    assert "requested subject, scene, style, and mood" in final_provider_prompt
    assert "unrelated props" in final_provider_prompt
    assert "watermarks" in final_provider_prompt
    assert "AI-generated marks" in final_provider_prompt
    assert "single complete image frame" in final_provider_prompt.lower()
    assert "collage" in final_provider_prompt.lower()
    assert "split screen" in final_provider_prompt.lower()
    assert "contact sheet" in final_provider_prompt.lower()
    assert "multi-panel layout" in (prompt.negative_prompt or "").lower()


def test_general_explicit_multilingual_literal_copy_is_frozen_and_does_not_conflict_with_no_text_guards() -> None:
    result = run_creative_planning(
        'Create one editorial still-life card image. Render this exact user-approved in-image text once, centered on the card: "CLEAR DAY". Add no other visible text.',
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )

    layout = result.layout_plans[0]
    prompt = result.prompt_compilations[0]
    final_provider_prompt = _provider_prompt_for_planning_result(result)

    assert layout.metadata["provider_native_literal_text"] == ["CLEAR DAY"]
    assert layout.metadata["provider_native_text_forbidden"] is False
    assert prompt.text_policy == "provider_native_text_requested"
    assert '"CLEAR DAY"' in final_provider_prompt
    assert "No literal copy is preselected" not in final_provider_prompt
    assert "Do not: do not add visible text" not in final_provider_prompt
    assert "new visible text" not in final_provider_prompt
    assert "extra generated text" in final_provider_prompt

    russian = run_creative_planning(
        'Create one editorial card image. Render this exact user-approved in-image text once: "ЧИСТЫЙ ДЕНЬ".',
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )
    assert russian.layout_plans[0].metadata["provider_native_literal_text"] == ["ЧИСТЫЙ ДЕНЬ"]
    assert russian.prompt_compilations[0].text_policy == "provider_native_text_requested"


def test_general_explicit_no_text_becomes_a_provider_native_final_pixel_constraint() -> None:
    result = run_creative_planning(
        "Create a clean still-life scene without any visible text, logo, watermark, badge, or signature.",
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )

    layout = result.layout_plans[0]
    prompt = result.prompt_compilations[0]
    final_provider_prompt = _provider_prompt_for_planning_result(result)

    assert layout.metadata["provider_native_literal_text"] == []
    assert layout.metadata["provider_native_text_forbidden"] is True
    assert prompt.text_policy == "provider_native_text_forbidden"
    assert "must contain no added visible text" in final_provider_prompt


def test_general_landscape_prompt_does_not_misclassify_surface_as_a_human_face() -> None:
    user_input = (
        "Create a quiet alpine lake at sunrise with mountain ridges, mist above the water, "
        "a natural rock surface, no people, no products, and no text."
    )
    result = run_creative_planning(
        user_input,
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative", "user_input": user_input},
    )

    final_provider_prompt = _provider_prompt_for_planning_result(result)

    assert "Human realism contract:" not in final_provider_prompt
    assert "creative image asset for a human photo" not in final_provider_prompt
    assert "natural rock surface" in final_provider_prompt


def test_structured_human_appearance_prompt_stays_on_general_path() -> None:
    result = run_creative_planning(
        STRUCTURED_APPEARANCE_PORTRAIT_PROMPT,
        optional_template_id="general_template",
        runtime_metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )

    prompt = result.prompt_compilations[0]
    final_provider_prompt = _provider_prompt_for_planning_result(result)
    model_facing_text = " ".join(
        [
            prompt.visual_prompt,
            prompt.negative_prompt or "",
            " ".join(prompt.hard_constraints),
            " ".join(prompt.layout_notes),
            result.brand_profile.layout_preference or "",
            final_provider_prompt,
        ]
    ).lower()

    assert result.metadata["selected_vertical_pack"] == "default_commercial_pack"
    assert result.commercial_brief.industry.value == "unknown"
    assert prompt.metadata["product_language_allowed"] is False
    assert "commercial product image asset" not in final_provider_prompt
    assert "ecommerce_generic" not in model_facing_text
    assert "product hero" not in model_facing_text
    assert "feature label" not in model_facing_text
    assert "pattern family" in final_provider_prompt.lower()
    assert "trim placement" in final_provider_prompt.lower()


def test_explicit_product_or_ecommerce_context_keeps_product_language() -> None:
    request = GenerationRequest(
        asset_spec=AssetSpec(
            asset_id="asset_ecom",
            asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
            platform=Platform.ECOMMERCE_GENERIC,
            aspect_ratio="1:1",
            purpose="commercial product conversion visual",
        ),
        layout_plan=LayoutPlan(
            layout_plan_id="layout_ecom",
            asset_id="asset_ecom",
            platform=Platform.ECOMMERCE_GENERIC,
            aspect_ratio="1:1",
            text_rendering=TextRenderingMode.HTML_OVERLAY,
            visual_hierarchy=["headline", "product", "offer_or_cta", "brand_mark"],
            product_area=LayoutRegion(name="product_area", position="center_large"),
        ),
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_ecom",
            asset_id="asset_ecom",
            visual_prompt="premium ecommerce product hero image",
            negative_prompt="fake text",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["premium", "clean"],
            layout_notes=["center product"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_ecom", asset_id="asset_ecom"),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_ecom",
            asset_id="asset_ecom",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={"template_id": "ecommerce_template", "scenario_id": "ecommerce"},
    )

    provider = ProductionImageGenerationProvider()
    final_provider_prompt = provider._generation_prompt(request, [])  # noqa: SLF001

    assert "commercial product image asset" in final_provider_prompt
    assert "product label" in final_provider_prompt
    assert "product facts" in final_provider_prompt
    assert "product identity" in final_provider_prompt
    assert "product claims" in final_provider_prompt


def test_real_general_remote_brain_direction_does_not_replay_local_suite_recipe() -> None:
    user_request = (
        "Create one full-body, age-appropriate child fashion photograph in daylight. "
        "Keep the exact blue floral A-line dress, fitted bodice, layered tulle, waist seam, "
        "scalloped hem, natural skin, believable hands, and no readable text."
    )
    remote_direction = (
        "REMOTE_BRAIN_DIRECTION: A relaxed school-age child stands in a sunlit garden wearing the specified "
        "blue floral A-line dress. The fitted bodice, full skirt, layered translucent tulle, waist seam, "
        "scalloped hem, natural folds, natural skin, and believable hands are clearly visible."
    )
    request = GenerationRequest(
        asset_spec=AssetSpec(
            asset_id="asset_remote_general",
            asset_type=AssetType.SINGLE_IMAGE,
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="2:3",
            purpose="single requested creative image",
        ),
        layout_plan=LayoutPlan(
            layout_plan_id="layout_remote_general",
            asset_id="asset_remote_general",
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="2:3",
            text_rendering=TextRenderingMode.MODEL_TEXT_ALLOWED,
            visual_hierarchy=["main_subject"],
            product_area=LayoutRegion(name="subject_area", position="center_subject"),
        ),
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_remote_general",
            asset_id="asset_remote_general",
            visual_prompt="LOCAL_PROMPT_COMPILER_RECIPE_MUST_NOT_REACH_THE_REAL_PROVIDER",
            negative_prompt="watermark, unreadable text",
            text_policy="provider_native_text_forbidden",
            hard_constraints=["LOCAL_SUITE_HARD_CONSTRAINT_MUST_NOT_REACH_THE_REAL_PROVIDER"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_remote_general", asset_id="asset_remote_general"),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_remote_general",
            asset_id="asset_remote_general",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
            metadata={"scenario_id": "general_creative", "output_index": 0},
        ),
        metadata={
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "require_real_images": True,
            "user_input": user_request,
            "output_index": 0,
            "llm_brain": {
                "llm_used": True,
                "fallback_used": False,
                "image_set_plan": {"shot_plan": [remote_direction]},
            },
            "mode_role_recipe": {
                "label": "LOCAL_SUITE_ROLE_MUST_NOT_REACH_THE_REAL_PROVIDER",
                "prompt_pressure": "LOCAL_SUITE_ROLE_PRESSURE_MUST_NOT_REACH_THE_REAL_PROVIDER",
            },
            "mode_execution_policy": {"mode": "delivery_suite"},
            "visual_cluster": {
                "human_photorealism_guidance": {
                    "positive_prompt_fragments": ["natural skin texture", "believable hands"],
                }
            },
        },
    )

    final_provider_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert user_request in final_provider_prompt
    assert remote_direction in final_provider_prompt
    assert "LOCAL_PROMPT_COMPILER_RECIPE" not in final_provider_prompt
    assert "LOCAL_SUITE_ROLE" not in final_provider_prompt
    assert "Role-specific generation contract:" not in final_provider_prompt
    assert "Mode quality contract:" not in final_provider_prompt
    assert len(final_provider_prompt) < 3500


def test_general_reference_asset_plan_uses_neutral_subject_language() -> None:
    request = GenerationRequest(
        asset_spec=AssetSpec(
            asset_id="asset_general_ref",
            asset_type=AssetType.SINGLE_IMAGE,
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="4:5",
            purpose="same-style portrait continuation",
        ),
        layout_plan=LayoutPlan(
            layout_plan_id="layout_general_ref",
            asset_id="asset_general_ref",
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="4:5",
            text_rendering=TextRenderingMode.HTML_OVERLAY,
            visual_hierarchy=["main_subject", "scene_atmosphere"],
            product_area=LayoutRegion(name="subject_area", position="center_subject"),
        ),
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_general_ref",
            asset_id="asset_general_ref",
            visual_prompt="summer portrait in a clean translucent style",
            negative_prompt="fake text",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["clean", "summer"],
            layout_notes=["center subject"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_general_ref", asset_id="asset_general_ref"),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_general_ref",
            asset_id="asset_general_ref",
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )
    provider = ProductionImageGenerationProvider()

    plan = provider._asset_plan(  # noqa: SLF001
        request,
        [
            {
                "asset_id": "selected_general_style",
                "role": "style",
                "file_path": "selected_general_style.png",
            }
        ],
    )

    constraints = " ".join(plan["assets"][0]["prompt_constraints"]).lower()
    assert "identity reference" in constraints or "subject style" in constraints
    assert "product" not in constraints


def test_production_provider_persists_visual_cluster_metadata(tmp_path) -> None:
    class FakeProductionProvider(ProductionImageGenerationProvider):
        def _select_provider(self, reference_assets):  # noqa: ANN001, ARG002
            return "openai_gpt_image"

        async def _generate_with_app_provider(self, provider_name, app_request):  # noqa: ANN001, ARG002
            return SimpleNamespace(
                provider="fake_image_provider",
                model="fake-image-model",
                raw_response_summary={"fake": True},
                outputs=[
                    {
                        "b64_json": _tiny_png_base64(),
                        "mime_type": "image/png",
                        "format": "png",
                        "width": 1,
                        "height": 1,
                    }
                ],
            )

    visual_cluster = {"cluster_id": "visual_cluster_test", "profile": {"style_signals": ["clean"]}}
    request = GenerationRequest(
        asset_spec=AssetSpec(
            asset_id="asset_general_visual",
            asset_type=AssetType.SINGLE_IMAGE,
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="4:5",
            purpose="summer portrait continuation",
        ),
        layout_plan=LayoutPlan(
            layout_plan_id="layout_general_visual",
            asset_id="asset_general_visual",
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="4:5",
            text_rendering=TextRenderingMode.HTML_OVERLAY,
            visual_hierarchy=["main_subject", "scene_atmosphere"],
            product_area=LayoutRegion(name="subject_area", position="center_subject"),
        ),
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_general_visual",
            asset_id="asset_general_visual",
            visual_prompt="fresh summer portrait in clean daylight",
            negative_prompt="fake text",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["clean", "summer"],
            layout_notes=["center subject"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_general_visual", asset_id="asset_general_visual"),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_general_visual",
            asset_id="asset_general_visual",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_visual_cluster",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "fresh summer portrait",
            "shared_capabilities": {"visual_cluster": visual_cluster},
        },
    )
    provider = FakeProductionProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))

    response = provider.generate(request)

    output_id = response.candidates[0].metadata["output_id"]
    output_json = tmp_path / "outputs" / output_id / "output.json"
    metadata = json.loads(output_json.read_text(encoding="utf-8"))["metadata"]
    assert metadata["visual_capability_cluster"]["cluster_id"] == "visual_cluster_test"
    assert metadata["shared_capabilities"]["visual_cluster"]["cluster_id"] == "visual_cluster_test"


def test_general_public_workflow_summary_uses_neutral_language(tmp_path) -> None:
    service = V3ProductApiService()

    created = service.create_job(
        {
            "user_input": "Create a clean summer portrait cover.",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "social_cover"},
        }
    )

    assert created.general_creative is not None
    public_summary = json.dumps(created.general_creative.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "subject or style references" in public_summary
    assert "important visible details" in public_summary
    assert "product" not in public_summary


def test_general_llm_brain_fallback_metadata_uses_neutral_creative_language() -> None:
    result = build_fallback_result(
        BrainRunRequest(
            user_input=GENERAL_SUMMER_PORTRAIT_PROMPT,
            scenario_id="general_creative",
            template_id="general_template",
        )
    )

    public_and_model_facing_metadata = json.dumps(result.safe_metadata(), ensure_ascii=False).lower()
    for term in PRODUCT_TERMS:
        assert term not in public_and_model_facing_metadata
    for term in GENERAL_AD_COPY_TERMS:
        assert term not in public_and_model_facing_metadata
    assert "creative visual" in public_and_model_facing_metadata
    assert "professionally polished" in public_and_model_facing_metadata


def test_product_language_predicate_reads_chinese_product_intent() -> None:
    assert product_language_allowed(
        template_id="general_template",
        scenario_id="general_creative",
        user_input="\u505a\u4e00\u5f20\u62a4\u80a4\u54c1\u74f6\u5b50\u4e3b\u56fe",
    )
    assert not product_language_allowed(
        template_id="general_template",
        scenario_id="general_creative",
        user_input="\u521b\u5efa\u4e00\u7ec4\u4e1c\u4e9a\u5e74\u8f7b\u5973\u6027\u590f\u65e5\u5199\u771f",
    )


def test_general_template_negated_product_words_do_not_enable_product_prompting() -> None:
    user_input = (
        "\u751f\u6210\u4e00\u5f20\u590f\u65e5\u6e05\u51c9\u4e1c\u65b9\u7f8e\u5973\u5199\u771f\uff0c"
        "\u753b\u9762\u5e72\u51c0\u660e\u4eae\uff0c\u9002\u5408\u793e\u5a92\u5c01\u9762\uff0c"
        "\u4e0d\u8981\u9999\u6c34\u3001\u62a4\u80a4\u54c1\u6216\u4efb\u4f55\u5546\u54c1"
    )
    result = run_creative_planning(
        user_input,
        optional_template_id="general_template",
        runtime_metadata={
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": user_input,
        },
    )
    final_provider_prompt = _provider_prompt_for_planning_result(result)
    model_facing_text = " ".join(
        [
            result.prompt_compilations[0].visual_prompt,
            result.prompt_compilations[0].negative_prompt or "",
            " ".join(result.prompt_compilations[0].hard_constraints),
            " ".join(result.prompt_compilations[0].layout_notes),
            result.brand_profile.layout_preference or "",
            final_provider_prompt,
        ]
    ).lower()

    assert product_language_allowed(
        template_id="general_template",
        scenario_id="general_creative",
        user_input=user_input,
    ) is False
    assert result.prompt_compilations[0].metadata["product_language_allowed"] is False
    assert "creative image asset" in final_provider_prompt
    assert "commercial product image asset" not in final_provider_prompt
    assert "center product" not in model_facing_text
    assert "product label" not in model_facing_text
    assert "product identity" not in model_facing_text
    assert "\u9999\u6c34" not in result.prompt_compilations[0].visual_prompt
    assert "\u62a4\u80a4\u54c1" not in result.prompt_compilations[0].visual_prompt
    assert "unrequested retail-style props" in result.prompt_compilations[0].negative_prompt
    assert "unrequested cosmetic containers" in final_provider_prompt


def test_general_template_strips_no_product_phrasing_from_positive_direction() -> None:
    user_input = "\u590f\u65e5\u4e1c\u65b9\u5973\u6027\u5199\u771f\uff0c\u65e0\u5546\u54c1\u3001\u65e0\u5305\u88c5\u3001\u65e0\u6587\u5b57"
    result = run_creative_planning(
        user_input,
        optional_template_id="general_template",
        runtime_metadata={
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "llm_brain": {
                "enabled": True,
                "prompt_guidance": {
                    "visual_direction_addons": [
                        "\u6e05\u723d\u590f\u65e5\u4eba\u50cf\uff0c\u65e0\u5546\u54c1\u3001\u65e0\u5305\u88c5\u3001\u65e0\u6587\u5b57"
                    ],
                    "negative_prompt_addons": [],
                    "hard_constraints": [],
                },
            },
        },
    )
    final_provider_prompt = _provider_prompt_for_planning_result(result)

    assert "\u65e0\u5546\u54c1" not in result.prompt_compilations[0].visual_prompt
    assert "\u65e0\u5305\u88c5" not in result.prompt_compilations[0].visual_prompt
    assert "\u65e0\u5546\u54c1" not in final_provider_prompt
    assert "\u65e0\u5305\u88c5" not in final_provider_prompt
    assert "unrequested retail-style props" in final_provider_prompt
