"""Doc136: typed Human Realism reaches the final Brain sign-off without local prose."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import _inspection_prompt
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _enforced_guidance():
    return HumanPhotorealismLayer().build(
        project_id="project_doc136",
        job_id="job_doc136",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=("A natural real-camera photograph of a school-age person wearing the approved reference garment; "
                    "the garment has an illustrated print but the whole image is photographic."),
        subject_type="product",
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "object_surface",
                "decision_owner": "remote_brain",
            },
        },
    )


def test_doc136_enforced_human_guidance_is_typed_and_has_no_local_prompt_or_retry_prose() -> None:
    guidance = _enforced_guidance()

    assert guidance.applies is True
    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []
    assert guidance.reference_preserve_rules == []
    assert guidance.reference_do_not_inherit_rules == []
    assert guidance.retry_patch_templates == {}
    assert guidance.semantic_contract["contract_version"] == "v3_human_realism_semantic_v2"
    assert guidance.semantic_contract["rendering_goal"] == "photographic_real_person"
    assert guidance.semantic_contract["ordinary_age_appropriate_context"] is True
    assert guidance.semantic_contract["natural_presence_priority"] == "individual_human_presence"
    assert guidance.semantic_contract["aesthetic_boundary"] == "preserve_user_style_without_generic_beauty_substitution"
    assert set(guidance.semantic_contract["quality_axes"]) == set(HUMAN_REALISM_REVIEW_DIMENSIONS)
    assert guidance.semantic_contract["creative_direction_owner"] == "remote_v3_llm_brain"
    assert guidance.semantic_contract["provider_prompt_owner"] == "remote_v3_llm_brain"


def test_doc136_finalizer_context_requires_and_whitelists_active_human_contract() -> None:
    guidance = _enforced_guidance().model_dump(mode="json")
    plan = SimpleNamespace(dependency_order=["human_realism"])
    ledger = SimpleNamespace(
        provider_projection={"capability_projection": {"human_photorealism_guidance": guidance}}
    )

    contracts = ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)
    assert contracts == [guidance["semantic_contract"]]
    serialized = json.dumps(contracts, ensure_ascii=False)
    assert "prompt_fragments" not in serialized
    assert "retry_patch" not in serialized

    guidance["semantic_contract"] = {}
    with pytest.raises(CapabilityActivationError, match="human_realism_semantic_contract_missing"):
        ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)


def test_doc136_general_runtime_delivers_human_contract_to_remote_finalizer(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": ("Create a natural real-camera photograph of a school-age person wearing the approved blue dress; "
                           "the illustrated garment print remains a factual object surface, not the whole-image style."),
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer_requests = [request for request in provider.requests if request["stage"] == "provider_prompt_finalize"]
    assert len(finalizer_requests) == 1
    context = finalizer_requests[0]["metadata"]["canonical_prompt_context"]
    contracts = context["active_semantic_capability_contracts"]
    assert len(contracts) == 1
    assert contracts[0]["capability_id"] == "human_realism"
    assert contracts[0]["rendering_goal"] == "photographic_real_person"
    assert contracts[0]["natural_presence_priority"] == "individual_human_presence"
    assert contracts[0]["aesthetic_boundary"] == "preserve_user_style_without_generic_beauty_substitution"
    assert set(contracts[0]["quality_axes"]) == set(HUMAN_REALISM_REVIEW_DIMENSIONS)
    assert "prompt_additions" not in json.dumps(context, ensure_ascii=False)
    assert "negative_additions" not in json.dumps(context, ensure_ascii=False)

    payload = json.loads(build_remote_payload(
        # The runtime sends this same shape to the adapter; using the recorded
        # request makes the assertion independent of the test double response.
        BrainRunRequest.model_validate(finalizer_requests[0])
    ))
    assert payload["frozen_render_context"]["active_semantic_capability_contracts"] == contracts


def test_doc136_enforced_reviewer_is_built_from_frozen_contract_not_legacy_catalog(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "A real-camera portrait of an adult in a cafe.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    ).planning_result

    prompt = _inspection_prompt(dict(result.metadata))
    assert "Frozen review contract:" in prompt
    for required in HUMAN_REALISM_REVIEW_DIMENSIONS:
        assert required in prompt
    assert "doll_like_child_face" not in prompt
    assert "Judge visible text artifacts, watermarks, collage/split panels" not in prompt
