"""Doc93 reference-channel ownership for V3 visual references."""

from __future__ import annotations

import re
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    PromptOwnershipDecision,
    ReferenceChannelPolicy,
    ResolvedReferencePolicyPackage,
    StrongReferenceBinding,
)


REFERENCE_CHANNEL_POLICY_MODULE_ID = "reference_channel_policy"

REFERENCE_CHANNELS = (
    "identity_geometry",
    "body_identity",
    "natural_complexion_direction",
    "hair_direction",
    "makeup_style",
    "wardrobe_structure",
    "accessory_system",
    "product_identity",
    "lighting_color",
    "scene_background",
    "camera_composition",
    "mood_art_direction",
    "style_finish",
)

REFERENCE_CHANNEL_COMMON_ISSUE_CODES = {
    "source_lighting_overinherited",
    "source_color_grade_overinherited",
    "source_scene_overinherited",
    "source_camera_overinherited",
    "source_whole_style_overinherited",
    "prompt_owned_channel_ignored",
    "selected_anchor_overrode_current_prompt",
    "structured_appearance_lock_misapplied",
}

REFERENCE_CHANNEL_PORTRAIT_ISSUE_CODES = {
    "source_hair_overinherited",
    "source_makeup_overinherited",
    "source_wardrobe_overinherited",
    "reference_used_as_style_when_identity_only",
}

REFERENCE_CHANNEL_ISSUE_CODES = {
    *REFERENCE_CHANNEL_COMMON_ISSUE_CODES,
    *REFERENCE_CHANNEL_PORTRAIT_ISSUE_CODES,
}


def reference_channel_issue_codes(package: Any) -> set[str]:
    """Return only review vocabulary justified by the frozen reference roles.

    Doc93's portrait-only language is meaningful for an ordinary portrait
    reference, but nonsensical for a product, animal, or generic-object truth
    source.  Keep the channel-boundary checks shared while letting the frozen
    policy decide whether portrait-specific checks are available.
    """

    if isinstance(package, dict):
        policies = package.get("policies") if isinstance(package.get("policies"), list) else []
    else:
        policies = getattr(package, "policies", []) or []
    roles = {
        str(policy.get("source_role") or "").strip().lower()
        if isinstance(policy, dict)
        else str(getattr(policy, "source_role", "") or "").strip().lower()
        for policy in policies
    }
    issues = set(REFERENCE_CHANNEL_COMMON_ISSUE_CODES)
    if "portrait_identity_reference" in roles:
        issues.update(REFERENCE_CHANNEL_PORTRAIT_ISSUE_CODES)
    return issues

_EXPLICIT_PROMPT_CHANNEL_RULES = {
    "hair_direction": (
        "Hair is current-prompt-owned: follow the exact requested hair color, length, parting, texture, and styling; "
        "conflicting hair pixels, streaks, highlights, or styling in an identity-only reference are non-authoritative."
    ),
    "makeup_style": (
        "Makeup is current-prompt-owned: follow the requested makeup and facial styling without copying source makeup "
        "or changing the reference person's facial geometry."
    ),
    "wardrobe_structure": (
        "Wardrobe is current-prompt-owned unless explicitly locked: follow the requested garment structure and do not "
        "copy clothing visible in an identity-only reference."
    ),
    "accessory_system": (
        "Accessories are current-prompt-owned unless explicitly locked; source accessories in an identity-only reference "
        "are non-authoritative."
    ),
    "lighting_color": (
        "Lighting and color are current-prompt-owned: use the requested light direction, exposure, color temperature, "
        "and grade instead of the identity reference's capture conditions."
    ),
    "scene_background": (
        "Scene and background are current-prompt-owned: build the requested environment and do not reconstruct the "
        "identity reference's location."
    ),
    "camera_composition": (
        "Camera and composition are current-prompt-owned: use the requested viewpoint, distance, crop, and lens language "
        "instead of cloning the identity reference frame."
    ),
    "mood_art_direction": (
        "Mood and art direction are current-prompt-owned; the identity reference must not act as a whole-image mood anchor."
    ),
    "style_finish": (
        "Finish is current-prompt-owned; preserve the same person without copying the identity reference's retouching, "
        "rendering style, or whole-frame finish."
    ),
}

_STRENGTH_RANK = {"off": 0, "prompt_owned": 1, "soft": 2, "medium": 3, "hard": 4}

