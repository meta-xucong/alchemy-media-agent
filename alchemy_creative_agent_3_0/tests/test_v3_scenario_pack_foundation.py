from alchemy_creative_agent_3_0.app.scenario_packs import (
    ScenarioPackRegistry,
    ScenarioPackStatus,
    ScenarioSelection,
)


def test_scenario_pack_registry_defaults_to_general_creative() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve()

    assert resolution.manifest.scenario_id == "general_creative"
    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.can_create_jobs is True
    assert resolution.selected_mode_id == "freeform"
    assert resolution.warnings == []


def test_scenario_pack_hub_lists_general_active_and_future_packs_placeholder() -> None:
    registry = ScenarioPackRegistry()

    manifests = registry.list_manifests()
    by_id = {manifest.scenario_id: manifest for manifest in manifests}

    assert set(by_id) == {"general_creative", "ecommerce", "new_media", "private_domain", "brand_ip"}
    assert by_id["general_creative"].status == ScenarioPackStatus.ACTIVE
    assert by_id["general_creative"].can_create_jobs is True
    assert by_id["ecommerce"].status == ScenarioPackStatus.ACTIVE
    assert by_id["ecommerce"].can_create_jobs is True
    assert by_id["ecommerce"].ui_card["primary_action"] == "create_job"
    assert by_id["new_media"].status == ScenarioPackStatus.PLACEHOLDER


def test_placeholder_scenario_resolves_without_allowing_job_creation() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve({"scenario_id": "new_media"})

    assert resolution.status == ScenarioPackStatus.PLACEHOLDER
    assert resolution.can_create_jobs is False
    assert resolution.selected_mode_id == "coming_soon"
    assert "not active" in resolution.warnings[0]


def test_ecommerce_scenario_selection_accepts_product_level_mode_preset_and_platform() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve(
        {
            "scenario_id": "ecommerce",
            "mode_id": "marketplace_listing_set",
            "preset_id": "marketplace_listing_set",
            "platform_profile": "amazon_us",
            "parameters": {"market": "US"},
        }
    )

    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.can_create_jobs is True
    assert resolution.selected_mode_id == "marketplace_listing_set"
    assert resolution.selected_preset_id == "marketplace_listing_set"
    assert resolution.selection.platform_profile == "amazon_us"


def test_general_scenario_selection_accepts_product_level_mode_and_preset() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve(
        ScenarioSelection(
            scenario_id="general_creative",
            mode_id="campaign_poster",
            preset_id="campaign_poster",
            parameters={"tone": "fresh"},
        )
    )

    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.selected_mode_id == "campaign_poster"
    assert resolution.selected_preset_id == "campaign_poster"
    assert resolution.selection.parameters == {"tone": "fresh"}


def test_unknown_scenario_resolves_as_inactive_product_level_state() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve({"scenario_id": "unknown_future_pack"})

    assert resolution.status == ScenarioPackStatus.INACTIVE
    assert resolution.can_create_jobs is False
    assert resolution.manifest.metadata["resolution_error"] == "unknown_scenario"


def test_unsupported_mode_and_preset_fall_back_to_safe_general_defaults() -> None:
    registry = ScenarioPackRegistry()

    resolution = registry.resolve(
        {
            "scenario_id": "general_creative",
            "mode_id": "not_a_real_mode",
            "preset_id": "not_a_real_preset",
        }
    )

    assert resolution.status == ScenarioPackStatus.ACTIVE
    assert resolution.can_create_jobs is True
    assert resolution.selected_mode_id == "freeform"
    assert resolution.selected_preset_id is None
    assert any("mode_id" in warning for warning in resolution.warnings)
    assert any("preset_id" in warning for warning in resolution.warnings)
