"""General Photography technique contributions for the P3 shadow runtime."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import (
    PhotographerProfileBinding,
    PhotographyBrief,
    PhotographySceneDomain,
)


GENERAL_TECHNIQUE_CAPABILITIES = (
    "photography_camera_optics",
    "photography_lighting_direction",
    "photography_composition_direction",
    "photography_color_finish",
    "photography_retouch_direction",
)


class GeneralPhotographyTechniqueDirector:
    """Build structured, observable photographic guidance for General Photography."""

    def build_contributions(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> list[CapabilityContribution]:
        if profile_binding.binding_mode != "general":
            raise ValueError("general_photography_technique_requires_general_profile_binding")
        return [
            self._camera(brief, activation_plan_id),
            self._lighting(brief, activation_plan_id),
            self._composition(brief, activation_plan_id),
            self._color(brief, activation_plan_id),
            self._retouch(brief, activation_plan_id),
        ]

    def _camera(self, brief: PhotographyBrief, activation_plan_id: str) -> CapabilityContribution:
        scene = brief.scene_domain
        if scene == PhotographySceneDomain.PORTRAIT:
            facts = {
                "camera_relation": "subject-level camera position with natural facial geometry",
                "depth_behavior": "background separation without waxy face smoothing",
            }
        elif scene == PhotographySceneDomain.LANDSCAPE:
            facts = {
                "camera_relation": "stable viewpoint with readable foreground-to-background depth",
                "depth_behavior": "deep focus unless prompt calls for atmospheric compression",
            }
        elif scene == PhotographySceneDomain.STILL_LIFE:
            facts = {
                "camera_relation": "controlled camera height chosen for object shape and edge readability",
                "depth_behavior": "selective focus only when material edges remain legible",
            }
        elif scene == PhotographySceneDomain.ANIMAL:
            facts = {
                "camera_relation": "eye-level or behavior-led camera placement that respects animal anatomy",
                "depth_behavior": "focus locks on the animal's face or decisive movement",
            }
        else:
            facts = {
                "camera_relation": (
                    "camera position and perspective follow the requested subject without assuming a person or animal"
                ),
                "depth_behavior": "focus placement and falloff make the requested subject legible",
            }
        return self._contribution(
            "photography_camera_optics",
            activation_plan_id,
            facts=facts,
            prompt_additions=[
                (
                    "Describe visible camera position, perspective, focus and motion behavior rather than relying "
                    "on camera brand tokens."
                )
            ],
            negative_additions=["distorted anatomy from impossible lens perspective", "random shallow focus"],
            review_contract={"issue_codes": ["photography_perspective_depth_focus_error"]},
        )

    def _lighting(self, brief: PhotographyBrief, activation_plan_id: str) -> CapabilityContribution:
        moody = brief.metadata.get("mood_family") == "low_key_or_moody"
        if moody:
            lighting = (
                "low-key or moody light with controlled highlights, soft-matte texture and believable shadow detail"
            )
        elif brief.scene_domain == PhotographySceneDomain.LANDSCAPE:
            lighting = "motivated natural light window with coherent sky, atmosphere and landform shadows"
        elif brief.scene_domain == PhotographySceneDomain.STILL_LIFE:
            lighting = "controlled set light that reveals material surface, edge and reflection behavior"
        elif brief.scene_domain == PhotographySceneDomain.PORTRAIT:
            lighting = "real-camera key and fill relationship with natural skin and controlled facial highlights"
        elif brief.scene_domain == PhotographySceneDomain.ANIMAL:
            lighting = "motivated light with believable fur, feather, scale and eye highlights"
        else:
            lighting = "scene-appropriate motivated light with coherent highlight, shadow and material response"
        return self._contribution(
            "photography_lighting_direction",
            activation_plan_id,
            facts={
                "lighting_topology": lighting,
                "human_realism_relevant": brief.scene_domain == PhotographySceneDomain.PORTRAIT,
            },
            prompt_additions=[lighting],
            negative_additions=[
                "plastic highlights",
                "flat AI glamour light",
                "light direction that contradicts shadows",
            ],
            review_contract={"issue_codes": ["photography_lighting_plausibility_error"]},
        )

    def _composition(self, brief: PhotographyBrief, activation_plan_id: str) -> CapabilityContribution:
        scene = brief.scene_domain
        if scene == PhotographySceneDomain.PORTRAIT:
            composition = "face, body, hands and environment form a clear photographic hierarchy"
        elif scene == PhotographySceneDomain.LANDSCAPE:
            composition = "foreground, middle distance and background create readable scale and visual rhythm"
        elif scene == PhotographySceneDomain.STILL_LIFE:
            composition = "object grouping, negative space and surface edges feel intentionally photographed"
        elif scene == PhotographySceneDomain.ANIMAL:
            composition = "animal body language, gaze and habitat relationship guide the frame"
        else:
            composition = "subject, environment and negative space create a clear photographic hierarchy"
        return self._contribution(
            "photography_composition_direction",
            activation_plan_id,
            facts={"composition_geometry": composition, "delivery_roles": list(brief.delivery_roles)},
            prompt_additions=[composition],
            negative_additions=["generic centered subject with no photographic hierarchy"],
            review_contract={"issue_codes": ["photography_composition_hierarchy_error"]},
        )

    def _color(self, brief: PhotographyBrief, activation_plan_id: str) -> CapabilityContribution:
        moody = brief.metadata.get("mood_family") == "low_key_or_moody"
        if moody:
            finish = (
                "controlled low-key color response, preserved mood, restrained saturation and natural black point"
            )
        elif brief.scene_domain == PhotographySceneDomain.LANDSCAPE:
            finish = "location-specific color, believable atmospheric contrast and natural highlight rolloff"
        else:
            finish = (
                "professional photographic color with restrained contrast, believable tone curve and natural texture"
            )
        return self._contribution(
            "photography_color_finish",
            activation_plan_id,
            facts={"color_response": finish, "anti_one_note_palette": True},
            prompt_additions=[finish],
            negative_additions=["overcooked HDR", "single-hue color wash", "synthetic AI saturation"],
            review_contract={"issue_codes": ["photography_color_tone_finish_error"]},
        )

    def _retouch(self, brief: PhotographyBrief, activation_plan_id: str) -> CapabilityContribution:
        if brief.scene_domain == PhotographySceneDomain.PORTRAIT:
            retouch = "skin and facial details remain attractive, natural and textured; do not erase identity geometry"
        elif brief.scene_domain == PhotographySceneDomain.ANIMAL:
            retouch = "fur, feathers, eyes and movement retain species-specific texture and believable detail"
        elif brief.scene_domain == PhotographySceneDomain.STILL_LIFE:
            retouch = "materials keep real edge, dust, reflection and surface cues without product-fake polish"
        elif brief.scene_domain == PhotographySceneDomain.LANDSCAPE:
            retouch = "landscape materials keep natural foliage, water, rock, sky and atmospheric detail"
        else:
            retouch = (
                "requested subject and environment keep natural material texture without domain-specific beauty treatment"
            )
        return self._contribution(
            "photography_retouch_direction",
            activation_plan_id,
            facts={"retouch_restraint": retouch, "reference_truth_override": "declared truth remains authoritative"},
            prompt_additions=[retouch],
            negative_additions=["over-smoothed texture", "AI wax finish", "watermark", "fake in-image text"],
            review_contract={"issue_codes": ["photography_retouch_restraint_error", "ai_artifact_severity"]},
        )

    def _contribution(
        self,
        capability_id: str,
        activation_plan_id: str,
        *,
        facts: dict,
        prompt_additions: list[str],
        negative_additions: list[str],
        review_contract: dict,
    ) -> CapabilityContribution:
        return CapabilityContribution(
            capability_id=capability_id,
            capability_version="p3-general-v1",
            activation_plan_id=activation_plan_id,
            facts=facts,
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            provider_input_requirements=[],
            review_contract={
                **review_contract,
                "metadata_only": True,
                "named_profile_fidelity_active": False,
            },
            retry_contract={
                "bounded_retry_owner": capability_id,
                "retry_must_preserve_profile_binding": True,
            },
            stages=["brief_direction", "shot_planning", "review_profile"],
            metadata={
                "owner": "photography_module",
                "phase": "P3_shadow_general_runtime",
                "direct_provider_call": False,
                "contains_named_photographer_identity": False,
            },
        )
