"""Deterministic Photography brief direction for the inactive module."""

from __future__ import annotations

import re
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographerProfileBinding,
    PhotographyBrief,
    PhotographyCommissionIntent,
    PhotographyDeliveryMode,
    PhotographyInputMode,
    PhotographySceneDomain,
    PhotographyUserControls,
)


SCENE_KEYWORDS: tuple[tuple[PhotographySceneDomain, tuple[str, ...]], ...] = (
    (PhotographySceneDomain.PORTRAIT, ("portrait", "headshot", "model", "person", "face", "people", "session")),
    (PhotographySceneDomain.LANDSCAPE, ("landscape", "mountain", "forest", "coast", "sky", "valley", "cityscape")),
    (PhotographySceneDomain.STILL_LIFE, ("still life", "still-life", "object", "vase", "flowers", "watch", "jewelry")),
    (PhotographySceneDomain.ANIMAL, ("animal", "pet", "dog", "cat", "horse", "bird", "wildlife")),
)

COMMISSION_KEYWORDS: tuple[tuple[PhotographyCommissionIntent, tuple[str, ...]], ...] = (
    (PhotographyCommissionIntent.EDITORIAL_STORY, ("editorial", "magazine", "story")),
    (PhotographyCommissionIntent.COMMERCIAL_IMAGE, ("commercial", "campaign", "advertising", "brand")),
    (PhotographyCommissionIntent.ENVIRONMENTAL_PORTRAIT, ("environmental portrait", "at work", "studio portrait")),
    (PhotographyCommissionIntent.DOCUMENTARY_MOMENT, ("documentary", "candid", "real moment")),
    (PhotographyCommissionIntent.FINE_ART_STUDY, ("fine art", "gallery", "print study")),
)

MOODY_TOKENS = ("moody", "dark", "low-key", "cinematic", "melancholic", "shadow")


