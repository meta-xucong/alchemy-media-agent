import importlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographerProfileSelectionSource,
    PhotographyScenarioPack,
    PhotographyTechniquePackage,
    PhotographyUserControls,
)
from alchemy_creative_agent_3_0.app.scenario_packs.photography.scene_directors import (
    PhotographySceneDirectorRegistry,
)
from alchemy_creative_agent_3_0.app.scenario_packs.photography.technique_modules import (
    PhotographyTechniqueModuleRegistry,
)
from alchemy_creative_agent_3_0.app.vertical_agents import VerticalAgentRegistry
from alchemy_creative_agent_3_0.app.vertical_agents.photography_pack import PhotographyAgentFamily


def test_photography_pack_is_inactive_and_cannot_create_jobs() -> None:
    pack = PhotographyScenarioPack()
    resolution = pack.resolve()

    assert resolution.manifest.scenario_id == "photography"
    assert resolution.status == ScenarioPackStatus.INACTIVE
    assert resolution.can_create_jobs is False
    assert resolution.selected_mode_id == "single_hero"
    assert resolution.manifest.enabled_capabilities == []
    assert resolution.manifest.metadata["activation_ready"] is False
    assert resolution.manifest.metadata["named_profile_selection"] == "user_explicit_ui_only"


def test_importing_photography_has_no_default_registry_side_effect() -> None:
    before = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]

    importlib.import_module("alchemy_creative_agent_3_0.app.scenario_packs.photography")

    after = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]
    assert before == after
    assert "photography" not in after
    assert ScenarioPackRegistry().get_pack("photography") is None


def test_photography_agent_is_unregistered_and_cannot_win_selection() -> None:
    registry = VerticalAgentRegistry()
    pack_names = [pack.name for pack in registry.packs]
    photography = PhotographyAgentFamily()

    assert "photography_agent_family" not in pack_names
    assert photography.activation_ready is False
    assert photography.match(creative_job=None) == 0.0  # type: ignore[arg-type]
    assert photography.metadata()["registered_in_default_vertical_registry"] is False


def test_no_profile_selection_resolves_to_general_photography() -> None:
    catalog = PhotographerProfileCatalog()

    binding = catalog.resolve_binding(PhotographyUserControls())

    assert binding.binding_mode == "general"
    assert binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID
    assert binding.selection_source is None
    assert binding.metadata["selection_is_llm_authorized"] is False
    assert catalog.selectable_named_profiles() == []


def test_free_text_metadata_cannot_activate_a_named_profile() -> None:
    catalog = PhotographerProfileCatalog()
    controls = PhotographyUserControls(metadata={"user_text": "use a famous photographer style"})

    binding = catalog.resolve_binding(controls)

    assert binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID
    assert binding.binding_mode == "general"


def test_named_profile_id_requires_explicit_ui_selection() -> None:
    with pytest.raises(ValidationError, match="named_profile_requires_explicit_ui_selection"):
        PhotographyUserControls(photographer_profile_id="named_test_profile")


def test_explicit_approved_named_profile_can_be_pinned_in_module_local_catalog() -> None:
    named = PhotographerProfile(
        profile_id="named_test_profile",
        profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
        public_display_name="Named Test Profile",
        technique_package=PhotographyTechniquePackage(lighting=["controlled directional light"]),
        rights_status=PhotographerProfileRightsStatus.APPROVED,
        availability_status=PhotographerProfileAvailability.ACTIVE,
        review_owner="test",
        reviewed_at="2026-07-12T00:00:00+08:00",
    )
    catalog = PhotographerProfileCatalog(profiles=[named])
    controls = PhotographyUserControls(
        photographer_profile_id=named.profile_id,
        photographer_profile_selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
    )

    binding = catalog.resolve_binding(controls)

    assert binding.binding_mode == "named"
    assert binding.profile_id == named.profile_id
    assert binding.selection_source == PhotographerProfileSelectionSource.USER_EXPLICIT_UI
    assert len(binding.technique_package_checksum) == 64


def test_explicit_unavailable_named_profile_blocks_without_general_fallback() -> None:
    unavailable = PhotographerProfile(
        profile_id="unavailable_test_profile",
        profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
        public_display_name="Unavailable Test Profile",
        rights_status=PhotographerProfileRightsStatus.PENDING_REVIEW,
        availability_status=PhotographerProfileAvailability.INACTIVE,
    )
    catalog = PhotographerProfileCatalog(profiles=[unavailable])
    controls = PhotographyUserControls(
        photographer_profile_id=unavailable.profile_id,
        photographer_profile_selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
    )

    with pytest.raises(ValueError, match="named_profile_unavailable"):
        catalog.resolve_binding(controls)


def test_first_wave_scene_directors_are_descriptors_only_and_inactive() -> None:
    registry = PhotographySceneDirectorRegistry.with_first_wave_skeletons()
    descriptors = registry.list_descriptors()

    assert {item.scene_id for item in descriptors} == {"portrait", "landscape", "still_life", "animal"}
    assert all(item.status == "inactive" for item in descriptors)
    assert all(item.activation_ready is False for item in descriptors)
    assert all(item.metadata["contributes_runtime_behavior"] is False for item in descriptors)


def test_technique_modules_are_descriptors_only_and_inactive() -> None:
    registry = PhotographyTechniqueModuleRegistry.with_p1_skeletons()
    descriptors = registry.list_descriptors()

    assert len(descriptors) == 10
    assert registry.get("photographer_profile_binding") is not None
    assert all(item.status == "inactive" for item in descriptors)
    assert all(item.activation_ready is False for item in descriptors)
    assert all(item.contribution_stages == [] for item in descriptors)


def test_p1_photography_package_has_no_provider_or_v1_v2_runtime_dependency() -> None:
    package = importlib.import_module("alchemy_creative_agent_3_0.app.scenario_packs.photography")
    package_root = Path(package.__file__).parent
    source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.rglob("*.py"))

    forbidden = (
        "custom_media_agent_docs",
        "src_skeleton.app",
        "generation_router.providers",
        "product_api.service",
        ".providers import",
    )
    assert not any(token in source for token in forbidden)
