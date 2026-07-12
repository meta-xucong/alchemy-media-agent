from alchemy_creative_agent_3_0.app.asset_pack import render_manifest_entry
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning, run_generation_loop
from alchemy_creative_agent_3_0.app.schemas import TextRenderingMode


def test_explicit_copy_uses_provider_native_complete_image_contract() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”。")
    layout = result.layout_plans[0]
    prompt = result.prompt_compilations[0]

    assert layout.text_rendering == TextRenderingMode.MODEL_TEXT_ALLOWED
    assert layout.reserved_text_regions == []
    assert layout.headline_area is None
    assert layout.cta_area is None
    assert layout.metadata["provider_native_literal_text"] == ["冬季双人套餐 128 元", "今日下单送小酥肉"]
    assert prompt.provider_notes["text_rendering_owner"] == "image_provider"
    assert prompt.provider_notes["text_overlay_required"] is False
    assert '"冬季双人套餐 128 元"' in prompt.visual_prompt
    assert '"今日下单送小酥肉"' in prompt.visual_prompt


def test_render_manifest_has_no_editable_external_text_layers_for_new_jobs() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”。")
    entry = render_manifest_entry(result.layout_plans[0])
    manifest = result.asset_pack.manifest

    assert entry["renderer"] == "image_provider"
    assert entry["runtime_mode"] == "provider_native_complete_image"
    assert entry["editable_text_layer_count"] == 0
    assert entry["composition_output"]["post_generation_overlay_allowed"] is False
    assert manifest["assets"][0]["rendering_required"] is False
    assert manifest["render_manifest"]["editable_text_layer_count"] == 0


def test_generation_keeps_provider_native_text_as_one_complete_image() -> None:
    result = run_generation_loop("做一张咖啡店海报，标题写“手作拿铁 第二杯半价”。")
    first_asset = result.asset_pack.manifest["assets"][0]

    assert first_asset["selected_candidate_id"]
    assert first_asset["render_manifest"]["renderer"] == "image_provider"
    assert first_asset["render_manifest"]["editable_text_layers"] == []
    assert first_asset["render_manifest"]["composition_output"]["owner"] == "image_provider"


def test_no_text_request_does_not_create_an_external_render_contract() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")
    layout = result.layout_plans[0]
    entry = render_manifest_entry(layout)

    assert layout.text_rendering == TextRenderingMode.NO_TEXT
    assert entry["renderer"] == "image_provider"
    assert entry["editable_text_layers"] == []
