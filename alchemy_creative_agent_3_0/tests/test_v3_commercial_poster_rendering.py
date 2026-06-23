from alchemy_creative_agent_3_0.app.asset_pack import render_manifest_entry
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning, run_generation_loop
from alchemy_creative_agent_3_0.app.layout_engine import build_html_render_spec, build_svg_render_spec, canvas_dimensions
from alchemy_creative_agent_3_0.app.schemas import LayoutRegion, TextRenderingMode


def test_html_render_spec_preserves_explicit_chinese_text_exactly() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”。")
    layout = result.layout_plans[0]

    spec = build_html_render_spec(layout)
    contents = [layer["content"] for layer in spec["text_layers"]]

    assert spec["renderer"] == "html_spec_renderer"
    assert spec["runtime_mode"] == "spec_only"
    assert spec["composition_output"]["format"] == "html"
    assert "冬季双人套餐 128 元" in contents
    assert "今日下单送小酥肉" in contents
    assert "冬季双人套餐 128 元" in spec["html"]
    assert "今日下单送小酥肉" in spec["html"]
    assert all(layer["editable"] is True for layer in spec["text_layers"])
    assert all(layer["preserve_exact_text"] is True for layer in spec["text_layers"])


def test_svg_render_spec_can_be_produced_from_layout_plan() -> None:
    result = run_creative_planning("做一张咖啡店海报，标题写“手作拿铁 第二杯半价”，下面写“今日到店可用”。")
    layout = result.layout_plans[0].model_copy(update={"text_rendering": TextRenderingMode.SVG_OVERLAY})

    spec = build_svg_render_spec(layout)

    assert spec["renderer"] == "svg_spec_renderer"
    assert spec["composition_output"]["format"] == "svg"
    assert "<svg" in spec["svg"]
    assert "手作拿铁 第二杯半价" in spec["svg"]
    assert "今日到店可用" in spec["svg"]
    assert spec["editable_text_layer_count"] >= 2


def test_planning_asset_pack_manifest_includes_editable_text_layers() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”。")

    manifest = result.asset_pack.manifest
    first_asset = manifest["assets"][0]
    text_layers = first_asset["editable_text_layers"]

    assert manifest["render_manifest"]["render_manifest_version"] == "v3.3-render-manifest-001"
    assert manifest["render_manifest"]["asset_count"] == len(result.layout_plans)
    assert first_asset["rendering_required"] is True
    assert first_asset["render_manifest"]["renderer"] == "html_spec_renderer"
    assert first_asset["render_manifest"]["preserves_exact_text"] is True
    assert [layer["content"] for layer in text_layers] == ["冬季双人套餐 128 元", "今日下单送小酥肉"]


def test_generated_asset_pack_keeps_render_manifest_with_selected_candidate() -> None:
    result = run_generation_loop("做一张咖啡店海报，标题写“手作拿铁 第二杯半价”，下面写“今日到店可用”。")

    first_asset = result.asset_pack.manifest["assets"][0]

    assert first_asset["selected_candidate_id"]
    assert first_asset["render_manifest"]["editable_text_layer_count"] >= 2
    assert first_asset["render_manifest"]["composition_output"]["format"] == "html"
    assert [layer["content"] for layer in first_asset["editable_text_layers"]] == ["手作拿铁 第二杯半价", "今日到店可用"]


def test_render_manifest_entry_is_serializable_and_layout_based() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")
    entry = render_manifest_entry(result.layout_plans[0])
    payload = result.asset_pack.model_dump(mode="json")

    assert entry["asset_id"] == result.layout_plans[0].asset_id
    assert entry["layout_plan_id"] == result.layout_plans[0].layout_plan_id
    assert payload["manifest"]["render_manifest"]["preserves_exact_text"] is True


def test_print_poster_render_spec_uses_a4_canvas() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”，用于打印张贴。")
    layout = result.layout_plans[0]

    spec = build_html_render_spec(layout)

    assert layout.aspect_ratio == "A4"
    assert spec["canvas"] == canvas_dimensions("A4")
    assert spec["canvas"] == {"width": 1240, "height": 1754}
    assert 'width:1240px;height:1754px' in spec["html"]


def test_same_named_distinct_reserved_regions_remain_editable_layers() -> None:
    result = run_creative_planning("做一张咖啡店海报，标题写“手作拿铁 第二杯半价”，下面写“今日到店可用”。")
    layout = result.layout_plans[0]
    extra_detail = LayoutRegion(
        name="headline_area",
        position="middle_left",
        relative_box={"x": 0.08, "y": 0.58, "w": 0.42, "h": 0.08},
        text="会员专享",
        notes="additional exact text detail",
    )
    layout = layout.model_copy(update={"reserved_text_regions": [*layout.reserved_text_regions, extra_detail]})

    spec = build_html_render_spec(layout)
    contents = [layer["content"] for layer in spec["text_layers"]]

    assert contents.count("手作拿铁 第二杯半价") == 1
    assert "会员专享" in contents
    assert spec["editable_text_layer_count"] == 3
