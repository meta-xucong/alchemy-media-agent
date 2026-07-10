"""Doc86 portrait bone-structure identity layer."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    BoneStructureRetryPatch,
    PortraitBoneStructureLock,
    PortraitIdentityStyleSeparationReview,
    PortraitIdentitySimilarityReview,
    PortraitReferenceBalancePolicy,
    PortraitReferenceBalanceRetryPatch,
    PortraitReferenceBalanceReview,
    PortraitReferenceInfluencePolicy,
    ReferenceOverinheritanceRetryPatch,
    ResolvedReferencePolicyPackage,
    StrongReferenceBinding,
    StylingDeltaPolicy,
    SubjectIdentityCard,
)


DOC86_IDENTITY_ISSUE_CODES = {
    "bone_structure_drift",
    "face_shape_drift",
    "cheek_jaw_chin_drift",
    "eye_shape_or_spacing_identity_drift",
    "eyebrow_eye_relationship_drift",
    "nose_mouth_relationship_identity_drift",
    "lip_contour_identity_drift",
    "age_impression_drift",
    "styling_changed_face_geometry",
    "archetype_overrode_reference_identity",
    "same_type_not_same_person",
    "identity_reference_underweighted",
}

DOC87_REFERENCE_BOUNDARY_ISSUE_CODES = {
    "source_lighting_overinherited",
    "source_color_temperature_overinherited",
    "source_scene_overinherited",
    "source_wardrobe_overinherited",
    "source_camera_mood_overinherited",
    "reference_used_as_style_when_identity_only",
    "prompt_style_underweighted",
    "makeup_changed_face_geometry",
    "hair_change_replaced_identity",
    "retry_repaired_artifact_but_changed_identity",
    "source_hair_overinherited",
    "source_makeup_overinherited",
    "source_color_grade_overinherited",
    "source_camera_overinherited",
    "source_whole_style_overinherited",
    "prompt_owned_channel_ignored",
    "selected_anchor_overrode_current_prompt",
    "structured_appearance_lock_misapplied",
}

DOC88_REFERENCE_BALANCE_ISSUE_CODES = {
    "prompt_mood_regression",
    "prompt_color_tone_regression",
    "approved_style_anchor_ignored",
    "identity_repair_damaged_prompt_direction",
    "overconstrained_identity_prompt",
    "scenario_specific_negative_overfit",
}


class PortraitBoneStructureIdentityLayer:
    """Build Doc86 identity locks, style-delta policies, and retry patches."""

    def build_lock(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        subject_identity_card: SubjectIdentityCard | None,
        strong_bindings: list[StrongReferenceBinding],
    ) -> PortraitBoneStructureLock | None:
        if subject_type != "character" or subject_identity_card is None or not subject_identity_card.applies:
            return None
        identity_bindings = [binding for binding in strong_bindings if binding.use_policy == "identity"]
        if not identity_bindings and subject_identity_card.source_priority in {"none", "planned_first_output_anchor"}:
            return None

        primary = _primary_identity_binding(identity_bindings)
        source_reference_id = primary.source_id if primary else None
        source_asset_id = primary.asset_id if primary and primary.asset_id else _first(subject_identity_card.source_asset_ids)
        source_output_id = primary.output_id if primary and primary.output_id else _first(subject_identity_card.source_output_ids)
        uploaded_truth = bool(primary and primary.source_type != "selected_output")

        stable_bone_traits = [
            "face width/length ratio",
            "forehead-to-midface-to-lower-face proportion",
            "cheek volume and cheekbone direction",
            "jaw width, jawline slope, and chin scale",
            "temple-cheek-jaw contour and original facial outline width",
            "natural age impression",
            "overall facial bone-structure family",
        ]
        stable_feature_relationships = [
            "eye spacing and base eye shape",
            "eye size family without beauty-filter enlargement",
            "eyelid direction and brow-eye relationship",
            "eyebrow base shape, thickness family, and visual temperament",
            "nose bridge, nose tip, nose wing, and mouth relationship",
            "mouth scale relative to nose, chin, and face width",
            "philtrum, mouth width, lip contour, and lip fullness family",
            "midface temperament",
        ]
        forbidden_geometry_drift = [
            "face slimming or V-shaped jaw replacement",
            "narrower, sharper, or longer target-style template face",
            "eye enlargement or eye-spacing drift",
            "nose reshaping",
            "smaller-mouth beauty-template replacement",
            "lip reshaping",
            "jaw or chin remodeling",
            "age-band shift",
            "generic beauty-face replacement",
            "same beauty type but different person",
            "scenario-specific beauty archetype face replacing the reference identity",
        ]
        allowed_surface_changes = [
            "makeup color and intensity",
            "hair styling, hair movement, and accessories when requested or required by target style",
            "wardrobe or costume according to the prompt unless the wardrobe is explicitly the reference truth",
            "lighting, color grade, and atmosphere according to the current prompt",
            "expression, gaze, pose, and head angle",
            "scene, lens, crop, and camera treatment according to the current prompt",
        ]
        prompt_rules = [
            "Portrait identity contract: use the reference as the same person's identity source before applying style or beauty words.",
            "Doc87 reference boundary: identity comes from the reference; direction comes from the current prompt.",
            "Preserve underlying bone structure and facial-feature relationships from the reference; same archetype is not enough.",
            "Do not copy the reference image's original lighting, color temperature, scene, wardrobe, camera mood, or whole-image style unless the user explicitly asks for style guidance.",
            "Treat makeup, wardrobe, hairstyle, lighting, pose, expression, and scene as prompt-owned styling channels that must not redesign the face.",
            "Do not reshape face, eyes, nose, mouth, jaw, chin, or age impression to fit a generic beauty archetype.",
            "Do not make the reference person more narrow-faced, pointed-chinned, larger-eyed, or smaller-mouthed to fit any scenario-specific beauty template.",
            "The result must still be readable as the uploaded person after makeup, costume, lighting, and scene change; same archetype is not enough.",
            "If the prompt asks for any portrait styling change, apply it to costume, makeup, hair, light, scene, mood, camera, and atmosphere without redesigning the face.",
        ]
        review_checks = [
            "ignore allowed makeup, wardrobe, lighting, expression, pose, camera, and scene changes",
            "judge whether the underlying face bone structure still reads as the same person",
            "penalize same-type-not-same-person outputs even when commercial beauty is high",
            "fail identity when eye/nose/mouth/jaw/chin relationships are remodeled by style words",
            "fail style-boundary review when source lighting, source color, source scene, or source camera mood overrides the prompt",
        ]
        return PortraitBoneStructureLock(
            lock_id=stable_id("portrait_bone_structure_lock", project_id, job_id, source_asset_id, source_output_id),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            source_reference_id=source_reference_id,
            source_asset_id=source_asset_id,
            source_output_id=source_output_id,
            priority="hard" if uploaded_truth else "medium",
            stable_bone_traits=stable_bone_traits,
            stable_feature_relationships=stable_feature_relationships,
            forbidden_geometry_drift=forbidden_geometry_drift,
            allowed_surface_changes=allowed_surface_changes,
            prompt_rules=prompt_rules,
            review_checks=review_checks,
            user_visible_summary=[
                "V3 will keep the same face structure.",
                "Styling, light, pose, and clothing may change.",
            ],
            metadata={
                "doc": "86",
                "extends": ["87"],
                "uploaded_truth_source": uploaded_truth,
                "subject_identity_card_id": subject_identity_card.card_id,
                "source_priority": subject_identity_card.source_priority,
            },
        )

    def build_styling_policy(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        lock: PortraitBoneStructureLock | None,
    ) -> StylingDeltaPolicy | None:
        if lock is None or not lock.applies:
            return None
        allowed = list(lock.allowed_surface_changes)
        disallowed = [
            "face slimming",
            "eye enlargement",
            "nose reshaping",
            "lip reshaping",
            "jaw/chin remodeling",
            "age-band shift",
            "generic beauty-face replacement",
        ]
        prompt_rules = [
            "Styling delta policy: requested style changes are surface-level changes only.",
            "A requested styling change is allowed; changing facial geometry is not.",
            "Any portrait style request is surface-level unless the user explicitly asks to change identity.",
            "Target-style, premium, delicate, or beautiful style words must not override the reference person's bone structure.",
            "Source-reference lighting, source color temperature, source scene, and source camera mood are not inherited unless explicitly requested.",
        ]
        return StylingDeltaPolicy(
            policy_id=stable_id("styling_delta_policy", project_id, job_id, lock.lock_id, user_input),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            allowed_changes=allowed,
            disallowed_identity_changes=disallowed,
            style_prompt_scope="surface_only",
            prompt_rules=prompt_rules,
            user_visible_summary=["V3 can change styling without changing the person."],
            metadata={"doc": "86", "extends": ["87"], "portrait_bone_structure_lock_id": lock.lock_id},
        )

    def build_reference_influence_policy(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        lock: PortraitBoneStructureLock | None,
        styling_policy: StylingDeltaPolicy | None,
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> PortraitReferenceInfluencePolicy | None:
        if lock is None or not lock.applies:
            return None
        channel_policy = next(
            (
                policy
                for policy in (reference_policy_package.policies if reference_policy_package else [])
                if policy.source_role == "portrait_identity_reference"
            ),
            None,
        )
        inherited = [
            "bone structure",
            "facial-feature relationships",
            "temple-cheek-jaw contour, cheek fullness, and face width/length direction",
            "base eye size/spacing and mouth scale relative to the face",
            "natural age impression",
            "distinctive identity marks when visible",
        ]
        if channel_policy and channel_policy.hair_direction in {"hard", "medium", "soft"}:
            inherited.append(f"hair direction at {channel_policy.hair_direction} strength")
        blocked = [
            "source lighting",
            "source color temperature",
            "source scene",
            "source camera mood",
            "source wardrobe unless explicitly marked as wardrobe truth",
            "whole-image style template",
            "beauty-camera bias",
            "scenario-specific archetype face",
            "face-slimming, V-chin, enlarged-eye, or smaller-mouth beauty filter",
        ]
        prompt_owned = (
            _dedupe(
                [
                    *channel_policy.prompt_owned_channels,
                    "makeup",
                    "wardrobe",
                    "lighting",
                    "color grade",
                    "scene",
                    "mood",
                    "camera",
                    "composition",
                    "art direction",
                ]
            )
            if channel_policy
            else [
                "makeup_style",
                "wardrobe_structure",
                "lighting_color",
                "scene_background",
                "mood_art_direction",
                "camera_composition",
                "style_finish",
            ]
        )
        prompt_rules = [
            "Reference inheritance boundary: Identity comes from the reference; direction comes from the prompt.",
            "Use the uploaded portrait as identity truth by default, not style truth.",
            "Do not copy the reference image's original lighting, color temperature, scene, wardrobe, camera mood, or whole-image style unless the user explicitly asks for style guidance.",
            "Follow the current prompt for lighting, color grade, scene, mood, camera, composition, wardrobe, and art direction.",
            "Preserve the same person's face geometry while allowing prompt-directed styling changes.",
            "Beautiful, delicate, premium, or target-style words may polish makeup and atmosphere, but they must not remodel the reference person's facial outline or feature scale.",
            "Hair is medium-preserve: keep broad direction and distinctive marks unless the prompt or template asks for a change.",
        ]
        if reference_policy_package and reference_policy_package.applies:
            prompt_rules = list(reference_policy_package.provider_prompt_rules)
            blocked = _dedupe(
                [
                    *blocked,
                    *(channel_policy.blocked_inheritance_channels if channel_policy else []),
                ]
            )
        if styling_policy and styling_policy.applies:
            prompt_rules.extend(styling_policy.prompt_rules[-2:])
        review_checks = [
            "identity source is preserved as the same person",
            "prompt lighting/color/scene/camera direction is followed",
            "source lighting/color/scene/camera mood does not override the prompt",
            "artifact or watermark cleanup does not replace the face",
            "beautiful output still fails if it is only the same beauty type",
        ]
        return PortraitReferenceInfluencePolicy(
            policy_id=stable_id("portrait_reference_influence_policy", project_id, job_id, lock.lock_id),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            identity_truth_strength=lock.priority if lock.priority == "hard" else "medium",
            makeup_style_strength="prompt_controlled",
            hair_strength=(channel_policy.hair_direction if channel_policy else "soft"),
            wardrobe_structure_strength="prompt_controlled",
            lighting_color_scene_strength="prompt_owned",
            camera_composition_strength="prompt_owned",
            inherited_reference_channels=inherited,
            blocked_reference_channels=blocked,
            prompt_owned_channels=prompt_owned,
            prompt_rules=_dedupe(prompt_rules),
            review_checks=review_checks,
            user_visible_summary=[
                "V3 will keep the person, not copy the old photo style.",
                "Lighting and scene follow your current request.",
            ],
            metadata={
                "doc": "87",
                "portrait_bone_structure_lock_id": lock.lock_id,
                "ordinary_portrait_reference_defaults_to_identity_truth": True,
                "doc93_reference_channel_policy": bool(reference_policy_package and reference_policy_package.applies),
                "reference_policy_package_id": reference_policy_package.package_id if reference_policy_package else None,
            },
        )

    def build_reference_balance_policy(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        selected_outputs: list[dict[str, Any]],
        lock: PortraitBoneStructureLock | None,
        reference_policy: PortraitReferenceInfluencePolicy | None,
    ) -> PortraitReferenceBalancePolicy | None:
        if lock is None or not lock.applies or reference_policy is None or not reference_policy.applies:
            return None

        approved_ids = _dedupe(
            _identity(item, "output_id", "asset_id", "candidate_id") for item in selected_outputs
        )
        current_prompt_truth_rules = [
            "Doc88 prompt truth: the current request controls this image's mood, color, light, scene, camera, composition, and art direction.",
            "Do not let identity repair flatten, warm-shift, darken, simplify, or otherwise damage the current prompt's intended atmosphere.",
            "If the prompt asks for a new visual direction, follow that direction while keeping the uploaded person recognizable.",
        ]
        uploaded_identity_truth_rules = [
            "Doc88 identity truth: uploaded portrait references preserve recognizable same-person identity, not the whole old photo.",
            "Use compact identity guidance: preserve face structure and feature relationships without overloading the prompt with scenario-specific negative words.",
            "Identity repair must keep the person inside the intended current atmosphere, not turn the task into a face-repair-only frame.",
        ]
        approved_visual_anchor_rules = [
            "Doc88 approved visual anchor: user-selected generated outputs may preserve positive color, lighting, composition, craft, and subject direction.",
            "Selected generated outputs are positive visual direction anchors, not replacements for uploaded portrait identity truth.",
            "Use approved outputs only when they do not conflict with the current prompt's requested mood, scene, or art direction.",
        ]
        if not approved_ids:
            approved_visual_anchor_rules.append(
                "No selected generated output is confirmed; do not use unselected or failed candidates as positive visual anchors."
            )
        prompt_ordering_rules = [
            "Provider prompt order: current prompt mood and art direction first.",
            "Then add uploaded same-person identity truth.",
            "Then add approved visual anchor guidance when available.",
            "Keep negative guidance compact and generic; do not paste scenario-specific examples into universal foundation prompts.",
        ]
        compact_negative_guidance = [
            "generic stylized template face",
            "scenario-specific beauty template face",
            "identity repair that damages prompt mood",
            "copied source-photo lighting when not requested",
            "approved visual direction ignored",
            "overloaded identity negatives",
        ]
        stop_conditions = [
            "stop automatic visual retry if the same balance issue repeats",
            "stop if repairing identity repeatedly damages the prompt's intended mood",
            "stop if the prompt direction and selected visual anchor conflict and no user choice resolves it",
        ]
        return PortraitReferenceBalancePolicy(
            policy_id=stable_id("portrait_reference_balance_policy", project_id, job_id, lock.lock_id, ",".join(approved_ids), user_input),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            current_prompt_truth_rules=current_prompt_truth_rules,
            uploaded_identity_truth_rules=uploaded_identity_truth_rules,
            approved_visual_anchor_rules=approved_visual_anchor_rules,
            prompt_ordering_rules=prompt_ordering_rules,
            compact_negative_guidance=compact_negative_guidance,
            stop_conditions=stop_conditions,
            user_visible_summary=[
                "V3 will keep the person while preserving this request's atmosphere.",
                "Selected good results can guide style without replacing identity.",
            ],
            metadata={
                "doc": "88",
                "extends": ["86", "87"],
                "portrait_bone_structure_lock_id": lock.lock_id,
                "portrait_reference_influence_policy_id": reference_policy.policy_id,
                "approved_visual_anchor_output_ids": approved_ids,
                "selected_output_count": len(selected_outputs),
                "user_input_digest": str(user_input or "")[:240],
            },
        )

    def build_balance_review(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        output_id: str | None,
        balance_policy: PortraitReferenceBalancePolicy | None,
        issue_codes: list[str],
        confidence: float = 0.9,
    ) -> PortraitReferenceBalanceReview | None:
        if balance_policy is None or not balance_policy.applies:
            return None
        relevant = [code for code in _dedupe(issue_codes) if code in DOC88_REFERENCE_BALANCE_ISSUE_CODES]
        if not relevant:
            return PortraitReferenceBalanceReview(
                review_id=stable_id("portrait_reference_balance_review", project_id, job_id, output_id, balance_policy.policy_id, "pass"),
                project_id=project_id,
                job_id=job_id,
                output_id=output_id,
                status="pass",
                prompt_mood_preservation_score=88,
                approved_anchor_obedience_score=86 if balance_policy.metadata.get("approved_visual_anchor_output_ids") else None,
                identity_prompt_balance_score=88,
                user_visible_summary=["V3 checked that identity, direction, and atmosphere stay balanced."],
                metadata={"doc": "88", "confidence": confidence, "policy_id": balance_policy.policy_id},
            )
        patch = self.build_balance_retry_patch(
            project_id=project_id,
            job_id=job_id,
            balance_policy=balance_policy,
            reason_codes=relevant,
        )
        return PortraitReferenceBalanceReview(
            review_id=stable_id("portrait_reference_balance_review", project_id, job_id, output_id, balance_policy.policy_id, ",".join(relevant)),
            project_id=project_id,
            job_id=job_id,
            output_id=output_id,
            status="fail_retryable" if confidence >= 0.65 else "manual_review",
            prompt_mood_preservation_score=58 if any(code in relevant for code in {"prompt_mood_regression", "prompt_color_tone_regression", "identity_repair_damaged_prompt_direction"}) else 78,
            approved_anchor_obedience_score=60 if "approved_style_anchor_ignored" in relevant else 82,
            identity_prompt_balance_score=56 if "overconstrained_identity_prompt" in relevant else 76,
            issue_codes=relevant,
            retry_patch=patch.model_dump(mode="json") if patch.applies and confidence >= 0.65 else {},
            user_visible_summary=["The person or style direction needs a more balanced retry."],
            metadata={"doc": "88", "confidence": confidence, "policy_id": balance_policy.policy_id},
        )

    def build_balance_retry_patch(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        balance_policy: PortraitReferenceBalancePolicy,
        reason_codes: list[str],
    ) -> PortraitReferenceBalanceRetryPatch:
        reasons = _dedupe(reason_codes)
        prompt_additions: list[str] = [
            "Doc88 balance repair: preserve the current prompt's requested mood, color, light, scene, camera, composition, and art direction while keeping the uploaded portrait identity recognizable.",
            "Use uploaded portrait references as identity truth, not as a whole-photo tone or scene template.",
            "Use user-approved generated outputs only as positive visual direction anchors when they do not conflict with the current prompt.",
        ]
        negative_additions = [
            "prompt mood regression",
            "prompt color or lighting regression",
            "identity repair that damages the requested atmosphere",
            "approved visual direction ignored",
            "overloaded identity negative prompt",
            "scenario-specific template face",
        ]
        identity_reinforcement = [
            "same person inside the current prompt's atmosphere",
            "identity, approved direction, and prompt mood must all survive the retry",
        ]
        shorten = False
        if "overconstrained_identity_prompt" in reasons or "scenario_specific_negative_overfit" in reasons:
            prompt_additions.append(
                "Shorten identity guidance to compact same-person face structure and feature-relationship rules; remove scenario-specific archetype negatives."
            )
            negative_additions.append("long scenario-specific identity negative list")
            shorten = True
        if "prompt_mood_regression" in reasons or "prompt_color_tone_regression" in reasons:
            prompt_additions.append("Restore the current prompt's color palette, lighting direction, scene atmosphere, and emotional tone.")
        if "approved_style_anchor_ignored" in reasons:
            prompt_additions.append("Re-apply the selected output's positive craft, composition, color, and subject direction without replacing uploaded identity truth.")
        if "identity_repair_damaged_prompt_direction" in reasons:
            prompt_additions.append("Repair identity without simplifying composition, changing the requested scene, or flattening the visual mood.")
        return PortraitReferenceBalanceRetryPatch(
            patch_id=stable_id("portrait_reference_balance_retry_patch", project_id, job_id, ",".join(reasons), balance_policy.policy_id),
            project_id=project_id,
            job_id=job_id,
            applies=bool(reasons),
            reason_codes=reasons,
            prompt_additions=_dedupe(prompt_additions),
            negative_additions=_dedupe(negative_additions),
            identity_reinforcement=_dedupe(identity_reinforcement),
            preserve_prompt_mood=True,
            preserve_approved_visual_anchor=bool(balance_policy.metadata.get("approved_visual_anchor_output_ids")),
            shorten_overconstrained_identity_guidance=shorten,
            metadata={"doc": "88", "portrait_reference_balance_policy_id": balance_policy.policy_id},
        )

    def build_review(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        output_id: str | None,
        lock: PortraitBoneStructureLock | None,
        styling_policy: StylingDeltaPolicy | None,
        issue_codes: list[str],
        confidence: float = 0.9,
    ) -> PortraitIdentitySimilarityReview | None:
        if lock is None or not lock.applies:
            return None
        relevant = [code for code in _dedupe(issue_codes) if code in DOC86_IDENTITY_ISSUE_CODES]
        if not relevant:
            return PortraitIdentitySimilarityReview(
                review_id=stable_id("portrait_identity_similarity_review", project_id, job_id, output_id, lock.lock_id, "pass"),
                project_id=project_id,
                job_id=job_id,
                output_id=output_id,
                reference_asset_id=lock.source_asset_id,
                status="pass",
                bone_structure_identity_score=88,
                facial_feature_relationship_score=88,
                styling_delta_correctness_score=90,
                same_person_readability_score=88,
                beauty_realism_score=86,
                allowed_difference_notes=list(lock.allowed_surface_changes[:5]),
                user_visible_summary=["V3 checked face-structure continuity."],
                metadata={"doc": "86", "confidence": confidence, "lock_id": lock.lock_id},
            )
        patch = self.build_retry_patch(
            project_id=project_id,
            job_id=job_id,
            lock=lock,
            styling_policy=styling_policy,
            reason_codes=relevant,
        )
        return PortraitIdentitySimilarityReview(
            review_id=stable_id("portrait_identity_similarity_review", project_id, job_id, output_id, lock.lock_id, ",".join(relevant)),
            project_id=project_id,
            job_id=job_id,
            output_id=output_id,
            reference_asset_id=lock.source_asset_id,
            status="fail_retryable" if confidence >= 0.65 else "manual_review",
            bone_structure_identity_score=62,
            facial_feature_relationship_score=64,
            styling_delta_correctness_score=80,
            same_person_readability_score=64,
            beauty_realism_score=78,
            issue_codes=relevant,
            allowed_difference_notes=list(lock.allowed_surface_changes[:5]),
            forbidden_drift_notes=list(lock.forbidden_geometry_drift[:8]),
            retry_patch=patch.model_dump(mode="json") if patch.applies and confidence >= 0.65 else {},
            user_visible_summary=[
                "The image looked good, but it did not keep the reference person's face closely enough.",
            ],
            metadata={"doc": "86", "confidence": confidence, "lock_id": lock.lock_id},
        )

    def build_style_separation_review(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        output_id: str | None,
        lock: PortraitBoneStructureLock | None,
        reference_policy: PortraitReferenceInfluencePolicy | None,
        issue_codes: list[str],
        confidence: float = 0.9,
    ) -> PortraitIdentityStyleSeparationReview | None:
        if lock is None or not lock.applies or reference_policy is None or not reference_policy.applies:
            return None
        relevant = [code for code in _dedupe(issue_codes) if code in DOC87_REFERENCE_BOUNDARY_ISSUE_CODES]
        if not relevant:
            return PortraitIdentityStyleSeparationReview(
                review_id=stable_id("portrait_identity_style_separation_review", project_id, job_id, output_id, lock.lock_id, "pass"),
                project_id=project_id,
                job_id=job_id,
                output_id=output_id,
                reference_asset_id=lock.source_asset_id,
                status="pass",
                prompt_style_obedience_score=88,
                lighting_color_scene_obedience_score=88,
                beauty_realism_score=86,
                reference_overinheritance_penalty=0,
                prompt_owned_pass_notes=list(reference_policy.prompt_owned_channels[:6]),
                reference_boundary_notes=list(reference_policy.blocked_reference_channels[:6]),
                user_visible_summary=["V3 checked that the new prompt controls style and scene."],
                metadata={"doc": "87", "confidence": confidence, "policy_id": reference_policy.policy_id},
            )
        patch = self.build_reference_overinheritance_retry_patch(
            project_id=project_id,
            job_id=job_id,
            lock=lock,
            reference_policy=reference_policy,
            reason_codes=relevant,
        )
        return PortraitIdentityStyleSeparationReview(
            review_id=stable_id("portrait_identity_style_separation_review", project_id, job_id, output_id, lock.lock_id, ",".join(relevant)),
            project_id=project_id,
            job_id=job_id,
            output_id=output_id,
            reference_asset_id=lock.source_asset_id,
            status="fail_retryable" if confidence >= 0.65 else "manual_review",
            prompt_style_obedience_score=64,
            lighting_color_scene_obedience_score=60,
            beauty_realism_score=78,
            reference_overinheritance_penalty=35,
            issue_codes=relevant,
            prompt_owned_pass_notes=list(reference_policy.prompt_owned_channels[:8]),
            reference_boundary_notes=list(reference_policy.blocked_reference_channels[:8]),
            retry_patch=patch.model_dump(mode="json") if patch.applies and confidence >= 0.65 else {},
            user_visible_summary=[
                "The face direction can stay, but the image copied too much of the old reference style.",
            ],
            metadata={"doc": "87", "confidence": confidence, "policy_id": reference_policy.policy_id},
        )

    def build_reference_overinheritance_retry_patch(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        lock: PortraitBoneStructureLock,
        reference_policy: PortraitReferenceInfluencePolicy,
        reason_codes: list[str],
    ) -> ReferenceOverinheritanceRetryPatch:
        prompt_additions = [
            "Doc87 reference-boundary repair: preserve the same person's face geometry from the portrait reference, but follow the current prompt for the image direction.",
            "Use the reference for identity only unless the user explicitly marked it as style guidance.",
            "do not copy source lighting, source color temperature, source scene, source wardrobe, source camera mood, or the original shoot style.",
            "Follow the current prompt's lighting, color grade, background, camera angle, mood, wardrobe, and art direction.",
            "When cleaning artifacts, preserve the same face; do not replace the person with a cleaner generic beauty face.",
            "Do not repair toward a narrower face, sharper chin, larger eyes, smaller mouth, or more generic scenario-specific beauty archetype.",
            "Doc88 balance: style-boundary repair must not damage the current prompt's requested tone, atmosphere, scene, or user-approved positive visual direction.",
        ]
        if lock.source_asset_id:
            prompt_additions.append(f"Use reference asset {lock.source_asset_id} as identity truth, not whole-image style truth.")
        negative_additions = [
            "copied source lighting",
            "copied source color temperature",
            "copied source scene",
            "copied source camera mood",
            "copied source wardrobe",
            "reference used as full style template",
            "prompt style ignored",
            "same type but different person after cleanup",
            "cleaner generic replacement face",
            "narrower target-style template face",
            "pointed scenario-specific beauty chin",
            "smaller-mouth beauty template",
        ]
        identity_reinforcement = [
            "preserve the same person's face geometry while changing prompt-owned style channels",
            "identity lock stays hard during style-boundary retry",
            "artifact repair must not change bone structure, eye spacing, nose-mouth relationship, jaw/chin direction, lip contour, or age impression",
            "style repair must keep face contour width, cheek fullness, base eye size, mouth scale, and lip family from the reference",
        ]
        return ReferenceOverinheritanceRetryPatch(
            patch_id=stable_id("reference_overinheritance_retry_patch", project_id, job_id, ",".join(reason_codes), lock.lock_id),
            project_id=project_id,
            job_id=job_id,
            applies=bool(reason_codes),
            reason_codes=_dedupe(reason_codes),
            prompt_additions=_dedupe(prompt_additions),
            negative_additions=_dedupe(negative_additions),
            identity_reinforcement=_dedupe(identity_reinforcement),
            preserve_identity_truth=True,
            block_source_style_channels=list(reference_policy.blocked_reference_channels[:8]),
            metadata={"doc": "87", "portrait_reference_influence_policy_id": reference_policy.policy_id},
        )

    def build_retry_patch(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        lock: PortraitBoneStructureLock,
        styling_policy: StylingDeltaPolicy | None,
        reason_codes: list[str],
    ) -> BoneStructureRetryPatch:
        prompt_additions = [
            "Doc86 same-person repair: regenerate as the same person from the portrait reference, not merely the same beauty type.",
            "Keep face width/length ratio, cheek volume, jawline slope, chin scale, eye spacing/base eye shape, eyebrow-eye relationship, nose-mouth relationship, lip contour, and age impression.",
            "Keep temple-cheek-jaw contour, face-outline width, base eye size, mouth scale relative to the face, and lip fullness family from the reference.",
            "Apply style only to makeup, wardrobe, hair styling, lighting, pose, expression, scene, and atmosphere.",
            "Reduce generic beauty archetype pressure; do not let target-style, delicate, or premium style words remodel the face.",
            "Preserve the current prompt's intended color, lighting, scene, composition, and atmosphere while repairing identity.",
            "A good-looking but narrower, sharper, smaller-mouthed, larger-eyed, or more template-like styled model is still an identity failure.",
        ]
        if lock.source_asset_id:
            prompt_additions.append(f"Use reference asset {lock.source_asset_id} as the face-geometry truth source.")
        negative_additions = [
            "same type but different person",
            "generic AI beauty replacement",
            "face slimming",
            "V-shaped jaw replacement",
            "narrower sharper style-template face",
            "eye enlargement",
            "eye spacing drift",
            "nose reshaping",
            "smaller mouth than the reference",
            "lip reshaping",
            "jaw or chin remodeling",
            "age impression drift",
            "style changed face geometry",
            "scenario-specific archetype replaced the reference person",
        ]
        identity_reinforcement = [
            "same person from the portrait reference; not merely the same beauty type",
            "bone structure beats styling: preserve facial geometry first, then apply makeup, costume, lighting, and mood",
            "same person under changed styling; not a similar-looking new model",
            "makeup and styling may change, but the viewer should recognize the original person's bone structure and feature scale",
        ]
        if styling_policy and styling_policy.applies:
            prompt_additions.extend(styling_policy.prompt_rules[:2])
        return BoneStructureRetryPatch(
            patch_id=stable_id("bone_structure_retry_patch", project_id, job_id, ",".join(reason_codes), lock.lock_id),
            project_id=project_id,
            job_id=job_id,
            applies=bool(reason_codes),
            reason_codes=_dedupe(reason_codes),
            prompt_additions=_dedupe(prompt_additions),
            negative_additions=_dedupe(negative_additions),
            identity_reinforcement=_dedupe(identity_reinforcement),
            reduce_style_pressure=True,
            reduce_archetype_language=True,
            require_reference_image=True,
            metadata={"doc": "86", "portrait_bone_structure_lock_id": lock.lock_id},
        )


def _primary_identity_binding(bindings: list[StrongReferenceBinding]) -> StrongReferenceBinding | None:
    if not bindings:
        return None
    for binding in bindings:
        if binding.source_type != "selected_output":
            return binding
    return bindings[0]


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def _identity(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
