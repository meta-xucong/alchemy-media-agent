from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.creative_core.prompt_language import split_positive_and_negative_prompt
from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    ProviderStrategy,
)


COMPLEX_FOUNTAIN_PROMPT = """
傍晚城市喷泉广场，一位年轻中国女性站在喷泉边缘的石台上，身体微微前倾，低头看向水面，一只手自然伸出轻触喷泉水流，水珠从指尖溅落形成细碎水花。她另一只手自然垂在身侧，姿态放松安静，神情温柔专注。

穿浅奶油黄色细肩带薄纱连衣裙，裙摆轻盈半透，随微风轻轻飘动，赤脚站在微湿的石面上。黑色中短发自然蓬松，被夜晚微风吹起几缕碎发，佩戴小巧耳坠与细项链。

背景是傍晚的城市公园喷泉池，周围有儿童嬉戏、模糊的人群与暖色灯光，喷泉水柱在右侧形成柔和动态水雾。远处树影与建筑灯光虚化成柔焦光斑。

低机位侧前方抓拍，35mm纪实人像风格，浅景深，人物为视觉中心，背景略虚化但保留环境氛围。整体色调为蓝灰夜色与暖黄色灯光交织，带轻微湿润空气感与胶片颗粒质感，真实自然摄影风格，竖版3:4。

负面提示词：

韩系水光肌，油亮脸，鼻尖高光，硅胶脸，过度磨皮，浓妆，塑料质感，过曝喷泉水流，水花形态异常，手指畸形，裙子结构错误，人物比例失真，强HDR，过度锐化，动漫，插画，CG，3D渲染。
""".strip()


def test_doc74_splits_chinese_negative_prompt_section() -> None:
    positive, negatives = split_positive_and_negative_prompt(COMPLEX_FOUNTAIN_PROMPT)

    assert "傍晚城市喷泉广场" in positive
    assert "轻触喷泉水流" in positive
    assert "负面提示词" not in positive
    assert "韩系水光肌" in negatives
    assert "手指畸形" in negatives
    assert "3D渲染" in negatives


def test_doc74_complex_prompt_compilation_keeps_details_and_negative_clean() -> None:
    result = run_creative_planning(COMPLEX_FOUNTAIN_PROMPT)
    prompt = result.prompt_compilations[0]
    text = " ".join([prompt.visual_prompt, *prompt.hard_constraints])

    assert "傍晚城市喷泉广场" in prompt.visual_prompt
    assert "喷泉边缘的石台" in prompt.visual_prompt
    assert "轻触喷泉水流" in prompt.visual_prompt
    assert "浅奶油黄色细肩带薄纱连衣裙" in prompt.visual_prompt
    assert "35mm纪实人像风格" in prompt.visual_prompt
    assert "竖版3:4" in prompt.visual_prompt
    assert "韩系水光肌" not in prompt.visual_prompt
    assert "手指畸形" not in prompt.visual_prompt
    assert "韩系水光肌" in prompt.negative_prompt
    assert "手指畸形" in prompt.negative_prompt
    assert "裙子结构错误" in prompt.negative_prompt
    assert "3d渲染" in prompt.negative_prompt.lower()
    assert "Preserve the user's detailed scene literally" in text
    assert "Treat the explicit negative prompt section only as things to avoid" in text
    assert prompt.metadata["complex_prompt_fidelity"] is True
    assert "韩系水光肌" in prompt.metadata["explicit_negative_prompt_parts"]


def test_doc74_fallback_brain_does_not_reinsert_negative_section_into_positive_direction() -> None:
    result = build_fallback_result(
        BrainRunRequest(
            user_input=COMPLEX_FOUNTAIN_PROMPT,
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=2,
            requested_image_size="1024x1536",
            metadata={"variation_mode": "selection_candidates"},
        )
    )

    optimized = result.prompt_guidance.optimized_direction

    assert "傍晚城市喷泉广场" in optimized
    assert "负面提示词" not in optimized
    assert "韩系水光肌" not in optimized
    assert "手指畸形" not in optimized


def test_doc74_final_provider_prompt_keeps_negatives_only_in_avoid_section() -> None:
    result = run_creative_planning(COMPLEX_FOUNTAIN_PROMPT)
    prompt = result.prompt_compilations[0]
    asset = AssetSpec(
        asset_id=prompt.asset_id,
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="complex portrait prompt validation",
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc74", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc74",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc74",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": COMPLEX_FOUNTAIN_PROMPT,
        },
    )

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001
    positive_region = final_prompt.split("\nAvoid:", 1)[0]

    assert "傍晚城市喷泉广场" in positive_region
    assert "轻触喷泉水流" in positive_region
    assert "负面提示词" not in positive_region
    assert "韩系水光肌" not in positive_region
    assert "手指畸形" not in positive_region
    assert "Avoid:" in final_prompt
    assert "韩系水光肌" in final_prompt
    assert "手指畸形" in final_prompt
