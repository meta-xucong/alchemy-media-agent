"""M3 seam from explicit People Asset evidence to the shared frozen plan."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from ..shared_capabilities.activation.contracts import (
    ActivationEvidence,
    CapabilityActivationPlan,
    VisualTaskProfile,
)
from ..schemas.models import V3BaseModel
from .authority import (
    ReferenceAdmissionResolver,
    ReferenceAdmissionResult,
    ReferenceChannelPlan,
    ReferenceEvidencePacket,
    VisualAssetBindingSet,
)
from .contracts import ProfessionalModeBinding


class CanonicalProviderPromptReceipt(V3BaseModel):
    """Receipt for a complete Brain-signed prompt; prompt text is not stored here."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    prompt_hash: str
    signed_by: Literal["remote_v3_llm_brain", "local_adapter"]
    signature_valid: bool
    renderer_model: str = "gpt-image-2"

class ProfessionalModeRuntimeBridge:
    """Prepare typed planning evidence and validate the frozen handoff."""

    def resolve_reference_admissions(
        self,
        binding: ProfessionalModeBinding,
        plans: list[ReferenceChannelPlan],
    ) -> ReferenceAdmissionResult:
        """Validate Brain/shared-evidence reference plans before Provider use."""

        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        return ReferenceAdmissionResolver().resolve(binding_set, plans)

    @staticmethod
    def validate_reference_evidence_parity(packet: ReferenceEvidencePacket) -> None:
        """Require Provider and Reviewer to consume one identical evidence set."""

        if set(packet.provider_evidence_ids) != set(packet.reviewer_evidence_ids):
            raise ValueError("Provider and Reviewer evidence sets must be identical")

    def bind_task_profile(
        self,
        profile: VisualTaskProfile,
        binding: ProfessionalModeBinding,
    ) -> VisualTaskProfile:
        if profile.project_id not in {None, binding.project_id}:
            raise ValueError("Professional Mode binding project does not match task profile")
        if profile.job_id != binding.job_id:
            raise ValueError("Professional Mode binding job does not match task profile")
        evidence = ActivationEvidence(
            evidence_id=f"professional_people_asset:{binding.people_asset_id}:{binding.pack_version_id}",
            evidence_type="professional_people_asset_binding",
            source="visual_asset_library",
            value=binding.to_brain_evidence(),
            confidence=1.0,
            metadata={"identity_only": True},
        )
        controls = dict(profile.explicit_user_controls)
        controls.update(
            {
                "professional_mode_selected": True,
                "professional_mode_binding": binding.to_brain_evidence(),
            }
        )
        existing = [item for item in profile.evidence if item.evidence_id != evidence.evidence_id]
        return profile.model_copy(update={"explicit_user_controls": controls, "evidence": [*existing, evidence]})

    @staticmethod
    def _face_identity_quality_contract(*, neutral_capture: bool = False) -> dict[str, object]:
        contract: dict[str, object] = {
            "contract_version": "professional_face_identity_quality_v2",
            "scope": "face_identity_anchor_pack",
            "priority_order": [
                "same_person_likeness",
                "natural_human_presence",
                "age_fidelity",
                "camera_observed_skin_materiality",
                "prompt_owned_view_and_styling",
            ],
            "anti_overperfection_boundary": "reject_generic_perfect_beauty_surface",
            "developmental_age_coherence": "whole_person_when_age_owned",
            "owner": "remote_v3_llm_brain",
            "review_owner": "v3_shared_vision",
        }
        if neutral_capture:
            contract["capture_presentation"] = "neutral_identity_evidence_capture"
        return contract

    @staticmethod
    def _reference_led_slot_delta_contract(
        *,
        slot_delta_type: Literal["view_angle", "expression", "body_pose"],
    ) -> dict[str, object]:
        return {
            "contract_version": "v3_reference_led_slot_delta_decision_v1",
            "required": True,
            "materialization_mode": "reference_led_slot_delta",
            "stable_identity_source": "approved_character_card_reference",
            "prompt_scope": "slot_delta_only",
            "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
            "slot_delta_type": slot_delta_type,
            "owner": "remote_v3_llm_brain",
        }

    @staticmethod
    def _front_pose_normalization_contract() -> dict[str, object]:
        """Contract for the first reusable Character Card front view.

        A source photo can be slightly angled.  For a reusable Face Identity
        card, that source angle is evidence of identity only, not an owned
        viewpoint.  The first slot must establish a standard straight-on
        capture that later slots can depend on.
        """

        return {
            "contract_version": "v3_character_card_front_pose_normalization_v1",
            "required": True,
            "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
            "front_pose_normalization": "normalize_to_symmetric_camera_facing_front",
            "face_axis_alignment": "face_midline_vertical_eyes_level_nose_centered",
            "owner": "remote_v3_llm_brain",
        }

    @staticmethod
    def _face_identity_framing_contract() -> dict[str, object]:
        """Fixed framing for reusable Face Identity card views."""

        return {
            "contract_version": "v3_character_card_face_framing_standard_v1",
            "required": True,
            "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
            "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
            "torso_scope": "upper_shoulders_only_no_half_body_or_big_head_crop",
            "owner": "remote_v3_llm_brain",
        }

    @staticmethod
    def _face_card_image_clarity_contract() -> dict[str, object]:
        """Commercial cleanliness bar for reusable Face Identity card pixels."""

        return {
            "contract_version": "v3_character_card_commercial_clarity_v1",
            "required": True,
            "clarity_standard": "commercial_clean_translucent_no_smear_no_dirty_noise",
            "skin_materiality_boundary": "real_skin_texture_without_plastic_or_waxy_smoothing",
            "minimum_review_scores": {
                "visual_quality": 0.96,
                "technical_finish": 0.96,
                "human_realism": 0.92,
            },
            "owner": "shared_v3_visual_review",
        }

    @staticmethod
    def _face_card_evidence_capture_contract() -> dict[str, object]:
        """Objective for reusable identity-card captures.

        The first Character Card views are not beauty portraits.  They are
        standardized evidence images that later expression/body/product scenes
        must be able to rely on.  Keep this generic: the requested age, gender,
        complexion and identity remain owned by user intent and references.
        """

        return {
            "contract_version": "v3_character_card_face_evidence_capture_v1",
            "required": True,
            "capture_objective": "standardized_identity_evidence_capture_not_portfolio_or_beauty_portrait",
            "pose_observability": "balanced_ears_cheeks_shoulders_no_head_turn_or_tilt",
            "expression_standard": "stage_appropriate_relaxed_neutral_attention_not_model_performance",
            "materiality_standard": "camera_observed_skin_and_hair_detail_with_minor_real_variation",
            "complexion_semantics": "fair_or_cool_white_means_neutral_white_balance_not_skin_whitening",
            "background_standard": "plain_white_matte_reference_field_no_vignette_or_glamour_gradient",
            "aspect_ratio_standard": "honor_frozen_rendering_size_as_reference_card_aspect_ratio",
            "lens_standard": "low_distortion_portrait_lens_no_big_eye_or_beauty_perspective",
            "owner": "remote_v3_llm_brain",
            "review_owner": "v3_shared_vision",
        }

    @staticmethod
    def anchor_pack_preparation_metadata(
        *,
        view_role: Literal[
            "standard_front", "three_quarter", "profile", "reverse_three_quarter", "rear_head"
        ],
        capture_scope: Literal["anchor_pack", "character_card_face_identity"] = "anchor_pack",
    ) -> dict[str, object]:
        """Return the formal shared-planning context for pack preparation.

        Preparing the first pack cannot require an already-active binding.
        This helper carries only the non-secret quality and stage contracts;
        root provenance and candidate lineage remain owned by the injected
        preparation host and the shared execution path.
        """

        if capture_scope not in {"anchor_pack", "character_card_face_identity"}:
            raise ValueError("professional anchor capture scope is invalid")
        quality_contract = ProfessionalModeRuntimeBridge._face_identity_quality_contract(neutral_capture=True)
        if capture_scope == "character_card_face_identity":
            quality_contract = {
                **quality_contract,
                "scope": "character_card_face_identity",
                "geometry_scope": "face_and_head_only",
                "body_silhouette_contract": "not_applicable_until_body_silhouette_stage",
                "face_identity_framing_contract": (
                    ProfessionalModeRuntimeBridge._face_identity_framing_contract()
                ),
                "face_card_image_clarity_contract": (
                    ProfessionalModeRuntimeBridge._face_card_image_clarity_contract()
                ),
                "face_card_evidence_capture_contract": (
                    ProfessionalModeRuntimeBridge._face_card_evidence_capture_contract()
                ),
                **(
                    {
                        "front_pose_normalization_contract": (
                            ProfessionalModeRuntimeBridge._front_pose_normalization_contract()
                        )
                    }
                    if view_role == "standard_front"
                    else {}
                ),
            }
        return {
            "professional_mode": True,
            "professional_anchor_pack_preparation": True,
            "professional_reference_stage": view_role,
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_anchor_capture_scope": capture_scope,
            "creative_direction_owner": "remote_v3_llm_brain",
            "reference_channel_owner": "shared_v3_reference_policy",
            "professional_face_identity_quality_contract": quality_contract,
            **(
                {
                    "reference_led_slot_delta_contract": (
                        ProfessionalModeRuntimeBridge._reference_led_slot_delta_contract(
                            slot_delta_type="view_angle"
                        )
                    )
                }
                if capture_scope == "character_card_face_identity" and view_role != "standard_front"
                else {}
            ),
        }

    @staticmethod
    def character_card_stage_metadata(
        *,
        stage: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        source_class: str | None = None,
    ) -> dict[str, object]:
        """Return typed stage context while leaving creative wording to Brain."""

        if stage not in {"expression_set", "body_silhouette"} or not slot_key.strip():
            raise ValueError("character card stage metadata is invalid")
        quality_contract = ProfessionalModeRuntimeBridge._face_identity_quality_contract()
        quality_contract = {
            **quality_contract,
            "scope": f"character_card_{stage}",
            "face_identity_binding": "must_use_active_face_identity_module",
            "module_continuity": "derive_from_active_character_card_identity",
        }
        if stage == "expression_set":
            quality_contract["expression_contract"] = "preserve_identity_while_varying_expression_only"
        else:
            quality_contract["body_silhouette_contract"] = "preserve_identity_scale_and_age_appropriate_body_proportion"
        return {
            "contract_version": "professional_character_card_stage_v1",
            "stage": stage,
            "slot_key": slot_key.strip(),
            "source_class": source_class,
            "creative_direction_owner": "remote_v3_llm_brain",
            "reference_channel_owner": "shared_v3_reference_policy",
            "review_owner": "v3_shared_vision",
            "professional_face_identity_quality_contract": quality_contract,
            "reference_led_slot_delta_contract": (
                ProfessionalModeRuntimeBridge._reference_led_slot_delta_contract(
                    slot_delta_type="expression" if stage == "expression_set" else "body_pose"
                )
            ),
        }

    @staticmethod
    def planning_metadata(
        binding: ProfessionalModeBinding,
        *,
        canonical_prompt_hash: str | None = None,
        canonical_prompt_hashes: list[str] | None = None,
        reference_admissions: ReferenceAdmissionResult | None = None,
    ) -> dict[str, object]:
        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        metadata: dict[str, object] = {
            "professional_mode": True,
            "professional_mode_binding": binding.to_brain_evidence(),
            "asset_channel_authority_contract_version": binding_set.contract_version,
            "asset_channel_claims": binding_set.to_provenance()["claims"],
            "creative_direction_owner": "remote_v3_llm_brain",
            "reference_channel_owner": "shared_v3_reference_policy",
            # This is a semantic quality contract for the Face Identity
            # anchor-pack workflow, not renderer prose.  It makes the
            # professional identity objective explicit to the Brain while
            # keeping prompt authorship and pixel review in the shared path.
            "professional_face_identity_quality_contract": (
                ProfessionalModeRuntimeBridge._face_identity_quality_contract()
            ),
        }
        if canonical_prompt_hash is not None:
            if not canonical_prompt_hash.strip():
                raise ValueError("canonical prompt hash must be non-empty when supplied")
            metadata["canonical_prompt_hash"] = canonical_prompt_hash
        if canonical_prompt_hashes:
            if any(not str(item).strip() for item in canonical_prompt_hashes):
                raise ValueError("canonical prompt hashes must be non-empty")
            metadata["canonical_prompt_hashes"] = list(dict.fromkeys(str(item) for item in canonical_prompt_hashes))
        if reference_admissions is None:
            metadata.update(
                {
                    "reference_admission_contract_version": "visual_asset_reference_admission_v1",
                    "reference_admission_status": "not_requested",
                    "reference_evidence_packet_contract_version": "visual_asset_reference_evidence_packet_v1",
                    "admitted_evidence_ids": [],
                }
            )
        else:
            if reference_admissions.status != "admitted":
                raise ValueError("Professional Mode reference admission is blocked")
            metadata.update(reference_admissions.to_provenance())
        return metadata

    def validate_frozen_plan(
        self,
        plan: CapabilityActivationPlan,
        binding: ProfessionalModeBinding,
        prompt_receipt: CanonicalProviderPromptReceipt | list[CanonicalProviderPromptReceipt],
    ) -> None:
        if plan.activation_mode != "enforced":
            raise ValueError("Professional Mode requires an enforced frozen capability plan")
        if plan.fallback_used:
            raise ValueError("Professional Mode cannot use a local or legacy activation fallback")
        if plan.job_id != binding.job_id or plan.project_id != binding.project_id:
            raise ValueError("Professional Mode frozen plan binding job/project mismatch")
        if not plan.is_active("portrait_identity"):
            raise ValueError("Professional Mode frozen plan must activate portrait_identity")
        if plan.metadata.get("professional_mode") is not True:
            raise ValueError("Professional Mode binding was not frozen before planning")
        if plan.metadata.get("professional_mode_binding") != binding.to_brain_evidence():
            raise ValueError("Professional Mode frozen plan binding does not match selected asset")
        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        if plan.metadata.get("asset_channel_authority_contract_version") != binding_set.contract_version:
            raise ValueError("Professional Mode asset authority contract is missing or unsupported")
        if plan.metadata.get("asset_channel_claims") != binding_set.to_provenance()["claims"]:
            raise ValueError("Professional Mode asset channel claims do not match selected asset")
        if plan.metadata.get("reference_evidence_packet_contract_version") != (
            "visual_asset_reference_evidence_packet_v1"
        ):
            raise ValueError("Professional Mode reference evidence packet contract is missing or unsupported")
        admission_status = str(plan.metadata.get("reference_admission_status") or "not_requested")
        if admission_status == "blocked":
            raise ValueError("Professional Mode frozen plan contains blocked reference admission")
        if admission_status not in {"admitted", "not_requested"}:
            raise ValueError("Professional Mode reference admission is incomplete")
        expected_hashes = [
            str(item).strip()
            for item in plan.metadata.get("canonical_prompt_hashes", [])
            if str(item).strip()
        ]
        if not expected_hashes:
            singular_hash = str(plan.metadata.get("canonical_prompt_hash") or "").strip()
            if singular_hash:
                expected_hashes = [singular_hash]
        receipts = prompt_receipt if isinstance(prompt_receipt, list) else [prompt_receipt]
        actual_hashes = [item.prompt_hash for item in receipts]
        if not expected_hashes or actual_hashes != expected_hashes:
            raise ValueError("canonical prompt hash is missing or mismatched")
        if any(item.signed_by != "remote_v3_llm_brain" or not item.signature_valid for item in receipts):
            raise ValueError("canonical prompt must be signed by the Remote Brain")
        if plan.metadata.get("human_realism_required") is True and not plan.is_active("human_realism"):
            raise ValueError("Professional Mode Human Realism activation is missing")
