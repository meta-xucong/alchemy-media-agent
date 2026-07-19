"""Explicit remote-Brain fixture for active Photography runtime tests.

Production intentionally never imports this module.  Active Photography is
LLM-first and fails closed without a remote creative Brain, so tests that need
successful generation must opt into this contract-shaped substitute.
"""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import VisionOutputInspector
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import _reference_channel_ownership_intent


class PhotographyRemoteBrainTestProvider:
    provider = "photography_remote_brain_test_double"
    model = "contract-fixture-v1"

    def __init__(self) -> None:
        self.requests = []

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request) -> dict:
        self.requests.append(request)
        payload = build_fallback_result(request).model_dump(mode="json")
        count = request.requested_image_count
        payload["image_set_plan"] = {
            "set_goal": "Test-only remote Brain photography delivery",
            "image_count": count,
            "size": request.requested_image_size,
            "shot_plan": [
                (
                    f"Remote Photography direction {index}: create one complete, original photographic image "
                    "that answers the user's request and respects the declared reference truth."
                )
                for index in range(1, count + 1)
            ],
            "composition_rules": ["The remote Brain owns each image's composition and visual treatment."],
            "quality_bar": ["Preserve explicit controls and reference truth without a local shot recipe."],
        }
        payload["prompt_guidance"] = {
            **payload["prompt_guidance"],
            "optimized_direction": "Use each remote Photography image intent as the complete creative direction.",
            "visual_direction_addons": ["Use the remote Photography image intent."],
        }
        # The fixture mirrors a complete remote semantic profile.  A
        # rendering-intent-only response is intentionally invalid for a real
        # Photography image, because it could inherit a local subject guess.
        payload["visual_task_profile"] = {
            **payload["visual_task_profile"],
            "reference_channel_ownership_intent": _reference_channel_ownership_intent(request),
            "rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        }
        canonical_context = request.metadata.get("canonical_prompt_context") if isinstance(request.metadata, dict) else {}
        preflight = canonical_context.get("final_prompt_semantic_preflight") if isinstance(canonical_context, dict) else {}
        requires_human_preflight = isinstance(preflight, dict) and bool(preflight.get("required"))
        decision_requirement = canonical_context.get("human_naturalness_decision") if isinstance(canonical_context, dict) else None
        requires_human_naturalness_decision = bool(
            request.stage in {
                "provider_prompt_human_naturalness_resign",
                "provider_prompt_developmental_presence_verify",
            }
            or (
                isinstance(decision_requirement, dict)
                and decision_requirement.get("required") is True
                and decision_requirement.get("contract_version") == "v3_human_naturalness_decision_v1"
                and decision_requirement.get("owner") == "remote_v3_llm_brain"
            )
        )
        ownership_requirement = (
            canonical_context.get("reference_channel_ownership_decision")
            if isinstance(canonical_context, dict)
            else None
        )
        requires_reference_ownership_decision = bool(
            isinstance(ownership_requirement, dict)
            and ownership_requirement.get("required") is True
            and ownership_requirement.get("contract_version")
            == "v3_reference_channel_ownership_decision_v1"
            and ownership_requirement.get("owner") == "remote_v3_llm_brain"
        )
        age_requirement = (
            canonical_context.get("human_developmental_age_decision")
            if isinstance(canonical_context, dict)
            else None
        )
        requires_developmental_age_decision = bool(
            isinstance(age_requirement, dict)
            and age_requirement.get("required") is True
            and age_requirement.get("contract_version")
            == "v3_human_developmental_age_decision_v2"
            and age_requirement.get("age_fidelity") == "follow_explicit_prompt"
            and age_requirement.get("source_age_inheritance")
            == "not_automatic_when_current_prompt_assigns_age"
            and age_requirement.get("developmental_age_coherence")
            == "whole_person_requested_stage"
            and age_requirement.get("developmental_presence")
            == "integrated_stage_coherent_face_attention_and_affect"
            and age_requirement.get("owner") == "remote_v3_llm_brain"
        )
        presence_requirement = (
            canonical_context.get("human_developmental_presence_decision")
            if isinstance(canonical_context, dict)
            else None
        )
        requires_developmental_presence_decision = bool(
            isinstance(presence_requirement, dict)
            and presence_requirement.get("required") is True
            and presence_requirement.get("contract_version")
            == "v3_human_developmental_presence_decision_v2"
            and presence_requirement.get("developmental_presence")
            == "integrated_stage_coherent_face_attention_and_affect"
            and presence_requirement.get("resolution_mode")
            == "holistic_person_and_situation_resolution"
            and presence_requirement.get("owner") == "remote_v3_llm_brain"
        )
        payload["canonical_provider_prompts"] = [
            {
                "output_index": index,
                "prompt": (
                    f"Remote Brain approved complete photography image {index}: create one coherent photographic "
                    "rendering that respects the user's request and frozen reference truth."
                ),
                "review_status": "approved",
                **({"semantic_preflight_status": "approved"} if requires_human_preflight else {}),
                **(
                    {
                        "human_naturalness_decision": {
                            "contract_version": "v3_human_naturalness_decision_v1",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_human_naturalness_decision
                    else {}
                ),
                **(
                    {
                        "reference_channel_ownership_decision": {
                            "contract_version": "v3_reference_channel_ownership_decision_v1",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_reference_ownership_decision
                    else {}
                ),
                **(
                    {
                        "human_developmental_age_decision": {
                            "contract_version": "v3_human_developmental_age_decision_v2",
                            "age_fidelity": "follow_explicit_prompt",
                            "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                            "developmental_age_coherence": "whole_person_requested_stage",
                            "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_developmental_age_decision
                    else {}
                ),
                **(
                    {
                        "human_developmental_presence_decision": {
                            "contract_version": "v3_human_developmental_presence_decision_v2",
                            "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                            "resolution_mode": "holistic_person_and_situation_resolution",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_developmental_presence_decision
                    else {}
                ),
            }
            for index in range(1, count + 1)
        ]
        return payload


class PhotographyVisionTestProvider:
    provider_name = "photography_vision_test_double"

    def available(self, *, force: bool = False) -> bool:
        return True

    def inspect(self, resolution, *, metadata=None) -> dict:
        return {
            "status": "pass",
            "confidence": 0.96,
            "issue_codes": [],
            "human_naturalness_verdict": {"status": "pass", "issue_codes": []},
            "scores": {"artifact_safety": 0.96, "composition": 0.94, "commercial_finish": 0.95, "overall": 0.95},
        }


def photography_test_runtime(**runtime_kwargs) -> ScenarioRuntime:
    return ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=PhotographyRemoteBrainTestProvider()),
        **runtime_kwargs,
    )


def photography_test_vision_inspector() -> VisionOutputInspector:
    return VisionOutputInspector(vision_provider=PhotographyVisionTestProvider())


def photography_test_service(**service_kwargs) -> V3ProductApiService:
    return V3ProductApiService(
        scenario_runtime=photography_test_runtime(),
        vision_inspector=photography_test_vision_inspector(),
        **service_kwargs,
    )
