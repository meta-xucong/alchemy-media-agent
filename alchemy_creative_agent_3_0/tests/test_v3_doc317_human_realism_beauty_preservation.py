from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    CANONICAL_FINALIZER_SYSTEM_PROMPT,
    HUMAN_REALISM_BEAUTY_PRESERVATION_INSTRUCTIONS,
    SYSTEM_PROMPT,
    _compact_human_realism_execution_contract,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_BEAUTY_PRESERVATION_POLICY_KEYS,
    HUMAN_REALISM_BEAUTY_PRESERVATION_POLICY_VERSION,
    HumanPhotorealismLayer,
    build_human_realism_beauty_preservation_policy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.module import (
    VisualCapabilityClusterModule,
)


def _guidance(*, brain_owned: bool = True):
    return HumanPhotorealismLayer().build(
        project_id="project_doc317",
        job_id="job_doc317",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a flattering real-camera editorial portrait of an adult in a blue coat at dusk.",
        subject_type="character",
        variation_mode="single_hero",
        has_identity_reference=True,
        metadata={
            "brain_owned_forward_execution": brain_owned,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    )


def test_doc317_policy_is_closed_fresh_and_scene_neutral() -> None:
    guidance = _guidance()
    policy = guidance.semantic_contract["beauty_preservation_policy"]

    assert policy == build_human_realism_beauty_preservation_policy()
    assert policy["contract_version"] == HUMAN_REALISM_BEAUTY_PRESERVATION_POLICY_VERSION
    assert set(policy) == HUMAN_REALISM_BEAUTY_PRESERVATION_POLICY_KEYS
    serialized = json.dumps(policy, ensure_ascii=False).lower()
    for forbidden in ("child", "east asian", "pore", "jaw", "template"):
        assert forbidden not in serialized


def test_doc317_policy_factory_does_not_share_mutable_lists() -> None:
    first = build_human_realism_beauty_preservation_policy()
    first["protected_channels"].append("caller_mutation")

    second = build_human_realism_beauty_preservation_policy()

    assert "caller_mutation" not in second["protected_channels"]


def test_doc317_brain_owned_guidance_keeps_policy_semantic_not_local_prompt_prose() -> None:
    guidance = _guidance()

    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []
    assert guidance.retry_patch_templates == {}
    assert guidance.semantic_contract["aesthetic_boundary"] == (
        "preserve_user_style_without_generic_beauty_substitution"
    )

    projected = _compact_human_realism_execution_contract(
        {"visual_cluster": {"human_photorealism_guidance": guidance.model_dump(mode="json")}}
    )
    semantic = projected["semantic_contract"]
    assert semantic["aesthetic_boundary"] == guidance.semantic_contract["aesthetic_boundary"]
    assert semantic["beauty_preservation_policy"] == guidance.semantic_contract[
        "beauty_preservation_policy"
    ]


def test_doc317_runtime_accepts_only_the_frozen_beauty_policy() -> None:
    guidance = _guidance().model_dump(mode="json")
    plan = SimpleNamespace(dependency_order=["human_realism"])
    ledger = SimpleNamespace(
        provider_projection={"capability_projection": {"human_photorealism_guidance": guidance}}
    )

    contracts = ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)
    assert contracts[0]["beauty_preservation_policy"]["conflict_resolution"] == (
        "preserve_beauty_reduce_realism_intervention"
    )

    guidance["semantic_contract"]["beauty_preservation_policy"]["priority"] = "soft"
    with pytest.raises(CapabilityActivationError, match="human_realism_semantic_contract_missing"):
        ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)


def test_doc317_final_execution_projection_carries_the_same_policy() -> None:
    guidance = _guidance().model_dump(mode="json")

    execution = ScenarioRuntime._human_realism_execution_contract(
        {"capability_projection": {"human_photorealism_guidance": guidance}}
    )

    assert execution["semantic_contract"]["aesthetic_boundary"] == (
        "preserve_user_style_without_generic_beauty_substitution"
    )
    assert execution["semantic_contract"]["beauty_preservation_policy"] == guidance[
        "semantic_contract"
    ]["beauty_preservation_policy"]


def test_doc317_brain_instructions_make_beauty_the_conflict_winner() -> None:
    expected = "If realism and beauty conflict, preserve beauty and reduce the"

    assert expected in HUMAN_REALISM_BEAUTY_PRESERVATION_INSTRUCTIONS
    assert expected in SYSTEM_PROMPT
    assert expected in CANONICAL_FINALIZER_SYSTEM_PROMPT
    assert "never redesign facial geometry" in HUMAN_REALISM_BEAUTY_PRESERVATION_INSTRUCTIONS
    assert "not a keyword list, checklist, or local repair phrase" in (
        HUMAN_REALISM_BEAUTY_PRESERVATION_INSTRUCTIONS
    )


def test_doc317_compatibility_retry_does_not_turn_asymmetry_or_brightness_into_realism() -> None:
    retry = VisualCapabilityClusterModule()._beautiful_realism_retry_patch(  # noqa: SLF001
        issue_codes=["real_but_unflattering"],
        subject_identity_card=None,
        human_photorealism=_guidance(brain_owned=False),
    )
    serialized = json.dumps(retry, ensure_ascii=False).lower()

    assert "reduce the realism intervention first" in serialized
    assert "tiny asymmetry" not in serialized
    assert "clean luminous complexion" not in serialized
    assert "without changing the requested mood or style" in serialized
