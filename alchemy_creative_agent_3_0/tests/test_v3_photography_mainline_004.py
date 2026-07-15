from __future__ import annotations

from copy import deepcopy
import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.providers.base import ProviderRuntimeError

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationProvider,
    GenerationRequest,
    GenerationResponse,
    GenerationRouter,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.project_mode.service import PhotographyRoleContinuationError
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographyScenarioPackPlanner,
    PhotographyTechniquePackage,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.specialized_planning import PhotographyScenarioPlanningAdapter
from alchemy_creative_agent_3_0.app.schemas import CandidateResult, ProviderStrategy
from alchemy_creative_agent_3_0.tests.photography_test_support import photography_test_runtime, photography_test_service


class _RecordingProductionProvider(GenerationProvider):
    """Provider fixture that persists pixels but never calls a real model."""

    provider_name = "recording_production_provider"

    def __init__(self, output_store: V3GeneratedOutputStore, *, fail_role: str | None = None) -> None:
        self.output_store = output_store
        self.fail_role = fail_role
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.requests.append(request.model_copy(deep=True))
        role = dict(request.metadata.get("mode_role_recipe") or {})
        role_key = str(role.get("role_key") or "")
        if role_key == self.fail_role:
            error = ProviderRuntimeError(
                f"simulated provider failure for {role_key}",
                provider=self.provider_name,
                detail={"private_provider_message": "must never reach a Project response"},
            )
            error.provider_failure_retry = {
                "final_status": "failed",
                "final_classification": "non_retryable_provider_failure",
                "final_failure_code": "image_generation_invalid_request_unattributed",
                "fresh_upstream_requests": 1,
                "reference_asset_count": 0,
                "reference_input_execution": {
                    "operation": "image_generate",
                    "reference_count": 0,
                    "operation_outcome": "failed",
                    "outer_request_count": 1,
                    "failure_code": "image_generation_invalid_request_unattributed",
                },
            }
            raise error
        image = BytesIO()
        Image.new("RGB", (32, 32), color=(104, 146, 184)).save(image, format="PNG")
        candidate_id = f"candidate_{role_key or len(self.requests)}"
        stored = self.output_store.save_base64_output(
            job_id=str(request.metadata["job_id"]),
            candidate_id=candidate_id,
            asset_id=request.generation_plan.asset_id,
            provider=self.provider_name,
            model="fixture",
            encoded_image=base64.b64encode(image.getvalue()).decode("ascii"),
            metadata={
                "mode_role_key": role_key,
                "mode_role_recipe": role,
                "role_specific_generation_plan": dict(request.metadata.get("role_specific_generation_plan") or {}),
            },
        )
        return GenerationResponse(
            candidates=[
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    file_path=stored.file_path,
                    uri=stored.thumbnail_url,
                    provider=self.provider_name,
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=False,
                    metadata={
                        "output_id": stored.output_id,
                        "download_url": stored.download_url,
                        "preview_url": stored.preview_url,
                        "thumbnail_url": stored.thumbnail_url,
                        "mode_role_key": role_key,
                        "mode_role_recipe": role,
                    },
                )
            ]
        )


def _handlers_with_recording_production_provider(
    tmp_path: Path,
    *,
    fail_role: str | None = None,
) -> tuple[V3ProductRouteHandlers, _RecordingProductionProvider]:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = photography_test_service(output_store=output_store)
    provider = _RecordingProductionProvider(output_store, fail_role=fail_role)
    service.scenario_runtime.generation_router = GenerationRouter(provider=provider)
    return V3ProductRouteHandlers(service=service, project_store=PersistentProjectStore(tmp_path / "projects")), provider


def _project_and_root(
    handlers: V3ProductRouteHandlers,
    *,
    profile: dict | None = None,
    mode_id: str = "professional_set",
) -> tuple[dict, dict]:
    project = handlers.post_projects(
        {
            "primary_template_id": "photographer_template",
            "user_goal": "Create a professional portrait session of a ceramic artist in her studio.",
        }
    )["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "photographer_template",
            "user_input": "Create a professional portrait session of a ceramic artist in her studio.",
            "photographer_profile_id": profile.get("profile_id") if profile else None,
            "photographer_profile_selection_source": profile.get("selection_source") if profile else None,
            "metadata": {"selected_mode_id": mode_id, "scene_domain": "portrait"},
        },
    )
    assert root["status"] == "planned"
    return project, root


