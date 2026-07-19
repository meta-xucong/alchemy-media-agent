"""Doc140: real-image semantics must be complete and Brain-owned."""

from __future__ import annotations

import copy
import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _remote_profile(*, visible_person: bool) -> dict:
    entities = []
    evidence = []
    if visible_person:
        entities = [
            {
                "entity_id": "remote_subject_1",
                "entity_type": "person",
                "role": "primary_subject",
                "source_asset_ids": [],
                "visible_in_target": True,
                "preservation_level": "none",
                "confidence": 0.96,
                "attributes": {},
            }
        ]
        evidence = [
            {
                "evidence_id": "remote_visible_person",
                "evidence_type": "visible_person",
                "source": "remote_semantic_interpretation",
                "value": True,
                "confidence": 0.96,
                "metadata": {},
            },
            {
                "evidence_id": "remote_real_human_output",
                "evidence_type": "real_human_output",
                "source": "remote_semantic_interpretation",
                "value": True,
                "confidence": 0.96,
                "metadata": {},
            },
        ]
    return {
        "rendering_intent": {
            "rendering_mode": "photoreal",
            "stylization_scope": "none",
            "decision_owner": "remote_brain",
        },
        "developmental_age_intent": "preserve_reference_stage" if visible_person else "not_applicable",
        "reference_channel_ownership_intent": {
            "applicability": "not_applicable",
            "decision_owner": "remote_brain",
            "reference_owned_channels": [],
            "current_request_owned_channels": [],
            "evidence_ids": [],
            "confidence": 0.96,
        },
        "subject_entities": entities,
        "visual_intent_tags": ["photographic_observation"],
        "unknown_requirements": [],
        "confidence": 0.96,
        "evidence": evidence,
    }


def _remote_activation_intent(*, visible_person: bool) -> dict:
    return {
        "requested_capabilities": (
            [
                {
                    "capability_id": "human_realism",
                    "activation_mode": "required",
                    "reason_codes": ["visible_real_person_execution_invariant"],
                    "evidence_ids": ["remote_visible_person", "remote_real_human_output"],
                    "requested_profile": None,
                    "confidence": 0.96,
                }
            ]
            if visible_person
            else []
        ),
        "rejected_capabilities": [],
        "unresolved_signals": [],
        "confidence": 0.96,
    }


class _SemanticProfileProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, visible_person: bool, partial: bool = False) -> None:
        super().__init__()
        self.visible_person = visible_person
        self.partial = partial

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage != "provider_prompt_finalize" and request.stage != "provider_prompt_human_naturalness_resign":
            profile = _remote_profile(visible_person=self.visible_person)
            if self.partial:
                profile = {"rendering_intent": profile["rendering_intent"]}
            payload["visual_task_profile"] = profile
            payload["capability_activation_intent"] = _remote_activation_intent(visible_person=self.visible_person)
        return payload


def _real_request(user_input: str) -> dict:
    return {
        "user_input": user_input,
        "scenario_selection": {"scenario_id": "general_creative"},
        "metadata": {"requested_image_count": 1, "require_real_images": True},
    }


def test_doc140_compact_real_image_schema_requires_complete_semantic_profile() -> None:
    request = BrainRunRequest(
        user_input="Create one observational studio photograph.",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_real_images": True},
    )

    payload = json.loads(build_remote_payload(request))
    profile = payload["return_schema"]["visual_task_profile"]

    assert {
        "rendering_intent",
        "developmental_age_intent",
        "subject_entities",
        "visual_intent_tags",
        "unknown_requirements",
        "confidence",
        "evidence",
    } <= set(profile)
    assert "capability_activation_intent" in payload["return_schema"]
    assert "explicit empty lists" in payload["remote_response_contract"]


def test_doc140_safe_age_sensitive_request_keeps_remote_json_contract_authority() -> None:
    assert "return the required JSON planning contract rather than a prose refusal" in SYSTEM_PROMPT
    assert "not turn it into a local branch" in SYSTEM_PROMPT
    assert "age-specific capability" in SYSTEM_PROMPT


def test_doc140_partial_remote_task_profile_blocks_before_signing_or_materialization() -> None:
    provider = _SemanticProfileProvider(visible_person=True, partial=True)
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        _real_request("Create one candid photograph of an adult ceramic artist at work in a quiet studio.")
    )

    assert result.status.value == "blocked"
    assert result.planning_result is None
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "remote_creative_brain_task_profile_invalid"
    assert outcome["remote_contract_rejected_sections"] == ["visual_task_profile"]
    assert [item["stage"] for item in provider.requests] == ["plan", "plan"]


def test_doc140_remote_adult_profile_activates_shared_human_realism_without_local_inference() -> None:
    provider = _SemanticProfileProvider(visible_person=True)
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        _real_request("Create one observational photograph of an adult ceramic artist making a vessel in a quiet studio.")
    )

    assert result.status.value == "planned"
    plan = result.planning_result.metadata["capability_activation_plan"]
    assert "human_realism" in plan["dependency_order"]
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["remote_visual_task_profile_received"] is True
    assert audit["canonical_provider_prompt_stages"] == ["provider_prompt_finalize"]
    assert [item["stage"] for item in provider.requests].count("provider_prompt_human_naturalness_resign") == 0
    assert audit["remote_brain_call_count"] == 2


def test_doc140_complete_product_only_profile_stays_human_inactive() -> None:
    provider = _SemanticProfileProvider(visible_person=False)
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        _real_request("Create one factual flat-lay photograph of a ceramic vase, with no people visible.")
    )

    assert result.status.value == "planned"
    plan = result.planning_result.metadata["capability_activation_plan"]
    assert "human_realism" not in plan["dependency_order"]
    assert [item["stage"] for item in provider.requests].count("provider_prompt_human_naturalness_resign") == 0


def test_doc140_remote_no_person_decision_overrides_an_older_fallback_subject_guess() -> None:
    provider = _SemanticProfileProvider(visible_person=False)
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        _real_request("Create a real-camera photograph that visibly includes a person.")
    )

    assert result.status.value == "planned"
    profile = result.metadata["llm_brain"]["visual_task_profile"]
    plan = result.planning_result.metadata["capability_activation_plan"]
    assert profile["subject_entities"] == []
    assert profile["evidence"] == []
    assert result.metadata["llm_brain"]["capability_activation_intent"]["requested_capabilities"] == []
    assert "human_realism" not in plan["dependency_order"]
