"""Doc114 Phase D frozen pixel-review and owner-local retry coverage."""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _apparel_profile() -> dict:
    return {
        "product_category": "apparel",
        "product_name": "blue layered occasion dress",
        "apparel_construction": {
            "silhouette_and_proportion": "A-line knee-length silhouette",
            "print_or_pattern_registration": "blue floral print remains registered across bodice and skirt",
            "layer_order": ["lining", "two uneven tulle overlays"],
            "seam_hem_edge_trim_fastening": "waist seam, scalloped hem trim, back button",
            "material_weight_and_surface_response": "matte woven lining and translucent tulle",
            "fold_tension_gravity_and_drape": "soft gravity-driven folds and irregular tulle edge separation",
        },
    }


def _ecommerce_request() -> dict:
    return {
        "user_input": "Create ecommerce images of a model wearing the supplied layered dress, with natural candid moments.",
        "scenario_selection": {
            "scenario_id": "ecommerce",
            "parameters": {"requested_image_count": 4, "provider_max_requested_images": 7},
        },
        "uploaded_asset_ids": ["dress-reference"],
        "product_profile": _apparel_profile(),
        "metadata": {"requested_image_count": 4, "provider_max_requested_images": 7},
    }


def _ecommerce_result(monkeypatch):
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = ecommerce_test_service()
    created = service.create_job(_ecommerce_request())
    record = service.job_store.get(created.job_id)
    assert record is not None and record.planning_result is not None
    return record.planning_result


class _ContractVisionProvider:
    provider_name = "doc114_contract_vision_test_double"

    def __init__(self, issue_codes: list[str]) -> None:
        self.issue_codes = issue_codes

    def available(self, *, force: bool = False) -> bool:
        return True

    def inspect(self, resolution, *, metadata=None) -> dict:
        return {
            "status": "fail_retryable",
            "confidence": 0.92,
            "issue_codes": list(self.issue_codes),
            "scores": {
                "product_fidelity": 0.42,
                "apparel_construction_fidelity": 0.36,
                "delivery_evidence_fidelity": 0.39,
                "overall": 0.45,
            },
            "summary": ["contract fixture"],
        }


def test_apparel_truth_is_derived_from_frozen_ledger_and_visible_to_pixel_reviewer(monkeypatch) -> None:
    result = _ecommerce_result(monkeypatch)
    delivery = result.metadata["template_deliverable_plan"]["deliverables"][0]
    metadata = {
        **result.metadata,
        "frozen_output_review_contract": {
            "source": "resolved_constraint_ledger",
            "deliverable_id": delivery["deliverable_id"],
        },
    }

    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)

    assert contract["enforced"] is True
    assert contract["apparel_construction_truth"]["applies"] is True
    assert set(contract["apparel_construction_truth"]["issue_codes"]) == {
        "product_silhouette_drift",
        "product_pattern_registration_drift",
        "product_layer_topology_drift",
        "product_construction_detail_drift",
        "product_material_response_drift",
        "product_drape_behavior_drift",
    }
    assert contract["template_delivery_evidence"]["applies"] is True
    assert "delivery_evidence_dimension_mismatch" in contract["issue_codes"]
    assert "blue floral print remains registered" in prompt
    assert "Frozen template output evidence" in prompt
    assert delivery["metadata"]["brain_evidence_dimensions"][0] in prompt
    assert "child" not in str(contract).lower()


def test_pixel_review_accepts_only_frozen_apparel_contract_issue_codes(monkeypatch) -> None:
    result = _ecommerce_result(monkeypatch)
    delivery = result.metadata["template_deliverable_plan"]["deliverables"][0]
    metadata = {
        **result.metadata,
        "vision_inspection_mode": "vision_model",
        "frozen_output_review_contract": {
            "source": "resolved_constraint_ledger",
            "deliverable_id": delivery["deliverable_id"],
        },
    }
    resolution = GeneratedOutputResolution(
        resolution_id="doc114-phase-d-resolution",
        job_id="doc114-phase-d-job",
        candidate_id="doc114-phase-d-candidate",
        output_id="doc114-phase-d-output",
        status="ready",
    )
    inspector = VisionOutputInspector(
        vision_provider=_ContractVisionProvider(
            [
                "product_pattern_registration_drift",
                "delivery_evidence_dimension_mismatch",
                "ai_face_render",
                "identity_drift",
            ]
        )
    )

    report = inspector.inspect(resolution, metadata=metadata)

    codes = [issue["code"] for issue in report.detected_issues]
    assert report.status == "fail_retryable"
    assert codes == [
        "product_pattern_registration_drift",
        "delivery_evidence_dimension_mismatch",
        "ai_face_render",
    ]
    assert "identity_drift" in report.evidence["ignored_out_of_scope_issue_codes"]
    assert report.retryable is True


def test_owner_local_retry_keeps_frozen_brain_evidence_map_and_product_truth(monkeypatch) -> None:
    result = _ecommerce_result(monkeypatch)
    service = V3ProductApiService()

    codes, patch, source = service._activation_filtered_retry_signal(
        result,
        ["product_pattern_registration_drift", "delivery_evidence_dimension_mismatch"],
        {},
        "doc114_phase_d_test",
    )

    assert source == "doc114_phase_d_test"
    assert codes == ["product_pattern_registration_drift", "delivery_evidence_dimension_mismatch"]
    assert any("supplied product" in item for item in patch["product_reinforcement"])
    assert any("prior frozen template-owned evidence map" in item for item in patch["prompt_additions"])
    assert any("output 1:" in item for item in patch["prompt_additions"])


def test_generic_human_realism_issues_route_back_to_their_active_owner(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a natural candid portrait of an adult woman in a real cafe with relaxed expression.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    ).planning_result

    codes, patch, _ = V3ProductApiService()._activation_filtered_retry_signal(
        result,
        ["flat_scene_lighting", "frozen_centered_pose"],
        {},
        "doc114_generic_owner_test",
    )

    assert codes == ["flat_scene_lighting", "frozen_centered_pose"]
    assert patch["prompt_additions"]
    assert "ignored_out_of_scope_issue_codes" not in result.metadata.get("capability_activation_audit", {})
