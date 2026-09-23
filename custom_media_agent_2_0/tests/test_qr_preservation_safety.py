"""QR is an explicitly authorized enhancement; failures preserve input bytes."""
import base64
import io
from unittest.mock import Mock

import pytest
import qrcode
from PIL import Image, ImageChops

from app.repositories.memory import utc_now
from app.schemas import ImageOutput
from app.services import qr_preservation as qr, output_storage as storage


def encoded(image, fmt="PNG", **kwargs):
    stream = io.BytesIO()
    image.save(stream, format=fmt, **kwargs)
    return stream.getvalue()


@pytest.fixture
def case(tmp_path, monkeypatch):
    payload = "https://example.test/qr/exact?item=1"
    source = qrcode.make(payload).convert("RGB")
    path = tmp_path / "reference.png"
    source.save(path)
    monkeypatch.setattr(qr, "uploaded_asset_path", lambda asset_id: path if asset_id == "source" else None)
    metadata = {"input_images": [{"asset_id": "source"}], "orchestrator_task_intent": {
        "slot_plan": [{"slot": "qr_code", "rule": "bottom_right", "target_surface": "poster"}]}}
    return encoded(Image.new("RGB", (1024, 1024), (78, 103, 147))), metadata, payload

@pytest.mark.parametrize("value", [False, None, "false", "true", 0, 1, [], {}])
def test_disabled_helper_never_reads_assets_or_pixels(case, monkeypatch, value):
    content, metadata, _ = case
    metadata.update({"user_prompt": "Do not invent QR codes", "qr_preservation_enabled": True})
    monkeypatch.setattr(qr, "uploaded_asset_path", Mock(side_effect=AssertionError("source read")))
    monkeypatch.setattr(qr, "_detect_qr_bbox", Mock(side_effect=AssertionError("QR detection")))
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=value)
    assert result.content == content


def test_old_metadata_and_negative_prompt_do_not_enable_qr(case, monkeypatch):
    content, metadata, _ = case
    metadata.update({"user_prompt": "Do not invent QR codes", "qr_preservation_enabled": True,
        "provider_input_plan": {"negative_prompt": "QR code"}})
    monkeypatch.setattr(qr, "_first_qr_crop", Mock(side_effect=AssertionError("QR activated")))
    assert qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png").content == content


def test_bbox_without_decode_never_becomes_preservation_crop(case, monkeypatch):
    content, metadata, _ = case
    monkeypatch.setattr(qr, "_detect_qr_bbox", lambda image: ((40, 40, 180, 180), ""))
    monkeypatch.setattr(qr, "_paste_qr_crop", Mock(side_effect=AssertionError("paste")))
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False

