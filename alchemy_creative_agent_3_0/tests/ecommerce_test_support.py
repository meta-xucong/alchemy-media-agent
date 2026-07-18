"""Explicit remote-Brain test double for E-Commerce-only tests.

Production never imports this helper.  It exists because E-Commerce correctly
fails closed without a remote creative Brain, while unit tests need a stable
contract-shaped substitute.
"""

from __future__ import annotations

from copy import deepcopy

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


class EcommerceRemoteBrainTestProvider:
    provider = "ecommerce_remote_brain_test_double"
    model = "contract-fixture-v1"

    def __init__(
        self,
        *,
        fault: str | None = None,
        developmental_age_intent: str = "not_applicable",
    ) -> None:
        self.fault = fault
        self.developmental_age_intent = developmental_age_intent
        self.requests: list[dict] = []

    def available(self, *, force: bool = False) -> bool:
        return self.fault != "unavailable"

    def run(self, request) -> dict:
        self.requests.append(deepcopy(request.model_dump(mode="json")))
        payload = build_fallback_result(request).model_dump(mode="json")
        count = request.requested_image_count
        if self.fault == "missing_image_set_plan":
            payload.pop("image_set_plan", None)
            return payload
        if self.fault == "empty_image_set_plan":
            payload["image_set_plan"] = {
                "set_goal": "Incomplete remote result",
                "image_count": count,
                "size": request.requested_image_size,
                "shot_plan": [],
            }
            return payload
        if self.fault == "mismatched_image_set_plan":
            payload["image_set_plan"] = {
                "set_goal": "Incomplete remote result",
                "image_count": count,
                "size": request.requested_image_size,
                "shot_plan": ["Only a partial remote direction"],
            }
            return payload
        payload["image_set_plan"] = {
            "set_goal": "Test-only remote Brain product image set",
            "image_count": count,
            "size": request.requested_image_size,
            "shot_plan": [
                f"Remote Brain test output {index}: communicate the supplied product facts and this request's buyer need."
                for index in range(1, count + 1)
            ],
            "evidence_dimensions_by_output": _apparel_evidence_dimensions(request, count),
            "composition_rules": ["Remote Brain decides the complete image treatment for each requested output."],
            "quality_bar": ["Product facts and approved claims remain faithful."],
        }
        payload["prompt_guidance"] = {
            **payload["prompt_guidance"],
            "optimized_direction": "Use the remote Brain's product-specific image intent.",
            "visual_direction_addons": ["Use the remote Brain's product-specific image intent."],
        }
        # Preserve the complete fixture profile, then make only the semantic
        # rendering decision explicitly remote. Production real-image paths
        # now reject a response which gives merely this one sub-object.
        payload["visual_task_profile"] = {
            **payload["visual_task_profile"],
            "developmental_age_intent": self.developmental_age_intent,
            "rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        }
        context = request.metadata.get("canonical_prompt_context") if isinstance(request.metadata, dict) else {}
        preflight = context.get("final_prompt_semantic_preflight") if isinstance(context, dict) else {}
        requires_human_preflight = isinstance(preflight, dict) and bool(preflight.get("required"))
        decision_requirement = context.get("human_naturalness_decision") if isinstance(context, dict) else None
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
            context.get("reference_channel_ownership_decision") if isinstance(context, dict) else None
        )
        requires_reference_ownership_decision = bool(
            isinstance(ownership_requirement, dict)
            and ownership_requirement.get("required") is True
            and ownership_requirement.get("contract_version")
            == "v3_reference_channel_ownership_decision_v1"
            and ownership_requirement.get("owner") == "remote_v3_llm_brain"
        )
        age_requirement = context.get("human_developmental_age_decision") if isinstance(context, dict) else None
        requires_developmental_age_decision = bool(
            isinstance(age_requirement, dict)
            and age_requirement.get("required") is True
            and age_requirement.get("contract_version") == "v3_human_developmental_age_decision_v2"
            and age_requirement.get("age_fidelity") == "follow_explicit_prompt"
            and age_requirement.get("source_age_inheritance")
            == "not_automatic_when_current_prompt_assigns_age"
            and age_requirement.get("developmental_age_coherence") == "whole_person_requested_stage"
            and age_requirement.get("developmental_presence")
            == "integrated_stage_coherent_face_attention_and_affect"
            and age_requirement.get("owner") == "remote_v3_llm_brain"
        )
        presence_requirement = (
            context.get("human_developmental_presence_decision")
            if isinstance(context, dict)
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
        anchor_view_requirement = (
            context.get("professional_anchor_view_decision") if isinstance(context, dict) else None
        )
        anchor_view_target = (
            str(anchor_view_requirement.get("target_view_role") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_view_version = (
            str(anchor_view_requirement.get("contract_version") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_capture_presentation = (
            str(anchor_view_requirement.get("capture_presentation") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_capture_continuity = (
            str(anchor_view_requirement.get("capture_continuity") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        requires_anchor_view_decision = bool(
            isinstance(anchor_view_requirement, dict)
            and anchor_view_requirement.get("required") is True
            and anchor_view_version in {
                "v3_professional_anchor_view_decision_v1",
                "v3_professional_anchor_view_decision_v2",
                "v3_professional_anchor_view_decision_v3",
            }
            and anchor_view_requirement.get("owner") == "remote_v3_llm_brain"
            and anchor_view_target in {"standard_front", "three_quarter", "profile"}
            and (
                anchor_capture_presentation == "neutral_identity_evidence_capture"
                and anchor_capture_continuity
                == (
                    "establish_neutral_capture"
                    if anchor_view_target == "standard_front"
                    else "preserve_approved_prior_capture"
                )
                if anchor_view_version == "v3_professional_anchor_view_decision_v3"
                else anchor_capture_presentation == "neutral_identity_evidence_capture"
                if anchor_view_version == "v3_professional_anchor_view_decision_v2"
                else not anchor_capture_presentation
            )
        )
        payload["canonical_provider_prompts"] = [
            {
                "output_index": index,
                "prompt": (
                    f"Remote Brain approved complete product image {index}: preserve the supplied product facts, "
                    "reference truth, and explicit user constraints in one coherent photographic image."
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
                            "resolution_mode": (
                                "holistic_person_and_situation_resolution"
                            ),
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_developmental_presence_decision
                    else {}
                ),
                **(
                    {
                        "professional_anchor_view_decision": {
                            "contract_version": anchor_view_version,
                            "target_view_role": anchor_view_target,
                            **(
                                {"capture_presentation": anchor_capture_presentation}
                                if anchor_capture_presentation
                                else {}
                            ),
                            **(
                                {"capture_continuity": anchor_capture_continuity}
                                if anchor_capture_continuity
                                else {}
                            ),
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_anchor_view_decision
                    else {}
                ),
            }
            for index in range(1, count + 1)
        ]
        return payload


def _apparel_evidence_dimensions(request, count: int) -> list[dict]:
    context = request.metadata.get("ecommerce_creative_context") if isinstance(request.metadata, dict) else None
    profile = context.get("apparel_on_model_evidence_profile") if isinstance(context, dict) else None
    if not isinstance(profile, dict) or not profile.get("applies") or count <= 1:
        return []
    dimensions = [str(item) for item in profile.get("allowed_evidence_dimensions", []) if str(item).strip()]
    if not dimensions:
        return []
    entries = []
    for index in range(1, count + 1):
        primary = dimensions[(index - 1) % len(dimensions)]
        evidence = [primary]
        if index > len(dimensions):
            evidence.append(dimensions[index % len(dimensions)])
        entries.append({"output_index": index, "evidence_dimensions": evidence})
    return entries


def ecommerce_test_service(
    *,
    brain_provider: EcommerceRemoteBrainTestProvider | None = None,
    **service_kwargs,
) -> V3ProductApiService:
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=brain_provider or EcommerceRemoteBrainTestProvider())
    )
    return V3ProductApiService(scenario_runtime=runtime, **service_kwargs)
