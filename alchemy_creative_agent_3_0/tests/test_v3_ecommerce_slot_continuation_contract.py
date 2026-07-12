from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "105_V3_ECOMMERCE_SLOT_CONTINUATION_AND_TEXT_PIXEL_DELIVERY_CONTRACT.md"
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"


def test_slot_continuation_contract_remains_the_ui_authority() -> None:
    contract = DOC.read_text(encoding="utf-8")
    assert "ecommerce-slots/{slot_id}/continuations" in contract
    assert "child continuation job" in contract
    assert "slot_continuation_not_supported" in contract
    assert "at most one amendment" in contract
    assert "must not render a" in contract


def test_ecommerce_workspace_exposes_only_a_runtime_backed_slot_redo_control() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "function v3EcommerceSlotContinuationContext(item, job = v3State.currentJob)" in source
    assert "if (!v3IsEcommerceJob(job)) return null;" in source
    assert 'String(job?.status || "").trim() !== "generated"' in source
    assert "function v3EcommerceSlotContinuationRoute(context)" in source
    assert "function v3EcommerceSlotDeliveryRoute(context)" in source
    assert "async function continueV3EcommerceSlot(item, job = v3State.currentJob)" in source
    assert "runV3GenerationWithRecovery({" in source
    assert "ecommerce_slot_continuation: true" in source
    assert 'data-v3-result-action="ecommerce_slot_continuation"' in source
    assert "重做这张" in source
    continuation_block = source[source.index("async function continueV3EcommerceSlot") : source.index("async function runV3GenerationWithRecovery")]
    assert "new_evidence_asset_ids" not in continuation_block
    assert "重做这张" not in html