def test_real_source_is_readable_after_encoding_and_second_call_is_noop(case, monkeypatch):
    content, metadata, payload = case
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.metadata["applied"] is True
    assert result.metadata["verified_decoded"] is True
    before = Image.open(io.BytesIO(content)).convert("RGBA")
    after = Image.open(io.BytesIO(result.content)).convert("RGBA")
    box = tuple(result.metadata["paste_box"])
    assert qr._detect_qr_bbox(after.crop(box))[1] == payload
    difference = ImageChops.difference(before, after)
    difference.paste((0, 0, 0, 0), box)
    assert all(band.getbbox() is None for band in difference.split())
    monkeypatch.setattr(qr, "_paste_qr_crop", Mock(side_effect=AssertionError("duplicate paste")))
    second = qr.preserve_requested_qr_code(content=result.content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert second.content == result.content
    assert second.metadata["reason"] == "already_satisfied"


def test_unverified_composition_returns_original_bytes(case, monkeypatch):
    content, metadata, _ = case
    monkeypatch.setattr(qr, "_composed_qr_decodes", lambda *args: False)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False
    assert result.metadata["reason"] == "postprocess_verification_failed"

@pytest.mark.parametrize("slots", [[], [{"slot": "logo", "rule": "top_left"}],
    [{"slot": "qr_code", "rule": "top_left", "target_surface": "packaging"}]])
def test_unbound_or_product_surface_target_is_not_a_corner_sticker(case, slots):
    content, metadata, _ = case
    metadata["user_prompt"] = "Logo top left. Keep packaging QR in its original position."
    metadata["orchestrator_task_intent"]["slot_plan"] = slots
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False


def test_qr_elsewhere_does_not_certify_an_empty_target(case):
    _, metadata, payload = case
    image = Image.new("RGB", (1024, 1024), "white")
    image.paste(qrcode.make(payload).convert("RGB"), (20, 20))
    assert qr._composed_qr_decodes(image, (700, 700, 1000, 1000), payload) is False


def test_source_exception_is_optional_not_a_generation_error(case, monkeypatch):
    content, metadata, _ = case
    monkeypatch.setattr(qr, "_first_qr_crop", Mock(side_effect=RuntimeError("source failed")))
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False

def test_storage_ignores_provider_metadata_flag_and_still_saves_previews(case, tmp_path, monkeypatch):
    content, metadata, _ = case
    from app.config import settings
    old = settings.storage_dir
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(storage, "preserve_requested_qr_code", Mock(side_effect=AssertionError("QR helper called")))
    metadata["qr_preservation_enabled"] = True
    metadata["pixel_preservation"] = {"qr_code": {"applied": True}}
    try:
        output = ImageOutput(output_id="out_disabled", job_id="job_test", url="", created_at=utc_now(), metadata=metadata)
        saved = storage.save_provider_output(job_id="job_test", output=output,
            encoded=base64.b64encode(content).decode(), output_format="png", mime_type="image/png")
        from pathlib import Path
        assert Path(saved.metadata["storage_path"]).read_bytes() == content
        assert Path(saved.metadata["thumbnail_path"]).exists()
        assert Path(saved.metadata["preview_path"]).exists()
        assert saved.metadata["qr_preservation_enabled"] is False
        assert not (saved.metadata.get("pixel_preservation") or {}).get("qr_code", {}).get("applied")
    finally:
        object.__setattr__(settings, "storage_dir", old)


def test_jpeg_is_retained_without_lossy_recompression(case):
    content, metadata, _ = case
    jpeg = encoded(Image.open(io.BytesIO(content)), "JPEG")
    result = qr.preserve_requested_qr_code(content=jpeg, metadata=metadata,
        output_format="jpeg", mime_type="image/jpeg", _qr_preservation_enabled=True)
    assert result.content == jpeg

def test_final_encoded_pixels_not_in_memory_candidate_are_verified(case, monkeypatch):
    content, metadata, _ = case
    original_save = Image.Image.save
    def discard_overlay(image, fp, *args, **kwargs):
        # Simulate an encoder producing a readable image with no retained QR.
        return original_save(Image.open(io.BytesIO(content)), fp, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "save", discard_overlay)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["reason"] == "postprocess_verification_failed"


def test_changes_outside_authorized_area_are_rejected(case, monkeypatch):
    content, metadata, _ = case
    original = qr._paste_qr_crop
    def wrong_pixel(*args, **kwargs):
        image, box = original(*args, **kwargs)
        image.putpixel((0, 0), (255, 255, 255, 255))
        return image, box
    monkeypatch.setattr(qr, "_paste_qr_crop", wrong_pixel)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["reason"] == "image_invariant_failed"

@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_supported_lossless_formats_preserve_transparency(case, fmt):
    _, metadata, _ = case
    baseline = Image.new("RGBA", (1024, 1024), (40, 50, 60, 87))
    content = encoded(baseline, fmt, **({"lossless": True, "exact": True} if fmt == "WEBP" else {}))
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format=fmt.lower(), mime_type=f"image/{fmt.lower()}", _qr_preservation_enabled=True)
    assert result.metadata["applied"] is True
    final = Image.open(io.BytesIO(result.content)).convert("RGBA")
    assert final.getpixel((0, 0)) == baseline.getpixel((0, 0))


def test_multiple_source_assets_are_not_silently_first_matched(case):
    content, metadata, _ = case
    metadata["input_images"].append({"asset_id": "other"})
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["reason"] == "source_ambiguous"


