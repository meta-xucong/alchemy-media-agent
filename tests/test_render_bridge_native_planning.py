"""Plan-only Bridge entry tests with local planning and explicit mock sign-off."""

from __future__ import annotations

import copy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from test_render_bridge_native_registration import (
    _forbidden,
    _receipt,
    _register,
    native_fixture,  # noqa: F401
    target_fixture,  # noqa: F401
)

from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import (
    BridgeNativeFacadeError,
    NativeFreezeTarget,
)
from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import NativeRenderBridgeGateway
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY, ReferenceInputPlan
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


@pytest.fixture
def planning_fixture(native_fixture, monkeypatch):
    fixture = native_fixture
    fixture.project_service = V3ProjectModeService(
        product_service=fixture.service,
        project_store=fixture.projects,
    )
    fixture.gateway = NativeRenderBridgeGateway(
        facade=fixture.facade,
        service=fixture.service,
        project_service=fixture.project_service,
        journal_root=fixture.journal_root,
        enabled=True,
    )
    fixture.planning_calls = []
    fixture.initial_job_ids = {record.job_id for record in fixture.jobs.list_recent(100)}
    canonical = copy.deepcopy(
        fixture.jobs.get(fixture.target.job_id).planning_result.generation_plans[0].metadata["llm_brain"]
    )
    original_plan = fixture.service.scenario_runtime.plan_job

    def local_plan_with_mock_signoff(request):
        fixture.planning_calls.append(copy.deepcopy(request))
        local_request = copy.deepcopy(request)
        local_request["metadata"]["require_real_images"] = False
        local_request["metadata"]["real_image_generation"] = False
        result = original_plan(local_request)
        assert result.planning_result is not None
        # The planning boundary is mocked, not Brain availability or quality.
        result.metadata["llm_brain"] = copy.deepcopy(canonical)
        result.planning_result.metadata["llm_brain"] = copy.deepcopy(canonical)
        for plan in result.planning_result.generation_plans:
            plan.metadata["llm_brain"] = copy.deepcopy(canonical)
        return result

    monkeypatch.setattr(fixture.service.scenario_runtime, "plan_job", local_plan_with_mock_signoff)
    monkeypatch.setattr(fixture.service.scenario_runtime, "generate_job", _forbidden)
    return fixture


def _create(fixture, *, user_input="A blue ceramic vase on a plain wooden table.", plan_key="native-plan-key"):
    return fixture.gateway.create_plan(
        7,
        fixture.project.project_id,
        user_input=user_input,
        plan_key=plan_key,
    )


def _new_target(fixture, planned):
    assert planned["status"] == "planned"
    target = NativeFreezeTarget(**planned["target"])
    return SimpleNamespace(**{**vars(fixture), "target": target})


def test_replayed_plan_key_creates_one_native_job_and_one_plan(planning_fixture):
    fixture = planning_fixture
    outcomes = [_create(fixture) for _ in range(25)]
    assert all(outcome == outcomes[0] for outcome in outcomes)
    bound = _new_target(fixture, outcomes[0])
    assert len(fixture.planning_calls) == 1
    assert {
        record.job_id for record in fixture.jobs.list_recent(100)
    } - fixture.initial_job_ids == {bound.target.job_id}
    assert fixture.project.job_ids.count(bound.target.job_id) == 1
    record = fixture.jobs.get(bound.target.job_id)
    assert record.status == ProductJobStatusValue.PLANNED
    assert record.generation_result is None
    assert record.selected_result is None
    assert record.request.uploaded_asset_ids == []
    assert record.request.image_options.model_dump(exclude_none=True) == {
        "size": "1024x1024",
        "quality": "auto",
        "output_format": "png",
    }
    marker = record.request.metadata["render_bridge_native_plan"]
    assert marker["project_id"] == fixture.project.project_id
    assert marker["owner_user_id"] == 7
    assert marker["plan_key"] == "native-plan-key"
    assert marker["user_input_sha256"] == hashlib.sha256(record.request.user_input.encode()).hexdigest()
    logical = ReferenceInputPlan.from_dict(
        record.request.metadata[PLAN_KEY],
        job_id=bound.target.job_id,
        project_id=bound.target.project_id,
    )
    assert logical.references(verify_bytes=False) == []
    frozen = fixture.gateway.prepare(7, bound.target)
    assert frozen["submission_ready"] is True
    assert frozen["references"] == []
    assert fixture.outputs.list_by_job(bound.target.job_id) == []
    assert fixture.reviews == []
    fixture.debit.assert_not_called()
    fixture.usage.assert_not_called()


