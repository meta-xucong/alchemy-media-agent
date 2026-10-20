"""Opt-in native checkpoint acceptance using fake pixels and mocked review.

These tests exercise native persistence, not provider quality or Veyra billing.
They must not authorize fake pixels for formal selection or export.
"""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from threading import Barrier
from unittest.mock import Mock

import pytest
from PIL import Image

from test_render_bridge_native_facade import target_fixture  # noqa: F401

from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.render_bridge_provider import (
    RenderBridgePlanIdentity,
    RenderBridgeReceiptProvider,
)
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    SelectResultRequest,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import (
    BridgeNativeFacadeError,
    RenderBridgeNativeFacade,
)
from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import (
    NativeRenderBridgeGateway,
)
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY, ReferenceInputPlan
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy


def _png_bytes(color: str = "blue", size: tuple[int, int] = (1024, 1024)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _forbidden(*args, **kwargs):
    pytest.fail("native receipt import invoked generation, auto-selection, or billing")


@pytest.fixture
def native_fixture(target_fixture, monkeypatch, tmp_path):
    fixture = target_fixture
    record = fixture.state["record"]
    no_references = ReferenceInputPlan.freeze(
        job_id=fixture.target.job_id,
        project_id=fixture.target.project_id,
        mode="standard",
        inputs=[],
    ).as_dict()
    options = {"size": "1024x1024", "quality": "auto", "output_format": "png"}
    for metadata in (
        record.request.metadata,
        record.planning_result.metadata,
        record.planning_result.generation_plans[0].metadata,
    ):
        metadata[PLAN_KEY] = copy.deepcopy(no_references)
        metadata["provider_image_options"] = dict(options)
    record.request.metadata["render_bridge_native_plan"] = RenderBridgePlanIdentity(
        project_id=fixture.target.project_id,
        owner_user_id=7,
        plan_key="native-fixture",
        user_input_sha256=hashlib.sha256(record.request.user_input.encode("utf-8")).hexdigest(),
    ).safe_metadata()
    jobs = PersistentProductJobStore(tmp_path / "jobs")
    jobs.save(record)
    project = ProjectRecord(
        project_id=fixture.target.project_id,
        title="Bridge native test",
        user_goal="A blue ceramic vase.",
        short_summary="Isolated fake-image import.",
        job_ids=[fixture.target.job_id],
        created_at="2026-10-20T12:00:00Z",
        updated_at="2026-10-20T12:00:00Z",
        metadata={"veyra_user_id": 7},
    )
    projects = InMemoryProjectStore()
    projects.save_project(project)
    outputs = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(
        job_store=jobs,
        output_store=outputs,
        asset_store=V3UploadedAssetStore(tmp_path / "uploads"),
    )
    facade = RenderBridgeNativeFacade(
        get_job_record=jobs.get,
        get_project_record=projects.get_project,
        enabled=True,
    )
    journal_root = tmp_path / "native-journal"
    gateway = NativeRenderBridgeGateway(
        facade=facade,
        service=service,
        journal_root=journal_root,
        enabled=True,
    )
    reviews = []
    review_only_calls = []
    original_resume = service._resume_finalizing_generation_review

    def mock_review(review_record, result, generate_request):
        reviews.append(
            {
                "job_id": review_record.job_id,
                "output_ids": [item.output_id for item in outputs.list_by_job(review_record.job_id)],
            }
        )
        # Deliberately not a certifying real-review receipt.
        return result.model_copy(
            update={
                "metadata": {
                    **result.metadata,
                    "post_generation_review_package": {
                        "status": "test_review_only",
                        "inspections": [],
                        "test_double": True,
                    },
                }
            }
        )

    def observe_resume(*args, **kwargs):
        review_only_calls.append(kwargs.get("review_only", False))
        return original_resume(*args, **kwargs)

    monkeypatch.setattr(service, "_attach_post_generation_review", mock_review)
    monkeypatch.setattr(service, "_resume_finalizing_generation_review", observe_resume)
    monkeypatch.setattr(service, "_run_visual_auto_retries", _forbidden)
    monkeypatch.setattr(
        ProductionImageGenerationProvider,
        "_run_app_provider_with_timeout_retry",
        _forbidden,
    )
    from app.services import veyra_auth, veyra_usage

    debit = Mock(side_effect=_forbidden)
    usage = Mock(side_effect=_forbidden)
    monkeypatch.setattr(veyra_auth, "debit_balance", debit)
    monkeypatch.setattr(veyra_usage, "record_veyra_usage", usage)
    return SimpleNamespace(
        target=fixture.target,
        facade=facade,
        gateway=gateway,
        service=service,
        jobs=jobs,
        projects=projects,
        project=project,
        outputs=outputs,
        journal_root=journal_root,
        reviews=reviews,
        review_only_calls=review_only_calls,
        debit=debit,
        usage=usage,
        tmp_path=tmp_path,
    )


def _receipt(fixture, frozen=None, content=None, **overrides):
    frozen = frozen or fixture.gateway.prepare(7, fixture.target)
    content = content if content is not None else _png_bytes()
    return {
        "import_key": "same-native-import",
        "frozen_request_id": frozen["frozen_request_id"],
        "receipt_id": "bridge_fake_receipt_1",
        "original_sha256": hashlib.sha256(content).hexdigest(),
        "artifact_bytes": content,
        "execution_profile_id": "fake-image",
        **overrides,
    }


def _register(fixture, **receipt):
    return fixture.gateway.register_receipt(7, fixture.target, **receipt)


def _journal_records(fixture):
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in fixture.journal_root.rglob("*.json")
    ]