def test_cancellation_is_not_swallowed(case, monkeypatch):
    content, metadata, _ = case
    monkeypatch.setattr(qr, "_first_qr_crop", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        qr.preserve_requested_qr_code(content=content, metadata=metadata,
            output_format="png", mime_type="image/png", _qr_preservation_enabled=True)

def test_qr_exception_keeps_valid_prior_text_overlay(case, tmp_path, monkeypatch):
    from pathlib import Path
    from app.config import settings
    content, metadata, _ = case
    overlay = encoded(Image.new("RGB", (1024, 1024), (60, 90, 120)))
    old = settings.storage_dir
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(storage, "apply_deterministic_text_overlay", lambda *a, **k: (overlay, {"applied": True}))
    monkeypatch.setattr(storage, "preserve_requested_qr_code", Mock(side_effect=RuntimeError("QR decoder unavailable")))
    try:
        output = ImageOutput(output_id="out_overlay", job_id="job_test", url="", created_at=utc_now(), metadata=metadata)
        saved = storage.save_provider_output(job_id="job_test", output=output, encoded=base64.b64encode(content).decode(),
            output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
        assert Path(saved.metadata["storage_path"]).read_bytes() == overlay
        assert saved.metadata["deterministic_text_overlay"]["applied"] is True
        assert saved.metadata["pixel_preservation"]["qr_code"]["applied"] is False
    finally:
        object.__setattr__(settings, "storage_dir", old)


def test_invalid_detected_geometry_does_not_produce_a_crop(case, monkeypatch):
    content, metadata, payload = case
    monkeypatch.setattr(qr, "_detect_qr_bbox", lambda image: ((-8, 20, 5000, 5000), payload))
    monkeypatch.setattr(qr, "_expand_bbox", Mock(side_effect=AssertionError("crop attempted")))
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["reason"] == "crop_invalid"

def test_multiple_codes_inside_one_reference_are_not_first_matched(case, tmp_path, monkeypatch):
    content, metadata, payload = case
    source = Image.new("RGB", (1000, 600), "white")
    source.paste(qrcode.make(payload).convert("RGB"), (20, 20))
    source.paste(qrcode.make("https://example.test/other").convert("RGB"), (550, 100))
    path = tmp_path / "multiple.png"
    source.save(path)
    monkeypatch.setattr(qr, "uploaded_asset_path", lambda _: path)
    result = qr.preserve_requested_qr_code(content=content, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == content
    assert result.metadata["applied"] is False


@pytest.mark.parametrize("orientation", [2, 6, 8])
def test_exif_transform_is_not_silently_applied_to_the_whole_image(case, orientation):
    content, metadata, _ = case
    image = Image.open(io.BytesIO(content))
    exif = image.getexif()
    exif[274] = orientation
    baseline = encoded(image, exif=exif)
    result = qr.preserve_requested_qr_code(content=baseline, metadata=metadata,
        output_format="png", mime_type="image/png", _qr_preservation_enabled=True)
    assert result.content == baseline
    assert result.metadata["reason"] == "image_invariant_failed"

def test_provider_and_request_metadata_cannot_enable_qr_in_generation(case, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    from app.config import settings
    from app.schemas import CreateImageJobRequest, ImagePromptPlan
    from app.services.generation import _job_from_result
    content, metadata, _ = case
    metadata.update({"qr_preservation_enabled": True, "pixel_preservation": {"qr_code": {"applied": True}}})
    request = CreateImageJobRequest(prompt_plan=ImagePromptPlan(plan_id="plan", mode="smart_enhance",
        prompt="Clean product photo", user_variables={"qr_preservation_enabled": True}))
    result = SimpleNamespace(provider="fixture", model="fixture", raw_response_summary={}, outputs=[SimpleNamespace(
        metadata=metadata, b64_json=base64.b64encode(content).decode(), format="png", mime_type="image/png")])
    old = settings.storage_dir
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(storage, "preserve_requested_qr_code", Mock(side_effect=AssertionError("unauthorized QR")))
    try:
        job = _job_from_result(request, result, job_id="job_closed", created_at=utc_now())
        saved = job.outputs[0]
        assert saved.metadata["qr_preservation_enabled"] is False
        assert Path(saved.metadata["storage_path"]).read_bytes() == content
        assert not (saved.metadata.get("pixel_preservation") or {}).get("qr_code", {}).get("applied")
    finally:
        object.__setattr__(settings, "storage_dir", old)

def test_core_storage_failure_is_not_hidden_by_optional_qr(case, tmp_path, monkeypatch):
    from pathlib import Path
    from app.config import settings
    content, metadata, _ = case
    old = settings.storage_dir
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(Path, "write_bytes", Mock(side_effect=PermissionError("disk unwritable")))
    try:
        output = ImageOutput(output_id="out_disk", job_id="job_test", url="", created_at=utc_now(), metadata=metadata)
        with pytest.raises(PermissionError):
            storage.save_provider_output(job_id="job_test", output=output, encoded=base64.b64encode(content).decode(),
                output_format="png", mime_type="image/png")
    finally:
        object.__setattr__(settings, "storage_dir", old)
