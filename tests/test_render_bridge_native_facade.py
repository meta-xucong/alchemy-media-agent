"""Read-only facade tests, not native import/usage acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import (
    BridgeNativeFacadeError,
    NativeFreezeTarget,
    RenderBridgeNativeFacade,
)
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY, ReferenceInputPlan
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


@pytest.fixture
def target_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    runtime_result = ScenarioRuntime().plan_job(
        {
            "user_input": "A blue ceramic vase on a plain wooden table.",
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 1}},
            "metadata": {
                "template_id": "general_template",
                "requested_image_count": 1,
                "requested_image_size": "1024x1024",
            },
        }
    )
    plan = runtime_result.planning_result
    assert plan is not None
    job_id = plan.creative_job.job_id
    target = NativeFreezeTarget(project_id="project_bridge", job_id=job_id, asset_id=plan.series_plan.assets[0].asset_id)
    references = []
    for index, color in enumerate(("blue", "red")):
        path = tmp_path / f"reference_{index}.png"
        Image.new("RGB", (256, 256), color).save(path)
        references.append(
            {"asset_id": f"source_{index}", "file_path": str(path), "mime_type": "image/png", "role": "style_reference"}
        )
    logical = ReferenceInputPlan.freeze(
        job_id=job_id, project_id=target.project_id, mode="standard", inputs=references
    ).as_dict()
    metadata = {
        "project_id": target.project_id,
        "veyra_user_id": 7,
        PLAN_KEY: logical,
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": "An approved blue ceramic vase on a plain wooden table, soft window light.",
                    "review_status": "approved",
                    "user_direction_integrity": {
                        "contract_version": "v3_user_direction_integrity_v1",
                        "status": "preserved",
                        "owner": "remote_v3_llm_brain",
                    },
                }
            ],
            "audit": {
                "canonical_provider_prompt_stage": "provider_prompt_finalize",
                "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
            },
        },
    }
    generation_plan = plan.generation_plans[0]
    generation_plan.metadata = {**generation_plan.metadata, **copy.deepcopy(metadata)}
    record = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="A blue vase.", metadata=copy.deepcopy(metadata)),
        status=ProductJobStatusValue.PLANNED,
        planning_result=plan,
    )
    project = SimpleNamespace(
        project_id=target.project_id,
        status="active",
        job_ids=[job_id],
        metadata={"veyra_user_id": 7},
        updated_at="2026-10-20T12:00:00Z",
    )
    state = {"record": record, "project": project}
    facade = RenderBridgeNativeFacade(
        get_job_record=lambda job_id: state["record"],
        get_project_record=lambda project_id: state["project"],
        enabled=True,
    )
    return SimpleNamespace(facade=facade, state=state, target=target, references=references, tmp_path=tmp_path)


def test_disabled_facade_does_not_even_read_target():
    def forbidden(_):
        pytest.fail("disabled facade invoked a lookup")

    facade = RenderBridgeNativeFacade(get_job_record=forbidden, get_project_record=forbidden)
    with pytest.raises(BridgeNativeFacadeError, match="render_bridge_native_disabled"):
        facade.freeze(7, NativeFreezeTarget("p", "j", "a"))


def test_freeze_reuses_real_materializer_without_mutation(target_fixture, monkeypatch):
    fixture = target_fixture
    record = fixture.state["record"]
    before = copy.deepcopy(record)
    plan = record.planning_result
    request = build_provider_generation_request(
        asset_spec=plan.series_plan.assets[0],
        layout_plan=plan.layout_plans[0],
        prompt_compilation=plan.prompt_compilations[0],
        condition_plan=plan.condition_plans[0],
        generation_plan=copy.deepcopy(plan.generation_plans[0]),
        job_id=record.job_id,
    )
    expected = ProductionImageGenerationProvider(output_store=object()).materialize_final_prompt(request)

    def forbidden(*args, **kwargs):
        pytest.fail("read-only facade entered generation or derivative creation")

    monkeypatch.setattr(ProductionImageGenerationProvider, "generate", forbidden)
    monkeypatch.setattr(ProductionImageGenerationProvider, "_reference_truth_derivatives", forbidden)
    files_before = sorted(path.relative_to(fixture.tmp_path) for path in fixture.tmp_path.rglob("*"))
    result = fixture.facade.freeze(7, fixture.target)
    assert result["status"] == "frozen"
    assert result["prompt"] == expected.generation_prompt
    assert result["prompt_sha256"] == expected.prompt_sha256
    assert result["prompt_source"] == "remote_brain_canonical"
    assert result["image_options"]["quality"] == expected.quality
    assert result["image_options"]["input_fidelity"] == expected.input_fidelity
    assert result["operation"] == "image_edit"
    assert result["submission_ready"] is False
    assert result["native_registration_connected"] is False
    assert [item["sha256"] for item in result["references"]] == [
        hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest() for item in expected.reference_assets
    ]
    assert str(fixture.tmp_path) not in json.dumps(result)
    assert record == before
    assert sorted(path.relative_to(fixture.tmp_path) for path in fixture.tmp_path.rglob("*")) == files_before
    assert fixture.facade.freeze(7, fixture.target) == result


def test_reference_read_rechecks_exact_snapshot_and_bytes(target_fixture):
    fixture = target_fixture
    frozen = fixture.facade.freeze(7, fixture.target)
    reference = frozen["references"][0]
    content, mime = fixture.facade.read_reference(
        7, fixture.target, frozen_request_id=frozen["frozen_request_id"], reference_id=reference["reference_id"]
    )
    assert hashlib.sha256(content).hexdigest() == reference["sha256"]
    assert mime == "image/png"
    fixture.state["project"].metadata["veyra_user_id"] = 8
    with pytest.raises(BridgeNativeFacadeError, match="target_not_found"):
        fixture.facade.read_reference(
            7, fixture.target, frozen_request_id=frozen["frozen_request_id"], reference_id=reference["reference_id"]
        )


@pytest.mark.parametrize("change", ["owner", "project_owner", "membership", "project_binding", "deleted"])
def test_scope_and_deletion_fail_closed(target_fixture, change):
    fixture = target_fixture
    if change == "owner":
        fixture.state["record"].request.metadata["veyra_user_id"] = 8
    elif change == "project_owner":
        fixture.state["project"].metadata["veyra_user_id"] = 8
    elif change == "membership":
        fixture.state["project"].job_ids = []
    elif change == "project_binding":
        fixture.state["record"].request.metadata["project_id"] = "other"
    else:
        fixture.state["record"] = None
    with pytest.raises(BridgeNativeFacadeError, match="target_not_found"):
        fixture.facade.freeze(7, fixture.target)


@pytest.mark.parametrize("change", ["cancel", "archive", "generating", "generated"])
def test_ineligible_targets_are_not_revived(target_fixture, change):
    fixture = target_fixture
    if change == "cancel":
        fixture.state["record"].request.metadata["cancel_requested"] = True
    elif change == "archive":
        fixture.state["project"].status = "archived"
    else:
        fixture.state["record"].status = ProductJobStatusValue(change)
    with pytest.raises(BridgeNativeFacadeError, match="target_not_eligible"):
        fixture.facade.freeze(7, fixture.target)


def test_missing_brain_approval_is_not_replaced_by_free_prompt(target_fixture):
    fixture = target_fixture
    fixture.state["record"].planning_result.generation_plans[0].metadata["llm_brain"] = {}
    with pytest.raises(BridgeNativeFacadeError, match="brain_approval_required|canonical_materialization_blocked"):
        fixture.facade.freeze(7, fixture.target)


def test_missing_frozen_reference_plan_does_not_reconstruct_sources(target_fixture):
    fixture = target_fixture
    fixture.state["record"].planning_result.generation_plans[0].metadata.pop(PLAN_KEY)
    with pytest.raises(BridgeNativeFacadeError, match="frozen_reference_plan_missing"):
        fixture.facade.freeze(7, fixture.target)


def test_changed_revision_and_reference_bytes_are_blocked(target_fixture):
    fixture = target_fixture
    frozen = fixture.facade.freeze(7, fixture.target)
    fixture.state["project"].updated_at = "2026-10-20T13:00:00Z"
    with pytest.raises(BridgeNativeFacadeError, match="target_revision_changed"):
        fixture.facade.freeze(7, fixture.target, expected_revision=frozen["target_revision"])
    fixture.state["project"].updated_at = "2026-10-20T12:00:00Z"
    Image.new("RGB", (256, 256), "green").save(fixture.references[0]["file_path"])
    with pytest.raises(BridgeNativeFacadeError, match="reference_changed"):
        fixture.facade.freeze(7, fixture.target)


def test_revision_race_during_materialization_is_blocked(target_fixture, monkeypatch):
    fixture = target_fixture
    original = ProductionImageGenerationProvider.materialize_final_prompt

    def mutate_after_freeze(self, request):
        result = original(self, request)
        fixture.state["project"].updated_at = "changed"
        return result

    monkeypatch.setattr(ProductionImageGenerationProvider, "materialize_final_prompt", mutate_after_freeze)
    with pytest.raises(BridgeNativeFacadeError, match="target_revision_changed"):
        fixture.facade.freeze(7, fixture.target)


def test_registration_100_times_stays_unavailable_not_false_native_acceptance(target_fixture):
    fixture = target_fixture
    before = copy.deepcopy(fixture.state["record"])
    results = [fixture.facade.register_receipt(7, fixture.target, import_key="same-import-key") for _ in range(100)]
    assert all(result == results[0] for result in results)
    assert results[0] == {
        "status": "blocked",
        "reason_code": "native_registration_unavailable",
        "native_registration_connected": False,
        "native_registration_ref": None,
        "retry_safe": False,
        "effect": "none",
    }
    assert fixture.facade.registration_status(7, fixture.target, import_key="same-import-key") == results[0]
    assert fixture.state["record"] == before
    # This proves zero native effects. It DOES NOT satisfy one-result/one-usage
    # registration acceptance, which remains a required later native stage.
