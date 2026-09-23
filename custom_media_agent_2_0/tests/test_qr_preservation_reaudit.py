"""Adversarial audit of QR authority and image-preservation boundaries."""
import io
import json
import struct
from pathlib import Path
from unittest.mock import Mock

import pytest
import qrcode
from PIL import Image, PngImagePlugin

from app.schemas import CreateCreativeRunRequest, CaseRetrievalPlan
from app.services import claude_orchestrator as brain, qr_preservation as qr
from test_qr_preservation_safety import case, encoded
from test_qr_preservation_decision_flow import decision


@pytest.mark.parametrize("field,before,after", [
    ("notes", "Preserve the reference QR.", "Do not retain any QR."),
    ("reference_mode", "preserve", "style_only"),
])
def test_exact_cache_binds_current_user_asset_instructions(monkeypatch, field, before, after):
    monkeypatch.setattr(brain, "get_uploaded_asset", lambda _: None)
    make = lambda value: CreateCreativeRunRequest.model_validate({
        "user_prompt": "Follow my current asset instructions.",
        "assets": [{"asset_id": "source", field: value}],
    })
    kwargs = {"fallback_mode": "smart_enhance", "fallback_retrieval_plan": CaseRetrievalPlan(query_text="product"), "candidate_cases": []}
    assert brain._cache_key(request=make(before), **kwargs) != brain._cache_key(request=make(after), **kwargs)

