from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from alchemy_creative_agent_3_0.app.photography_profiles import (
    PhotographerProfileCatalog,
    PhotographerProfileDefinition,
    PhotographerProfileSelectionError,
)
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import ProjectTemplateRegistry, V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import TemplateStatus
from alchemy_creative_agent_3_0.app.project_mode.templates.contracts import (
    ProjectTemplateManifest,
    TemplateContextReadPolicy,
    TemplateContextWritePolicy,
    TemplateOutputSummaryPolicy,
)
from alchemy_creative_agent_3_0.app.scenario_packs import (
    ScenarioPack,
    ScenarioPackManifest,
    ScenarioPackRegistry,
    ScenarioPackStatus,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


def _profile_catalog(*, availability: str = "available", regions: list[str] | None = None) -> PhotographerProfileCatalog:
    return PhotographerProfileCatalog(
        [
            PhotographerProfileDefinition(
                profile_id="licensed_editorial",
                display_name="Licensed Editorial",
                profile_version="2026.07",
                availability=availability,
                allowed_regions=regions or [],
                technique_package_checksum="sha256:licensed-editorial-2026-07",
            )
        ]
    )


def _photography_runtime() -> ScenarioRuntime:
    packs = ScenarioPackRegistry().list_packs()
    packs.append(
        ScenarioPack(
            ScenarioPackManifest(
                scenario_id="photography",
                display_name="Photography",
                category="photography",
                status=ScenarioPackStatus.ACTIVE,
                description="Test-only Photography scenario contract.",
            )
        )
    )
    return ScenarioRuntime(scenario_registry=ScenarioPackRegistry(packs))


def _service(*, catalog: PhotographerProfileCatalog | None = None, region: str | None = None) -> V3ProductApiService:
    return V3ProductApiService(
        scenario_runtime=_photography_runtime(),
        photographer_profile_catalog=catalog or _profile_catalog(),
        photographer_profile_region_resolver=lambda: region,
    )


def _named_photography_request(**overrides: object) -> dict:
    payload: dict = {
        "user_input": "Create a quiet editorial portrait in natural window light.",
        "scenario_selection": {"scenario_id": "photography"},
        "photographer_profile_id": "licensed_editorial",
        "photographer_profile_selection_source": "user_explicit_ui",
    }
    payload.update(overrides)
    return payload


def _active_photography_template_registry(runtime: ScenarioRuntime) -> ProjectTemplateRegistry:
    template = ProjectTemplateManifest(
        template_id="photographer_template",
        display_name="Photography",
        short_description="Test-only Photography template.",
        scenario_pack_id="photography",
        status=TemplateStatus.ACTIVE,
        context_read_policy=TemplateContextReadPolicy(),
        context_write_policy=TemplateContextWritePolicy(can_create_jobs=True),
        output_summary_policy=TemplateOutputSummaryPolicy(),
        frontend_workspace="photographer_project_workspace",
    )
    return ProjectTemplateRegistry(manifests=[template], scenario_registry=runtime.scenario_registry)


def test_public_catalog_hides_unavailable_profiles_and_exposes_explicit_confirmation_contract() -> None:
    catalog = _profile_catalog()

    public = catalog.public_catalog()

    assert public["default_profile_id"] == "general_photography"
    named = next(item for item in public["profiles"] if item["profile_id"] == "licensed_editorial")
    assert named["binding_mode"] == "named"
    assert named["selection_requires_confirmation"] is True
    assert "technique_package_checksum" not in named

    unavailable = _profile_catalog(availability="rights_review_pending").public_catalog()
    assert [item["profile_id"] for item in unavailable["profiles"]] == ["general_photography"]


def test_named_profile_requires_explicit_ui_and_pins_an_immutable_snapshot() -> None:
    service = _service()

    with pytest.raises(PhotographerProfileSelectionError, match="must be confirmed") as exc_info:
        service.create_job(_named_photography_request(photographer_profile_selection_source=None))
    assert exc_info.value.code == "named_profile_requires_explicit_ui_selection"
    assert exc_info.value.v3_status_code == 422

    created = service.create_job(_named_photography_request())
    binding = service.photographer_profile_binding_for_job(created.job_id)

    assert binding is not None
    assert binding.binding_mode == "named"
    assert binding.profile_id == "licensed_editorial"
    assert binding.profile_version == "2026.07"
    assert binding.selection_source == "user_explicit_ui"
    assert created.metadata["photographer_profile_binding"]["profile_id"] == "licensed_editorial"

    with pytest.raises(PhotographerProfileSelectionError) as retry_error:
        service.generate_job(created.job_id, {"metadata": {"photographer_profile_id": "other"}})
    assert retry_error.value.code == "photographer_profile_binding_immutable"
    assert retry_error.value.v3_status_code == 409
    assert service.photographer_profile_binding_for_job(created.job_id) == binding


def test_profile_fields_are_inert_outside_photography_and_catalog_enforces_availability_and_region() -> None:
    service = _service()
    general = service.create_job(
        {
            "user_input": "Create a simple social-media cover.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "photographer_profile_id": "licensed_editorial",
            "photographer_profile_selection_source": "user_explicit_ui",
        }
    )
    assert "photographer_profile_binding" not in general.metadata

    unavailable_service = _service(catalog=_profile_catalog(availability="expired"))
    with pytest.raises(PhotographerProfileSelectionError) as unavailable:
        unavailable_service.create_job(_named_photography_request())
    assert unavailable.value.code == "photographer_profile_unavailable"
    assert unavailable.value.v3_status_code == 409

    region_service = _service(catalog=_profile_catalog(regions=["US"]), region="CN")
    with pytest.raises(PhotographerProfileSelectionError) as restricted:
        region_service.create_job(_named_photography_request())
    assert restricted.value.code == "photographer_profile_region_restricted"
    assert restricted.value.v3_status_code == 403


def test_project_mode_persists_exact_binding_without_defaulting_future_jobs() -> None:
    service = _service()
    project_service = V3ProjectModeService(
        product_service=service,
        template_registry=_active_photography_template_registry(service.scenario_runtime),
    )
    project = project_service.create_project(
        {"user_goal": "Plan a calm editorial portrait session.", "primary_template_id": "photographer_template"}
    ).project

    named = project_service.create_project_job(
        project.project_id,
        {
            "template_id": "photographer_template",
            "user_input": "Use the licensed editorial profile.",
            "photographer_profile_id": "licensed_editorial",
            "photographer_profile_selection_source": "user_explicit_ui",
        },
    )
    persisted = project_service.project_store.get_project(project.project_id)
    assert persisted is not None
    assert persisted.photographer_profile_bindings[named.job_id]["profile_id"] == "licensed_editorial"
    assert named.metadata["project_context_snapshot"]["photographer_profile_binding"]["profile_id"] == "licensed_editorial"

    general = project_service.create_project_job(
        project.project_id,
        {"template_id": "photographer_template", "user_input": "Create a separate general photography direction."},
    )
    assert persisted.photographer_profile_bindings[named.job_id]["profile_id"] == "licensed_editorial"
    general_binding = service.photographer_profile_binding_for_job(general.job_id)
    assert general_binding is not None
    assert general_binding.binding_mode == "general"
    assert general_binding.profile_id == "general_photography"


def test_catalog_route_and_frontend_only_offer_named_profile_after_manual_confirmation(monkeypatch) -> None:
    from app import main as app_main

    service = _service()
    monkeypatch.setattr(app_main, "v3_route_handlers", V3ProductRouteHandlers(service=service))
    client = TestClient(app_main.app)
    response = client.get("/api/v3/creative-agent/scenarios/photography/photographer-profiles")

    assert response.status_code == 200
    assert response.json()["default_profile_id"] == "general_photography"

    frontend = (app_main.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert 'photographer_profile_selection_source: namedPhotographerProfileConfirmed ? "user_explicit_ui" : undefined' in frontend
    assert 'photographerProfile?.binding_mode === "named"' in frontend
    assert 'selectedPhotographerProfileId === "general_photography"' in frontend
    assert 'selected !== "photography"' in frontend
