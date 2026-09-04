"""Explicit remote-Brain test double for E-Commerce-only tests.

Production never imports this helper.  It exists because E-Commerce correctly
fails closed without a remote creative Brain, while unit tests need a stable
contract-shaped substitute.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.physical_renderer_reference_plan import (
    DOC269_MAX_REFERENCE_IMAGES,
    build_physical_renderer_reference_plan,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    ProductTruthAdmission,
    ProductTruthSource,
    _upload_receipt_digest,
    build_physical_product_projection,
    build_product_truth_admission,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import VariationExecutionContract
from services.alchemy_codex_local_adapter.ecommerce_authority import (
    _LEGACY_TEST_AUTHORITY_CAPABILITY,
    NativeEcommerceAuthority,
    NativeEcommerceAuthorityPreflight,
)


def _resolve_ecommerce_test_authority(
    *,
    planning_result: Any,
    project_id: str,
    job_id: str,
    asset_id: str,
    output_index: int,
    **_: Any,
) -> NativeEcommerceAuthority | None:
    """Re-type the test runtime's server-owned E-Commerce planning result.

    This is deliberately a test-only host seam.  The input is the typed
    runtime result, never the public Native request or its metadata.
    """

    generation_plans = getattr(planning_result, "generation_plans", None)
    if not isinstance(generation_plans, list) or not generation_plans:
        return None
    if not isinstance(output_index, int) or isinstance(output_index, bool) or output_index < 1:
        return None
    try:
        planning_metadata = getattr(planning_result, "metadata", None)
        if not isinstance(planning_metadata, dict):
            return None
        deliverable_plan = planning_metadata.get("template_deliverable_plan")
        deliverables = deliverable_plan.get("deliverables") if isinstance(deliverable_plan, dict) else None
        if not isinstance(deliverables, list) or len(deliverables) != len(generation_plans):
            return None

        generation_metadata_by_position: dict[int, dict[str, Any]] = {}
        product_assets_by_id: dict[str, dict[str, Any]] = {}
        identity_assets_by_id: dict[str, dict[str, Any]] = {}
        for position, generation_plan in enumerate(generation_plans):
            metadata = getattr(generation_plan, "metadata", None)
            if not isinstance(metadata, dict) or not isinstance(metadata.get("reference_assets"), list):
                return None
            internal_output_index = metadata.get("output_index")
            if (
                not isinstance(internal_output_index, int)
                or isinstance(internal_output_index, bool)
                or internal_output_index != position
            ):
                return None
            generation_metadata_by_position[position] = metadata
            for raw_asset in metadata["reference_assets"]:
                if not isinstance(raw_asset, dict):
                    return None
                reference_asset_id = str(raw_asset.get("asset_id") or "").strip()
                if not reference_asset_id:
                    return None
                if raw_asset.get("role") == "product_reference":
                    product_assets_by_id[reference_asset_id] = raw_asset
                elif raw_asset.get("role") == "face_reference":
                    identity_assets_by_id[reference_asset_id] = raw_asset
        positions = tuple(range(len(generation_plans)))
        if tuple(sorted(generation_metadata_by_position)) != positions or not product_assets_by_id:
            return None

        product_sources = []
        for source_asset_id, raw_asset in product_assets_by_id.items():
            asset_metadata = raw_asset.get("metadata")
            content_sha256 = (
                asset_metadata.get("source_integrity_id")
                if isinstance(asset_metadata, dict)
                else None
            )
            if not isinstance(content_sha256, str):
                return None
            consent_reference = "doc134_test_product_truth_consent"
            rights_reference = "doc134_test_product_truth_rights"
            product_sources.append(
                ProductTruthSource(
                    asset_id=source_asset_id,
                    content_sha256=content_sha256,
                    consent_reference=consent_reference,
                    rights_reference=rights_reference,
                    receipt_digest=_upload_receipt_digest(
                        asset_id=source_asset_id,
                        content_sha256=content_sha256,
                        role="product_reference",
                        product_truth_channel="product_truth",
                        consent_reference=consent_reference,
                        rights_reference=rights_reference,
                    ),
                    role="product_reference",
                    product_truth_channel="product_truth",
                    readiness="ready",
                    file_integrity="sha256_verified",
                    provenance="doc134_typed_test_planning_result",
                )
            )
        admission = build_product_truth_admission(
            project_id=str(project_id),
            job_id=str(job_id),
            sources=product_sources,
            product_truth_plan_digest=hashlib.sha256(
                ("doc134_test_product_truth|" + "|".join(item.asset_id for item in product_sources)).encode()
            ).hexdigest(),
        )
        projections = []
        physical_plans = []
        for position in positions:
            contract_output_index = position + 1
            deliverable = deliverables[position]
            deliverable_output_index = deliverable.get("output_index") if isinstance(deliverable, dict) else None
            if (
                not isinstance(deliverable_output_index, int)
                or isinstance(deliverable_output_index, bool)
                or deliverable_output_index != contract_output_index
            ):
                return None
            deliverable_metadata = deliverable.get("metadata") if isinstance(deliverable, dict) else None
            if not isinstance(deliverable_metadata, dict):
                return None
            selected = deliverable_metadata.get("selected_product_truth_asset_ids")
            role = deliverable_metadata.get("product_truth_selection_role")
            if not isinstance(selected, list) or not selected or not isinstance(role, str):
                return None
            projection = build_physical_product_projection(
                job_id=str(job_id),
                output_index=contract_output_index,
                admission=admission,
                selected_product_asset_ids=[str(item) for item in selected],
                selection_source="doc134_typed_test_planning_result",
                selection_role=role,
                cap_reservation=max(1, min(2, len(selected))),
            )
            physical_plan = build_physical_renderer_reference_plan(
                admission=admission,
                projection=projection,
                uploaded_assets=list(product_assets_by_id.values()),
                locked_identity_references=list(identity_assets_by_id.values()),
                selected_continuation_references=[],
                maximum_reference_images=DOC269_MAX_REFERENCE_IMAGES,
            )
            projections.append(projection)
            physical_plans.append(physical_plan)
        primary_projection = next(item for item in projections if item.output_index == output_index)
        primary_plan = next(item for item in physical_plans if item.output_index == output_index)
        return NativeEcommerceAuthority(
            project_id=str(project_id),
            job_id=str(job_id),
            asset_id=str(asset_id),
            output_index=output_index,
            admission=admission,
            projection=primary_projection,
            physical_plan=primary_plan,
            projections=tuple(projections),
            physical_plans=tuple(physical_plans),
        )
    except (KeyError, TypeError, ValueError, StopIteration):
        return None


class _EcommerceTestAuthorityResolver:
    """Explicit test-host seam for the server-owned Native authority.

    The preflight is intentionally derived only from the test host's frozen
    job scope.  The callable resolves the final typed records after the
    runtime returns output positions; it never accepts authority dictionaries
    from a public MCP request.
    """

    # This adapter intentionally preserves legacy fixture construction.  The
    # production planner accepts this path only for a test-module resolver.
    legacy_test_only_post_brain_resolution = True

    def preflight(
        self,
        *,
        project_id: str,
        job_id: str,
        requested_output_count: int,
        server_owned_references: tuple[Any, ...] = (),
        server_owned_body_references: tuple[Any, ...] = (),
    ) -> NativeEcommerceAuthorityPreflight | None:
        digest = hashlib.sha256(
            (
                "doc134-test-server-authority|"
                f"{project_id}|{job_id}|{requested_output_count}"
            ).encode("utf-8")
        ).hexdigest()
        try:
            return NativeEcommerceAuthorityPreflight(
                schema_version="native_ecommerce_authority_preflight_v1",
                project_id=project_id,
                job_id=job_id,
                requested_output_count=requested_output_count,
                authority_digest=digest,
                legacy_test_adapter_capability=_LEGACY_TEST_AUTHORITY_CAPABILITY,
            )
        except ValueError:
            return None

    def __call__(self, **kwargs: Any) -> NativeEcommerceAuthority | None:
        return _resolve_ecommerce_test_authority(**kwargs)


ecommerce_test_authority_resolver = _EcommerceTestAuthorityResolver()


class EcommerceRemoteBrainTestProvider:
    provider = "ecommerce_remote_brain_test_double"
    model = "contract-fixture-v1"

    def __init__(
        self,
        *,
        fault: str | None = None,
        developmental_age_intent: str = "not_applicable",
        visible_ecommerce_person: bool | None = None,
    ) -> None:
        self.fault = fault
        self.developmental_age_intent = developmental_age_intent
        self.visible_ecommerce_person = visible_ecommerce_person
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
            "evidence_dimensions_by_output": _ecommerce_output_contract(request, count),
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
        if self.visible_ecommerce_person is not None and request.scenario_id == "ecommerce":
            payload["visual_task_profile"]["subject_entities"] = (
                [
                    {
                        "entity_id": "test_remote_brain_visible_person",
                        "entity_type": "person",
                        "role": "subject",
                        "source_asset_ids": [],
                        "visible_in_target": True,
                        "preservation_level": "balanced",
                        "confidence": 0.98,
                        "attributes": {},
                    }
                ]
                if self.visible_ecommerce_person
                else []
            )
        context = request.metadata.get("canonical_prompt_context") if isinstance(request.metadata, dict) else {}
        variation_contract = None
        raw_variation_contract = context.get("variation_execution_contract") if isinstance(context, dict) else None
        frozen_binding = context.get("frozen_binding") if isinstance(context, dict) else None
        frozen_variation_binding = (
            frozen_binding.get("variation_execution_contract")
            if isinstance(frozen_binding, dict)
            else None
        )
        if (
            request.stage == "provider_prompt_finalize"
            and request.scenario_id == "general_creative"
            and request.template_id == "general_template"
            and count > 1
            and isinstance(context, dict)
            and context.get("variation_execution_contract_required") is True
            and isinstance(raw_variation_contract, dict)
        ):
            try:
                candidate_contract = VariationExecutionContract.model_validate(raw_variation_contract)
            except Exception:
                candidate_contract = None
            if (
                candidate_contract is not None
                and candidate_contract.contract_digest
                == candidate_contract.computed_digest()
                and candidate_contract.requested_image_count == count
                and isinstance(frozen_variation_binding, dict)
                and frozen_variation_binding.get("contract_version") == candidate_contract.contract_version
                and frozen_variation_binding.get("contract_digest") == candidate_contract.contract_digest
            ):
                variation_contract = candidate_contract
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
                and anchor_torso_scope == "visible_neck_collar_and_upper_shoulders"
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
                == "standard_front_model_card_view"
                and anchor_face_axis_alignment
                == "camera_facing_front_model_card_view"
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
                "Photographer-shot standard-front model-card portrait on a clean white background; "
                "same person, complete hair outline, small natural headroom, visible neck, collar and upper shoulders, "
                "consistent photographer distance, mature commercial photo finish."
            ),
            "three_quarter": (
                "Photographer-shot left-front 45-degree model-card portrait on a clean white background; "
                "same person, complete hair outline, small natural headroom, visible neck, collar and upper shoulders, "
                "consistent photographer distance, mature commercial photo finish."
            ),
            "profile": (
                "Photographer-shot side-profile 90-degree model-card portrait on a clean white background; "
                "same person, complete hair outline, small natural headroom, visible neck, collar and upper shoulders, "
                "consistent photographer distance, mature commercial photo finish."
            ),
            "reverse_three_quarter": (
                "Photographer-shot right-front 45-degree model-card portrait on a clean white background; "
                "same person, complete hair outline, small natural headroom, visible neck, collar and upper shoulders, "
                "consistent photographer distance, mature commercial photo finish."
            ),
            "rear_head": (
                "Photographer-shot rear-head model-card portrait on a clean white background; "
                "same person hair and head shape, complete hair outline, small natural headroom, visible neck, collar and upper shoulders, "
                "consistent photographer distance, mature commercial photo finish."
            ),
        }.get(anchor_view_target)
        expression_slot_prompt = {
            "laugh": (
                "Reference-led Character Card expression.laugh portrait of the same person, "
                "clearly readable joyful laugh keyframe with eye-cheek-jaw participation, clean white reference-card framing."
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
                        f"{request.user_input} Remote Brain approved complete product image {index}: preserve the supplied product facts, "
                        "reference truth, and explicit user constraints in one coherent photographic image."
                    )
                ),
                "review_status": "approved",
                **(
                    {
                        "variation_execution_receipt": {
                            "contract_version": variation_contract.contract_version,
                            "contract_digest": variation_contract.contract_digest,
                            "output_index": index,
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if variation_contract is not None
                    else {}
                ),
                **(
                    {
                        "user_direction_integrity": {
                            "contract_version": "v3_user_direction_integrity_v1",
                            "status": "preserved",
                            "owner": "remote_v3_llm_brain",
                        }
                    }
                    if request.metadata.get("require_lossless_user_direction") is True
                    else {}
                ),
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


def _ecommerce_output_contract(request, count: int) -> list[dict]:
    pose_contract_by_output = _professional_ecommerce_pose_contract_by_output(request)
    product_truth_ids = _product_truth_asset_ids(request)
    requires_product_truth_selection = bool(
        isinstance(request.metadata, dict)
        and request.metadata.get("professional_product_truth_required")
    )
    requires_body_proportion_receipt = bool(
        isinstance(request.metadata, dict)
        and request.metadata.get("professional_body_proportion_receipt_required")
    )
    if (
        not requires_product_truth_selection
        and not requires_body_proportion_receipt
        and not pose_contract_by_output
    ):
        return []
    entries = []
    for index in range(1, count + 1):
        entry = {"output_index": index, "evidence_dimensions": []}
        if requires_product_truth_selection and product_truth_ids:
            entry["product_truth_selection_role"] = _product_truth_selection_role(index)
            entry["selected_product_truth_asset_ids"] = [
                product_truth_ids[(index - 1) % len(product_truth_ids)]
            ]
        if requires_body_proportion_receipt:
            entry["professional_body_proportion_requirement"] = "not_required"
        pose_contract = pose_contract_by_output.get(index)
        if pose_contract:
            entry["professional_ecommerce_pose_role"] = pose_contract.get("pose_role")
            entry["standing_pose_requirements"] = list(
                pose_contract.get("standing_requirements") or []
            )
            entry["standing_presentation_requirements"] = list(
                pose_contract.get("standing_presentation_requirements") or []
            )
        entries.append(entry)
    return entries


def _professional_ecommerce_pose_contract_by_output(request) -> dict[int, dict]:  # noqa: ANN001
    context = request.metadata.get("ecommerce_creative_context") if isinstance(request.metadata, dict) else None
    contract = (
        context.get("professional_ecommerce_pose_contract")
        if isinstance(context, dict)
        else None
    )
    if not isinstance(contract, dict):
        return {}
    entries = contract.get("required_pose_by_output")
    if not isinstance(entries, list):
        return {}
    resolved: dict[int, dict] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        index = item.get("output_index")
        if type(index) is not int:
            continue
        resolved[index] = item
    return resolved


def _product_truth_selection_role(index: int) -> str:
    roles = [
        "lifestyle_primary_product_view",
        "playful_environment_interaction_view",
        "walking_or_lookback_view",
        "back_or_structure_view",
        "product_detail_or_print_view",
        "playful_environment_interaction_view",
    ]
    return roles[(index - 1) % len(roles)]


def _product_truth_asset_ids(request) -> list[str]:  # noqa: ANN001
    ids: list[str] = []
    for item in request.uploaded_assets:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        channel = str(metadata.get("codex_native_reference_channel") or "").strip()
        role = str(item.get("role") or "").strip()
        if channel == "product_truth" or role == "product_reference":
            asset_id = str(item.get("asset_id") or "").strip()
            if asset_id:
                ids.append(asset_id)
    return list(dict.fromkeys(ids))


def ecommerce_test_service(
    *,
    brain_provider: EcommerceRemoteBrainTestProvider | None = None,
    **service_kwargs,
) -> V3ProductApiService:
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=brain_provider or EcommerceRemoteBrainTestProvider())
    )
    return V3ProductApiService(scenario_runtime=runtime, **service_kwargs)