_CHANNEL_TERMS: dict[str, tuple[str, ...]] = {
    "identity_geometry": (
        "same person",
        "same face",
        "facial geometry",
        "bone structure",
        "identity",
        "\u540c\u4e00\u4e2a\u4eba",
        "\u540c\u4e00\u5f20\u8138",
        "\u9aa8\u76f8",
        "\u4e94\u5b98",
        "\u8138\u578b",
        "\u4eba\u7269\u4e00\u81f4",
    ),
    "body_identity": ("body type", "body proportion", "physique", "\u8eab\u6750", "\u4f53\u578b", "\u8eab\u4f53\u6bd4\u4f8b"),
    "natural_complexion_direction": (
        "complexion",
        "skin tone",
        "fair skin",
        "tan skin",
        "\u80a4\u8272",
        "\u51b7\u767d\u76ae",
        "\u767d\u7699",
        "\u9ea6\u8272",
        "\u6652\u9ed1",
    ),
    "hair_direction": ("hair", "hairstyle", "hair color", "\u5934\u53d1", "\u53d1\u578b", "\u53d1\u8272", "\u53d1\u4e1d"),
    "makeup_style": ("makeup", "lip color", "eyeliner", "\u5986\u5bb9", "\u5986\u9762", "\u5507\u8272", "\u773c\u5986", "\u82b1\u94bf"),
    "wardrobe_structure": (
        "wardrobe",
        "outfit",
        "clothing",
        "garment",
        "dress",
        "shirt",
        "suit",
        "jacket",
        "coat",
        "robe",
        "skirt",
        "top",
        "pants",
        "trousers",
        "costume",
        "appearance asset",
        "silhouette",
        "sash",
        "sleeve",
        "collar",
        "embroidery",
        "pattern family",
        "trim placement",
        "layered",
        "\u670d\u88c5",
        "\u8863\u670d",
        "\u7a7f\u7740",
        "\u8fde\u8863\u88d9",
        "\u53e4\u88c5",
        "\u6c49\u670d",
        "\u4e1d\u7ef8",
        "\u8863\u6599",
        "\u886c\u886b",
        "\u897f\u88c5",
        "\u5916\u5957",
        "\u4e0a\u8863",
        "\u534a\u8eab\u88d9",
        "\u88e4\u5b50",
    ),
    "accessory_system": (
        "accessory",
        "accessories",
        "jewelry",
        "earring",
        "necklace",
        "\u914d\u9970",
        "\u9996\u9970",
        "\u8033\u5760",
        "\u9879\u94fe",
        "\u82b1\u94bf",
    ),
    "product_identity": (
        "same product",
        "product identity",
        "packaging",
        "label",
        "logo",
        "\u540c\u4e00\u5546\u54c1",
        "\u4ea7\u54c1\u5916\u89c2",
        "\u5305\u88c5",
        "\u6807\u7b7e",
        "\u5546\u6807",
    ),
    "lighting_color": (
        "lighting",
        "light setup",
        "window light",
        "studio light",
        "natural light",
        "natural-light",
        "daylight",
        "sunlight",
        "open shade",
        "afternoon light",
        "color grade",
        "color temperature",
        "palette",
        "warm light",
        "cool light",
        "\u5149\u7ebf",
        "\u706f\u5149",
        "\u8272\u8c03",
        "\u8272\u6e29",
        "\u4e3b\u8272\u8c03",
        "\u51b7\u9752",
        "\u6696\u9ec4",
        "\u9634\u5f71",
        "\u805a\u5149",
        "\u81ea\u7136\u5149",
        "\u7a97\u5149",
        "\u65e5\u5149",
    ),
    "scene_background": (
        "scene",
        "background",
        "location",
        "environment",
        "garden",
        "fountain",
        "beach",
        "office",
        "studio",
        "indoor",
        "outdoor",
        "room",
        "\u573a\u666f",
        "\u80cc\u666f",
        "\u73af\u5883",
        "\u82b1\u56ed",
        "\u55b7\u6cc9",
        "\u6d77\u8fb9",
        "\u68a8\u82b1",
        "\u57ce\u5e02",
        "\u529e\u516c\u5ba4",
        "\u5f71\u68da",
        "\u5ba4\u5185",
        "\u6237\u5916",
    ),
    "camera_composition": (
        "camera",
        "lens",
        "angle",
        "crop",
        "composition",
        "close-up",
        "wide shot",
        "35mm",
        "50mm",
        "\u673a\u4f4d",
        "\u955c\u5934",
        "\u89c6\u89d2",
        "\u6784\u56fe",
        "\u8fd1\u666f",
        "\u8fdc\u666f",
        "\u666f\u6df1",
        "\u4fef\u89c6",
        "\u4ef0\u89c6",
    ),
    "mood_art_direction": (
        "mood",
        "art direction",
        "atmosphere",
        "cinematic",
        "documentary",
        "\u6c1b\u56f4",
        "\u610f\u5883",
        "\u7535\u5f71\u611f",
        "\u7eaa\u5b9e",
        "\u6e05\u51b7",
        "\u5fe7\u90c1",
        "\u68a6\u5e7b",
    ),
    "style_finish": (
        "style",
        "finish",
        "film look",
        "photorealistic",
        "editorial",
        "\u98ce\u683c",
        "\u8d28\u611f",
        "\u80f6\u7247",
        "\u5199\u5b9e",
        "\u67d4\u7126",
        "\u6444\u5f71",
        "\u7ec6\u817b",
    ),
}

