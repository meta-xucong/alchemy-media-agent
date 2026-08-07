from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService


def test_project_read_hides_durable_ecommerce_continuation_lineage_from_browser_payload():
    store = InMemoryProjectStore()
    service = V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=store,
    )
    created = service.create_project(
        {
            "user_goal": "Create an ecommerce project with a durable continuation plan.",
            "primary_template_id": "ecommerce_template",
        }
    ).project
    assert created is not None
    created.metadata["ecommerce_slot_lineage_records"] = {
        "job_internal": {
            "planning_request": {"private_contract": "x" * 250_000},
            "frozen_capability_activation_plan": {"private_contract": "x" * 250_000},
        }
    }
    store.save_project(created)

    public_response = service.get_project(created.project_id)
    public_payload = public_response.model_dump(mode="json")
    durable = store.get_project(created.project_id)

    assert public_response.project is not None
    assert "ecommerce_slot_lineage_records" not in public_response.project.metadata
    assert len(json.dumps(public_payload, ensure_ascii=False).encode("utf-8")) < 50_000
    assert durable is not None
    assert "ecommerce_slot_lineage_records" in durable.metadata
