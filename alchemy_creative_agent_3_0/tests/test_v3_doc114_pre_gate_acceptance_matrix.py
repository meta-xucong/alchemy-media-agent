"""Passive Doc114 fixture contract before runtime implementation is allowed.

This test deliberately validates evaluation material only.  It must stay free
of provider calls and must not require a child-specific runtime branch.
"""

from __future__ import annotations

import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "doc114_apparel_on_child_acceptance.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _case_by_id(payload: dict, case_id: str) -> dict:
    return next(case for case in payload["cases"] if case["case_id"] == case_id)


def test_doc114_pre_gate_matrix_has_the_required_cross_domain_cases() -> None:
    payload = _fixture()

    assert payload["schema_version"] == 1
    assert payload["authority"] == "Doc114"
    assert payload["fixture_asset_policy"].startswith("Textual and structured evidence only")
    assert {case["case_id"] for case in payload["cases"]} == {
        "A_child_apparel_real_camera",
        "B_adult_apparel_on_person",
        "C_same_person_portrait",
        "D_non_person_product_object",
        "E_high_key_soft_commercial_person",
        "F_moody_cinematic_person",
    }


def test_doc114_merge_requires_the_three_external_acceptances() -> None:
    payload = _fixture()

    assert payload["merge_validation_gates"] == [
        "ecommerce_real_product_reference_brain_provider_review_retry_acceptance",
        "photography_p10_cross_domain_acceptance",
        "browser_gate_d_delivery_continuation_recovery_acceptance",
    ]


def test_doc114_child_apparel_case_uses_generic_facts_and_independent_garment_channels() -> None:
    payload = _fixture()
    case = _case_by_id(payload, "A_child_apparel_real_camera")

    assert case["required_normalized_facts"] == payload["generic_activation_facts"]
    assert case["required_ledger_channels"] == [
        "product_silhouette",
        "product_pattern_registration",
        "product_layer_topology",
        "product_construction_detail",
        "product_material_response",
        "product_drape_behavior",
    ]
    assert case["template_owner"] == "ecommerce_template"
    assert case["shared_owner"] == "human_realism"
    assert case["review_requirement"] == "real_or_hybrid_pixel_review"
    assert [item["requested_count"] for item in case["requested_output_variants"]] == [1, 7]


def test_doc114_cross_domain_cases_prevent_child_and_ecommerce_leakage() -> None:
    payload = _fixture()
    cases = {case["case_id"]: case for case in payload["cases"]}

    assert cases["B_adult_apparel_on_person"]["shared_owner"] == "human_realism"
    assert "product_on_person" in cases["B_adult_apparel_on_person"]["required_normalized_facts"]
    assert cases["C_same_person_portrait"]["template_owner"] == "general_template"
    assert "product_on_person" in cases["C_same_person_portrait"]["forbidden_normalized_facts"]
    assert cases["D_non_person_product_object"]["forbidden_normalized_facts"] == [
        "visible_person",
        "product_on_person",
        "explicit_age_direction",
        "wearable_apparel_evidence",
    ]
    assert cases["F_moody_cinematic_person"]["template_owner"] == "general_template"
    assert set(payload["forbidden_runtime_identifiers"]) >= {
        "kidswear_module",
        "child_template",
        "child_provider_route",
        "ecommerce_human_realism_plugin",
        "shared_ecommerce_delivery_map",
    }