_PRESERVE_TERMS = (
    "keep",
    "preserve",
    "retain",
    "same",
    "unchanged",
    "\u4fdd\u6301",
    "\u4fdd\u7559",
    "\u6cbf\u7528",
    "\u540c\u6837",
    "\u540c\u4e00",
    "\u4e0d\u53d8",
    "\u4e00\u81f4",
)

_CHANGE_TERMS = (
    "change",
    "replace",
    "different",
    "new",
    "switch",
    "\u6539\u53d8",
    "\u66f4\u6362",
    "\u6362",
    "\u4e0d\u540c",
    "\u65b0\u7684",
    "\u91cd\u65b0\u8bbe\u8ba1",
)


class PromptOwnershipResolver:
    """Resolve explicit prompt channels without requiring a live LLM call."""

    def resolve(self, user_input: str, metadata: dict[str, Any] | None = None) -> PromptOwnershipDecision:
        text = str(user_input or "").strip().lower()
        explicit: list[str] = []
        preserve: list[str] = []
        change: list[str] = []
        evidence: dict[str, list[str]] = {}
        confidence: dict[str, float] = {}
        clauses = _clauses(text)
        for channel, terms in _CHANNEL_TERMS.items():
            hits = _dedupe(term for term in terms if term.lower() in text)
            if not hits:
                continue
            explicit.append(channel)
            evidence[channel] = hits[:8]
            confidence[channel] = min(0.98, 0.72 + (0.04 * min(len(hits), 5)))
            channel_clauses = [clause for clause in clauses if any(term.lower() in clause for term in terms)]
            if any(_intent_near_channel(clause, terms, _CHANGE_TERMS) for clause in channel_clauses):
                change.append(channel)
            elif any(_intent_near_channel(clause, terms, _PRESERVE_TERMS) for clause in channel_clauses):
                preserve.append(channel)

        brain = (metadata or {}).get("prompt_ownership_decision")
        if isinstance(brain, dict):
            explicit = _dedupe([*explicit, *_string_list(brain.get("explicit_channels"))])
            preserve = _dedupe([*preserve, *_string_list(brain.get("preserve_requests"))])
            change = _dedupe([*change, *_string_list(brain.get("change_requests"))])
            for channel, score in dict(brain.get("confidence_by_channel") or {}).items():
                try:
                    confidence[str(channel)] = max(confidence.get(str(channel), 0.0), float(score))
                except (TypeError, ValueError):
                    continue
            for channel, values in dict(brain.get("evidence_by_channel") or {}).items():
                evidence[str(channel)] = _dedupe([*evidence.get(str(channel), []), *_string_list(values)])

        return PromptOwnershipDecision(
            explicit_channels=explicit,
            preserve_requests=preserve,
            change_requests=change,
            confidence_by_channel=confidence,
            evidence_by_channel=evidence,
            metadata={
                "doc": "93",
                "resolver": "deterministic_with_optional_brain_overlay",
                "has_brain_overlay": isinstance(brain, dict),
            },
        )