def test_changed_input_with_same_plan_key_is_a_conflict(planning_fixture):
    fixture = planning_fixture
    first = _create(fixture)
    with pytest.raises(BridgeNativeFacadeError, match="conflict|changed"):
        _create(fixture, user_input="An entirely different green vase.")
    assert len(fixture.planning_calls) == 1
    assert fixture.gateway.plan_status(
        7, fixture.project.project_id, plan_key="native-plan-key"
    ) == first


def test_missing_plan_status_does_not_start_planning(planning_fixture):
    fixture = planning_fixture
    result = fixture.gateway.plan_status(7, fixture.project.project_id, plan_key="never-started")
    assert result["status"] == "not_planned"
    assert fixture.planning_calls == []
    assert {record.job_id for record in fixture.jobs.list_recent(100)} == fixture.initial_job_ids


def test_blocked_brain_plan_is_terminal_without_an_implicit_retry(planning_fixture, monkeypatch):
    fixture = planning_fixture
    # Restore the real local runtime boundary. With real images required but
    # remote Brain disabled by the safe test environment, planning fails closed.
    blocked_plan = Mock(
        side_effect=lambda request: ScenarioRuntime.plan_job(fixture.service.scenario_runtime, request)
    )
    monkeypatch.setattr(fixture.service.scenario_runtime, "plan_job", blocked_plan)
    result = _create(fixture)
    assert result["status"] == "plan_blocked"
    assert fixture.gateway.plan_status(
        7, fixture.project.project_id, plan_key="native-plan-key"
    ) == result
    assert _create(fixture) == result
    blocked_plan.assert_called_once()
    record = fixture.jobs.get(result["job_id"])
    assert record.planning_result is None
    assert record.generation_result is None
    assert record.status == ProductJobStatusValue.BLOCKED
    assert fixture.outputs.list_by_job(record.job_id) == []
    assert fixture.reviews == []


def test_lost_plan_response_recovers_exact_job_and_project_membership(planning_fixture, monkeypatch):
    fixture = planning_fixture
    original = fixture.service.create_render_bridge_plan
    committed = []

    def lose_response(**kwargs):
        result = original(**kwargs)
        if not committed:
            committed.append(result.job_id)
            raise TimeoutError("simulated response loss after native plan save")
        return result

    monkeypatch.setattr(fixture.service, "create_render_bridge_plan", lose_response)
    unknown = _create(fixture)
    assert unknown["status"] == "plan_unknown"
    assert len(committed) == len(fixture.planning_calls) == 1
    reconciled = fixture.gateway.plan_status(
        7, fixture.project.project_id, plan_key="native-plan-key"
    )
    bound = _new_target(fixture, reconciled)
    assert bound.target.job_id == committed[0]
    assert fixture.project.job_ids.count(bound.target.job_id) == 1
    assert _create(fixture) == reconciled
    assert len(fixture.planning_calls) == 1
    assert fixture.gateway.prepare(7, bound.target)["submission_ready"] is True
    assert fixture.outputs.list_by_job(bound.target.job_id) == []


def test_uncertain_plan_without_a_native_record_never_starts_second_plan(planning_fixture, monkeypatch):
    fixture = planning_fixture
    create = Mock(side_effect=TimeoutError("uncertain planning transport"))
    monkeypatch.setattr(fixture.project_service, "create_render_bridge_plan", create)
    assert _create(fixture)["status"] == "plan_unknown"
    assert fixture.gateway.plan_status(
        7, fixture.project.project_id, plan_key="native-plan-key"
    )["status"] == "plan_unknown"
    assert _create(fixture)["status"] == "plan_unknown"
    create.assert_called_once()
    assert fixture.planning_calls == []
    assert {record.job_id for record in fixture.jobs.list_recent(100)} == fixture.initial_job_ids


@pytest.mark.parametrize("actor", [0, 8])
def test_plan_entry_rejects_non_owner_before_planning(planning_fixture, actor):
    fixture = planning_fixture
    with pytest.raises(BridgeNativeFacadeError, match="owner|not_found|authenticated"):
        fixture.gateway.create_plan(
            actor,
            fixture.project.project_id,
            user_input="A blue vase.",
            plan_key="wrong-owner",
        )
    assert fixture.planning_calls == []
    assert {record.job_id for record in fixture.jobs.list_recent(100)} == fixture.initial_job_ids


