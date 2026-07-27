"""Doc E24 deterministic contract tests for E-Commerce creative risk preflight."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import (
    EcommerceCreativeRiskPreflight,
    build_professional_ecommerce_identity_preflight,
    ecommerce_human_realism_review_context_from_preflight_payload,
    validate_ecommerce_creative_risk_preflight_payload,
)
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


_E24_DOC = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "ecommerce_module"
    / "E24_CREATIVE_RISK_PREFLIGHT_CONTRACT.md"
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


def test_e24_current_typed_runtime_shape_matches_model() -> None:
    document = _E24_DOC.read_text(encoding="utf-8")
    marker = "Current typed runtime shape:"
    assert marker in document
    section = document.split(marker, 1)[1]
    match = re.search(r"```json\s*(\{.*?\})\s*```", section, flags=re.DOTALL)
    assert match is not None
    payload = json.loads(match.group(1))

    validated = EcommerceCreativeRiskPreflight.model_validate(payload)

    assert validated.mode == "professional"
    assert validated.risk_items_by_output[1].primary_goal_hint == "back_or_structure"
    assert "avoid_static_presenter_grin" in validated.risk_items_by_output[0].strategy_policy


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
        _preflight(
            risk_items_by_output=[
                _risk_item(risk_family=["template_expression", "pasted_face"]),
            ],
            global_risks=["template_expression", "pasted_face"],
        )
    )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(global_risks=["template_expression", "template_expression"])
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(global_risks=["unknown_global_risk"])
        )

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(
                risk_items_by_output=[
                    _risk_item(risk_family=["template_expression"]),
                ],
                global_risks=["pasted_face"],
            )
        )

    with pytest.raises(ValueError, match="global_risks_must_be_subset"):
        validate_ecommerce_creative_risk_preflight_payload(
            _preflight(
                risk_items_by_output=[
                    _risk_item(risk_family=["template_expression"]),
                ],
                global_risks=["pasted_face"],
            ),
            scenario_id="ecommerce",
            mode="standard",
            requested_image_count=1,
        )


def test_risk_items_cardinality_and_output_index_contract() -> None:
    EcommerceCreativeRiskPreflight.model_validate(
        _preflight(risk_items_by_output=[], global_risks=[])
    )
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


def test_planning_gate_direct_call_fail_closes_invalid_request_context() -> None:
    preflight = EcommerceCreativeRiskPreflight.model_validate(
        _preflight(risk_items_by_output=[_risk_item(1)])
    )

    gate = preflight.planning_gate(requested_image_count=0)

    assert gate["status"] == "blocked"
    assert gate["requested_image_count"] == 0
    assert gate["output_indexes_preserved"] == []
    assert gate["deleted_output_indexes"] == []
    assert gate["split_allowed"] is False
    assert gate["fallback_allowed"] is False
    assert gate["prompt_patch_allowed"] is False
    assert gate["fail_closed_reasons"] == ["requested_image_count_invalid"]


def test_planning_gate_direct_call_fail_closes_duplicate_or_out_of_range_items() -> None:
    duplicate = EcommerceCreativeRiskPreflight.model_validate(
        _preflight(risk_items_by_output=[_risk_item(1), _risk_item(1)])
    )
    duplicate_gate = duplicate.planning_gate(requested_image_count=2)

    assert duplicate_gate["status"] == "blocked"
    assert duplicate_gate["output_indexes_preserved"] == [1, 2]
    assert duplicate_gate["deleted_output_indexes"] == []
    assert duplicate_gate["split_allowed"] is False
    assert duplicate_gate["fallback_allowed"] is False
    assert duplicate_gate["prompt_patch_allowed"] is False
    assert duplicate_gate["fail_closed_reasons"] == ["duplicate_output_index"]

    out_of_range = EcommerceCreativeRiskPreflight.model_validate(
        _preflight(risk_items_by_output=[_risk_item(2)])
    )
    out_of_range_gate = out_of_range.planning_gate(requested_image_count=1)

    assert out_of_range_gate["status"] == "blocked"
    assert out_of_range_gate["output_indexes_preserved"] == [1]
    assert out_of_range_gate["deleted_output_indexes"] == []
    assert out_of_range_gate["split_allowed"] is False
    assert out_of_range_gate["fallback_allowed"] is False
    assert out_of_range_gate["prompt_patch_allowed"] is False
    assert out_of_range_gate["fail_closed_reasons"] == ["output_index_out_of_range"]


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


def test_ecommerce_preflight_projects_public_safe_shared_human_review_context() -> None:
    payload = _preflight(
        mode="professional",
        global_risks=["template_expression", "pasted_face"],
        risk_items_by_output=[
            _risk_item(
                1,
                risk_family=["template_expression", "pasted_face"],
                primary_goal_hint="emotion_hero",
                strategy_policy=[
                    "action_triggered_expression",
                    "avoid_static_presenter_grin",
                ],
                professional_identity_hint={
                    "preferred_identity_view_kind": "front",
                    "identity_strategy": "secondary_face",
                    "source": "professional_binding_resolver",
                },
            )
        ],
    )

    context = ecommerce_human_realism_review_context_from_preflight_payload(
        payload,
        scenario_id="ecommerce",
        mode="professional",
        requested_image_count=2,
        approved_identity_view_kinds={"front"},
    )

    assert context["contract_version"] == "ecommerce_human_realism_review_context_v1"
    assert context["owner"] == "shared_human_realism_review"
    assert context["post_review_authority"] == "shared_human_realism_review"
    assert context["retry_authority"] == "shared_human_realism_review"
    assert context["ecommerce_may_score_pixels"] is False
    assert context["ecommerce_may_trigger_retry"] is False
    assert context["risk_items_by_output"][0]["professional_identity_hint"] == {
        "preferred_identity_view_kind": "front",
        "identity_strategy": "secondary_face",
        "source": "professional_binding_resolver",
    }
    serialized = json.dumps(context, ensure_ascii=False)
    assert "asset" not in serialized
    assert "v3_output" not in serialized
    assert "provider" not in serialized
    assert "D:" not in serialized


def test_ecommerce_preflight_shared_review_projection_respects_stop_gate() -> None:
    with pytest.raises(ValueError, match="creative_risk_preflight_blocked"):
        ecommerce_human_realism_review_context_from_preflight_payload(
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
            requested_image_count=2,
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

    with pytest.raises(ValidationError):
        EcommerceCreativeRiskPreflight.model_validate(
            _preflight(risk_items_by_output=[_risk_item(professional_identity_hint=hint)])
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


def test_professional_contributor_projects_only_explicit_resolver_hints() -> None:
    preflight = build_professional_ecommerce_identity_preflight(
        requested_image_count=2,
        professional_identity_hints_by_output={
            1: {
                "preferred_identity_view_kind": "front",
                "identity_strategy": "front_primary",
                "source": "professional_binding_resolver",
            },
            2: {
                "preferred_identity_view_kind": "profile",
                "identity_strategy": "secondary_face",
                "source": "professional_binding_resolver",
            },
        },
        approved_identity_view_kinds={"front", "profile"},
    )

    assert preflight.mode == "professional"
    assert [item.output_index for item in preflight.risk_items_by_output] == [1, 2]
    assert [
        item.professional_identity_hint.model_dump(mode="json")
        for item in preflight.risk_items_by_output
    ] == [
        {
            "preferred_identity_view_kind": "front",
            "identity_strategy": "front_primary",
            "source": "professional_binding_resolver",
        },
        {
            "preferred_identity_view_kind": "profile",
            "identity_strategy": "secondary_face",
            "source": "professional_binding_resolver",
        },
    ]

    payload = preflight.model_dump(mode="json")
    validate_ecommerce_creative_risk_preflight_payload(
        payload,
        scenario_id="ecommerce",
        mode="professional",
        requested_image_count=2,
        approved_identity_view_kinds={"front", "profile"},
    )
    serialized = preflight.model_dump_json()
    assert "face_profile" not in serialized
    assert "face_front" not in serialized
    assert "asset_id" not in serialized
    assert "output_id" not in serialized
    assert "path" not in serialized
    assert "provider_payload" not in serialized


def test_professional_contributor_never_ranks_or_fills_missing_resolver_hints() -> None:
    with pytest.raises(ValueError, match="professional_identity_hint_missing"):
        build_professional_ecommerce_identity_preflight(
            requested_image_count=1,
            professional_identity_hints_by_output={},
            approved_identity_view_kinds={"front", "profile"},
        )

    with pytest.raises(ValueError, match="preferred_identity_view_not_approved"):
        build_professional_ecommerce_identity_preflight(
            requested_image_count=1,
            professional_identity_hints_by_output={
                1: {
                    "preferred_identity_view_kind": "profile",
                    "identity_strategy": "secondary_face",
                    "source": "professional_binding_resolver",
                }
            },
            approved_identity_view_kinds={"front"},
        )


@pytest.mark.parametrize("invalid_count", [True, "1", 1.0, 0])
def test_professional_contributor_rejects_invalid_requested_image_count(
    invalid_count: object,
) -> None:
    with pytest.raises(ValueError, match="requested_image_count_invalid"):
        build_professional_ecommerce_identity_preflight(
            requested_image_count=invalid_count,  # type: ignore[arg-type]
            professional_identity_hints_by_output={
                1: {
                    "preferred_identity_view_kind": "front",
                    "identity_strategy": "front_primary",
                    "source": "professional_binding_resolver",
                }
            },
            approved_identity_view_kinds={"front"},
        )


def test_professional_contributor_rejects_non_integer_hint_output_keys() -> None:
    hint = {
        "preferred_identity_view_kind": "front",
        "identity_strategy": "front_primary",
        "source": "professional_binding_resolver",
    }
    for invalid_key in ("1", 1.0, True):
        with pytest.raises(ValueError, match="professional_identity_hint_output_index_invalid"):
            build_professional_ecommerce_identity_preflight(
                requested_image_count=1,
                professional_identity_hints_by_output={invalid_key: hint},
                approved_identity_view_kinds={"front"},
            )

    with pytest.raises(ValueError, match="professional_identity_hint_output_index_out_of_range"):
        build_professional_ecommerce_identity_preflight(
            requested_image_count=1,
            professional_identity_hints_by_output={0: hint},
            approved_identity_view_kinds={"front"},
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


def test_stop_true_preflight_blocks_before_remote_brain_or_business_mutation() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    stop_preflight = _preflight(
        risk_items_by_output=[
            _risk_item(
                stop=True,
                fail_closed_reason="provider_reference_capacity_unrepresentable",
            )
        ]
    )

    result = runtime.plan_job(
        {
            "user_input": "Create a two image ecommerce set.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 2},
            },
            "metadata": {
                "requested_image_count": 2,
                "ecommerce_creative_context": {
                    "context_id": "ctx_e24_stop_gate",
                    "source_version": "ecommerce_creative_context_v2",
                    "product_truth": {"hard_facts": ["blue swimsuit"]},
                    "creative_risk_preflight": stop_preflight,
                },
            },
            "product_profile": {"product_category": "kidswear swimsuit"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.generation_result is None
    assert provider.requests == []
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "ecommerce_creative_risk_preflight_blocked"
    assert outcome["llm_used"] is False
    assert any("ecommerce_creative_risk_preflight_blocked" in item for item in result.warnings)


@pytest.mark.parametrize(
    "malformed_preflight",
    (
        _preflight(
            risk_items_by_output=[
                _risk_item(risk_family=["unknown_risk_family"]),
            ]
        ),
        _preflight(
            risk_items_by_output=[
                _risk_item(risk_family=["template_expression"]),
            ],
            global_risks=["pasted_face"],
        ),
        _preflight(raw_path="D:/private/should_not_cross.png"),
        "not-a-dict-preflight",
        None,
    ),
)
def test_malformed_preflight_blocks_before_remote_brain_without_leaking_payload(
    malformed_preflight: object,
) -> None:
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": "Create one ecommerce image.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 1},
            },
            "metadata": {
                "requested_image_count": 1,
                "ecommerce_creative_context": {
                    "context_id": "ctx_e24_invalid_gate",
                    "source_version": "ecommerce_creative_context_v2",
                    "product_truth": {"hard_facts": ["blue swimsuit"]},
                    "creative_risk_preflight": malformed_preflight,
                },
            },
            "product_profile": {"product_category": "kidswear swimsuit"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.generation_result is None
    assert provider.requests == []
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "ecommerce_creative_risk_preflight_invalid"
    assert outcome["llm_used"] is False
    assert any("ecommerce_creative_risk_preflight_invalid" in item for item in result.warnings)
    serialized_result = result.model_dump_json()
    assert "unknown_risk_family" not in serialized_result
    assert "D:/private/should_not_cross.png" not in serialized_result
    assert "not-a-dict-preflight" not in serialized_result


def test_professional_preflight_missing_binding_blocks_before_remote_brain() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    professional_preflight = _preflight(
        mode="professional",
        risk_items_by_output=[_risk_item(professional_identity_hint=None)],
    )

    result = runtime.plan_job(
        {
            "user_input": "Create one professional ecommerce image.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 1},
            },
            "metadata": {
                "requested_image_count": 1,
                "professional_mode": "professional",
                "ecommerce_creative_context": {
                    "context_id": "ctx_e24_professional_missing_binding",
                    "source_version": "ecommerce_creative_context_v2",
                    "product_truth": {"hard_facts": ["blue swimsuit"]},
                    "creative_risk_preflight": professional_preflight,
                },
            },
            "product_profile": {"product_category": "kidswear swimsuit"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.generation_result is None
    assert provider.requests == []
    assert "remote_creative_brain_outcome" not in result.metadata
    assert any("professional_mode_binding_invalid" in item for item in result.warnings)


def test_professional_preflight_unapproved_view_hint_blocks_before_remote_brain() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    profile_hint = {
        "preferred_identity_view_kind": "profile",
        "identity_strategy": "profile_primary",
        "source": "professional_binding_resolver",
    }
    professional_preflight = _preflight(
        mode="professional",
        risk_items_by_output=[_risk_item(professional_identity_hint=profile_hint)],
    )

    result = runtime.plan_job(
        {
            "user_input": "Create one professional ecommerce image.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 1},
            },
            "metadata": {
                "requested_image_count": 1,
                "professional_mode": "professional",
                "professional_mode_binding_record": {
                    "job_id": "job_professional",
                    "project_id": "project_professional",
                    "people_asset_id": "person_1",
                    "face_module_id": "face_v1",
                    "pack_version_id": "pack_v1",
                    "identity_view_ids": ["face_front"],
                },
                "ecommerce_creative_context": {
                    "context_id": "ctx_e24_professional_unapproved_view",
                    "source_version": "ecommerce_creative_context_v2",
                    "product_truth": {"hard_facts": ["blue swimsuit"]},
                    "creative_risk_preflight": professional_preflight,
                },
            },
            "product_profile": {"product_category": "kidswear swimsuit"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.generation_result is None
    assert provider.requests == []
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "ecommerce_creative_risk_preflight_invalid"
