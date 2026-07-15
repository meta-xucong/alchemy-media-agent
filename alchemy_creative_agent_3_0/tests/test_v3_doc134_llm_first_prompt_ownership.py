"""Doc134: Brain-owned semantics and canonical Provider-prompt sign-off."""

from __future__ import annotations

import json

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    GenerationRequest,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
    ecommerce_test_service,
)


def test_frozen_brain_object_surface_semantics_override_legacy_cartoon_keyword() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc134",
        job_id="job_doc134",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Photograph a school-age girl wearing the supplied blue dress with a cartoon princess print.",
        subject_type="product",
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "object_surface",
                "decision_owner": "remote_brain",
            },
        },
    )

    assert guidance.applies is True
    assert guidance.metadata["enable_reason"] == "frozen_human_realism_execution"
    assert guidance.metadata["human_realism_plugin"]["disabled_by_style"] is False


def test_finalizer_payload_exposes_frozen_contract_not_local_prompt_atoms() -> None:
    request = BrainRunRequest(
        user_input="Create a real photographic image from the approved reference.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "protected_user_intent": "Create a real photographic image from the approved reference.",
                "rendering_semantics": {"rendering_mode": "photoreal", "stylization_scope": "none"},
                "active_shared_capability_ids": ["human_realism", "product_identity"],
                "deliverables": [{"output_index": 1, "image_intent": "one natural photographic scene"}],
                "frozen_binding": {"envelope_id": "opaque", "ledger_id": "opaque"},
            }
        },
    )

    payload = json.loads(build_remote_payload(request))
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["task"] == "finalize_canonical_image_provider_prompts"
    assert set(payload["return_schema"]) == {"canonical_provider_prompts"}
    assert "prompt_additions" not in serialized
    assert "negative_additions" not in serialized
    assert "casebook" not in serialized.lower()


def test_ecommerce_provider_receives_exact_brain_signed_prompt_without_local_append() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    service = ecommerce_test_service(brain_provider=provider)
    created = service.create_job(
        {
            "user_input": "Create one factual product image from the approved product facts.",
            "scenario_selection": {"scenario_id": "ecommerce", "parameters": {"requested_image_count": 1}},
            "metadata": {"requested_image_count": 1},
        }
    )

    assert created.status == "planned"
    frozen = service.job_store.get(created.job_id).request.metadata["frozen_remote_creative_brain"]
    signed_prompt = frozen["brain_result"]["canonical_provider_prompts"][0]["prompt"]
    assert provider.requests[-1]["stage"] == "provider_prompt_finalize"
    finalizer_context = provider.requests[-1]["metadata"]["canonical_prompt_context"]
    assert finalizer_context["brain_draft_directions"] == [
        {
            "output_index": 1,
            "direction": "Remote Brain test output 1: communicate the supplied product facts and this request's buyer need.",
        }
    ]

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    assert generated.status == "generated"
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    request = GenerationRequest(
        asset_spec=record.generation_result.series_plan.assets[0],
        layout_plan=record.generation_result.layout_plans[0],
        prompt_compilation=record.generation_result.prompt_compilations[0],
        condition_plan=record.generation_result.condition_plans[0],
        generation_plan=record.generation_result.generation_plans[0],
        metadata=dict(record.generation_result.generation_plans[0].metadata),
    )

    materialized = ProductionImageGenerationProvider().materialize_final_prompt(request)
    assert materialized.generation_prompt == signed_prompt
    assert materialized.prompt_source == "remote_brain_canonical"
    assert materialized.prompt_audit["prompt_source"] == "remote_brain_canonical"
    assert "Human realism contract:" not in materialized.generation_prompt
    assert "Role-specific generation contract:" not in materialized.generation_prompt

    missing_signoff_request = request.model_copy(
        update={
            "metadata": {
                **dict(request.metadata),
                "llm_brain": {},
                # The normalized enforced V3 contract alone is sufficient;
                # this must not rely on an incidental caller flag.
                "require_real_images": False,
                "real_image_generation": False,
            }
        }
    )
    with pytest.raises(Exception, match="canonical Provider prompt"):
        ProductionImageGenerationProvider().materialize_final_prompt(missing_signoff_request)


def test_missing_final_signoff_blocks_before_new_job_can_be_planned() -> None:
    class MissingFinalizer(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                return {"canonical_provider_prompts": []}
            return super().run(request)

    service = ecommerce_test_service(brain_provider=MissingFinalizer())
    result = service.create_job(
        {
            "user_input": "Create one factual product image.",
            "scenario_selection": {"scenario_id": "ecommerce", "parameters": {"requested_image_count": 1}},
            "metadata": {"requested_image_count": 1},
        }
    )

    assert result.status == "blocked"
    assert result.asset_series == []
    assert result.metadata["remote_creative_brain_outcome"]["reason_code"] == (
        "remote_creative_brain_prompt_signoff_unavailable"
    )