def _ready_nonhuman_identity_upload(handlers: V3ProductRouteHandlers, *, filename: str) -> str:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(170, 142, 96)).save(buffer, format="PNG")
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "nonhuman_identity_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {"content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"), "mime_type": "image/png"},
    )
    assert handlers.post_upload_complete(created["asset_id"])["status"] == "ready"
    return created["asset_id"]


def test_professional_set_executes_three_frozen_roles_and_resolves_one_winner_per_role(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    project, root = _project_and_root(handlers)
    record = handlers.service.get_job_record(root["job_id"])
    assert record is not None
    specialized = record.request.metadata["specialized_scenario_plan"]
    assert specialized["execution_plan"]["metadata"]["professional_set"] is True
    assert [item["role_key"] for item in specialized["execution_plan"]["role_recipes"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]

    generated = handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    assert generated["status"] == "generated"
    assert len(generated["asset_series"]) == 3
    assert [item["metadata"]["asset_metadata"]["mode_role_key"] for item in generated["asset_series"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert len(generated["metadata"]["post_generation_review"]["inspections"]) == 3

    for role_id in ("session_hero", "environmental_context", "detail_or_moment"):
        delivery = handlers.get_project_photography_role_delivery(project["project_id"], root["job_id"], role_id)
        assert delivery["current_delivery"]["job_id"] == root["job_id"]
        assert delivery["current_delivery"]["role_id"] == role_id
        assert delivery["metadata"]["final_role_winner_only"] is True


def test_professional_set_t2i_executes_three_frozen_roles_without_generated_image_edit_chain(monkeypatch, tmp_path) -> None:
    """P10-T2I must make one shared provider request per frozen role, not an edit chain."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers, provider = _handlers_with_recording_production_provider(tmp_path)
    project, root = _project_and_root(handlers)

    generated = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard", "metadata": {"require_real_images": True, "disable_visual_auto_retry": True}},
    )

    assert generated["status"] == "generated"
    assert len(provider.requests) == 3
    assert [request.metadata["mode_role_recipe"]["role_key"] for request in provider.requests] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert all(request.metadata.get("reference_assets") == [] for request in provider.requests)
    assert all(request.metadata["auto_batch_identity_anchor_policy"]["enabled"] is False for request in provider.requests)
    assert all(
        request.metadata["capability_execution_envelope"]["activation_plan"]["activation_mode"] == "enforced"
        for request in provider.requests
    )
    rendered_prompts = [
        ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001
        for request in provider.requests
    ]
    assert "This image role: Session Hero" in rendered_prompts[0]
    assert "This image role: Environmental Context" in rendered_prompts[1]
    assert "This image role: Detail Or Moment" in rendered_prompts[2]
    assert all("Remote Photography direction" in prompt for prompt in rendered_prompts)
    assert all("Suite director rules:" not in prompt for prompt in rendered_prompts)
    assert all("Cover hero" not in prompt for prompt in rendered_prompts)
    summary = generated["metadata"]["specialized_execution_summary"]
    assert summary["status"] == "complete"
    assert [item["role_key"] for item in summary["roles"]] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert len([item for item in generated["asset_series"] if item["output_id"]]) == 3


def test_professional_set_role_failure_is_explicit_and_never_reconciles_as_a_single_delivery(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers, provider = _handlers_with_recording_production_provider(tmp_path, fail_role="environmental_context")
    project, root = _project_and_root(handlers)

    blocked = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard", "metadata": {"require_real_images": True, "disable_visual_auto_retry": True}},
    )

    assert blocked["status"] == "blocked"
    assert [request.metadata["mode_role_recipe"]["role_key"] for request in provider.requests] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    summary = blocked["metadata"]["specialized_execution_summary"]
    assert summary["status"] == "incomplete"
    assert summary["missing_role_keys"] == ["environmental_context"]
    assert summary["final_delivery_withheld"] is True
    failed_role = next(item for item in summary["roles"] if item["role_key"] == "environmental_context")
    assert failed_role["provider_failure"] == {
        "state": "blocked",
        "classification": "non_retryable_provider_failure",
        "failure_code": "image_generation_invalid_request_unattributed",
        "operation": "image_generate",
        "reference_count": 0,
        "outer_request_count": 1,
    }
    assert "private_provider_message" not in str(summary)

    timeline = handlers.get_project_timeline(project["project_id"])["items"]
    root_items = [item for item in timeline if item.get("job_id") == root["job_id"]]
    assert not any(item["item_type"] == "job_generated" for item in root_items)
    assert any(
        item["item_type"] == "note_added"
        and item["metadata"].get("execution_diagnostic") == "specialized_role_coverage_incomplete"
        for item in root_items
    )
    assert handlers.get_project_outputs(project_id=project["project_id"])["items"] == []


def test_frontend_uses_safe_specialized_provider_failure_when_a_role_has_no_delivery() -> None:
    script = (Path(__file__).resolve().parents[2] / "src_skeleton" / "app" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "function v3SpecializedProviderFailure(job)" in script
    assert "|| specializedFailure.failure_code" in script


def test_metadata_only_photography_project_withholds_pixels_and_records_safe_review_state(monkeypatch) -> None:
    """Non-certifying pixels remain history, never ordinary project delivery."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    project, root = _project_and_root(handlers, mode_id="single_hero")

    blocked = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "metadata_only"}},
    )

    assert blocked["status"] == "blocked"
    certification = blocked["metadata"]["review_certification"]
    assert certification["state"] == "blocked"
    assert certification["final_delivery_withheld"] is True
    assert handlers.get_project_outputs(project_id=project["project_id"])["items"] == []

    timeline = handlers.get_project_timeline(project["project_id"])["items"]
    review_items = [item for item in timeline if item.get("job_id") == root["job_id"]]
    assert any(
        item["metadata"].get("review_certification", {}).get("state") == "blocked"
        and item["metadata"].get("normal_project_delivery_withheld") is True
        for item in review_items
    )


def test_manual_vision_confirmation_is_visible_but_never_counts_as_photography_delivery(monkeypatch) -> None:
    """A live but inconclusive pixel review must remain visible and withheld."""

    class ManualVisionProvider:
        provider_name = "manual_confirmation_fixture"

        def available(self, *, force: bool = False) -> bool:
            return True

        def inspect(self, resolution, *, metadata=None) -> dict:
            return {
                "status": "manual_review",
                "confidence": 0.4,
                "issue_codes": ["low_confidence_review"],
                "scores": {"artifact_safety": 0.5, "composition": 0.5, "commercial_finish": 0.5, "overall": 0.5},
            }

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    service = photography_test_service()
    service.vision_inspector.vision_provider = ManualVisionProvider()
    handlers = V3ProductRouteHandlers(service=service)
    project, root = _project_and_root(handlers, mode_id="single_hero")

    blocked = handlers.post_project_job_generate(
        project["project_id"],
        root["job_id"],
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model"}},
    )

    certification = blocked["metadata"]["review_certification"]
    assert blocked["status"] == "blocked"
    assert certification["state"] == "manual_confirmation_required"
    assert certification["automatic_delivery_certified"] is False
    assert certification["manual_confirmation_required"] is True
    assert certification["final_delivery_withheld"] is True
    assert certification["roles"][0]["review_mode"] == "vision_model"
    assert certification["roles"][0]["review_status"] == "manual_review"
    assert handlers.get_project_outputs(project_id=project["project_id"])["items"] == []

    timeline = handlers.get_project_timeline(project["project_id"])["items"]
    assert any(
        item["metadata"].get("review_certification", {}).get("state") == "manual_confirmation_required"
        and item["metadata"].get("normal_project_delivery_withheld") is True
        for item in timeline
        if item.get("job_id") == root["job_id"]
    )


def test_photography_project_summary_and_terminal_delivery_keep_the_photographer_binding(monkeypatch) -> None:
    """A Photography project must never be summarized as General after a terminal job."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    project, root = _project_and_root(handlers, mode_id="single_hero")

    assert project["primary_template_id"] == "photographer_template"
    assert project["memory_summary"]["active_template_label"] == "摄影师模板"
    assert root["scenario"]["scenario_id"] == "photography"
    assert root["metadata"]["template_id"] == "photographer_template"

    generated = handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    assert generated["status"] == "generated"
    assert generated["scenario"]["scenario_id"] == "photography"
    assert len(generated["asset_series"]) == 1
    assert all(item["output_id"] for item in generated["asset_series"])

    reopened = handlers.get_project(project["project_id"])["project"]
    recent = handlers.get_projects(limit=10)
    summary = next(item for item in recent["projects"] if item["project_id"] == project["project_id"])
    terminal = handlers.get_job(root["job_id"])
    timeline = handlers.get_project_timeline(project["project_id"])["items"]

    assert reopened["primary_template_id"] == "photographer_template"
    assert reopened["memory_summary"]["active_template_label"] == "摄影师模板"
    assert summary["active_template_label"] == "摄影师模板"
    assert terminal["status"] == "generated"
    assert terminal["scenario"]["scenario_id"] == "photography"
    assert len(terminal["asset_series"]) == 1
    assert terminal["asset_series"][0]["output_id"]
    assert terminal["asset_series"][0]["preview_url"]
    assert any(item["item_type"] == "job_generated" and item["job_id"] == root["job_id"] for item in timeline)


def test_role_continuation_is_append_only_and_reuses_the_exact_frozen_plan(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    project, root = _project_and_root(handlers)
    handlers.post_project_job_generate(project["project_id"], root["job_id"], {"quality_mode": "standard"})
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    frozen_parent_metadata = deepcopy(root_record.request.metadata)

    continuation = handlers.post_project_photography_role_continuation(
        project["project_id"],
        root["job_id"],
        "environmental_context",
        {"correction_note": "Show more of the working studio while keeping the same color finish."},
    )
    child_record = handlers.service.get_job_record(continuation["child_job_id"])
    assert child_record is not None
    assert continuation["lineage"]["root_job_id"] == root["job_id"]
    assert continuation["lineage"]["parent_role_id"] == "environmental_context"
    assert child_record.request.metadata["capability_activation_plan"] == frozen_parent_metadata["capability_activation_plan"]
    child_execution = child_record.request.metadata["specialized_scenario_plan"]["execution_plan"]
    assert child_execution["requested_image_count"] == 1
    assert [item["role_key"] for item in child_execution["role_recipes"]] == ["environmental_context"]
    assert root_record.request.metadata == frozen_parent_metadata

    child = handlers.post_project_job_generate(project["project_id"], continuation["child_job_id"], {"quality_mode": "standard"})
    assert child["status"] == "generated"
    assert len(child["asset_series"]) == 1
    delivery = handlers.get_project_photography_role_delivery(project["project_id"], root["job_id"], "environmental_context")
    assert delivery["current_delivery"]["job_id"] == continuation["child_job_id"]
    assert [attempt["job_id"] for attempt in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]


def test_named_profile_continuation_requires_exact_explicit_reconfirmation(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    operator_catalog = PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="licensed_session_v1",
                profile_version="2026.07",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Licensed Session Profile",
                supported_scene_ids=["portrait"],
                supported_commission_ids=["single_hero", "professional_session"],
                technique_package=PhotographyTechniquePackage(
                    composition=["deliberate environmental portrait hierarchy"],
                    lighting=["soft directional window light"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                allowed_regions=["CN"],
            )
        ],
        catalog_version="mainline-004-test",
    )
    runtime = photography_test_runtime(
        specialized_planning_adapters=[
            PhotographyScenarioPlanningAdapter(
                planner=PhotographyScenarioPackPlanner(
                    profile_catalog=operator_catalog,
                    named_profiles_enabled=True,
                )
            )
        ]
    )
    service = V3ProductApiService(
        scenario_runtime=runtime,
        photographer_profile_catalog=operator_catalog.shared_catalog(),
        photographer_profile_region_resolver=lambda: "CN",
    )
    handlers = V3ProductRouteHandlers(service=service)
    project, root = _project_and_root(
        handlers,
        profile={"profile_id": "licensed_session_v1", "selection_source": "user_explicit_ui"},
    )
    with pytest.raises(PhotographyRoleContinuationError, match="named_profile_continuation_requires_explicit_ui_reconfirmation"):
        handlers.post_project_photography_role_continuation(
            project["project_id"], root["job_id"], "session_hero", {"correction_note": "Use a calmer expression."}
        )
    binding = service.photographer_profile_binding_for_job(root["job_id"])
    assert binding is not None
    continuation = handlers.post_project_photography_role_continuation(
        project["project_id"],
        root["job_id"],
        "session_hero",
        {
            "correction_note": "Use a calmer expression.",
            "profile_selection_source": "user_explicit_ui",
            "reconfirmed_profile_id": binding.profile_id,
            "reconfirmed_profile_version": binding.profile_version,
            "reconfirmed_technique_package_checksum": binding.technique_package_checksum,
        },
    )
    child_binding = service.photographer_profile_binding_for_job(continuation["child_job_id"])
    assert child_binding is not None
    assert child_binding.model_dump(mode="json") == binding.model_dump(mode="json")


def test_role_lineage_survives_project_store_reload_and_general_is_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    store_root = Path(tmp_path) / "projects"
    first = V3ProductRouteHandlers(service=photography_test_service(), project_store=PersistentProjectStore(store_root))
    project, root = _project_and_root(first)
    restarted = V3ProductRouteHandlers(service=photography_test_service(), project_store=PersistentProjectStore(store_root))
    continuation = restarted.post_project_photography_role_continuation(
        project["project_id"], root["job_id"], "detail_or_moment", {"correction_note": "Emphasize the hands and clay detail."}
    )
    delivery = restarted.get_project_photography_role_delivery(project["project_id"], root["job_id"], "detail_or_moment")
    assert continuation["child_status"] == "planned"
    assert [item["job_id"] for item in delivery["attempts"]] == [root["job_id"], continuation["child_job_id"]]

    general = first.post_projects({"user_goal": "Create an abstract book cover"})["project"]
    general_job = first.post_project_job(general["project_id"], {"user_input": "Create an abstract book cover"})
    with pytest.raises(PhotographyRoleContinuationError) as unsupported:
        first.post_project_photography_role_continuation(
            general["project_id"], general_job["job_id"], "session_hero", {}
        )
    assert unsupported.value.code == "photography_role_continuation_not_supported"


def test_new_animal_identity_evidence_is_renegotiated_and_blocks_without_shared_native_support(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    handlers = V3ProductRouteHandlers(service=photography_test_service())
    original_reference = _ready_nonhuman_identity_upload(handlers, filename="dog-original.png")
    project = handlers.post_projects(
        {
            "primary_template_id": "photographer_template",
            "user_goal": "Professionally reshoot the same dog running through a forest.",
            "uploaded_asset_ids": [original_reference],
        }
    )["project"]
    root = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "photographer_template",
            "user_input": "Professionally reshoot the same dog running through a forest.",
            "uploaded_asset_ids": [original_reference],
            "metadata": {
                "selected_mode_id": "professional_set",
                "scene_domain": "animal",
                "preserve_nonhuman_identity": True,
            },
        },
    )
    root_record = handlers.service.get_job_record(root["job_id"])
    assert root_record is not None
    assert "nonhuman_subject_identity" in root_record.request.metadata["capability_activation_plan"]["dependency_order"]
    new_reference = _ready_nonhuman_identity_upload(handlers, filename="dog-new-angle.png")
    handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": new_reference, "use_policy": "identity", "label": "new dog identity view"},
    )
    preview_calls: list[dict] = []

    def unavailable(payload: dict):
        preview_calls.append(payload)
        raise RuntimeError("native high-fidelity identity support unavailable")

    monkeypatch.setattr(handlers.service, "preview_capability_activation", unavailable)
    with pytest.raises(PhotographyRoleContinuationError) as blocked:
        handlers.post_project_photography_role_continuation(
            project["project_id"],
            root["job_id"],
            "session_hero",
            {"new_reference_asset_ids": [new_reference]},
        )
    assert blocked.value.code == "photography_role_plan_amendment_unavailable"
    assert preview_calls and new_reference in preview_calls[0]["uploaded_asset_ids"]
    assert preview_calls[0]["scenario_selection"]["scenario_id"] == "photography"
