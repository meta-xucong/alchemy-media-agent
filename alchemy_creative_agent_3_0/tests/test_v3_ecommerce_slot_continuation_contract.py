from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "105_V3_ECOMMERCE_SLOT_CONTINUATION_AND_TEXT_PIXEL_DELIVERY_CONTRACT.md"
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"


def test_slot_continuation_contract_is_frozen_before_ui_implementation() -> None:
    contract = DOC.read_text(encoding="utf-8")
    assert "ecommerce-slots/{slot_id}/continuations" in contract
    assert "child continuation job" in contract
    assert "slot_continuation_not_supported" in contract
    assert "at most one amendment" in contract
    assert "must not render a" in contract


def test_ecommerce_workspace_has_no_premature_slot_redo_control() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "ecommerce-slots" not in source
    assert "重做这张" not in source
    assert "重做这张" not in html