def test_default_off_gateway_does_not_read_or_write(native_fixture, monkeypatch):
    fixture = native_fixture
    monkeypatch.setattr(fixture.facade, "_get_job", _forbidden)
    monkeypatch.setattr(fixture.facade, "_get_project", _forbidden)
    gateway = NativeRenderBridgeGateway(
        facade=fixture.facade,
        service=fixture.service,
        journal_root=fixture.journal_root,
    )
    for action in (
        lambda: gateway.prepare(7, fixture.target),
        lambda: gateway.registration_status(7, fixture.target, import_key="disabled"),
        lambda: gateway.register_receipt(
            7,
            fixture.target,
            import_key="disabled",
            frozen_request_id="disabled",
            receipt_id="disabled",
            original_sha256="0" * 64,
            artifact_bytes=b"disabled",
        ),
    ):
        with pytest.raises(BridgeNativeFacadeError, match="disabled"):
            action()
    assert not fixture.journal_root.exists()
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []


def test_unmarked_ordinary_plan_cannot_be_prepared_for_native_import(native_fixture):
    fixture = native_fixture
    record = fixture.jobs.get(fixture.target.job_id)
    record.request.metadata.pop("render_bridge_native_plan")
    fixture.jobs.save(record)
    with pytest.raises(BridgeNativeFacadeError, match="native_plan_required"):
        fixture.gateway.prepare(7, fixture.target)
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []
    assert fixture.reviews == []


def test_one_hundred_identical_receipts_have_one_native_checkpoint(native_fixture):
    fixture = native_fixture
    frozen = fixture.gateway.prepare(7, fixture.target)
    assert frozen["operation"] == "image_generate"
    assert frozen["references"] == []
    assert frozen["image_options"] == {
        "size": "1024x1024",
        "quality": "auto",
        "output_format": "png",
        "input_fidelity": None,
        "background": None,
        "moderation": None,
        "output_compression": None,
    }
    receipt = _receipt(fixture, frozen)
    results = [_register(fixture, **receipt) for _ in range(100)]
    assert all(result == results[0] for result in results)
    result = results[0]
    assert result["status"] == "registered"
    assert result["billing"] == {"mode": "v3_zero_credit_stub", "charged": False}
    assert result["execution_audit_count"] == 1
    outputs = fixture.outputs.list_by_job(fixture.target.job_id)
    assert len(outputs) == 1
    output = outputs[0]
    assert output.output_id == result["native_registration_ref"]
    assert output.job_id == fixture.target.job_id
    assert output.asset_id == fixture.target.asset_id
    assert result["original_sha256"] == receipt["original_sha256"]
    assert result["normalized_sha256"] == hashlib.sha256(Path(output.file_path).read_bytes()).hexdigest()
    assert fixture.gateway.registration_status(
        7, fixture.target, import_key=receipt["import_key"]
    ) == result
    journals = _journal_records(fixture)
    assert len(journals) == 1
    audit = journals[0]["execution_audit"]
    assert isinstance(audit, dict) or (isinstance(audit, list) and len(audit) == 1)
    assert len(fixture.reviews) == 1
    assert fixture.reviews[0]["output_ids"] == [output.output_id]
    assert fixture.review_only_calls == [True]
    record = fixture.jobs.get(fixture.target.job_id)
    assert record.selected_result is None
    assert record.generation_result.asset_pack.assets[0].metadata["selected_candidate_is_mock"] is True
    fixture.debit.assert_not_called()
    fixture.usage.assert_not_called()


