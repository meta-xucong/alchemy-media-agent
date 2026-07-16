"""Doc142: the existing Human Realism re-signer returns an auditable decision."""

from __future__ import annotations

import copy
import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


_HUMAN_REQUEST = {
    "user_input": (
        "Create one candid real-camera photograph of a visible adult person who is a ceramic artist naturally working in a sunlit studio. "
        "Keep the physical presence credible and preserve the ordinary, unstaged mood."
    ),
    "scenario_selection": {"scenario_id": "general_creative"},
    "metadata": {"requested_image_count": 1, "requested_image_size": "1024x1536", "require_real_images": True},
}


class _DecisionResigner(EcommerceRemoteBrainTestProvider):
    """Return only the public-safe receipt required by Doc142 M1."""

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_human_naturalness_resign":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A candid real-camera photograph of an adult ceramic artist absorbed in shaping clay at a worktable "
                "in a sunlit studio, preserving the ordinary working moment and the requested mood."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        return payload


class _MissingDecisionResigner(EcommerceRemoteBrainTestProvider):
    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_human_naturalness_resign":
            for prompt in payload["canonical_provider_prompts"]:
                prompt.pop("human_naturalness_decision", None)
        return payload


def test_doc142_active_human_resigner_requires_one_safe_decision_receipt() -> None:
    provider = _DecisionResigner()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(copy.deepcopy(_HUMAN_REQUEST))

    assert result.status.value == "planned"
    stages = [item["stage"] for item in provider.requests]
    assert stages == ["plan", "provider_prompt_finalize", "provider_prompt_human_naturalness_resign"]
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["human_realism_natural_presence_decision_required"] is True
    assert audit["human_realism_natural_presence_decision_signed"] is True
    assert audit["human_realism_natural_presence_decisions"] == [
        {
            "contract_version": "v3_human_naturalness_decision_v1",
            "status": "rewritten",
            "owner": "remote_v3_llm_brain",
        }
    ]

    resign_request = next(item for item in provider.requests if item["stage"] == "provider_prompt_human_naturalness_resign")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(resign_request)))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]
    assert schema["human_naturalness_decision"] == {
        "contract_version": "v3_human_naturalness_decision_v1",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "third Brain" not in payload["remote_response_contract"]


def test_doc142_missing_decision_receipt_blocks_with_its_own_safe_reason() -> None:
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=_MissingDecisionResigner())).plan_job(
        copy.deepcopy(_HUMAN_REQUEST)
    )

    assert result.status.value == "blocked"
    assert result.planning_result is None
    assert result.metadata["remote_creative_brain_outcome"]["reason_code"] == (
        "human_realism_natural_presence_decision_missing"
    )


def test_doc142_non_human_job_neither_requires_nor_emits_a_decision_receipt() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create one factual flat-lay photograph of a ceramic vase with no people.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    assert [item["stage"] for item in provider.requests] == ["plan", "provider_prompt_finalize"]
    audit = result.metadata["llm_brain"]["audit"]
    assert audit.get("human_realism_natural_presence_decision_required") is not True
    assert audit.get("human_realism_natural_presence_decisions") in (None, [])


def test_doc142_enforced_human_review_keeps_only_normalized_evidence_for_brain() -> None:
    layer = HumanPhotorealismLayer()
    guidance = layer.build(
        project_id="project_doc142",
        job_id="job_doc142",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a candid real-camera portrait of a visible adult person.",
        subject_type="person",
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    )

    review = layer.review(
        guidance=guidance,
        project_id="project_doc142",
        job_id="job_doc142",
        issue_codes=["plastic_skin", "bad_hands_or_body"],
    )

    assert review.issue_codes == ["human_skin_or_retouch", "human_anatomy_or_proportion"]
    assert review.retry_patch == {}
    assert review.metadata["retry_evidence_only"] is True


def test_doc142_retry_normalizes_human_evidence_before_finalizer_and_hides_it_from_resigner() -> None:
    provider = _DecisionResigner()
    request = copy.deepcopy(_HUMAN_REQUEST)
    request["metadata"].update(
        {
            "visual_auto_retry_active": True,
            "visual_retry_reason_codes": ["plastic_skin", "bad_hands_or_body", "product_identity_drift"],
        }
    )

    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(request)

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    resigner = next(item for item in provider.requests if item["stage"] == "provider_prompt_human_naturalness_resign")
    assert finalizer["metadata"]["canonical_prompt_context"]["retry_evidence"] == {
        "active": True,
        "issue_codes": [
            "human_skin_or_retouch",
            "human_anatomy_or_proportion",
            "product_identity_drift",
        ],
    }
    assert "retry_evidence" not in resigner["metadata"]["canonical_prompt_context"]


@pytest.mark.parametrize(
    "user_input",
    [
        "Create a candid real-camera photograph of a visible adult person waiting naturally at a bus stop.",
        "Create a fully clothed, family-friendly real-camera photograph of a visible school-age person wearing the supplied blue dress in an ordinary garden.",
        "Create a real-camera photograph of a visible adult person naturally holding a ceramic cup at a worktable.",
        "Create a restrained low-key real-camera portrait of a visible older person in a quiet studio.",
    ],
)
def test_doc142_shared_contract_covers_distinct_real_person_contexts(user_input: str) -> None:
    provider = _DecisionResigner()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": user_input,
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["human_realism_natural_presence_decision_signed"] is True
    assert audit["human_realism_natural_presence_decisions"][0]["owner"] == "remote_v3_llm_brain"
    assert [item["stage"] for item in provider.requests].count("provider_prompt_human_naturalness_resign") == 1
