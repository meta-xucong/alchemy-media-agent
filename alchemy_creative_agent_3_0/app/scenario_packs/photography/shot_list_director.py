"""Photography shot-list planning for the P3 shadow runtime."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from ...shared_capabilities.activation import CapabilityContribution
from .contracts import (
    PhotoShotSpec,
    PhotographyBrief,
    PhotographyDeliveryMode,
    PhotographySceneDomain,
    PhotographyUserControls,
)


class PhotographyShotListDirector:
    """Build shot specs without creating template-specific packages elsewhere."""

    def plan(
        self,
        *,
        brief: PhotographyBrief,
        controls: PhotographyUserControls,
        contributions: list[CapabilityContribution],
        job_key: str,
    ) -> list[PhotoShotSpec]:
        if controls.delivery_mode != PhotographyDeliveryMode.SINGLE_HERO:
            raise ValueError("p3_shadow_runtime_supports_single_hero_only")
        return [self._single_hero(brief=brief, contributions=contributions, job_key=job_key)]

    def _single_hero(
        self,
        *,
        brief: PhotographyBrief,
        contributions: list[CapabilityContribution],
        job_key: str,
    ) -> PhotoShotSpec:
        scene = brief.scene_domain
        scene_defaults = self._scene_defaults(scene)
        review_issue_codes = [
            issue_code
            for contribution in contributions
            for issue_code in contribution.review_contract.get("issue_codes", [])
        ]
        return PhotoShotSpec(
            shot_id=stable_id("photo_shot", job_key, brief.brief_id, "hero"),
            role="hero_photograph",
            sequence_index=1,
            subject_and_decisive_moment=scene_defaults["moment"],
            framing_and_crop=scene_defaults["framing"],
            camera_position_and_perspective_effect=scene_defaults["camera"],
            depth_and_focus_behavior=scene_defaults["depth"],
            motion_behavior=scene_defaults["motion"],
            lighting_map_and_exposure_key=self._fact(
                contributions,
                "photography_lighting_direction",
                "lighting_topology",
            ),
            palette_and_tone_curve=self._fact(contributions, "photography_color_finish", "color_response"),
            surface_texture_and_grain=scene_defaults["texture"],
            subject_direction="; ".join(brief.moment_and_subject_direction),
            retouch_direction=self._fact(contributions, "photography_retouch_direction", "retouch_restraint"),
            immutable_reference_truth=self._immutable_reference_truth(brief),
            allowed_changes=self._allowed_changes(brief),
            negative_constraints=list(
                dict.fromkeys(
                    [
                        "no watermark",
                        "no fake in-image text",
                        *self._scene_negative_constraints(scene),
                        *[
                            item
                            for contribution in contributions
                            for item in contribution.negative_additions
                        ],
                    ]
                )
            ),
            review_profile={
                "profile_id": "photography_professional_review",
                "metadata_only": True,
                "named_profile_technique_review_active": False,
                "issue_codes": sorted(set(review_issue_codes)),
            },
            metadata={
                "source": "PhotographyShotListDirector",
                "phase": "P3_shadow_general_runtime",
                "single_hero_only": True,
                "provider_strategy": "planning_only",
            },
        )

    def _scene_defaults(self, scene: PhotographySceneDomain) -> dict[str, str]:
        if scene == PhotographySceneDomain.LANDSCAPE:
            return {
                "moment": "place, weather and light window form the decisive photographic moment",
                "framing": "wide or medium-wide frame with clear foreground, middle distance and background",
                "camera": "stable viewpoint that makes scale and atmosphere legible",
                "depth": "deep focus with believable atmospheric separation",
                "motion": "cloud, water or foliage motion is deliberate if present",
                "texture": "rock, foliage, water, sky and air texture remain natural",
            }
        if scene == PhotographySceneDomain.STILL_LIFE:
            return {
                "moment": "objects are arranged at a deliberate final-settle moment",
                "framing": "controlled crop with object edges, surface and negative space balanced",
                "camera": "camera height chosen to reveal shape, material and relationship between objects",
                "depth": "focus supports the hero object while important edges stay readable",
                "motion": "stillness is intentional; no accidental smear or floating objects",
                "texture": "material grain, reflection, dust and edge cues stay physically believable",
            }
        if scene == PhotographySceneDomain.ANIMAL:
            return {
                "moment": "animal gaze, posture or movement creates a natural decisive moment",
                "framing": "frame respects full body language or face detail without cropping important anatomy",
                "camera": "camera position follows animal scale and behavior instead of human glamour framing",
                "depth": "focus anchors on the eye or behavior-critical body area",
                "motion": "motion freeze or blur matches the animal action",
                "texture": "fur, feather, scale, eye and habitat details remain species-plausible",
            }
        if scene == PhotographySceneDomain.PORTRAIT:
            return {
                "moment": "subject expression, posture and environment create a direct professional portrait moment",
                "framing": "face, body, hands and environment are cropped with professional portrait hierarchy",
                "camera": "subject-level camera relation preserves attractive facial geometry and natural proportions",
                "depth": "focus sits on eyes or face with natural falloff and enough context",
                "motion": "pose is alive but not blurred unless requested",
                "texture": "skin, hair, wardrobe and background textures remain natural and attractive",
            }
        return {
            "moment": "the requested subject, environment and timing form a deliberate photographic moment",
            "framing": (
                "crop and negative space make the requested subject legible without assuming portrait or product layout"
            ),
            "camera": "camera position and perspective follow the requested subject and spatial evidence",
            "depth": "focus and depth separation support the requested subject without arbitrary blur",
            "motion": "motion treatment follows visible action or intentional stillness",
            "texture": "materials and environmental detail remain physically believable and scene-appropriate",
        }

    def _scene_negative_constraints(self, scene: PhotographySceneDomain) -> list[str]:
        if scene == PhotographySceneDomain.PORTRAIT:
            return ["no malformed face, hands or human anatomy"]
        if scene == PhotographySceneDomain.ANIMAL:
            return ["no malformed animal anatomy, eyes, limbs, fur, feathers or scales"]
        if scene == PhotographySceneDomain.STILL_LIFE:
            return ["no broken object geometry, floating objects or impossible material edges"]
        if scene == PhotographySceneDomain.LANDSCAPE:
            return ["no repeated foliage, melted landforms, impossible water or incoherent sky lighting"]
        return ["no malformed subject structure or physically incoherent scene detail"]

    def _immutable_reference_truth(self, brief: PhotographyBrief) -> list[str]:
        hard_truth = list(brief.reference_policy_summary.get("hard_reference_truth") or [])
        preservation_controls = brief.reference_policy_summary.get("preservation_controls") or {}
        reference_owned_levels = {"preserve", "hard", "locked", "strict", "reference_owned", "identity_truth"}
        for channel, level in preservation_controls.items():
            if str(level).strip().lower() in reference_owned_levels:
                hard_truth.append(f"{channel}:{level}")
        return list(dict.fromkeys(hard_truth))

    def _allowed_changes(self, brief: PhotographyBrief) -> list[str]:
        allowed = list(brief.reference_policy_summary.get("prompt_owned_channels") or [])
        preservation_controls = brief.reference_policy_summary.get("preservation_controls") or {}
        prompt_owned_levels = {"prompt_owned", "change", "allowed", "free", "redesign"}
        for channel, level in preservation_controls.items():
            if str(level).strip().lower() in prompt_owned_levels:
                allowed.append(str(channel))
        if brief.reference_policy_summary.get("mode") == "reference_to_professional_reshoot":
            allowed.extend(["camera", "lighting", "staging", "finish"])
        return list(dict.fromkeys(allowed))

    def _fact(
        self,
        contributions: list[CapabilityContribution],
        capability_id: str,
        fact_key: str,
    ) -> str:
        for contribution in contributions:
            if contribution.capability_id == capability_id:
                value = contribution.facts.get(fact_key)
                if value:
                    return str(value)
        return "scene-appropriate professional photographic behavior"