def test_concurrent_receipt_replays_commit_one_native_checkpoint(native_fixture):
    fixture = native_fixture
    receipt = _receipt(fixture)
    start = Barrier(4)

    def register_once():
        start.wait(timeout=10)
        try:
            return _register(fixture, **receipt)
        except BridgeNativeFacadeError as exc:
            assert exc.code == "render_bridge_registration_in_progress"
            return {"status": "registration_in_progress"}

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(lambda _: register_once(), range(4)))
    assert any(item["status"] == "registered" for item in outcomes)
    assert {item["status"] for item in outcomes} <= {"registered", "registration_in_progress"}
    status = fixture.gateway.registration_status(
        7, fixture.target, import_key=receipt["import_key"]
    )
    assert status["status"] == "registered"
    assert status["execution_audit_count"] == 1
    assert len(fixture.outputs.list_by_job(fixture.target.job_id)) == 1
    assert len(fixture.reviews) == 1
    assert len(_journal_records(fixture)) == 1
    fixture.debit.assert_not_called()
    fixture.usage.assert_not_called()


def test_same_import_key_with_changed_content_is_a_conflict(native_fixture):
    fixture = native_fixture
    frozen = fixture.gateway.prepare(7, fixture.target)
    receipt = _receipt(fixture, frozen)
    accepted = _register(fixture, **receipt)
    with pytest.raises(BridgeNativeFacadeError, match="conflict|mismatch"):
        _register(fixture, **_receipt(fixture, frozen, content=_png_bytes("red")))
    assert len(fixture.outputs.list_by_job(fixture.target.job_id)) == 1
    assert fixture.gateway.registration_status(
        7, fixture.target, import_key=receipt["import_key"]
    ) == accepted
    assert len(fixture.reviews) == 1


def test_unknown_response_after_native_commit_is_reconciled_without_another_import(native_fixture, monkeypatch):
    fixture = native_fixture
    receipt = _receipt(fixture)
    original_register = fixture.service.register_render_bridge_result
    original_lookup = fixture.service.lookup_render_bridge_registration
    commits = []
    lookups = []

    def lose_committed_response(*args, **kwargs):
        committed = original_register(*args, **kwargs)
        assert committed["status"] == "registered"
        commits.append(committed)
        raise TimeoutError("simulated lost response after native commit")

    def lookup(*args, **kwargs):
        lookups.append(args[0])
        return original_lookup(*args, **kwargs)

    monkeypatch.setattr(fixture.service, "register_render_bridge_result", lose_committed_response)
    monkeypatch.setattr(fixture.service, "lookup_render_bridge_registration", lookup)
    result = _register(fixture, **receipt)
    status = fixture.gateway.registration_status(
        7, fixture.target, import_key=receipt["import_key"]
    )
    assert result["status"] == "import_unknown"
    assert result["retry_safe"] is False
    assert status["status"] == "registered"
    assert commits[0]["native_registration_ref"] == status["native_registration_ref"]
    assert len(commits) == 1
    assert len(lookups) >= 1
    assert _register(fixture, **receipt) == status
    assert len(commits) == 1
    assert len(fixture.outputs.list_by_job(fixture.target.job_id)) == 1
    assert len(_journal_records(fixture)) == 1
    assert status["execution_audit_count"] == 1
    assert len(fixture.reviews) == 1


