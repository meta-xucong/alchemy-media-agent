"""Doc66 selected-reference closure and mode quality profiles."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    HumanPhotorealismGuidance,
    ModeQualityProfile,
    ProjectIdentityAnchor,
    ResolvedReferencePolicyPackage,
    StrongReferenceClosurePackage,
    StrongReferenceContinuationPlan,
    VisualIdentityLockProfile,
)


STRONG_REFERENCE_CLOSURE_MODULE_ID = "strong_reference_closure"
MODE_QUALITY_PROFILE_MODULE_ID = "mode_quality_profile"


class StrongReferenceClosureBuilder:
    """Summarize selected references into one provider/review continuation contract."""

    module_id = STRONG_REFERENCE_CLOSURE_MODULE_ID

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        continuation_plan: StrongReferenceContinuationPlan | None,
        anchors: list[ProjectIdentityAnchor],
        identity_locks: list[VisualIdentityLockProfile],
        human_photorealism: HumanPhotorealismGuidance | None,
        reference_policy_package: ResolvedReferencePolicyPackage | None = None,
    ) -> StrongReferenceClosurePackage:
        provider_ids = _dedupe(continuation_plan.provider_required_reference_ids if continuation_plan else [])
        prompt_only_ids = _dedupe(continuation_plan.prompt_only_reference_ids if continuation_plan else [])
        lock_targets = _dedupe(continuation_plan.lock_targets if continuation_plan else [])
        active = bool(provider_ids or prompt_only_ids or anchors)
        reference_strength = "hard" if provider_ids else "prompt_only" if prompt_only_ids or anchors else "none"
        policy_active = bool(reference_policy_package and reference_policy_package.applies)
        identity_keep_rules = _dedupe(
            [
                *[rule for lock in identity_locks for rule in lock.keep_rules],
                *[rule for lock in identity_locks for rule in lock.prompt_constraints],
                *[rule for anchor in anchors for rule in anchor.identity_keep_rules],
                *(
                    []
                    if policy_active
                    else human_photorealism.reference_preserve_rules
                    if human_photorealism and human_photorealism.applies
                    else []
                ),
            ]
        )[:14]
        style_reference_active = bool(
            reference_policy_package
            and any(
                policy.style_finish in {"hard", "medium"}
                or policy.mood_art_direction in {"hard", "medium"}
                for policy in reference_policy_package.policies
            )
        )
        style_keep_rules = _dedupe(
            [
                *(
                    [rule for anchor in anchors for rule in anchor.style_keep_rules]
                    if not policy_active or style_reference_active
                    else []
                ),
                *(
                    continuation_plan.prompt_additions
                    if continuation_plan and (not policy_active or style_reference_active)
                    else []
                ),
            ]
        )[:12]
        allowed_variations = _dedupe(
            [
                *[rule for anchor in anchors for rule in anchor.allowed_variations],
                *self._default_allowed_variations(subject_type),
                "change scene depth or layout when the selected mode requires it",
            ]
        )[:10]
        forbidden_drift = _dedupe(
            [
                *[rule for lock in identity_locks for rule in lock.forbidden_drift],
                *[rule for anchor in anchors for rule in anchor.forbidden_drift],
                *self._default_forbidden_drift(subject_type),
            ]
        )[:12]
        negative_rules = _dedupe(
            [
                *(continuation_plan.negative_additions if continuation_plan else []),
                *[rule for lock in identity_locks for rule in lock.negative_constraints],
                *(human_photorealism.reference_do_not_inherit_rules if human_photorealism and human_photorealism.applies else []),
                *(human_photorealism.negative_prompt_fragments if human_photorealism and human_photorealism.applies else []),
            ]
        )[:18]
        provider_rules = self._provider_rules(
            subject_type=subject_type,
            reference_strength=reference_strength,
            lock_targets=lock_targets,
            identity_keep_rules=identity_keep_rules,
            style_keep_rules=style_keep_rules,
            allowed_variations=allowed_variations,
            forbidden_drift=forbidden_drift,
            reference_policy_package=reference_policy_package,
        )
        if policy_active:
            negative_rules = _dedupe(
                [
                    *negative_rules,
                    *reference_policy_package.provider_negative_rules,
                ]
            )[:24]
        return StrongReferenceClosurePackage(
            closure_id=stable_id("strong_reference_closure", project_id, job_id, subject_type, ",".join(provider_ids), ",".join(prompt_only_ids)),
            project_id=project_id,
            job_id=job_id,
            active=active,
            subject_type=subject_type,
            reference_strength=reference_strength,
            provider_reference_required_ids=provider_ids,
            prompt_only_reference_ids=prompt_only_ids,
            identity_keep_rules=identity_keep_rules,
            style_keep_rules=style_keep_rules,
            allowed_variations=allowed_variations,
            forbidden_drift=forbidden_drift,
            provider_prompt_rules=provider_rules,
            negative_prompt_rules=negative_rules,
            user_visible_summary=self._summary(active, subject_type, reference_strength),
            metadata={
                "doc": "66",
                "module_id": self.module_id,
                "anchor_count": len(anchors),
                "identity_lock_count": len(identity_locks),
                "lock_targets": lock_targets,
                "human_photorealism_applies": bool(human_photorealism and human_photorealism.applies),
                "doc128_casebook_runtime_retired": True,
                "doc93_reference_channel_policy": policy_active,
                "reference_policy_package_id": (
                    reference_policy_package.package_id if reference_policy_package else None
                ),
            },
        )

    def _default_allowed_variations(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return [
                "change expression, gaze, pose, head angle, crop, and camera distance naturally",
                "change hand placement, body turn, micro-expression, and small hair movement when this improves a real shoot sequence",
            ]
        if subject_type == "product":
            return [
                "change camera angle, crop, lighting, surrounding context, and scene depth while preserving the product truth",
            ]
        return [
            "change framing, viewpoint, lighting detail, scene depth, or layout while preserving the selected visual direction",
        ]

    def _default_forbidden_drift(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return [
                "do not change the core person identity",
                "do not copy the exact same still, expression, pose, crop, or face angle",
                "do not preserve reference artifacts such as AI badges, watermarks, plastic skin, or synthetic highlights",
            ]
        if subject_type == "product":
            return [
                "do not change the core product identity",
                "do not replace the referenced product with a generic object or preserve reference watermarks and AI marks",
            ]
        return [
            "do not change the core visual direction, composition language, or selected subject direction",
            "do not copy the exact same frame or preserve reference watermarks, AI badges, or synthetic artifacts",
        ]

    def _provider_rules(
        self,
        *,
        subject_type: str,
        reference_strength: str,
        lock_targets: list[str],
        identity_keep_rules: list[str],
        style_keep_rules: list[str],
        allowed_variations: list[str],
        forbidden_drift: list[str],
        reference_policy_package: ResolvedReferencePolicyPackage | None,
    ) -> list[str]:
        if reference_strength == "none":
            return []
        if reference_policy_package and reference_policy_package.applies:
            return _dedupe(
                [
                    *reference_policy_package.provider_prompt_rules,
                    "Preserve identity through stable traits; do not clone the exact source frame.",
                    "Allowed variation: " + "; ".join(allowed_variations[:5]) if allowed_variations else "",
                    "Do not drift: " + "; ".join(forbidden_drift[:5]) if forbidden_drift else "",
                ]
            )
        if subject_type == "product":
            lead = "Use selected references as product truth: preserve product shape, material, color, proportions, label/logo placement, and package silhouette."
        elif subject_type == "character":
            lead = "Use selected references as person identity truth only; preserve recognizable face geometry and body identity while the current prompt controls styling, lighting, scene, camera, and style unless a channel is explicitly assigned to a reference."
        else:
            lead = "Use selected references as visual direction: preserve the selected style world, composition language, lighting, and subject direction."
        rules = [
            lead,
            (
                "Preserve identity through stable traits; do not clone the exact source frame."
                if subject_type in {"character", "product"}
                else "Preserve stable visual anchors; do not clone the exact source frame."
            ),
            "Allowed variation: " + "; ".join(allowed_variations[:5]) if allowed_variations else "",
            "Do not drift: " + "; ".join(forbidden_drift[:5]) if forbidden_drift else "",
            "Keep: " + "; ".join(_dedupe([*identity_keep_rules, *style_keep_rules])[:6]) if identity_keep_rules or style_keep_rules else "",
            "Locked targets: " + ", ".join(lock_targets[:6]) if lock_targets else "",
        ]
        return [rule for rule in rules if rule]

    def _summary(self, active: bool, subject_type: str, reference_strength: str) -> list[str]:
        if not active:
            return ["No selected reference is active yet"]
        if subject_type == "product":
            return ["Selected product direction is locked", "New images may change scene and layout"]
        if subject_type == "character":
            return ["Selected person direction is locked", "Expression, pose, angle, and crop may change naturally"]
        return ["Selected visual direction is locked", "New images may change content details"]


class ModeQualityProfileBuilder:
    """Make Doc54 modes visible to review, provider prompt, and retry selection."""

    module_id = MODE_QUALITY_PROFILE_MODULE_ID

    def build(self, *, project_id: str | None, job_id: str | None, mode: str, subject_type: str) -> ModeQualityProfile:
        key = _canonical_mode(str(mode or "delivery_suite").strip() or "delivery_suite")
        normalized_subject_type = str(subject_type or "generic").strip().lower() or "generic"
        data = _mode_data_for_subject(key, normalized_subject_type)
        return ModeQualityProfile(
            profile_id=stable_id("mode_quality_profile", project_id, job_id, key, normalized_subject_type),
            mode=key,
            user_visible_label=data["label"],
            review_priorities=list(data["review_priorities"]),
            pass_conditions=list(data["pass_conditions"]),
            retry_triggers=list(data["retry_triggers"]),
            prompt_guidance=list(data["prompt_guidance"]),
            negative_guidance=list(data["negative_guidance"]),
            metadata={"doc": "66", "module_id": self.module_id, "subject_type": normalized_subject_type},
        )


_MODE_DATA: dict[str, dict[str, list[str] | str]] = {
    "selection_candidates": {
        "label": "Similar alternatives",
        "review_priorities": ["same subject direction", "small visible pose/expression/crop differences", "no clone-like repetition"],
        "pass_conditions": ["outputs feel comparable but not identical", "identity direction remains stable"],
        "retry_triggers": ["selection_candidate_distance_risk", "same_ai_face_repetition", "mode_role_duplication", "over_cloned_portrait_batch"],
        "prompt_guidance": ["create close alternatives for choosing the best image; keep the same subject direction while varying one or two natural details such as gaze, hand placement, crop, or micro-expression"],
        "negative_guidance": ["wildly different identity", "same exact still repeated", "same expression and head angle in every candidate", "unrelated style jump"],
    },
    "delivery_suite": {
        "label": "Commercial suite",
        "review_priorities": ["clear role separation", "cover/detail/context usefulness", "commercial finish", "natural role-to-role variation"],
        "pass_conditions": ["each output has a distinct purpose", "the set feels like one directed shoot", "human sets avoid cloned expression/pose/crop"],
        "retry_triggers": ["delivery_suite_role_collapse", "mode_role_duplication", "low_commercial_finish", "over_cloned_portrait_batch"],
        "prompt_guidance": ["make each image serve a different commercial role while keeping one visual world; vary expression, pose, angle, scale, or scene depth according to role"],
        "negative_guidance": ["same image duty repeated", "same crop for every output", "same face angle and expression in every output", "unclear role separation"],
    },
    "creative_exploration": {
        "label": "Creative exploration",
        "review_priorities": ["meaningful creative distance", "core subject continuity", "usable finish"],
        "pass_conditions": ["visual direction changes are intentional", "subject identity or product truth does not collapse"],
        "retry_triggers": ["creative_distance_missing", "identity_drift", "product_identity_drift"],
        "prompt_guidance": ["explore a stronger scene, mood, or art direction while preserving the core subject"],
        "negative_guidance": ["no creative change", "lost identity", "uncontrolled style drift"],
    },
    "format_layout_adaptation": {
        "label": "Layout adaptation",
        "review_priorities": ["crop safety", "subject placement", "usable negative space", "platform/aspect fit"],
        "pass_conditions": ["subject remains readable after crop", "layout has clean usable space"],
        "retry_triggers": ["format_layout_collapse", "composition_mismatch", "camera_distance_drift"],
        "prompt_guidance": ["adapt the same direction to the requested format with safe crop and clear subject placement"],
        "negative_guidance": ["bad crop", "subject cut off", "no usable negative space"],
    },
}


def _mode_data_for_subject(mode: str, subject_type: str) -> dict[str, list[str] | str]:
    """Keep general mode semantics neutral unless a character capability is active."""

    key = mode if mode in _MODE_DATA else "delivery_suite"
    data = _MODE_DATA[key]
    if subject_type == "character":
        return data
    if key == "selection_candidates":
        if subject_type == "product":
            return {
                "label": "Similar alternatives",
                "review_priorities": ["same product truth", "small framing/camera/light differences", "no duplicate-like repetition"],
                "pass_conditions": ["outputs feel comparable but not identical", "product identity remains stable"],
                "retry_triggers": ["selection_candidate_distance_risk", "product_identity_drift", "mode_role_duplication"],
                "prompt_guidance": ["create close alternatives for choosing the best image; keep the same product direction while varying framing, camera angle, lighting, or surrounding context"],
                "negative_guidance": ["generic product replacement", "same exact still repeated", "unrelated style jump"],
            }
        return {
            "label": "Similar alternatives",
            "review_priorities": ["same visual direction", "small framing/camera/light/scene-depth differences", "no duplicate-like repetition"],
            "pass_conditions": ["outputs feel comparable but not identical", "core subject and style direction remain stable"],
            "retry_triggers": ["selection_candidate_distance_risk", "mode_role_duplication"],
            "prompt_guidance": ["create close alternatives for choosing the best image; keep the same visual direction while varying framing, viewpoint, camera, lighting, or scene depth"],
            "negative_guidance": ["wildly different core subject or scene", "same exact still repeated", "unrelated style jump"],
        }
    if key == "delivery_suite":
        return {
            "label": "Creative suite",
            "review_priorities": ["clear role separation", "context/detail/composition usefulness", "polished finish", "natural role-to-role variation"],
            "pass_conditions": ["each output has a distinct purpose", "the set keeps one directed visual world"],
            "retry_triggers": ["delivery_suite_role_collapse", "mode_role_duplication", "low_commercial_finish"],
            "prompt_guidance": ["make each image serve a different creative role while keeping one visual world; vary framing, viewpoint, scale, lighting, or scene depth according to role"],
            "negative_guidance": ["same image duty repeated", "same crop for every output", "unclear role separation"],
        }
    if key == "creative_exploration" and subject_type == "generic":
        return {
            "label": "Creative exploration",
            "review_priorities": ["meaningful creative distance", "core visual direction", "usable finish"],
            "pass_conditions": ["visual direction changes are intentional", "core subject and style direction remain recognizable"],
            "retry_triggers": ["creative_distance_missing", "subject_direction_drift"],
            "prompt_guidance": ["explore a stronger scene, mood, or art direction while preserving the core visual direction"],
            "negative_guidance": ["no creative change", "lost core direction", "uncontrolled style drift"],
        }
    return data


def _canonical_mode(value: str) -> str:
    aliases = {
        "creative_explore": "creative_exploration",
        "layout_adaptation": "format_layout_adaptation",
        "format_adaptation": "format_layout_adaptation",
    }
    return aliases.get(value, value)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
