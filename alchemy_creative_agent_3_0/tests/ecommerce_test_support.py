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
            "reference_channel_ownership_intent": _reference_channel_ownership_intent(request),
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
        anchor_capture_scope = (
            str(anchor_view_requirement.get("capture_scope") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_framing_standard = (
            str(anchor_view_requirement.get("framing_standard") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_crop_policy = (
            str(anchor_view_requirement.get("crop_policy") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_torso_scope = (
            str(anchor_view_requirement.get("torso_scope") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_aspect_ratio_standard = (
            str(anchor_view_requirement.get("aspect_ratio_standard") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_source_viewpoint_inheritance = (
            str(anchor_view_requirement.get("source_viewpoint_inheritance") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_front_pose_normalization = (
            str(anchor_view_requirement.get("front_pose_normalization") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_face_axis_alignment = (
            str(anchor_view_requirement.get("face_axis_alignment") or "").strip()
            if isinstance(anchor_view_requirement, dict)
            else ""
        )
        anchor_character_card_framing_valid = (
            anchor_capture_scope != "character_card_face_identity"
            or anchor_view_target != "standard_front"
            or (
                anchor_framing_standard == "consistent_head_and_upper_shoulders_reference_crop"
                and anchor_crop_policy == "head_top_margin_full_face_neck_and_upper_shoulders_visible"
                and anchor_torso_scope == "upper_shoulders_only_no_half_body_or_big_head_crop"
                and anchor_aspect_ratio_standard
                == "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
            )
        )
        anchor_front_pose_normalization_valid = (
            anchor_capture_scope != "character_card_face_identity"
            or anchor_view_target != "standard_front"
            or (
                anchor_source_viewpoint_inheritance
                == "identity_only_do_not_inherit_source_pose_angle"
                and anchor_front_pose_normalization
                == "normalize_to_symmetric_camera_facing_front"
                and anchor_face_axis_alignment
                == "face_midline_vertical_eyes_level_nose_centered"
            )
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
            and anchor_view_target
            in {"standard_front", "three_quarter", "profile", "reverse_three_quarter", "rear_head"}
            and anchor_capture_scope in {"", "character_card_face_identity"}
            and anchor_character_card_framing_valid
            and anchor_front_pose_normalization_valid
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
        provider_admission_requirement = (
            context.get("provider_admission_decision") if isinstance(context, dict) else None
        )
        requires_provider_admission_decision = bool(
            isinstance(provider_admission_requirement, dict)
            and provider_admission_requirement.get("required") is True
            and provider_admission_requirement.get("contract_version")
            == "v3_provider_admission_decision_v1"
            and provider_admission_requirement.get("provider_admission_status") == "admitted"
            and provider_admission_requirement.get("prompt_language_mode")
            == "concise_positive_renderer_direction"
            and provider_admission_requirement.get("safety_sensitive_prompt_normalized") == "applied"
            and provider_admission_requirement.get("owner") == "remote_v3_llm_brain"
        )
        slot_delta_requirement = (
            context.get("reference_led_slot_delta_decision") if isinstance(context, dict) else None
        )
        slot_delta_type = (
            str(slot_delta_requirement.get("slot_delta_type") or "").strip()
            if isinstance(slot_delta_requirement, dict)
            else ""
        )
        slot_delta_target = (
            context.get("character_card_slot_delta_target") if isinstance(context, dict) else None
        )
        slot_delta_target = slot_delta_target if isinstance(slot_delta_target, dict) else {}
        expression_target = str(slot_delta_target.get("expression") or "").strip()
        body_target = str(slot_delta_target.get("body_slot") or "").strip()
        requires_slot_delta_decision = bool(
            isinstance(slot_delta_requirement, dict)
            and slot_delta_requirement.get("required") is True
            and slot_delta_requirement.get("contract_version")
            == "v3_reference_led_slot_delta_decision_v1"
            and slot_delta_requirement.get("materialization_mode") == "reference_led_slot_delta"
            and slot_delta_requirement.get("stable_identity_source")
            == "approved_character_card_reference"
            and slot_delta_requirement.get("prompt_scope") == "slot_delta_only"
            and slot_delta_requirement.get("safety_sensitive_repetition_policy")
            == "avoid_repeating_stable_person_biology"
            and slot_delta_type in {"view_angle", "expression", "body_pose"}
            and slot_delta_requirement.get("owner") == "remote_v3_llm_brain"
        )
        character_card_face_prompt = {
            "standard_front": (
                "Clean straight-on front-facing, symmetric, centered face-midline identity reference portrait; "
                "eyes level and nose centered, vertical 2:3 card, consistent head-and-upper-shoulders crop on a plain white studio "
                "background, same person, natural camera-observed human materiality, crisp commercial clean finish."
            ),
            "three_quarter": (
                "Clean left-front 45-degree three-quarter vertical 2:3 card head-and-upper-shoulders identity reference portrait on a plain white studio "
                "background, same person, left ear visible on image-left and nose angled toward image-right, "
                "same camera distance and head size as the approved front card, complete head-and-hair silhouette around the cranium, "
                "similar head-top margin, same foreground card scale and subject top margin, full face, neck, upper shoulders and collar line visible, allowing natural face-box projection changes from the head turn, "
                "crop ends just below the upper shoulders with clean white padding below the shoulder line, long hair may crop naturally below the upper shoulders, not a tight face close-up "
                "and not a half-body crop, no chest-or-torso panel below the upper shoulders, not zoomed in, no soft feathered vignette or faded hair boundary, natural camera-observed human materiality, crisp commercial clean finish."
            ),
            "profile": (
                "Clean side profile vertical 2:3 card head-and-upper-shoulders identity reference portrait on a plain white studio "
                "background, same person, same camera distance and head size as the approved front card, complete head-and-hair silhouette around the cranium, "
                "similar head-top margin, same foreground card scale and subject top margin, neck, upper shoulders and collar line visible, same head-and-upper-shoulders card scale, "
                "crop ends just below the upper shoulders with clean white padding below the shoulder line, long hair may crop naturally below the upper shoulders, not a tight face close-up and not a half-body crop, "
                "no chest-or-torso panel below the upper shoulders, not zoomed in, no soft feathered vignette or faded hair boundary, natural camera-observed human materiality, crisp commercial clean finish."
            ),
            "reverse_three_quarter": (
                "Clean right-front opposite 45-degree three-quarter vertical 2:3 card head-and-upper-shoulders identity reference portrait on a plain white studio "
                "background, same person, independent opposite-side right-front view with right ear visible on image-right "
                "and nose angled toward image-left, not a horizontal flip or literal mirror of the left-front card, preserving natural left/right face and hair asymmetry, "
                "same camera distance and head size as the approved front card, complete head-and-hair silhouette around the cranium, "
                "similar head-top margin, same foreground card scale and subject top margin, full face, neck, upper shoulders and collar line visible, allowing natural face-box projection changes from the head turn, "
                "crop ends just below the upper shoulders with clean white padding below the shoulder line, long hair may crop naturally below the upper shoulders, not a tight face close-up and not a half-body crop, "
                "no chest-or-torso panel below the upper shoulders, not zoomed in, no soft feathered vignette or faded hair boundary, natural camera-observed human materiality, crisp commercial clean finish."
            ),
            "rear_head": (
                "Clean rear head view vertical 2:3 card head-and-upper-shoulders identity reference portrait on a plain white studio "
                "background, same person hair and head shape, same camera distance and head size as the approved front card, complete back-of-head silhouette around the cranium, "
                "similar head-top margin, same foreground card scale and subject top margin, neck, upper shoulders and back collar line visible, same back-of-head head-and-upper-shoulders card scale, "
                "crop ends just below the upper shoulders with clean white padding below the shoulder line, long hair may crop naturally below the upper shoulders, no visible face and no visible eyes, "
                "not a tight head close-up and not a half-body crop, no chest-or-torso panel below the upper shoulders, not zoomed in, no soft feathered vignette "
                "or faded hair boundary, natural camera-observed human materiality, crisp commercial clean finish."
            ),
        }.get(anchor_view_target)
        expression_slot_prompt = {
            "laugh": (
                "Reference-led Character Card expression.laugh portrait of the same person, "
                "medium-arousal naturally amused laugh keyframe, clean white reference-card framing."
            ),
            "anger": (
                "Reference-led Character Card expression.anger portrait of the same person, "
                "mild age-appropriate annoyed serious expression, clean white reference-card framing."
            ),
            "sad": (
                "Reference-led Character Card expression.sad portrait of the same person, "
                "quiet age-appropriate sad pensive expression, clean white reference-card framing."
            ),
        }.get(expression_target)
        body_slot_prompt = (
            f"Reference-led Character Card body.{body_target} silhouette card of the same person, "
            "clean white full-body modeling-card framing."
            if body_target
            else None
        )
        slot_delta_prompt = (
            expression_slot_prompt
            if slot_delta_type == "expression"
            else body_slot_prompt
            if slot_delta_type == "body_pose"
            else None
        )
        payload["canonical_provider_prompts"] = [
            {
                "output_index": index,
                "prompt": (
                    character_card_face_prompt
                    if requires_anchor_view_decision
                    and anchor_capture_scope == "character_card_face_identity"
                    and character_card_face_prompt
                    else slot_delta_prompt
                    if requires_slot_delta_decision and slot_delta_prompt
                    else (
                        f"Remote Brain approved complete product image {index}: preserve the supplied product facts, "
                        "reference truth, and explicit user constraints in one coherent photographic image."
                    )
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
                            **(
                                {"capture_scope": anchor_capture_scope}
                                if anchor_capture_scope
                                else {}
                            ),
                            **(
                                {
                                    "framing_standard": anchor_framing_standard,
                                    "crop_policy": anchor_crop_policy,
                                    "torso_scope": anchor_torso_scope,
                                    "aspect_ratio_standard": anchor_aspect_ratio_standard,
                                }
                                if anchor_capture_scope == "character_card_face_identity"
                                and anchor_view_target == "standard_front"
                                else {}
                            ),
                            **(
                                {
                                    "source_viewpoint_inheritance": anchor_source_viewpoint_inheritance,
                                    "front_pose_normalization": anchor_front_pose_normalization,
                                    "face_axis_alignment": anchor_face_axis_alignment,
                                }
                                if anchor_capture_scope == "character_card_face_identity"
                                and anchor_view_target == "standard_front"
                                else {}
                            ),
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_anchor_view_decision
                    else {}
                ),
                **(
                    {
                        "provider_admission_decision": {
                            "contract_version": "v3_provider_admission_decision_v1",
                            "provider_admission_status": "admitted",
                            "prompt_language_mode": "concise_positive_renderer_direction",
                            "safety_sensitive_prompt_normalized": "applied",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_provider_admission_decision
                    else {}
                ),
                **(
                    {
                        "reference_led_slot_delta_decision": {
                            "contract_version": "v3_reference_led_slot_delta_decision_v1",
                            "materialization_mode": "reference_led_slot_delta",
                            "stable_identity_source": "approved_character_card_reference",
                            "prompt_scope": "slot_delta_only",
                            "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
                            "slot_delta_type": slot_delta_type,
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if requires_slot_delta_decision
                    else {}
                ),
            }
            for index in range(1, count + 1)
        ]
        return payload


def _reference_channel_ownership_intent(request) -> dict:  # noqa: ANN001
    """Contract-shaped remote semantic decision for test-only Brain fixtures."""

    assets = [
        *list(getattr(request, "reference_assets", []) or []),
        *list(getattr(request, "uploaded_assets", []) or []),
    ]
    if not assets:
        return {
            "applicability": "not_applicable",
            "decision_owner": "remote_brain",
            "reference_owned_channels": [],
            "current_request_owned_channels": [],
            "evidence_ids": [],
            "confidence": 0.98,
        }
    roles = {
        str((item if isinstance(item, dict) else {}).get("role") or "").strip().lower()
        for item in assets
    }
    reference_owned: list[str] = []
    if any("face" in role or "portrait" in role or "identity" in role for role in roles):
        reference_owned.append("identity_geometry")
    if any("product" in role for role in roles):
        reference_owned.append("product_identity")
    if any("appearance" in role or "garment" in role for role in roles):
        reference_owned.append("wardrobe_structure")
    current_owned = [
        channel
        for channel in (
            "body_identity",
            "natural_complexion_direction",
            "hair_direction",
            "makeup_style",
            "wardrobe_structure",
            "accessory_system",
            "lighting_color",
            "scene_background",
            "camera_composition",
            "mood_art_direction",
            "style_finish",
        )
        if channel not in reference_owned
    ]
    return {
        "applicability": "applicable",
        "decision_owner": "remote_brain",
        "reference_owned_channels": reference_owned,
        "current_request_owned_channels": current_owned,
        "evidence_ids": ["test_fixture_declared_reference"],
        "confidence": 0.98,
    }


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