def test_public_metadata_cannot_forge_native_plan_marker(planning_fixture):
    fixture = planning_fixture
    forged = CreateCreativeJobRequest(
        user_input="A forged native-only request.",
        metadata={
            "project_id": fixture.project.project_id,
            "veyra_user_id": 7,
            "render_bridge_native_plan": {
                "schema_version": "render_bridge_native_plan_v1",
                "project_id": fixture.project.project_id,
                "owner_user_id": 7,
                "plan_key": "forged",
                "user_input_sha256": "0" * 64,
            },
        },
    )
    with pytest.raises(ValueError, match="server_owned|untrusted"):
        fixture.service.create_creative_job(forged)
    assert fixture.planning_calls == []
    assert {record.job_id for record in fixture.jobs.list_recent(100)} == fixture.initial_job_ids


def test_native_plan_cannot_enter_ordinary_generate(planning_fixture):
    fixture = planning_fixture
    bound = _new_target(fixture, _create(fixture))
    result = fixture.service.generate_job(bound.target.job_id)
    assert result.status == ProductJobStatusValue.PLANNED
    record = fixture.jobs.get(bound.target.job_id)
    assert record.generation_result is None
    assert fixture.outputs.list_by_job(bound.target.job_id) == []
    assert len(fixture.planning_calls) == 1


def test_cancelled_native_plan_cannot_generate_or_register(planning_fixture):
    fixture = planning_fixture
    bound = _new_target(fixture, _create(fixture))
    receipt = _receipt(bound)
    canceled = fixture.gateway.cancel_target(7, bound.target)
    assert canceled["status"] == "canceled"
    record = fixture.jobs.get(bound.target.job_id)
    assert record.request.metadata["cancel_requested"] is True
    assert record.status == ProductJobStatusValue.BLOCKED
    assert fixture.service.generate_job(bound.target.job_id).status == ProductJobStatusValue.BLOCKED
    with pytest.raises(BridgeNativeFacadeError, match="not_eligible|canceled|revision_changed"):
        _register(bound, **receipt)
    with pytest.raises(BridgeNativeFacadeError, match="not_eligible|canceled|revision_changed"):
        fixture.gateway.registration_status(7, bound.target, import_key="canceled-target")
    assert fixture.outputs.list_by_job(bound.target.job_id) == []
    assert fixture.reviews == []
    assert len(fixture.planning_calls) == 1


def test_cancel_after_registration_does_not_delete_or_revoke_checkpoint(planning_fixture):
    fixture = planning_fixture
    bound = _new_target(fixture, _create(fixture))
    accepted = _register(bound, **_receipt(bound))
    assert accepted["status"] == "registered"
    before = fixture.outputs.get_output(accepted["native_registration_ref"])
    result = fixture.gateway.cancel_target(7, bound.target)
    assert result["status"] == "already_registered"
    after = fixture.outputs.get_output(accepted["native_registration_ref"])
    assert before == after
    assert len(fixture.outputs.list_by_job(bound.target.job_id)) == 1
    assert fixture.jobs.get(bound.target.job_id).generation_result is not None


def test_normal_unmarked_job_keeps_original_generate_path(planning_fixture, monkeypatch):
    fixture = planning_fixture
    planned = fixture.service.create_creative_job(
        CreateCreativeJobRequest(
            user_input="An ordinary local planning fixture.",
            metadata={"project_id": fixture.project.project_id, "veyra_user_id": 7},
        )
    )
    assert planned.status == ProductJobStatusValue.PLANNED
    original = fixture.jobs.get(planned.job_id)
    assert "render_bridge_native_plan" not in original.request.metadata
    entered = Mock(side_effect=RuntimeError("test stops before rendering"))
    monkeypatch.setattr(fixture.service.scenario_runtime, "generate_job", entered)
    fixture.service.generate_job(planned.job_id)
    entered.assert_called_once()
    assert fixture.outputs.list_by_job(planned.job_id) == []


def test_default_off_plan_entry_performs_no_reads_or_writes(planning_fixture, monkeypatch):
    fixture = planning_fixture
    monkeypatch.setattr(fixture.projects, "get_project", _forbidden)
    monkeypatch.setattr(fixture.facade, "_get_project", _forbidden)
    disabled = NativeRenderBridgeGateway(
        facade=fixture.facade,
        service=fixture.service,
        project_service=fixture.project_service,
        journal_root=fixture.journal_root,
    )
    for action in (
        lambda: disabled.create_plan(7, fixture.project.project_id, user_input="A vase.", plan_key="off"),
        lambda: disabled.plan_status(7, fixture.project.project_id, plan_key="off"),
        lambda: disabled.cancel_target(7, fixture.target),
    ):
        with pytest.raises(BridgeNativeFacadeError, match="disabled"):
            action()
    assert fixture.planning_calls == []
    assert not fixture.journal_root.exists()