def test_registered_outcome_survives_fresh_service_and_gateway(native_fixture, monkeypatch):
    fixture = native_fixture
    receipt = _receipt(fixture)
    accepted = _register(fixture, **receipt)
    fresh_jobs = PersistentProductJobStore(fixture.tmp_path / "jobs")
    fresh_service = V3ProductApiService(
        job_store=fresh_jobs,
        output_store=V3GeneratedOutputStore(fixture.tmp_path / "outputs"),
        asset_store=V3UploadedAssetStore(fixture.tmp_path / "uploads"),
    )
    fresh_facade = RenderBridgeNativeFacade(
        get_job_record=fresh_jobs.get,
        get_project_record=fixture.projects.get_project,
        enabled=True,
    )
    restarted = NativeRenderBridgeGateway(
        facade=fresh_facade,
        service=fresh_service,
        journal_root=fixture.journal_root,
        enabled=True,
    )
    monkeypatch.setattr(fresh_service, "register_render_bridge_result", _forbidden)
    assert restarted.registration_status(
        7, fixture.target, import_key=receipt["import_key"]
    ) == accepted
    assert restarted.register_receipt(7, fixture.target, **receipt) == accepted
    assert len(fresh_service.output_store.list_by_job(fixture.target.job_id)) == 1
    assert len(_journal_records(fixture)) == 1


@pytest.mark.parametrize("change", ["job_owner", "project_owner", "membership"])
def test_committed_status_does_not_bypass_current_ownership(native_fixture, change):
    fixture = native_fixture
    receipt = _receipt(fixture)
    _register(fixture, **receipt)
    if change == "job_owner":
        record = fixture.jobs.get(fixture.target.job_id)
        record.request.metadata["veyra_user_id"] = 8
        fixture.jobs.save(record)
    elif change == "project_owner":
        fixture.project.metadata["veyra_user_id"] = 8
    else:
        fixture.project.job_ids = []
    with pytest.raises(BridgeNativeFacadeError, match="not_found"):
        fixture.gateway.registration_status(7, fixture.target, import_key=receipt["import_key"])
    with pytest.raises(BridgeNativeFacadeError, match="not_found"):
        _register(fixture, **receipt)
    assert len(fixture.outputs.list_by_job(fixture.target.job_id)) == 1
    assert len(fixture.reviews) == 1


@pytest.mark.parametrize("change", ["cancel", "job_owner", "project_owner", "revision", "membership"])
def test_live_authority_change_after_prepare_blocks_native_import(native_fixture, change):
    fixture = native_fixture
    receipt = _receipt(fixture)
    record = fixture.jobs.get(fixture.target.job_id)
    if change == "cancel":
        record.request.metadata["cancel_requested"] = True
        fixture.jobs.save(record)
    elif change == "job_owner":
        record.request.metadata["veyra_user_id"] = 8
        fixture.jobs.save(record)
    elif change == "project_owner":
        fixture.project.metadata["veyra_user_id"] = 8
    elif change == "membership":
        fixture.project.job_ids = []
    else:
        fixture.project.updated_at = "2026-10-20T13:00:00Z"
    with pytest.raises(
        BridgeNativeFacadeError,
        match="not_found|not_eligible|revision_changed|frozen_request_changed",
    ):
        _register(fixture, **receipt)
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []
    assert fixture.reviews == []
    fixture.debit.assert_not_called()
    fixture.usage.assert_not_called()


