"""Doc E24 deterministic contract tests for E-Commerce creative risk preflight."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import (
    EcommerceCreativeRiskPreflight,
    validate_ecommerce_creative_risk_preflight_payload,
)


def _risk_item(index: int = 1, **overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "output_index": index,
        "risk_family": ["template_expression"],
        "primary_goal_hint": "emotion_hero",
        "risk_level": "medium",
        "strategy_policy": ["action_triggered_expression"],
        "stop": False,
        "fail_closed_reason": None,
        "professional_identity_hint": None,
    }
    item.update(overrides)
    return item


def _preflight(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "ecommerce_creative_risk_preflight_v1",
        "owner": "ecommerce_specialized_preflight",
        "applies_to": "ecommerce",
        "mode": "standard",
        "risk_items_by_output": [_risk_item()],
        "global_risks": ["template_expression"],
    }
    payload.update(overrides)
    return payload


def test_creative_risk_preflight_accepts_closed_standard_contract() -> None:
    preflight = validate_ecommerce_creative_risk_preflight_payload(
        _preflight(),
        scenario_id="ecommerce",
        mode="standard",
        requested_image_count=2,
    )

    assert preflight.mode == "standard"
    assert preflight.risk_items_by_output[0].output_index == 1
    assert preflight.planning_gate(requested_image_count=2) == {
        "status": "ready",
        "requested_image_count": 2,
        "output_indexes_preserved": [1, 2],
        "deleted_output_indexes": [],
        "split_allowed": False,
        "fallback_allowed": False,
        "prompt_patch_allowed": False,
        "fail_closed_reasons": [],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("risk_family", ["free_text_risk"]),
        ("primary_goal_hint", "free_text_goal"),
        ("risk_level", "severe"),
        ("strategy_policy", ["write_provider_prompt_fragment"]),
        ("fail_closed_reason", "free_text_reason"),
    ),
)
def test_creative_risk_preflight_rejects_unknown_enum_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(
                risk_items_by_output=[
                    _risk_item(
                        stop=True if field == "fail_closed_reason" else False,
                        **{field: value},
                    )
                ]
            )
        )


def test_global_risks_are_risk_family_subset_and_unique() -> None:
    EcommerceCreativeRiskPreflight.model_validate(
        _preflight(global_risks=["template_expression", "pasted_face"])
    )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(global_risks=["template_expression", "template_expression"])
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(global_risks=["unknown_global_risk"])
        )


def test_risk_items_cardinality_and_output_index_contract() -> None:
    EcommerceCreativeRiskPreflight.model_validate(_preflight(risk_items_by_output=[]))
    validate_ecommerce_creative_risk_preflight_payload(
        _preflight(risk_items_by_output=[_risk_item(1), _risk_item(2)]),
        scenario_id="ecommerce",
        mode="standard",
        requested_image_count=2,
    )

    with pytest.raises(ValueError, match="duplicate_output_index"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(risk_items_by_output=[_risk_item(1), _risk_item(1)]),
            scenario_id="ecommerce",
            mode="standard",
            requested_image_count=2,
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(risk_items_by_output=[_risk_item(0)])
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(risk_items_by_output=[_risk_item("1")])
        )

    with pytest.raises(ValueError, match="output_index_out_of_range"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(risk_items_by_output=[_risk_item(3)]),
            scenario_id="ecommerce",
            mode="standard",
            requested_image_count=2,
        )


def test_stop_true_blocks_whole_exact_n_request_without_fallback_or_prompt_patch() -> None:
    preflight = validate_ecommerce_creative_risk_preflight_payload(
        _preflight(
            risk_items_by_output=[
                _risk_item(
                    stop=True,
                    fail_closed_reason="reference_role_conflict",
                )
            ]
        ),
        scenario_id="ecommerce",
        mode="standard",
        requested_image_count=6,
    )

    assert preflight.planning_gate(requested_image_count=6) == {
        "status": "blocked",
        "requested_image_count": 6,
        "output_indexes_preserved": [1, 2, 3, 4, 5, 6],
        "deleted_output_indexes": [],
        "split_allowed": False,
        "fallback_allowed": False,
        "prompt_patch_allowed": False,
        "fail_closed_reasons": ["reference_role_conflict"],
    }


def test_stop_true_requires_fail_closed_reason_and_stop_false_requires_null_reason() -> None:
    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(risk_items_by_output=[_risk_item(stop=True, fail_closed_reason=None)])
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(
                risk_items_by_output=[
                    _risk_item(stop=False, fail_closed_reason="reference_role_conflict")
                ]
            )
        )


def test_general_requests_must_not_carry_ecommerce_preflight() -> None:
    with pytest.raises(ValueError, match="creative_risk_preflight_not_allowed"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(),
            scenario_id="general_creative",
            mode="standard",
            requested_image_count=1,
        )


def test_standard_rejects_professional_identity_hints_and_raw_fields() -> None:
    hint = {
        "preferred_identity_view_kind": "profile",
        "identity_strategy": "profile_primary",
        "source": "professional_binding_resolver",
    }

    with pytest.raises(ValueError, match="professional_identity_hint_not_allowed"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(risk_items_by_output=[_risk_item(professional_identity_hint=hint)]),
            scenario_id="ecommerce",
            mode="standard",
            requested_image_count=1,
        )

    raw_hint = {
        **hint,
        "asset_id": "v3_output_should_not_leak",
        "path": "D:/secret/original.png",
        "provider_payload": {"private": True},
    }
    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(risk_items_by_output=[_risk_item(professional_identity_hint=raw_hint)])
        )


def test_professional_identity_hint_requires_approved_binding_and_view_kind() -> None:
    hint = {
        "preferred_identity_view_kind": "profile",
        "identity_strategy": "profile_primary",
        "source": "professional_binding_resolver",
    }

    with pytest.raises(ValueError, match="professional_binding_views_required"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(
                mode="professional",
                risk_items_by_output=[_risk_item(professional_identity_hint=hint)],
            ),
            scenario_id="ecommerce",
            mode="professional",
            requested_image_count=1,
        )

    with pytest.raises(ValueError, match="preferred_identity_view_not_approved"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(
                mode="professional",
                risk_items_by_output=[_risk_item(professional_identity_hint=hint)],
            ),
            scenario_id="ecommerce",
            mode="professional",
            requested_image_count=1,
            approved_identity_view_kinds={"front"},
        )

    preflight = validate_ecommerce_creative_risk_preflight_payload(
        _preflight(
            mode="professional",
            risk_items_by_output=[_risk_item(professional_identity_hint=hint)],
        ),
        scenario_id="ecommerce",
        mode="professional",
        requested_image_count=1,
        approved_identity_view_kinds={"front", "profile"},
    )

    assert preflight.risk_items_by_output[0].professional_identity_hint
    assert (
        preflight.risk_items_by_output[0]
        .professional_identity_hint.preferred_identity_view_kind
        == "profile"
    )


def test_preflight_contract_does_not_mutate_core_ecommerce_authorities() -> None:
    preflight = validate_ecommerce_creative_risk_preflight_payload(
        _preflight(),
        scenario_id="ecommerce",
        mode="standard",
        requested_image_count=6,
    )

    authority = preflight.authority_invariants()

    assert authority == {
        "product_truth_selection_owner": "remote_brain_image_set_plan",
        "provider_reference_cap_owner": "provider_materializer_contract",
        "exact_n_owner": "runtime_exact_count_validation",
        "prompt_authority_owner": "remote_brain_provider_prompt_finalize",
        "preflight_may_select_product_truth": False,
        "preflight_may_change_provider_cap": False,
        "preflight_may_change_output_count": False,
        "preflight_may_author_provider_prompt": False,
    }
