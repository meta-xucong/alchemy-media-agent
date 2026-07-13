from __future__ import annotations

from pathlib import Path

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import ProjectTemplateRegistry
from alchemy_creative_agent_3_0.app.project_mode.contracts import TemplateStatus
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographyScenarioPackPlanner,
    PhotographyTechniquePackage,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_runtime.specialized_planning import PhotographyScenarioPlanningAdapter
from alchemy_creative_agent_3_0.app.shared_capabilities import AssetRole, UploadedAssetInfo
from alchemy_creative_agent_3_0.tests.photography_test_support import (
    PhotographyRemoteBrainTestProvider,
    photography_test_runtime,
    photography_test_service,
    photography_test_vision_inspector,
)


def _binding() -> dict:
    return {
        "binding_mode": "general",
        "profile_id": "general_photography",
        "profile_display_name": "General Photography",
        "profile_version": "v1",
        "selection_source": None,
        "catalog_version": "mainline-catalog-v1",
        "availability_decision": "general_default",
        "technique_package_checksum": "general-photography-v1",
        "pinned_at": "2026-07-13T00:00:00+00:00",
    }


def _request(**overrides) -> dict:
    payload = {
        "user_input": "Create a quiet editorial portrait in natural window light.",
        "scenario_selection": {"scenario_id": "photography", "mode_id": "single_hero"},
        "metadata": {"template_id": "photographer_template", "photographer_profile_binding": _binding()},
    }
    payload.update(overrides)
    return payload


def test_gate_off_leaves_photography_unregistered_and_template_placeholder(monkeypatch) -> None:
    monkeypatch.delenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", raising=False)

    registry = ScenarioPackRegistry()
    assert registry.get_pack("photography") is None
    manifest = ProjectTemplateRegistry(scenario_registry=registry).get_manifest("photographer_template")
    assert manifest is not None
    assert manifest.status == TemplateStatus.PLACEHOLDER
    assert manifest.scenario_pack_id == "future_photographer"

    result = ScenarioRuntime(scenario_registry=registry).plan_job(_request())
    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.scenario_resolution.can_create_jobs is False


def test_gate_on_freezes_photography_plan_then_uses_shared_generation_review_and_retry(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    service = photography_test_service()

    created = service.create_job(
        {
            "user_input": "Create a quiet editorial portrait in natural window light.",
            "scenario_selection": {"scenario_id": "photography", "mode_id": "single_hero"},
        }
    )
    assert created.status.value == "planned"
    assert created.scenario.scenario_id == "photography"
    record = service.get_job_record(created.job_id)
    assert record is not None
    frozen = record.request.metadata["specialized_scenario_plan"]
    assert frozen["planner_id"] == "photography_scenario_pack"
    assert frozen["safe_summary"]["shared_execution_only"] is True
    assert record.request.metadata["photographer_profile_binding"]["profile_id"] == "general_photography"
    assert "photography_direction" in record.request.metadata["capability_activation_plan"]["dependency_order"]

    generated = service.generate_job(created.job_id)
    assert generated.status.value == "generated"
    generated_record = service.get_job_record(created.job_id)
    assert generated_record is not None
    assert generated_record.request.metadata["specialized_scenario_plan"] == frozen
    assert generated.metadata["post_generation_review"]
    assert generated.metadata["visual_auto_retry"].get("append_only") is True
    assert generated.metadata["specialized_scenario_plan_summary"]["scene_domain"] == "portrait"


def test_adapter_uses_only_pinned_entry_point_and_composer_materializes_direction(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    planner = PhotographyScenarioPackPlanner(named_profiles_enabled=True)
    calls: list[str] = []
    original = planner.plan_from_pinned_binding

    def pinned_only(**kwargs):
        calls.append(str(kwargs["profile_binding"].get("profile_id")))
        return original(**kwargs)

    def forbidden_local_selection(**_kwargs):
        raise AssertionError("the activated runtime must not call PhotographyScenarioPackPlanner.plan")

    monkeypatch.setattr(planner, "plan_from_pinned_binding", pinned_only)
    monkeypatch.setattr(planner, "plan", forbidden_local_selection)
    runtime = photography_test_runtime(specialized_planning_adapters=[PhotographyScenarioPlanningAdapter(planner=planner)])

    result = runtime.generate_job(_request())
    assert result.status == ScenarioRuntimeStatus.GENERATED
    assert calls == ["general_photography"]
    cluster = result.metadata["shared_capabilities"]["visual_cluster"]
    composed = cluster["composed_visual_contribution"]
    assert "photography_direction" in composed["active_capability_ids"]
    photography_contribution = next(
        item for item in cluster["capability_contributions"] if item["capability_id"] == "photography_direction"
    )
    assert photography_contribution["prompt_additions"] == []
    assert photography_contribution["negative_additions"] == []
    assert photography_contribution["metadata"]["static_recipe_present"] is False


def test_nonhuman_identity_request_blocks_without_typed_native_reference_and_requires_shared_capability(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=PhotographyRemoteBrainTestProvider())
    )
    unknown = UploadedAssetInfo(asset_id="asset_dog", role=AssetRole.UNKNOWN_REFERENCE, uri="memory://dog")
    blocked = runtime.plan_job(
        _request(
            user_input="Create a professional reshoot of the same dog in a forest.",
            scenario_selection={"scenario_id": "photography", "mode_id": "reference_reshoot"},
            uploaded_assets=[unknown],
        )
    )
    assert blocked.status == ScenarioRuntimeStatus.BLOCKED
    assert "nonhuman_identity_reference_required" in " ".join(blocked.warnings)

    reference = Path(tmp_path / "dog.png")
    reference.write_bytes(b"not-read-during-planning")
    typed = UploadedAssetInfo(
        asset_id="asset_dog_identity",
        role=AssetRole.NONHUMAN_IDENTITY_REFERENCE,
        file_path=str(reference),
        filename=reference.name,
        mime_type="image/png",
    )
    accepted = runtime.plan_job(
        _request(
            user_input="Create a professional reshoot of the same dog in a forest.",
            scenario_selection={"scenario_id": "photography", "mode_id": "reference_reshoot"},
            uploaded_assets=[typed],
        )
    )
    assert accepted.status == ScenarioRuntimeStatus.PLANNED
    frozen = accepted.metadata["capability_activation_plan"]
    assert "nonhuman_subject_identity" in frozen["dependency_order"]
    assert accepted.metadata["specialized_scenario_plan_summary"]["required_capability_ids"] == [
        "nonhuman_subject_identity"
    ]


def test_general_and_ecommerce_never_activate_photography_direction_when_gate_is_on(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=PhotographyRemoteBrainTestProvider())
    )

    general = runtime.plan_job({"user_input": "Create a calm abstract book cover.", "scenario_selection": {"scenario_id": "general_creative"}})
    ecommerce = runtime.plan_job({"user_input": "Create a clean product atmosphere image.", "scenario_selection": {"scenario_id": "ecommerce"}})

    for result in (general, ecommerce):
        assert result.status == ScenarioRuntimeStatus.PLANNED
        plan = result.metadata["capability_activation_plan"]
        assert "photography_direction" not in plan["dependency_order"]
        assert "specialized_scenario_plan" not in result.metadata