def test_cancel_between_receipt_consumption_and_output_persistence_blocks_checkpoint(native_fixture, monkeypatch):
    fixture = native_fixture
    receipt = _receipt(fixture)
    consume = RenderBridgeReceiptProvider._run_app_provider_with_timeout_retry

    def cancel_after_receipt(self, *args, **kwargs):
        result = consume(self, *args, **kwargs)
        record = fixture.jobs.get(fixture.target.job_id)
        record.request.metadata["cancel_requested"] = True
        fixture.jobs.save(record)
        return result

    monkeypatch.setattr(
        RenderBridgeReceiptProvider, "_run_app_provider_with_timeout_retry", cancel_after_receipt
    )
    with pytest.raises(BridgeNativeFacadeError, match="not_eligible|revision_changed"):
        _register(fixture, **receipt)
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []
    assert fixture.reviews == []


def test_fake_import_review_never_rerenders_or_auto_selects(native_fixture, monkeypatch):
    fixture = native_fixture
    monkeypatch.setattr(fixture.service, "select_result", _forbidden)
    result = _register(fixture, **_receipt(fixture))
    assert result["status"] == "registered"
    assert fixture.review_only_calls == [True]
    assert len(fixture.reviews) == 1
    record = fixture.jobs.get(fixture.target.job_id)
    assert record.generation_result is not None
    assert record.selected_result is None
    assert fixture.project.selected_output_refs == []


def test_fake_import_cannot_be_selected_or_exported_as_formal_delivery(native_fixture):
    fixture = native_fixture
    result = _register(fixture, **_receipt(fixture))
    record = fixture.jobs.get(fixture.target.job_id)
    delivery, output_ids, asset_ids = fixture.service._public_final_delivery_projection(record.generation_result)
    assert delivery["delivery_gate_applies"] is True
    assert delivery["automatic_delivery_available"] is False
    assert delivery["final_delivery_output_count"] == 0
    assert output_ids == asset_ids == set()
    output = fixture.outputs.list_by_job(fixture.target.job_id)[0]
    for request in (
        SelectResultRequest(),
        SelectResultRequest(selected_candidate_ids=[output.candidate_id]),
        SelectResultRequest(selected_asset_ids=[output.asset_id]),
    ):
        selection = fixture.service.select_result(fixture.target.job_id, request)
        assert selection.metadata["selection_held"] is True
        assert fixture.jobs.get(fixture.target.job_id).selected_result is None
    export = fixture.service.export_job(fixture.target.job_id)
    assert result["native_registration_ref"] not in json.dumps(export.manifest)


@pytest.mark.parametrize("profile", ["codex-image", "unverified-image"])
def test_unverified_execution_profile_is_rejected(native_fixture, profile):
    fixture = native_fixture
    receipt = _receipt(fixture, execution_profile_id=profile)
    with pytest.raises(BridgeNativeFacadeError, match="profile|contract|unsupported"):
        _register(fixture, **receipt)
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []
    assert fixture.reviews == []


@pytest.mark.parametrize(
    "content,sha256",
    [
        (b"not-an-image", None),
        (_png_bytes(size=(256, 256)), None),
        (_png_bytes(), "0" * 64),
    ],
)
def test_invalid_receipt_pixels_are_rejected_before_native_output(native_fixture, content, sha256):
    fixture = native_fixture
    receipt = _receipt(fixture, content=content)
    if sha256 is not None:
        receipt["original_sha256"] = sha256
    with pytest.raises(BridgeNativeFacadeError):
        _register(fixture, **receipt)
    assert fixture.outputs.list_by_job(fixture.target.job_id) == []
    assert fixture.reviews == []


def test_default_provider_checkpoint_hook_and_routes_remain_unchanged():
    provider = ProductionImageGenerationProvider(output_store=object())
    assert provider._native_output_checkpoint_id(None, output_index=0) is None
    assert provider._native_output_checkpoint_id(None, output_index=19) is None
    router = GenerationRouter()
    assert router.provider is None
    assert type(router.providers[ProviderStrategy.DEFAULT_IMAGE_PROVIDER]) is ProductionImageGenerationProvider
    assert type(router.providers[ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER]) is ProductionImageGenerationProvider
    assert not any(isinstance(item, RenderBridgeReceiptProvider) for item in router.providers.values())
    assert inspect.signature(
        V3ProductApiService._resume_finalizing_generation_review
    ).parameters["assert_current"].default is None