class PhotographyBriefDirector:
    """Resolve a beginner request into Photography-owned planning facts."""

    def build(
        self,
        *,
        user_input: str,
        controls: PhotographyUserControls,
        uploaded_asset_ids: list[str],
        profile_binding: PhotographerProfileBinding,
        job_key: str,
        llm_profile_proposal: str | None = None,
    ) -> PhotographyBrief:
        normalized = _normalized(user_input)
        scene_domain, scene_unknown = self._resolve_scene(normalized, controls)
        commission_intent = self._resolve_commission(normalized, controls, uploaded_asset_ids)
        delivery_roles = self._delivery_roles(controls, commission_intent)
        warnings = self._profile_warnings(
            profile_binding=profile_binding,
            llm_profile_proposal=llm_profile_proposal,
        )
        unknown_requirements: list[str] = []
        if scene_unknown:
            unknown_requirements.append("scene_domain_inferred_from_general_photography_default")
        if controls.aspect_ratio is None:
            unknown_requirements.append("aspect_ratio_not_specified")
        if controls.output_count > 1 and controls.delivery_mode == PhotographyDeliveryMode.SINGLE_HERO:
            warnings.append("output_count_trimmed_by_single_hero_p3_shadow_runtime")

        return PhotographyBrief(
            brief_id=stable_id("photography_brief", job_key, user_input, controls.model_dump_json()),
            job_key=job_key,
            subject_entities=self._subject_entities(
                user_input=user_input,
                scene_domain=scene_domain,
                uploaded_asset_ids=uploaded_asset_ids,
            ),
            scene_domain=scene_domain,
            commission_intent=commission_intent,
            audience_and_use=self._audience_and_use(commission_intent),
            story_or_emotional_goal=self._story_goal(user_input),
            location_and_environment=self._environment(scene_domain, normalized),
            wardrobe_prop_and_set_needs=self._set_needs(scene_domain, normalized),
            moment_and_subject_direction=self._moment_direction(scene_domain, normalized),
            delivery_roles=delivery_roles,
            reference_policy_summary=self._reference_policy(controls, uploaded_asset_ids),
            profile_binding_summary={
                "binding_mode": profile_binding.binding_mode,
                "profile_id": profile_binding.profile_id,
                "profile_version": profile_binding.profile_version,
                "catalog_version": profile_binding.catalog_version,
                "named_profile_active": profile_binding.binding_mode == "named",
                "selection_source": (
                    profile_binding.selection_source.value
                    if profile_binding.selection_source is not None
                    else None
                ),
            },
            unknown_requirements=unknown_requirements,
            warnings=warnings,
            metadata={
                "source": "PhotographyBriefDirector",
                "phase": "P3_shadow_general_runtime",
                "general_profile_default": profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID,
                "production_activation_ready": False,
                "llm_may_select_named_profile": False,
                "mood_family": "low_key_or_moody" if _contains_any(normalized, MOODY_TOKENS) else "scene_default",
            },
        )

    def _resolve_scene(
        self,
        normalized: str,
        controls: PhotographyUserControls,
    ) -> tuple[PhotographySceneDomain, bool]:
        if controls.explicit_scene_id:
            try:
                return PhotographySceneDomain(controls.explicit_scene_id), False
            except ValueError:
                return PhotographySceneDomain.GENERAL, True
        for scene_domain, keywords in SCENE_KEYWORDS:
            if _contains_any(normalized, keywords):
                return scene_domain, False
        return PhotographySceneDomain.GENERAL, True

    def _resolve_commission(
        self,
        normalized: str,
        controls: PhotographyUserControls,
        uploaded_asset_ids: list[str],
    ) -> PhotographyCommissionIntent:
        if controls.input_mode == PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT or uploaded_asset_ids:
            return PhotographyCommissionIntent.REFERENCE_RESHOOT
        if controls.delivery_mode == PhotographyDeliveryMode.PROFESSIONAL_SET:
            return PhotographyCommissionIntent.PROFESSIONAL_SESSION
        for commission, keywords in COMMISSION_KEYWORDS:
            if _contains_any(normalized, keywords):
                return commission
        return PhotographyCommissionIntent.SINGLE_HERO

    def _delivery_roles(
        self,
        controls: PhotographyUserControls,
        commission_intent: PhotographyCommissionIntent,
    ) -> list[str]:
        if controls.delivery_mode == PhotographyDeliveryMode.PROFESSIONAL_SET:
            return ["session_hero", "environmental_context", "detail_or_moment"]
        if commission_intent == PhotographyCommissionIntent.REFERENCE_RESHOOT:
            return ["professional_reshoot_hero"]
        return ["hero_photograph"]

    def _profile_warnings(
        self,
        *,
        profile_binding: PhotographerProfileBinding,
        llm_profile_proposal: str | None,
    ) -> list[str]:
        warnings: list[str] = []
        if llm_profile_proposal:
            warnings.append("llm_profile_proposal_ignored_named_profiles_require_explicit_ui")
        if profile_binding.binding_mode == "general":
            return warnings
        warnings.append("named_profile_binding_not_allowed_in_p3_general_runtime")
        return warnings

    def _subject_entities(
        self,
        *,
        user_input: str,
        scene_domain: PhotographySceneDomain,
        uploaded_asset_ids: list[str],
    ) -> list[str]:
        if uploaded_asset_ids:
            return [f"reference_subject_from:{uploaded_asset_ids[0]}"]
        compact = " ".join(user_input.split())[:96]
        if compact:
            return [compact]
        return [scene_domain.value.replace("_", " ")]

    def _audience_and_use(self, commission_intent: PhotographyCommissionIntent) -> str:
        mapping = {
            PhotographyCommissionIntent.EDITORIAL_STORY: "editorial photographic publication or story opener",
            PhotographyCommissionIntent.COMMERCIAL_IMAGE: (
                "commercial campaign image without e-commerce listing packaging"
            ),
            PhotographyCommissionIntent.ENVIRONMENTAL_PORTRAIT: (
                "professional portrait use with context and subject credibility"
            ),
            PhotographyCommissionIntent.DOCUMENTARY_MOMENT: "documentary-feeling still image with believable timing",
            PhotographyCommissionIntent.FINE_ART_STUDY: "fine-art photographic study or print",
            PhotographyCommissionIntent.REFERENCE_RESHOOT: (
                "professional AI reshoot while preserving declared reference truth"
            ),
            PhotographyCommissionIntent.PROFESSIONAL_SESSION: "coherent professional photography session planning",
            PhotographyCommissionIntent.SINGLE_HERO: "single professional hero photograph",
        }
        return mapping[commission_intent]

    def _story_goal(self, user_input: str) -> str | None:
        compact = " ".join(user_input.split())
        return compact[:180] if compact else None

    def _environment(self, scene_domain: PhotographySceneDomain, normalized: str) -> str:
        if scene_domain == PhotographySceneDomain.LANDSCAPE:
            return "location-first outdoor environment with foreground, middle distance and background depth"
        if scene_domain == PhotographySceneDomain.STILL_LIFE:
            return "controlled tabletop or set surface with intentional object spacing"
        if scene_domain == PhotographySceneDomain.ANIMAL:
            return "believable habitat or studio-safe animal setting with natural scale cues"
        if scene_domain == PhotographySceneDomain.GENERAL:
            return "scene-appropriate photographic environment with coherent physical light and scale"
        if "outdoor" in normalized or "street" in normalized:
            return "real outdoor or street environment that supports the subject"
        return "controlled photographic environment with believable physical light"

    def _set_needs(self, scene_domain: PhotographySceneDomain, normalized: str) -> list[str]:
        needs: dict[PhotographySceneDomain, list[str]] = {
            PhotographySceneDomain.PORTRAIT: [
                "wardrobe and grooming follow the current prompt unless explicitly preserved"
            ],
            PhotographySceneDomain.LANDSCAPE: ["weather, light window and viewpoint must stay coherent"],
            PhotographySceneDomain.STILL_LIFE: [
                "surface, background and object spacing should look intentionally arranged"
            ],
            PhotographySceneDomain.ANIMAL: ["habitat, handler distance and body language must look safe and natural"],
            PhotographySceneDomain.GENERAL: [
                "subject, environment and scale should remain coherent without assuming a human, animal or product"
            ],
        }
        values = list(needs[scene_domain])
        if _contains_any(normalized, ("moody", "dark", "low-key")):
            values.append("preserve requested low-key mood while avoiding plastic highlights")
        return values

    def _moment_direction(self, scene_domain: PhotographySceneDomain, normalized: str) -> list[str]:
        if scene_domain == PhotographySceneDomain.PORTRAIT:
            base = ["natural expression, intentional posture, no frozen mannequin feel"]
        elif scene_domain == PhotographySceneDomain.LANDSCAPE:
            base = ["viewpoint and light timing create a clear sense of place"]
        elif scene_domain == PhotographySceneDomain.STILL_LIFE:
            base = ["objects feel placed by a photographer, not scattered by decoration"]
        elif scene_domain == PhotographySceneDomain.ANIMAL:
            base = ["species behavior, gaze and motion remain anatomically believable"]
        else:
            base = ["the subject and decisive moment follow the request without importing unrelated scene grammar"]
        if _contains_any(normalized, ("action", "motion", "running", "flying")):
            base.append("motion treatment must be deliberate rather than accidental blur")
        return base

    def _reference_policy(
        self,
        controls: PhotographyUserControls,
        uploaded_asset_ids: list[str],
    ) -> dict[str, Any]:
        if controls.input_mode == PhotographyInputMode.TEXT_TO_PHOTO and not uploaded_asset_ids:
            return {
                "mode": "text_to_photo",
                "hard_reference_truth": [],
                "prompt_owned_channels": ["camera", "lighting", "scene", "color", "finish"],
            }
        return {
            "mode": controls.input_mode.value,
            "reshoot_strength": controls.reshoot_strength.value if controls.reshoot_strength is not None else None,
            "source_asset_ids": uploaded_asset_ids,
            "preservation_controls": dict(controls.preservation_controls),
            "channel_policy": "preserve declared truth only; do not silently inherit all source style channels",
        }


def _normalized(value: str) -> str:
    return " ".join(value.lower().split())


def _contains_any(value: str, keywords: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", value, flags=re.IGNORECASE) is not None
        for keyword in keywords
    )