def test_named_profile_is_validated_and_pinned_by_mainline_then_read_by_photography_planner(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    operator_catalog = PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="licensed_editorial_v1",
                profile_version="2026.07",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Licensed Editorial Profile",
                supported_scene_ids=["portrait"],
                supported_commission_ids=["single_hero"],
                technique_package=PhotographyTechniquePackage(
                    composition=["asymmetric frame with deliberate negative space"],
                    lighting=["soft directional window light with restrained fill"],
                    forbidden_techniques=["imitative signature or watermark"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                allowed_regions=["CN"],
            )
        ],
        catalog_version="photography-production-activation-test",
    )
    planner = PhotographyScenarioPackPlanner(profile_catalog=operator_catalog, named_profiles_enabled=True)
    runtime = photography_test_runtime(specialized_planning_adapters=[PhotographyScenarioPlanningAdapter(planner=planner)])
    service = V3ProductApiService(
        scenario_runtime=runtime,
        vision_inspector=photography_test_vision_inspector(),
        photographer_profile_catalog=operator_catalog.shared_catalog(),
        photographer_profile_region_resolver=lambda: "CN",
    )

    created = service.create_job(
        {
            "user_input": "Create a quiet editorial portrait of a ceramic artist in her studio.",
            "scenario_selection": {"scenario_id": "photography", "mode_id": "single_hero"},
            "photographer_profile_id": "licensed_editorial_v1",
            "photographer_profile_selection_source": "user_explicit_ui",
        }
    )
    record = service.get_job_record(created.job_id)
    assert record is not None
    assert record.request.metadata["photographer_profile_binding"]["profile_id"] == "licensed_editorial_v1"
    draft = record.request.metadata["specialized_scenario_plan"]["capability_contribution_draft"]
    assert draft["prompt_additions"] == []
    assert draft["metadata"]["creative_direction_owner"] == "remote_v3_llm_brain"

    generated = service.generate_job(created.job_id)
    assert generated.status.value == "generated"
    assert service.get_job_record(created.job_id).request.metadata["photographer_profile_binding"] == record.request.metadata[
        "photographer_profile_binding"
    ]
