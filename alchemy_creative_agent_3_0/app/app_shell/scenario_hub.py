"""Scenario Hub contract for the V3 app shell."""

from __future__ import annotations

from typing import Any

from ..scenario_packs import ScenarioPackRegistry, ScenarioPackStatus
from .navigation import get_navigation_entry
from .routes import API_NAMESPACE, get_route_contracts


def get_scenario_hub_contract(registry: ScenarioPackRegistry | None = None) -> dict[str, Any]:
    registry = registry or ScenarioPackRegistry()
    nav = get_navigation_entry()
    scenario_cards = []
    for manifest in registry.list_manifests():
        scenario_cards.append(
            {
                "scenario_id": manifest.scenario_id,
                "display_name": manifest.display_name,
                "status": manifest.status.value,
                "can_create_jobs": manifest.can_create_jobs,
                "route_hint": manifest.route_hint,
                "default_mode_id": manifest.default_mode_id,
                "supported_mode_ids": list(manifest.supported_mode_ids),
                "preset_ids": list(manifest.preset_ids),
                "ui_card": dict(manifest.ui_card),
                "primary_action": "create_job" if manifest.status == ScenarioPackStatus.ACTIVE else "show_placeholder",
                "description": manifest.description,
            }
        )
    return {
        "entry_route": nav["route"],
        "api_namespace": API_NAMESPACE,
        "routes": get_route_contracts(),
        "default_scenario_id": registry.default_pack().scenario_id,
        "scenario_cards": scenario_cards,
        "active_scenario_ids": [
            card["scenario_id"] for card in scenario_cards if card["status"] == ScenarioPackStatus.ACTIVE.value
        ],
        "placeholder_scenario_ids": [
            card["scenario_id"] for card in scenario_cards if card["status"] == ScenarioPackStatus.PLACEHOLDER.value
        ],
        "metadata": {
            "source": "V3ScenarioHubContract",
            "placeholder_cards_do_not_create_jobs": True,
        },
    }
