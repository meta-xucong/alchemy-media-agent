from alchemy_creative_agent_3_0.app.app_shell import (
    get_minimal_ui_contract,
    get_route_contracts,
    get_scenario_hub_contract,
    render_minimal_job_view,
)
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers


def _service(tmp_path) -> V3ProductApiService:
    brand_service = BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))
    return V3ProductApiService(brand_profile_service=brand_service)


def test_scenario_hub_contract_exposes_general_active_and_placeholders() -> None:
    hub = get_scenario_hub_contract()
    routes = get_route_contracts()
    minimal_ui = get_minimal_ui_contract()
    cards = {card["scenario_id"]: card for card in hub["scenario_cards"]}

    assert routes["scenario_hub"] == "/api/v3/creative-agent/scenarios"
    assert hub["default_scenario_id"] == "general_creative"
    assert hub["active_scenario_ids"] == ["general_creative", "ecommerce"]
    assert set(hub["placeholder_scenario_ids"]) == {"new_media", "private_domain", "brand_ip"}
    assert cards["general_creative"]["primary_action"] == "create_job"
    assert cards["general_creative"]["can_create_jobs"] is True
    assert cards["ecommerce"]["primary_action"] == "create_job"
    assert cards["ecommerce"]["can_create_jobs"] is True
    assert minimal_ui["scenario_hub"]["metadata"]["placeholder_cards_do_not_create_jobs"] is True
    assert any(control["name"] == "scenario_id" for control in minimal_ui["semantic_controls"])

    html = render_minimal_job_view()
    assert 'name="scenario_id"' in html
    assert 'value="general_creative" selected' in html

    handler_hub = V3ProductRouteHandlers().get_scenarios()
    assert handler_hub["routes"]["scenario_hub"] == "/api/v3/creative-agent/scenarios"
    assert handler_hub["default_scenario_id"] == "general_creative"


def test_product_job_lifecycle_records_create_generate_and_select(tmp_path) -> None:
    service = _service(tmp_path)

    created = service.create_job(
        {
            "user_input": "Create a clean launch image series for a tea shop.",
            "scenario_selection": {"scenario_id": "general_creative"},
        }
    )
    record = service.job_store.get(created.job_id)

    assert created.status == ProductJobStatusValue.PLANNED
    assert record is not None
    assert record.lifecycle is not None
    assert record.lifecycle.job.status == "planned"
    assert record.lifecycle.job.scenario_id == "general_creative"
    assert len(record.lifecycle.runs) == 1
    assert record.lifecycle.exports
    assert created.metadata["lifecycle"]["run_count"] == 1

    generated = service.generate_job(created.job_id)
    record = service.job_store.get(created.job_id)

    assert generated.status == ProductJobStatusValue.GENERATED
    assert record.lifecycle is not None
    assert record.lifecycle.job.status == "generated"
    assert any(run.status == "generated" for run in record.lifecycle.runs)
    assert record.lifecycle.candidates
    assert generated.metadata["lifecycle"]["candidate_count"] == len(record.lifecycle.candidates)

    selected = service.select_result(created.job_id)
    record = service.job_store.get(created.job_id)

    assert selected.status == ProductJobStatusValue.SELECTED
    assert record.lifecycle is not None
    assert record.lifecycle.job.status == "selected"
    assert len(record.lifecycle.selections) == 1
    assert selected.job_status.metadata["lifecycle"]["selection_count"] == 1


def test_future_placeholder_scenario_has_blocked_lifecycle_without_runs(tmp_path) -> None:
    service = _service(tmp_path)

    created = service.create_job(
        {
            "user_input": "Create a short-form content material set.",
            "scenario_selection": {"scenario_id": "new_media"},
        }
    )
    record = service.job_store.get(created.job_id)

    assert created.status == ProductJobStatusValue.BLOCKED
    assert record is not None
    assert record.lifecycle is not None
    assert record.lifecycle.job.status == "blocked"
    assert record.lifecycle.job.scenario_id == "new_media"
    assert record.lifecycle.runs == []
    assert record.lifecycle.candidates == []
    assert record.lifecycle.exports == []
    assert created.metadata["lifecycle"]["run_count"] == 0
    assert created.metadata["lifecycle"]["export_count"] == 0
