"""Minimal V3 UI contract and static semantic view helpers."""

from __future__ import annotations

from html import escape
from typing import Any

from .navigation import get_navigation_entry
from .routes import API_NAMESPACE, get_route_contracts
from .scenario_hub import get_scenario_hub_contract


def get_minimal_ui_contract() -> dict[str, Any]:
    routes = get_route_contracts()
    nav = get_navigation_entry()
    return {
        "app_root_id": "alchemy-creative-agent-v3",
        "entry_route": nav["route"],
        "api_namespace": API_NAMESPACE,
        "scenario_hub": get_scenario_hub_contract(),
        "default_flow": [
            "input_request",
            "show_asset_series_status",
            "generate_candidates",
            "select_result",
            "continue_style_from_brand",
        ],
        "semantic_controls": [
            {"element": "select", "name": "scenario_id", "label": "Scenario"},
            {"element": "form", "name": "Create creative job", "method": "POST", "action": routes["create_job"]},
            {"element": "textarea", "name": "user_input", "label": "Creative request"},
            {"element": "input", "name": "brand_id", "label": "Brand ID"},
            {"element": "button", "name": "create_job", "label": "Create job"},
            {"element": "button", "name": "generate_asset_series", "label": "Generate asset series"},
            {"element": "button", "name": "select_result", "label": "Select result"},
        ],
        "visible_state_regions": [
            {"id": "v3-job-status", "label": "Job status"},
            {"id": "v3-asset-series", "label": "Asset series"},
            {"id": "v3-candidates", "label": "Candidates"},
            {"id": "v3-selected-result", "label": "Selected result"},
            {"id": "v3-balance-estimate", "label": "Balance estimate"},
        ],
        "calls_only_v3_api_namespace": API_NAMESPACE,
        "does_not_share_v1_v2_workflow_state": True,
    }


def render_minimal_job_view(status: dict[str, Any] | None = None) -> str:
    """Render deterministic semantic HTML for browser probes and future adapters."""

    status = status or {}
    scenario_hub = get_scenario_hub_contract()
    scenario = status.get("scenario") or {}
    selected_scenario_id = str(scenario.get("scenario_id") or scenario_hub["default_scenario_id"])
    scenario_options = "\n".join(
        (
            f'<option value="{escape(str(card["scenario_id"]))}"'
            f'{" selected" if str(card["scenario_id"]) == selected_scenario_id else ""}'
            f' data-status="{escape(str(card["status"]))}">'
            f'{escape(str(card["display_name"]))}</option>'
        )
        for card in scenario_hub["scenario_cards"]
    )
    job_status = escape(str(status.get("status", "ready")))
    job_id = escape(str(status.get("job_id", "")))
    balance = status.get("balance_estimate", {})
    credits_required = escape(str(balance.get("credits_required", 0)))
    asset_items = status.get("asset_series", [])
    candidate_items = status.get("candidates", [])
    selected = status.get("selected_result") or {}

    asset_markup = "\n".join(
        (
            f'<li data-asset-id="{escape(str(asset.get("asset_id", "")))}">'
            f'{escape(str(asset.get("platform", "")))} '
            f'{escape(str(asset.get("purpose", "")))} '
            f'{escape(str(asset.get("status", "")))}'
            "</li>"
        )
        for asset in asset_items
    )
    candidate_markup = "\n".join(
        (
            f'<li data-candidate-id="{escape(str(candidate.get("candidate_id", "")))}">'
            f'{escape(str(candidate.get("asset_id", "")))} '
            f'{escape(str(candidate.get("recommendation", "")))}'
            "</li>"
        )
        for candidate in candidate_items
    )
    selected_ids = ", ".join(selected.get("selected_candidate_ids", []))

    return f"""<main id="alchemy-creative-agent-v3" data-api-namespace="{API_NAMESPACE}">
  <form aria-label="Create creative job" method="post" action="{get_route_contracts()["create_job"]}">
    <label for="v3-scenario-id">Scenario</label>
    <select id="v3-scenario-id" name="scenario_id">{scenario_options}</select>
    <label for="v3-user-input">Creative request</label>
    <textarea id="v3-user-input" name="user_input" required></textarea>
    <label for="v3-brand-id">Brand ID</label>
    <input id="v3-brand-id" name="brand_id" />
    <button type="submit" name="create_job">Create job</button>
  </form>
  <section id="v3-job-status" aria-label="Job status" data-job-id="{job_id}">{job_status}</section>
  <section id="v3-balance-estimate" aria-label="Balance estimate">{credits_required}</section>
  <section id="v3-asset-series" aria-label="Asset series"><ul>{asset_markup}</ul></section>
  <section id="v3-candidates" aria-label="Candidates"><ul>{candidate_markup}</ul></section>
  <section id="v3-selected-result" aria-label="Selected result">{escape(selected_ids)}</section>
  <button type="button" name="generate_asset_series">Generate asset series</button>
  <button type="button" name="select_result">Select result</button>
</main>"""