@pytest.mark.parametrize("stage", ["inline", "intent", "intent_micro"])
def test_user_asset_notes_reach_brain_without_becoming_automatic_asset_facts(tmp_path, stage):
    notes = "Keep the existing source QR only; never invent a different code."
    request = {"user_prompt": "Follow my asset notes.", "assets": [{"asset_id": "source", "notes": notes, "reference_mode": "preserve"}]}
    (tmp_path / "context.json").write_text(json.dumps({"request": request}), encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text(json.dumps([{"asset_id": "source", "brief": {"visual_summary": "QR-like decoration"}}]), encoding="utf-8")
    prompt = brain._build_inline_json_prompt(tmp_path) if stage == "inline" else brain._build_checkpoint_stage_prompt(tmp_path, stage_name=stage)
    payload = json.loads(prompt.split("\n", 1)[1])
    assert payload["user_asset_instructions"] == request["assets"]


@pytest.mark.parametrize("intent_permission", [False, None, "true", 1])
def test_compressed_final_stage_cannot_invent_permission_missing_from_full_intent(intent_permission):
    raw = {"mode": "smart_enhance", "final_prompt": "Preserve a reference product in a clean photograph.", "qr_preservation_enabled": True}
    value = brain._compress_checkpoint_decision(raw, intent={"qr_preservation_enabled": intent_permission}, visual_strategy={}, fallback=decision())
    assert value["qr_preservation_enabled"] is False


def test_intent_boolean_reaches_compact_checkpoint():
    data = brain._compact_generation_checkpoints({"intent": {"qr_preservation_enabled": False}})
    assert data["intent"]["qr_preservation_enabled"] is False
    assert "qr_preservation_enabled" in brain.CLAUDE_INTENT_CHECKPOINT_SCHEMA["properties"]
    assert "qr_preservation_enabled" not in brain.CLAUDE_INTENT_CHECKPOINT_SCHEMA["required"]

def test_all_existing_search_zones_are_checked_for_distinct_source_codes(monkeypatch):
    results = iter([None, ((1, 1, 31, 31), "first"), ((1, 1, 31, 31), "second")])
    monkeypatch.setattr(qr, "_detect_qr_bbox_on_image", lambda *a, **k: next(results))
    monkeypatch.setattr(qr, "_qr_search_zones", lambda size: [(0, 0, 40, 40), (50, 50, 90, 90)])
    with pytest.raises(qr._QrSkip):
        qr._detect_qr_bbox(Image.new("RGB", (100, 100)))


def test_ambiguous_target_is_not_treated_as_an_empty_slot(case, monkeypatch):
    content, metadata, _ = case
    source = qr._first_qr_crop(metadata["input_images"])
    monkeypatch.setattr(qr, "_first_qr_crop", lambda _: source)
    monkeypatch.setattr(qr, "_detect_qr_bbox", Mock(side_effect=qr._QrSkip("source_ambiguous")))
    paste = Mock(side_effect=AssertionError("ambiguous target was overwritten"))
    monkeypatch.setattr(qr, "_paste_qr_crop", paste)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata, output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    paste.assert_not_called()
    assert result.content == content
    assert result.metadata["applied"] is False


def test_invisible_source_pixels_do_not_prove_a_visible_original_qr(case, tmp_path, monkeypatch):
    content, metadata, payload = case
    invisible = qrcode.make(payload).convert("RGBA")
    invisible.putalpha(0)
    path = tmp_path / "invisible.png"
    invisible.save(path)
    monkeypatch.setattr(qr, "uploaded_asset_path", lambda _: path)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata, output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False


@pytest.mark.parametrize("chunk,value", [(b"gAMA", struct.pack(">I", 100000)), (b"sRGB", b"\x00")])
def test_png_rendering_metadata_must_not_disappear_from_accepted_output(case, chunk, value):
    content, metadata, _ = case
    info = PngImagePlugin.PngInfo()
    info.add(chunk, value)
    baseline = encoded(Image.open(io.BytesIO(content)), pnginfo=info)
    result = qr.preserve_requested_qr_code(content=baseline, metadata=metadata, output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    if result.metadata["applied"] is True:
        original = Image.open(io.BytesIO(baseline))
        final = Image.open(io.BytesIO(result.content))
        for key in ("gamma", "srgb"):
            assert final.info.get(key) == original.info.get(key)
    else:
        assert result.content == baseline

def test_no_source_checkpoint_omits_optional_qr_placeholder(tmp_path):
    (tmp_path / "context.json").write_text(json.dumps({"request": {"user_prompt": "A quiet landscape."}}), encoding="utf-8")
    payload = json.loads(brain._build_checkpoint_stage_prompt(tmp_path, stage_name="intent").split("\n", 1)[1])
    assert "qr_preservation_enabled" not in payload["json_skeleton"]
    assert "qr_preservation_enabled" not in brain.CLAUDE_INTENT_CHECKPOINT_SCHEMA["required"]


def test_explicit_intent_and_final_confirmation_keep_positive_capability():
    raw = {"mode": "smart_enhance", "final_prompt": "A product photo retaining its original reference QR.", "qr_preservation_enabled": True}
    compact = brain._compact_generation_checkpoints({"intent": {"qr_preservation_enabled": True}})
    value = brain._compress_checkpoint_decision(raw, intent=compact["intent"], visual_strategy={}, fallback=decision())
    assert value["qr_preservation_enabled"] is True

def test_retired_whitening_and_relocation_code_is_removed():
    # These were unreachable after opt-in repair; keep them out of future fallbacks.
    for name in ("_information_integrity_active", "_paste_qr_crop_to_bbox",
        "_placeholder_safe_for_qr", "_cover_bbox_with_light_card", "_compose_qr_crop_at_bbox",
        "_resize_qr_crop_for_decoding", "_qr_size_candidates", "_resize_preserving_aspect"):
        assert not hasattr(qr, name)


def test_invalid_internal_placement_cannot_fall_back_to_a_corner():
    with pytest.raises(KeyError):
        qr._placement_xy((1024, 1024), (200, 200), padding=12, margin=40, placement="unknown")

def test_unique_current_reference_is_bound_by_server_not_model_identifier():
    from app.services.prompting import _task_intent_payload
    from test_qr_preservation_decision_flow import decision
    model = decision(qr_preservation_enabled=True, task_intent={'slot_plan': [{
        'slot': 'qr_code', 'rule': 'bottom_right', 'target_surface': 'poster',
        'source_asset_id': 'not-a-real-asset-id'}]})
    context = {'uploaded_assets': [{'asset_id': 'current'}],
        'provider_input_images': [{'asset_id': 'current'}]}
    projected = _task_intent_payload(model, asset_context=context)
    assert projected['slot_plan'][0]['source_asset_id'] == 'current'
    assert model.task_intent.slot_plan[0]['source_asset_id'] == 'not-a-real-asset-id'


@pytest.mark.parametrize('uploads,inputs,enabled', [
    (['first', 'second'], ['first', 'second'], True),
    (['first', 'second'], ['first'], True),
    (['first'], ['second'], True),
    (['first'], ['first'], False),
    ([], [], True),
])
def test_server_single_reference_binding_never_selects_or_grants_authority(uploads, inputs, enabled):
    from app.services.prompting import _task_intent_payload
    from test_qr_preservation_decision_flow import decision
    model = decision(qr_preservation_enabled=enabled, task_intent={'slot_plan': [{
        'slot': 'qr_code', 'rule': 'bottom_right', 'target_surface': 'poster', 'source_asset_id': 'original'}]})
    context = {'uploaded_assets': [{'asset_id': value} for value in uploads],
        'provider_input_images': [{'asset_id': value} for value in inputs]}
    assert _task_intent_payload(model, asset_context=context)['slot_plan'][0]['source_asset_id'] == 'original'
