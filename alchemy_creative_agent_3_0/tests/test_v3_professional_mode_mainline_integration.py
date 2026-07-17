from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    InMemoryVisualAssetCatalog,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _catalog() -> InMemoryVisualAssetCatalog:
    catalog = InMemoryVisualAssetCatalog()
    project_id = "project_professional"
    people_asset_id = "person_1"
    pack_id = "pack_1"
    views = [
        AnchorView(
            view_id=view_id,
            view_role=role,
            output_id=f"output_{role}",
            source_candidate_ids=[f"candidate_{role}"],
            identity_scores=IdentityScoreSummary(
                same_face_score=0.95,
                visual_quality_score=0.9,
                distinctive_feature_score=0.94,
                human_realism_score=0.9,
            ),
        )
        for view_id, role in (
            ("front_1", "standard_front"),
            ("three_quarter_1", "three_quarter"),
            ("profile_1", "profile"),
        )
    ]
    pack = IdentityAnchorPackVersion(
        pack_version_id=pack_id,
        people_asset_id=people_asset_id,
        status="active",
        anchor_views=views,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="portrait_root",
            project_id=project_id,
        ),
        user_activation_confirmed=True,
    )
    asset = PeopleAsset(
        people_asset_id=people_asset_id,
        project_id=project_id,
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_1",
            people_asset_id=people_asset_id,
            active_version_id=pack_id,
            status="active",
        ),
        active_pack_version_id=pack_id,
        status="active",
    )
    catalog.save_pack(pack, project_id=project_id, event_type="activate")
    catalog.save(asset, project_id=project_id, event_type="activate")
    return catalog


def _service(provider: EcommerceRemoteBrainTestProvider | None = None) -> tuple[V3ProductApiService, EcommerceRemoteBrainTestProvider]:
    brain_provider = provider or EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain_provider))
    return (
        V3ProductApiService(
            scenario_runtime=runtime,
            visual_asset_catalog=_catalog(),
        ),
        brain_provider,
    )


def _request() -> dict:
    return {
        "user_input": "Create a realistic portrait of the selected person in a calm indoor setting.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "professional_mode": "professional",
        "people_asset_id": "person_1",
        "metadata": {
            "project_id": "project_professional",
            "template_id": "general_template",
            "requested_image_count": 1,
            "require_real_images": True,
        },
    }


def test_product_api_wires_explicit_professional_mode_into_shared_planning() -> None:
    service, provider = _service()

    status = service.create_job(_request())

    assert status.status == ProductJobStatusValue.PLANNED
    assert status.metadata["professional_mode"] is True
    execution = status.metadata["professional_mode_execution"]
    assert execution["status"] == "ready"
    record = service.get_job_record(status.job_id)
    assert record is not None
    plan = record.request.metadata["capability_activation_plan"]
    assert plan["metadata"]["professional_mode"] is True
    assert "portrait_identity" in plan["dependency_order"]
    assert all("professional_mode_binding_record" not in request["metadata"] for request in provider.requests)
    assert all("professional_reference_channel_plans" not in request["metadata"] for request in provider.requests)


def test_professional_planning_provenance_boolean_is_accepted_on_generation() -> None:
    service, _ = _service()
    status = service.create_job(_request())

    assert status.status == ProductJobStatusValue.PLANNED
    record = service.get_job_record(status.job_id)
    assert record is not None
    assert record.request.metadata["professional_mode"] is True

    # The Product API stores planning provenance as a boolean, then reuses
    # that record for generation.  Scenario Runtime must normalize it back to
    # the explicit Professional Mode semantic instead of rejecting the job.
    runtime_payload = service._runtime_request_payload(record.request)  # noqa: SLF001
    planned = service.scenario_runtime.plan_job(runtime_payload)
    assert planned.status.value == "planned"
    assert "professional_mode_selection_invalid" not in " ".join(planned.warnings)
    assert planned.metadata["professional_mode"] is True


def test_professional_mode_missing_people_asset_is_a_structured_block() -> None:
    service, _ = _service()
    request = _request()
    request["people_asset_id"] = "missing_person"

    status = service.create_job(request)

    assert status.status == ProductJobStatusValue.BLOCKED
    assert status.asset_series == []
    assert "professional_people_asset_not_found" in " ".join(status.warnings)


def test_standard_mode_rejects_professional_metadata_before_runtime() -> None:
    service, _ = _service()
    request = _request()
    request["professional_mode"] = "standard"
    request["people_asset_id"] = None
    request["metadata"]["professional_mode_binding"] = {"people_asset_id": "person_1"}

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(request)


def test_professional_reference_admission_blocks_unsafe_full_frame_before_brain() -> None:
    service, provider = _service()
    request = _request()
    create_request = service._coerce_create_job_request(request)  # noqa: SLF001
    service._bind_server_job_instance_id(create_request)  # noqa: SLF001
    service._bind_professional_mode(create_request, trusted_capability_plan_reuse=False)  # noqa: SLF001
    payload = service._runtime_request_payload(create_request)  # noqa: SLF001
    binding = create_request.metadata["professional_mode_binding_record"]
    payload["metadata"] = {
        **payload["metadata"],
        "professional_reference_channel_plans": [
            {
                "project_id": binding["project_id"],
                "job_id": binding["job_id"],
                "reference_id": "mixed_full_frame",
                "declared_channels": ["object"],
                "channel_evidence": [
                    {
                        "channel": "object",
                        "evidence_ids": ["evidence_mixed_full_frame"],
                        "representation": "full_frame",
                    }
                ],
            }
        ],
    }

    result = service.scenario_runtime.plan_job(payload)

    assert result.status.value == "blocked"
    assert "professional_mode_reference_admission_blocked" in " ".join(result.warnings)
    assert provider.requests == []