class ReferenceChannelPolicyModule:
    """Build the sole reference-inheritance policy consumed downstream."""

    module_id = REFERENCE_CHANNEL_POLICY_MODULE_ID

    def __init__(self, prompt_ownership_resolver: PromptOwnershipResolver | None = None) -> None:
        self.prompt_ownership_resolver = prompt_ownership_resolver or PromptOwnershipResolver()

    def resolve(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        subject_type: str,
        template_id: str,
        strong_bindings: list[StrongReferenceBinding | dict[str, Any]],
        selected_outputs: list[dict[str, Any]] | None = None,
        advanced_reference_controls: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResolvedReferencePolicyPackage:
        ownership = self.prompt_ownership_resolver.resolve(user_input, metadata=metadata)
        bindings = [_binding_dict(binding) for binding in strong_bindings]
        controls = dict(advanced_reference_controls or {})
        has_uploaded_identity = any(
            _is_uploaded(binding) and _canonical_role(binding) == "portrait_identity_reference"
            for binding in bindings
        )
        policies = [
            self._policy_for_binding(
                project_id=project_id,
                job_id=job_id,
                binding=binding,
                ownership=ownership,
                controls=controls,
                has_uploaded_identity=has_uploaded_identity,
            )
            for binding in bindings
        ]
        effective_owners = self._effective_channel_owners(policies, ownership)
        provider_rules = self._provider_rules(policies, ownership)
        provider_negatives = self._provider_negative_rules(policies)
        review_targets = self._review_targets(policies)
        applies = bool(policies)
        return ResolvedReferencePolicyPackage(
            package_id=stable_id(
                "resolved_reference_policy",
                project_id,
                job_id,
                user_input,
                ",".join(policy.policy_id for policy in policies),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=applies,
            policies=policies,
            prompt_ownership=ownership,
            effective_channel_owners=effective_owners,
            provider_prompt_rules=provider_rules,
            provider_negative_rules=provider_negatives,
            review_targets=review_targets,
            retry_issue_map={
                "source_hair_overinherited": ["hair_direction"],
                "source_makeup_overinherited": ["makeup_style"],
                "source_wardrobe_overinherited": ["wardrobe_structure", "accessory_system"],
                "source_lighting_overinherited": ["lighting_color"],
                "source_color_grade_overinherited": ["lighting_color"],
                "source_scene_overinherited": ["scene_background"],
                "source_camera_overinherited": ["camera_composition"],
                "source_whole_style_overinherited": ["mood_art_direction", "style_finish"],
                "reference_used_as_style_when_identity_only": ["style_finish", "mood_art_direction"],
                "prompt_owned_channel_ignored": list(ownership.explicit_channels),
                "selected_anchor_overrode_current_prompt": list(ownership.explicit_channels),
                "structured_appearance_lock_misapplied": ["wardrobe_structure", "accessory_system"],
            },
            user_visible_summary=self._summary(policies, ownership),
            metadata={
                "doc": "93",
                "module_id": self.module_id,
                "subject_type": subject_type,
                "template_id": template_id,
                "policy_count": len(policies),
                "selected_output_count": len(selected_outputs or []),
                "uploaded_identity_truth_present": has_uploaded_identity,
                "advanced_reference_controls": controls,
                "human_realism_may_expand_inheritance": False,
            },
        )

    def _policy_for_binding(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        binding: dict[str, Any],
        ownership: PromptOwnershipDecision,
        controls: dict[str, Any],
        has_uploaded_identity: bool,
    ) -> ReferenceChannelPolicy:
        source_id = _source_id(binding)
        role = _canonical_role(binding)
        source_type = str(binding.get("source_type") or "project_reference")
        profile = _default_profile(role, binding=binding, has_uploaded_identity=has_uploaded_identity)
        explicit_locks: list[str] = []
        conflicts: list[dict[str, Any]] = []

        for channel in ownership.explicit_channels:
            current = str(profile.get(channel) or "off")
            if channel in ownership.preserve_requests and _reference_can_supply(role, channel):
                profile[channel] = "hard" if channel in {"identity_geometry", "product_identity", "wardrobe_structure", "scene_background"} else "medium"
                explicit_locks.append(channel)
                conflicts.append({"channel": channel, "resolution": "explicit_user_lock", "previous": current})
                continue
            if channel in {"identity_geometry", "product_identity"} and current == "hard":
                conflicts.append({"channel": channel, "resolution": "hard_truth_preserved", "previous": current})
                continue
            profile[channel] = "prompt_owned"
            conflicts.append(
                {
                    "channel": channel,
                    "resolution": "explicit_current_prompt",
                    "previous": current,
                    "change_requested": channel in ownership.change_requests,
                }
            )

        if controls.get("preserve_person_identity") and role in {"portrait_identity_reference", "selected_generated_output"}:
            if role == "portrait_identity_reference" or "identity" in _binding_policy(binding):
                profile["identity_geometry"] = "hard"
                profile["body_identity"] = _stronger(str(profile.get("body_identity")), "medium")
                profile["natural_complexion_direction"] = _stronger(
                    str(profile.get("natural_complexion_direction")), "medium"
                )
                explicit_locks.append("identity_geometry")
        if controls.get("preserve_product_appearance") and role in {"product_identity_reference", "selected_generated_output"}:
            if role == "product_identity_reference" or "product" in _binding_policy(binding):
                profile["product_identity"] = "hard"
                explicit_locks.append("product_identity")
        if controls.get("preserve_scene_consistency") and role in {
            "scene_reference",
            "style_reference",
            "selected_generated_output",
            "portrait_identity_reference",
            "product_identity_reference",
        }:
            profile["scene_background"] = "hard"
            profile["camera_composition"] = _stronger(str(profile.get("camera_composition")), "medium")
            profile["lighting_color"] = _stronger(str(profile.get("lighting_color")), "medium")
            explicit_locks.append("scene_background")

        prompt_owned = [channel for channel in REFERENCE_CHANNELS if profile.get(channel) == "prompt_owned"]
        blocked = [channel for channel in REFERENCE_CHANNELS if profile.get(channel) in {"prompt_owned", "off"}]
        contributions = [
            f"{channel}:{profile[channel]}"
            for channel in REFERENCE_CHANNELS
            if profile.get(channel) in {"hard", "medium", "soft"}
        ]
        provider_rules = _policy_provider_rules(role, profile, source_id)
        provider_negatives = _policy_negative_rules(role, blocked)
        return ReferenceChannelPolicy(
            policy_id=stable_id("reference_channel_policy", project_id, job_id, source_id, role),
            project_id=project_id,
            job_id=job_id,
            source_asset_id=source_id,
            source_role=role,
            source_type=source_type,
            **{channel: str(profile.get(channel) or "off") for channel in REFERENCE_CHANNELS},
            prompt_owned_channels=prompt_owned,
            explicit_user_locks=_dedupe(explicit_locks),
            blocked_inheritance_channels=blocked,
            allowed_reference_contributions=contributions,
            conflict_resolutions=conflicts,
            provider_prompt_rules=provider_rules,
            provider_negative_rules=provider_negatives,
            metadata={
                "doc": "93",
                "binding_id": binding.get("binding_id"),
                "binding_use_policy": binding.get("use_policy"),
                "selected_output_anchor": _is_selected(binding),
                "uploaded_truth_source": _is_uploaded(binding),
                "ordinary_portrait_identity_only_default": role == "portrait_identity_reference",
            },
        )

    def _effective_channel_owners(
        self,
        policies: list[ReferenceChannelPolicy],
        ownership: PromptOwnershipDecision,
    ) -> dict[str, str]:
        owners: dict[str, str] = {}
        for channel in REFERENCE_CHANNELS:
            explicit_prompt = channel in ownership.explicit_channels and channel not in ownership.preserve_requests
            if explicit_prompt and channel not in {"identity_geometry", "product_identity"}:
                owners[channel] = "current_prompt"
                continue
            candidates = [
                policy
                for policy in policies
                if getattr(policy, channel) in {"hard", "medium", "soft"}
            ]
            if not candidates:
                owners[channel] = "current_prompt_or_defaults"
                continue
            candidates.sort(
                key=lambda policy: (
                    _STRENGTH_RANK.get(str(getattr(policy, channel)), 0),
                    0 if policy.source_type == "selected_output" else 1,
                    1 if policy.metadata.get("uploaded_truth_source") else 0,
                ),
                reverse=True,
            )
            winner = candidates[0]
            owners[channel] = f"reference:{winner.source_asset_id}:{getattr(winner, channel)}"
        return owners

    def _provider_rules(
        self,
        policies: list[ReferenceChannelPolicy],
        ownership: PromptOwnershipDecision,
    ) -> list[str]:
        rules = [rule for policy in policies for rule in policy.provider_prompt_rules]
        if ownership.explicit_channels:
            rules.insert(
                0,
                "Current prompt owns its explicit visual channels: " + ", ".join(ownership.explicit_channels[:10]) + ".",
            )
            if any(policy.source_role == "portrait_identity_reference" for policy in policies):
                rules[1:1] = [
                    _EXPLICIT_PROMPT_CHANNEL_RULES[channel]
                    for channel in ownership.explicit_channels
                    if channel in _EXPLICIT_PROMPT_CHANNEL_RULES
                ]
        if any(policy.metadata.get("selected_output_anchor") for policy in policies):
            rules.append(
                "Selected generated outputs provide approved medium-strength direction only; they must yield to uploaded truth and any new explicit prompt instruction."
            )
        return _dedupe(rules)[:16]

    def _provider_negative_rules(self, policies: list[ReferenceChannelPolicy]) -> list[str]:
        return _dedupe(rule for policy in policies for rule in policy.provider_negative_rules)[:16]

    def _review_targets(self, policies: list[ReferenceChannelPolicy]) -> list[str]:
        targets = [
            "reference roles influence only their assigned visual channels",
            "current prompt-owned channels remain visible in the result",
            "selected generated anchors do not override uploaded truth or the current prompt",
        ]
        if any(policy.source_role == "portrait_identity_reference" for policy in policies):
            targets.extend(
                [
                    "same-person face geometry is preserved",
                    "source hair, makeup, wardrobe, lighting, scene, camera, and whole-image style do not leak by default",
                ]
            )
        if any(policy.source_role == "product_identity_reference" for policy in policies):
            targets.append("product truth is preserved while scene and lighting follow the current request")
        return _dedupe(targets)

    def _summary(
        self,
        policies: list[ReferenceChannelPolicy],
        ownership: PromptOwnershipDecision,
    ) -> list[str]:
        summary: list[str] = []
        if any(policy.source_role == "portrait_identity_reference" for policy in policies):
            summary.append("Kept the same person's recognizable face and identity.")
        if any(policy.source_role == "product_identity_reference" for policy in policies):
            summary.append("Kept the referenced product's recognizable appearance.")
        if ownership.explicit_channels:
            summary.append("Styling, light, scene, and camera follow this request where specified.")
        return summary or ["Reference roles were resolved for this generation."]


def reference_channel_retry_patch(
    issue_codes: list[str] | tuple[str, ...] | set[str],
    *,
    preserve_portrait_identity: bool = False,
) -> dict[str, list[str]]:
    """Return one module-owned, channel-specific repair patch for Doc93/Doc103 issues."""

    codes = {str(item).strip() for item in issue_codes if str(item).strip()}
    prompt_additions = [
        "Doc93 channel repair with Doc103 evidence isolation: preserve valid identity or product truth while repairing only the reference channel that crossed its assigned boundary.",
        "do not increase whole-image reference strength and do not let a selected generated output override uploaded truth or the current prompt.",
    ]
    negative_additions: list[str] = []
    identity_reinforcement = (
        ["Keep the same person's face geometry and feature relationships while changing prompt-owned surface styling or environmental channels."]
        if preserve_portrait_identity
        else []
    )
    composition_repair: list[str] = []

    if "source_hair_overinherited" in codes:
        prompt_additions.append(
            "Replace only inherited source hair color, streaks, highlights, length, parting, texture, and styling with the exact current prompt hair direction."
        )
        negative_additions.extend(["source hair color leakage", "source hair streaks or highlights", "source hairstyle copied"])
    if "source_makeup_overinherited" in codes:
        prompt_additions.append(
            "Replace only inherited source makeup with the exact current prompt makeup while preserving underlying facial geometry."
        )
        negative_additions.extend(["source makeup copied", "source cosmetic color leakage"])
    if "source_wardrobe_overinherited" in codes or "structured_appearance_lock_misapplied" in codes:
        prompt_additions.append(
            "Use the current prompt wardrobe and accessories unless that exact appearance channel is explicitly locked to a reference."
        )
        negative_additions.extend(["source wardrobe leakage", "source accessory leakage", "misapplied outfit lock"])
    if "source_lighting_overinherited" in codes or "source_color_grade_overinherited" in codes:
        prompt_additions.append(
            "Restore the current prompt light direction, exposure, color temperature, and color grade without altering the assigned subject or product truth."
        )
        negative_additions.extend(["source lighting copied", "source color grade copied"])
    if "source_scene_overinherited" in codes:
        prompt_additions.append("Replace the source location with the exact current prompt scene and background.")
        prompt_additions.append(
            "Keep the scene boundary strict: do not copy source lighting, source color temperature, source scene, source camera mood, or whole-image style; actively rebuild only the reported environment channel."
        )
        negative_additions.append("source scene or background copied")
        composition_repair.append("Rebuild only the requested environment while retaining the same person or product truth.")
    if "source_camera_overinherited" in codes:
        prompt_additions.append("Restore the current prompt viewpoint, camera distance, crop, and lens language.")
        negative_additions.append("source camera frame copied")
        composition_repair.append("Use the requested camera composition instead of cloning the reference frame.")
    if codes & {"source_whole_style_overinherited", "reference_used_as_style_when_identity_only"}:
        if preserve_portrait_identity:
            prompt_additions.append(
                "Use the identity-only reference for identity channels only and restore the current prompt mood, art direction, and finish."
            )
            negative_additions.append("identity reference used as a style template")
        else:
            prompt_additions.append(
                "Use the reference only for its assigned truth channels and restore the current prompt mood, art direction, and finish."
            )
        negative_additions.append("source whole-image finish copied")
    if codes & {"prompt_owned_channel_ignored", "selected_anchor_overrode_current_prompt"}:
        prompt_additions.append(
            "Re-read every explicit current-prompt channel and make each requested change visibly dominant over conflicting reference pixels."
        )
        negative_additions.append("current prompt overridden by reference pixels")

    return {
        "prompt_additions": _dedupe(prompt_additions),
        "negative_additions": _dedupe(negative_additions),
        "identity_reinforcement": _dedupe(identity_reinforcement),
        "composition_repair": _dedupe(composition_repair),
    }


def _default_profile(
    role: str,
    *,
    binding: dict[str, Any],
    has_uploaded_identity: bool,
) -> dict[str, str]:
    profile = {channel: "off" for channel in REFERENCE_CHANNELS}
    for channel in (
        "hair_direction",
        "makeup_style",
        "wardrobe_structure",
        "accessory_system",
        "lighting_color",
        "scene_background",
        "camera_composition",
        "mood_art_direction",
        "style_finish",
    ):
        profile[channel] = "prompt_owned"

    if role == "portrait_identity_reference":
        profile.update(
            identity_geometry="hard",
            body_identity="medium",
            natural_complexion_direction="medium",
            hair_direction="prompt_owned",
        )
    elif role == "nonhuman_subject_identity_reference":
        # Individual non-human truth is governed by its own shared capability;
        # no human appearance or source-frame style channel is inherited here.
        pass
    elif role == "product_identity_reference":
        profile["product_identity"] = "hard"
    elif role == "structured_appearance_reference":
        profile["wardrobe_structure"] = "hard"
        profile["accessory_system"] = "medium"
    elif role == "style_reference":
        profile["style_finish"] = "medium"
        profile["mood_art_direction"] = "medium"
        profile["lighting_color"] = "medium"
        profile["camera_composition"] = "soft"
    elif role == "scene_reference":
        profile["scene_background"] = "medium"
        profile["camera_composition"] = "medium"
        profile["lighting_color"] = "medium"
    elif role == "composition_reference":
        profile["camera_composition"] = "medium"
    elif role == "lighting_reference":
        profile["lighting_color"] = "medium"
    elif role == "brand_asset_reference":
        profile["product_identity"] = "medium"
        profile["style_finish"] = "soft"
    elif role == "selected_generated_output":
        profile["style_finish"] = "medium"
        profile["mood_art_direction"] = "medium"
        profile["lighting_color"] = "soft"
        profile["camera_composition"] = "soft"
        policy = _binding_policy(binding)
        if "identity" in policy and not has_uploaded_identity:
            profile["identity_geometry"] = "medium"
            profile["body_identity"] = "soft"
        if "product" in policy:
            profile["product_identity"] = "medium"
    return profile


def _policy_provider_rules(role: str, profile: dict[str, str], source_id: str) -> list[str]:
    if role == "portrait_identity_reference":
        return [
            f"Reference {source_id} is same-person identity truth only.",
            "Preserve underlying face geometry and facial-feature relationships.",
            "Follow the current prompt for hair styling, makeup, wardrobe, accessories, lighting, color, scene, camera, mood, and art direction unless the user explicitly locks one of those channels.",
            "Do not copy the reference image's original lighting, color temperature, scene, wardrobe, camera mood, or whole-image style unless the user explicitly assigns that channel to the reference.",
        ]
    if role == "nonhuman_subject_identity_reference":
        return [
            f"Reference {source_id} is individual non-human subject identity truth.",
            "Preserve stable morphology, head geometry, body proportions, and distinctive markings or pattern.",
            "Follow the current prompt for habitat, action, camera, lighting, color treatment, and finish; do not copy the reference frame as a style template.",
        ]
    if role == "product_identity_reference":
        return [
            f"Reference {source_id} is product identity truth.",
            "Preserve product shape, proportions, material, surface, packaging, pattern, label, and logo placement when visible.",
            "Follow the current prompt for background, lighting, camera, layout, and style unless separately locked.",
        ]
    if role == "structured_appearance_reference":
        return [
            f"Reference {source_id} is structured appearance truth.",
            "Preserve the assigned garment or appearance structure while current prompt controls person identity, lighting, scene, and camera unless separately assigned.",
        ]
    if role == "selected_generated_output":
        return [
            f"Reference {source_id} is a user-approved generated direction at medium strength.",
            *(
                ["When assigned to identity, this selected output provides medium same-person identity truth below any uploaded identity truth."]
                if profile.get("identity_geometry") in {"hard", "medium"}
                else []
            ),
            "Use only its assigned channels; do not clone the whole frame or override uploaded truth or new prompt instructions.",
        ]
    if role == "scene_reference":
        return [f"Reference {source_id} guides scene and spatial continuity only; it does not define person or product identity."]
    if role == "composition_reference":
        return [f"Reference {source_id} guides composition only; it does not define identity, wardrobe, or whole-image style."]
    if role == "lighting_reference":
        return [f"Reference {source_id} guides lighting and color only; it does not define identity or wardrobe."]
    if role == "style_reference":
        return [f"Reference {source_id} guides explicitly assigned style channels only; it does not define person, product, or garment identity."]
    if role == "brand_asset_reference":
        return [f"Reference {source_id} preserves assigned brand colors, marks, and placement logic only."]
    return []


def _policy_negative_rules(role: str, blocked: list[str]) -> list[str]:
    if role != "portrait_identity_reference":
        return []
    mapping = {
        "hair_direction": "copied source hairstyle when current prompt specifies hair",
        "makeup_style": "copied source makeup when current prompt specifies makeup",
        "wardrobe_structure": "copied source wardrobe without an explicit same-outfit request",
        "accessory_system": "copied source accessories without an explicit lock",
        "lighting_color": "copied source lighting or color grade",
        "scene_background": "copied source scene or background",
        "camera_composition": "copied source camera angle or composition",
        "mood_art_direction": "copied source mood or art direction",
        "style_finish": "portrait identity reference used as a whole-image style template",
    }
    return [mapping[channel] for channel in blocked if channel in mapping]


def _reference_can_supply(role: str, channel: str) -> bool:
    role_channels = {
        "portrait_identity_reference": {
            "identity_geometry",
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
        },
        "product_identity_reference": {"product_identity", "lighting_color", "scene_background", "camera_composition", "style_finish"},
        "structured_appearance_reference": {"wardrobe_structure", "accessory_system"},
        "style_reference": {"style_finish", "mood_art_direction", "lighting_color", "camera_composition"},
        "scene_reference": {"scene_background", "camera_composition", "lighting_color"},
        "composition_reference": {"camera_composition"},
        "lighting_reference": {"lighting_color"},
        "selected_generated_output": set(REFERENCE_CHANNELS),
    }
    return channel in role_channels.get(role, set())


def _canonical_role(binding: dict[str, Any]) -> str:
    if _is_selected(binding):
        return "selected_generated_output"
    value = " ".join(
        [
            str(binding.get("role") or ""),
            str(binding.get("use_policy") or ""),
            str((binding.get("metadata") or {}).get("raw_role") or ""),
        ]
    ).lower()
    if "nonhuman_identity_reference" in value or "nonhuman_subject_identity" in value:
        return "nonhuman_subject_identity_reference"
    if "product" in value:
        return "product_identity_reference"
    if any(token in value for token in ("appearance", "wardrobe", "garment", "outfit", "clothing")):
        return "structured_appearance_reference"
    if any(token in value for token in ("identity", "face", "portrait", "person", "character")):
        return "portrait_identity_reference"
    if any(token in value for token in ("scene", "background", "mood")):
        return "scene_reference"
    if "composition" in value:
        return "composition_reference"
    if "light" in value or "color" in value:
        return "lighting_reference"
    if "brand" in value or "logo" in value:
        return "brand_asset_reference"
    if "style" in value:
        return "style_reference"
    return "generic_reference"


def _binding_dict(binding: StrongReferenceBinding | dict[str, Any]) -> dict[str, Any]:
    if hasattr(binding, "model_dump"):
        return binding.model_dump(mode="json")
    return dict(binding or {})


def _binding_policy(binding: dict[str, Any]) -> str:
    return " ".join([str(binding.get("use_policy") or ""), str(binding.get("role") or "")]).lower()


def _source_id(binding: dict[str, Any]) -> str:
    return str(
        binding.get("asset_id")
        or binding.get("output_id")
        or binding.get("source_id")
        or binding.get("binding_id")
        or "unknown_reference"
    )


def _is_selected(binding: dict[str, Any]) -> bool:
    source_type = str(binding.get("source_type") or "").lower()
    metadata = binding.get("metadata") if isinstance(binding.get("metadata"), dict) else {}
    return bool(
        source_type in {"selected_output", "generated_selected"}
        or metadata.get("selected_output_anchor")
        or metadata.get("selected_project_anchor")
    )


def _is_uploaded(binding: dict[str, Any]) -> bool:
    source_type = str(binding.get("source_type") or "").lower()
    metadata = binding.get("metadata") if isinstance(binding.get("metadata"), dict) else {}
    return bool(source_type == "uploaded" or metadata.get("v3_upload_lookup") == "ready" or metadata.get("uploaded_truth_source"))


def _stronger(left: str, right: str) -> str:
    return left if _STRENGTH_RANK.get(left, 0) >= _STRENGTH_RANK.get(right, 0) else right


def _clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,.;:!?\n\u3002\uff0c\uff1b\uff1a\uff01\uff1f]+|\b(?:but|while|whereas)\b", text) if part.strip()]


def _intent_near_channel(
    clause: str,
    channel_terms: tuple[str, ...],
    intent_terms: tuple[str, ...],
    max_distance: int = 32,
) -> bool:
    def positions(term: str) -> list[int]:
        needle = term.lower()
        values: list[int] = []
        start = 0
        while needle:
            index = clause.find(needle, start)
            if index < 0:
                break
            values.append(index)
            start = index + max(1, len(needle))
        return values

    channel_positions = [position for term in channel_terms for position in positions(term)]
    intent_positions = [
        (position, term.lower())
        for term in intent_terms
        for position in positions(term)
    ]
    if not channel_positions or not intent_positions:
        return False
    short_scope_terms = {term.lower() for term in _PRESERVE_TERMS}
    return any(
        abs(channel_pos - intent_pos) <= (18 if intent_term in short_scope_terms else max_distance)
        for channel_pos in channel_positions
        for intent_pos, intent_term in intent_positions
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
