"""Bounded real-profile protocol fixtures, never real account/tool acceptance."""

from dataclasses import replace
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random

from PIL import Image
import pytest

from test_render_bridge_native_planning import (
    _create, _new_target, _upload_reference, planning_fixture,  # noqa: F401
)
from test_render_bridge_native_registration import (
    _forbidden, _receipt, _register, native_fixture, target_fixture,  # noqa: F401
)
from alchemy_creative_agent_3_0.app.generation_router.render_bridge_provider import (
    RENDER_BRIDGE_PROFILES, RenderBridgePlanIdentity, RenderBridgeRegistration,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import SelectResultRequest
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import BridgeNativeFacadeError
from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import NativeRenderBridgeGateway


@pytest.fixture
def options_fixture(planning_fixture):
    fixture = planning_fixture
    fixture.gateway = NativeRenderBridgeGateway(
        facade=fixture.facade, service=fixture.service, project_service=fixture.project_service,
        journal_root=fixture.journal_root, enabled=True, allowed_profiles=RENDER_BRIDGE_PROFILES,
    )
    return fixture


def _image(output_format, *, noise=False):
    buffer = BytesIO()
    pixels = (Image.frombytes("RGB", (1024, 1024), random.Random(7).randbytes(1024 * 1024 * 3))
              if noise else Image.new("RGB", (1024, 1024), "blue"))
    pixels.save(buffer, format=output_format.upper())
    return buffer.getvalue()


def _planned(fixture, profile="codex-image", output_format="png", **kwargs):
    bound = _new_target(fixture, _create(
        fixture, execution_profile_id=profile, output_format=output_format, **kwargs,
    ))
    frozen = bound.gateway.prepare(7, bound.target, execution_profile_id=profile)
    return bound, frozen


@pytest.mark.parametrize("profile", RENDER_BRIDGE_PROFILES)
@pytest.mark.parametrize("output_format", ["png", "jpeg"])
def test_profile_format_originals_register_once_and_remain_review_only(options_fixture, profile, output_format):
    bound, frozen = _planned(options_fixture, profile, output_format)
    content = _image(output_format)
    assert frozen["image_options"]["output_format"] == output_format
    assert frozen["execution_profile_id"] == profile
    assert frozen["test_fixture"] is (profile == "fake-image")
    receipt = _receipt(bound, frozen, content=content, execution_profile_id=profile)
    accepted = _register(bound, **receipt)
    assert accepted["status"] == "registered"
    assert accepted["formal_delivery"] is False
    assert accepted["test_fixture"] is (profile == "fake-image")
    assert accepted["original_sha256"] == accepted["normalized_sha256"] == hashlib.sha256(content).hexdigest()
    for _ in range(5):
        assert _register(bound, **receipt) == accepted
    assert bound.gateway.registration_status(7, bound.target, import_key=receipt["import_key"]) == accepted
    output = bound.outputs.get_output(accepted["native_registration_ref"])
    assert Path(output.file_path).read_bytes() == content
    assert output.output_format == output_format
    assert output.mime_type == f"image/{output_format}"
    assert Path(output.file_path).suffix == (".jpg" if output_format == "jpeg" else ".png")
    record = bound.jobs.get(bound.target.job_id)
    result = record.generation_result
    assert result.asset_pack.assets[0].metadata["selected_candidate_is_mock"] is (profile == "fake-image")
    metadata = result.metadata["render_bridge_registration"]
    if profile != "fake-image":
        assert metadata["development_only"] is True
        assert metadata["real_tool_verified"] is False
    else:
        assert "development_only" not in metadata
        assert "real_tool_verified" not in metadata
    delivery, output_ids, asset_ids = bound.service._public_final_delivery_projection(result)
    assert delivery["final_delivery_status"] == (
        "withheld_test_fixture" if profile == "fake-image" else "withheld_bridge_development"
    )
    assert output_ids == asset_ids == set()
    assert not delivery["automatic_delivery_available"]
    assert record.selected_result is None
    assert len(bound.planning_calls) == len(bound.outputs.list_by_job(bound.target.job_id)) == len(bound.reviews) == 1
    assert bound.review_only_calls == [True]
    bound.debit.assert_not_called()
    bound.usage.assert_not_called()


@pytest.mark.parametrize("profile", ["codex-image", "midjourney-manual"])
def test_real_development_result_cannot_select_export_or_gain_formal_review_authority(options_fixture, profile):
    bound, frozen = _planned(options_fixture, profile, "jpeg")
    accepted = _register(bound, **_receipt(bound, frozen, content=_image("jpeg"), execution_profile_id=profile))
    output = bound.outputs.get_output(accepted["native_registration_ref"])
    for request in (SelectResultRequest(), SelectResultRequest(selected_candidate_ids=[output.candidate_id]),
                    SelectResultRequest(selected_asset_ids=[output.asset_id])):
        selection = bound.service.select_result(bound.target.job_id, request)
        assert selection.metadata["selection_held"] is True
        assert bound.jobs.get(bound.target.job_id).selected_result is None
    export = bound.service.export_job(bound.target.job_id)
    assert output.output_id not in json.dumps(export.manifest)


@pytest.mark.parametrize("profile", ["codex-image", "midjourney-manual", "unknown-profile"])
def test_default_allowlist_blocks_profiles_before_brain(planning_fixture, profile):
    with pytest.raises(BridgeNativeFacadeError, match="profile"):
        _create(planning_fixture, execution_profile_id=profile)
    assert planning_fixture.planning_calls == []
    assert not planning_fixture.journal_root.exists()


def test_native_gate_and_profile_allowlist_are_independent(options_fixture):
    fixture = options_fixture
    fixture.gateway.enabled = False
    with pytest.raises(BridgeNativeFacadeError, match="disabled"):
        _create(fixture, execution_profile_id="codex-image")
    assert fixture.planning_calls == []
    with pytest.raises(ValueError, match="allowed_profiles_invalid"):
        NativeRenderBridgeGateway(facade=fixture.facade, service=fixture.service,
                                  journal_root=fixture.journal_root, allowed_profiles=("unknown",))


@pytest.mark.parametrize("option", [{"execution_profile_id": "midjourney-manual"}, {"output_format": "jpeg"}])
def test_plan_key_binds_profile_and_format(options_fixture, option):
    _create(options_fixture, execution_profile_id="codex-image")
    with pytest.raises(BridgeNativeFacadeError, match="plan_key_conflict"):
        _create(options_fixture, **{"execution_profile_id": "codex-image", **option})
    assert len(options_fixture.planning_calls) == 1


def test_prepare_and_receipt_cannot_substitute_another_allowed_profile(options_fixture):
    bound, frozen = _planned(options_fixture)
    with pytest.raises(BridgeNativeFacadeError, match="profile_binding_mismatch"):
        bound.gateway.prepare(7, bound.target, execution_profile_id="midjourney-manual")
    with pytest.raises(BridgeNativeFacadeError, match="profile_binding_mismatch"):
        _register(bound, **_receipt(bound, frozen, execution_profile_id="midjourney-manual"))
    assert bound.outputs.list_by_job(bound.target.job_id) == []


def test_real_profile_plan_response_loss_recovers_bound_jpeg_without_second_brain_call(options_fixture, monkeypatch):
    fixture = options_fixture
    original = fixture.service.create_render_bridge_plan

    def lose_response(**kwargs):
        original(**kwargs)
        raise TimeoutError("fixture loses durable plan response")

    monkeypatch.setattr(fixture.service, "create_render_bridge_plan", lose_response)
    assert _create(fixture, execution_profile_id="codex-image", output_format="jpeg")["status"] == "plan_unknown"
    monkeypatch.setattr(fixture.service, "create_render_bridge_plan", original)
    recovered = fixture.gateway.plan_status(7, fixture.project.project_id, "native-plan-key")
    bound = _new_target(fixture, recovered)
    frozen = bound.gateway.prepare(7, bound.target, execution_profile_id="codex-image")
    assert frozen["image_options"]["output_format"] == "jpeg"
    assert _create(fixture, execution_profile_id="codex-image", output_format="jpeg") == recovered
    assert len(fixture.planning_calls) == 1


@pytest.mark.parametrize("output_format", ["webp", "jpg", "PNG", "", None])
def test_unknown_format_rejected_before_planning(options_fixture, output_format):
    with pytest.raises(BridgeNativeFacadeError, match="output_format_unsupported"):
        _create(options_fixture, execution_profile_id="codex-image", output_format=output_format)
    assert options_fixture.planning_calls == []


def test_manual_references_rejected_before_gateway_or_service_planning(options_fixture):
    fixture = options_fixture
    refs = [_upload_reference(fixture).asset_id]
    with pytest.raises(BridgeNativeFacadeError, match="references_unsupported"):
        _create(fixture, execution_profile_id="midjourney-manual", uploaded_asset_ids=refs)
    for service in (fixture.project_service, fixture.service):
        with pytest.raises(ValueError, match="references_unsupported"):
            service.create_render_bridge_plan(
                project_id=fixture.project.project_id, owner_user_id=7, user_input="A vase", plan_key="manual",
                execution_profile_id="midjourney-manual", uploaded_asset_ids=refs,
            )
    assert fixture.planning_calls == []


def test_codex_transports_two_exact_originals_with_profile_bound_read(options_fixture):
    fixture = options_fixture
    refs = [_upload_reference(fixture, color="red"), _upload_reference(fixture, image_format="JPEG")]
    bound, frozen = _planned(fixture, uploaded_asset_ids=[item.asset_id for item in refs], size="768x1024")
    for original, reference in zip(refs, frozen["references"], strict=True):
        read = bound.gateway.read_reference(
            7, bound.target, frozen_request_id=frozen["frozen_request_id"], reference_id=reference["reference_id"],
            execution_profile_id="codex-image",
        )
        assert read == {"content": Path(original.file_path).read_bytes(), "mime_type": original.mime_type}
    with pytest.raises(BridgeNativeFacadeError, match="profile_binding_mismatch"):
        bound.gateway.read_reference(7, bound.target, frozen_request_id=frozen["frozen_request_id"],
                                     reference_id=frozen["references"][0]["reference_id"])


@pytest.mark.parametrize("field,value", [
    ("quality", "high"), ("output_format", "jpeg"), ("background", "transparent"),
    ("moderation", "low"), ("output_compression", 90),
])
def test_canonical_options_outside_plan_are_not_rewritten(options_fixture, field, value):
    bound, _frozen = _planned(options_fixture)
    record = bound.jobs.get(bound.target.job_id)
    record.planning_result.generation_plans[0].metadata["provider_image_options"][field] = value
    bound.jobs.save(record)
    before = copy.deepcopy(record)
    with pytest.raises(BridgeNativeFacadeError, match="native_subset_unsupported"):
        bound.gateway.prepare(7, bound.target, execution_profile_id="codex-image")
    assert bound.jobs.get(bound.target.job_id) == before


def test_actual_identity_reference_high_fidelity_is_rejected(options_fixture):
    fixture = options_fixture
    upload = _upload_reference(fixture, role="product_reference")
    bound = _new_target(fixture, _create(fixture, execution_profile_id="codex-image", uploaded_asset_ids=[upload.asset_id]))
    canonical = bound.facade.freeze(7, bound.target)
    assert canonical["image_options"]["input_fidelity"] == "high"
    with pytest.raises(BridgeNativeFacadeError, match="native_subset_unsupported"):
        bound.gateway.prepare(7, bound.target, execution_profile_id="codex-image")
    assert bound.outputs.list_by_job(bound.target.job_id) == []


@pytest.mark.parametrize("expected,actual", [("png", "jpeg"), ("jpeg", "png")])
def test_format_is_verified_from_original_not_transcoded(options_fixture, expected, actual):
    bound, frozen = _planned(options_fixture, output_format=expected)
    with pytest.raises(BridgeNativeFacadeError, match="artifact_invalid"):
        _register(bound, **_receipt(bound, frozen, content=_image(actual), execution_profile_id="codex-image"))
    assert bound.outputs.list_by_job(bound.target.job_id) == []


def test_profile_specific_output_byte_limit_and_decoding():
    content = _image("png", noise=True)
    assert 1_048_576 < len(content) < 16_777_216
    digest = hashlib.sha256(content).hexdigest()
    with pytest.raises(BridgeNativeFacadeError, match="hash_mismatch"):
        NativeRenderBridgeGateway._validate_artifact(content, digest)
    for profile in ("codex-image", "midjourney-manual"):
        NativeRenderBridgeGateway._validate_artifact(content, digest, execution_profile_id=profile)
    oversized = b"x" * 16_777_217
    with pytest.raises(BridgeNativeFacadeError, match="hash_mismatch"):
        NativeRenderBridgeGateway._validate_artifact(oversized, hashlib.sha256(oversized).hexdigest(),
                                                   execution_profile_id="codex-image")
    malformed = _image("jpeg")[:-100]
    with pytest.raises(BridgeNativeFacadeError, match="artifact_invalid"):
        NativeRenderBridgeGateway._validate_artifact(malformed, hashlib.sha256(malformed).hexdigest(),
                                                   execution_profile_id="codex-image", output_format="jpeg")


def test_profile_and_format_identity_defaults_preserve_old_records():
    plan = RenderBridgePlanIdentity("p", 7, "k", "a" * 64)
    old = {"project_id": "p", "owner_user_id": 7, "plan_key": "k", "user_input_sha256": "a" * 64}
    assert plan.instance_id == hashlib.sha256(json.dumps(old, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert plan.safe_metadata() == {"schema_version": "render_bridge_native_plan_v1", **old}
    assert len({plan.instance_id, replace(plan, output_format="jpeg").instance_id,
                replace(plan, execution_profile_id="codex-image").instance_id}) == 3
    binding = RenderBridgeRegistration("k", "p", "j", "a", "f", "t", "s", "r", "h")
    assert "output_format" not in binding.safe_metadata()
    assert "development_only" not in binding.safe_metadata()
    assert len({binding.output_id, replace(binding, output_format="jpeg").output_id,
                replace(binding, execution_profile_id="codex-image").output_id}) == 3


@pytest.mark.parametrize("checkpoint", ["output", "committed"])
def test_real_profile_partial_checkpoint_and_lost_response_recover_without_renderer(options_fixture, monkeypatch, checkpoint):
    bound, frozen = _planned(options_fixture, output_format="jpeg")
    receipt = _receipt(bound, frozen, content=_image("jpeg"), execution_profile_id="codex-image")
    if checkpoint == "output":
        original = bound.service._project_frozen_provider_candidate

        def lose_response(*args, **kwargs):
            raise TimeoutError("fixture interrupts after native output checkpoint")

        monkeypatch.setattr(bound.service, "_project_frozen_provider_candidate", lose_response)
    else:
        original = bound.service.register_render_bridge_result

        def lose_response(*args, **kwargs):
            original(*args, **kwargs)
            raise TimeoutError("fixture loses committed registration response")

        monkeypatch.setattr(bound.service, "register_render_bridge_result", lose_response)
    assert _register(bound, **receipt)["status"] == "import_unknown"
    assert len(bound.outputs.list_by_job(bound.target.job_id)) == 1
    if checkpoint == "output":
        assert bound.gateway.registration_status(7, bound.target, import_key=receipt["import_key"])["retry_safe"] is True
        monkeypatch.setattr(bound.service, "_project_frozen_provider_candidate", original)
    else:
        monkeypatch.setattr(bound.service, "register_render_bridge_result", _forbidden)
    accepted = _register(bound, **receipt)
    assert accepted["status"] == "registered"
    assert _register(bound, **receipt) == accepted
    assert len(bound.outputs.list_by_job(bound.target.job_id)) == len(bound.reviews) == 1
    assert bound.review_only_calls == [True]
    assert accepted["execution_audit_count"] == 1
