"""Frozen real-provider acceptance matrices for the Photography P6 gate.

This is a specialized-template test plan, not a renderer, provider adapter,
pixel scorer, retry loop or final-result selector.  It lets the front-end and
human reviewer run the same documented matrix once the gated shared runtime is
available.
"""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import (
    PhotographyDeliveryMode,
    PhotographyInputMode,
    PhotographyProviderAcceptanceCase,
    PhotographyProviderAcceptanceMatrix,
    PhotographySceneDomain,
)


_SCENE_CASES: tuple[tuple[PhotographySceneDomain, str, str, dict[str, str], list[str]], ...] = (
    (
        PhotographySceneDomain.PORTRAIT,
        "Create a natural environmental portrait of a ceramic artist at work in her studio, with believable window light and intentional hands, expression and posture.",
        "Professionally reshoot this ordinary portrait as an environmental studio photograph while keeping the same person; wardrobe, lighting and setting follow the current request.",
        {"person_identity": "preserve", "wardrobe": "prompt_owned", "lighting": "prompt_owned"},
        ["human_realism", "portrait_identity", "reference_channel_policy"],
    ),
    (
        PhotographySceneDomain.LANDSCAPE,
        "Create a photographic landscape of a misty coastal valley at dawn, with coherent foreground depth, weather and natural atmospheric perspective.",
        "Professionally reshoot this landmark landscape at dawn while preserving the place; weather, color and light follow the current request.",
        {"scene_landmark_truth": "preserve", "weather": "prompt_owned", "lighting": "prompt_owned"},
        ["scene_continuity", "reference_channel_policy"],
    ),
    (
        PhotographySceneDomain.STILL_LIFE,
        "Create a minimal still-life photograph of a ceramic vase, glass and dark stone with controlled reflections, material edges and deliberate negative space.",
        "Professionally reshoot this object as a minimal still life while preserving its shape and material truth; surface, background and finish follow the current request.",
        {"object_truth": "preserve", "background": "prompt_owned", "finish": "prompt_owned"},
        ["product_identity", "reference_channel_policy"],
    ),
    (
        PhotographySceneDomain.ANIMAL,
        "Create a professional animal photograph of a horse moving through a meadow, with believable anatomy, behavior, eye focus and motivated natural light.",
        "Professionally reshoot this individual animal in a new meadow setting while preserving the same individual; habitat, action, camera and lighting follow the current request.",
        {"nonhuman_subject_identity": "preserve", "habitat": "prompt_owned", "action": "prompt_owned", "lighting": "prompt_owned"},
        ["nonhuman_subject_identity", "reference_channel_policy"],
    ),
)


_UNIVERSAL_REVIEW_DIMENSIONS = [
    "brief_fidelity",
    "composition_and_visual_hierarchy",
    "lighting_plausibility_and_exposure_integrity",
    "perspective_depth_and_focus_logic",
    "color_tone_and_texture",
    "natural_moment_and_subject_direction",
    "retouch_restraint",
    "ai_artifact_severity",
    "reference_truth_fidelity",
    "professional_direct_use_readiness",
]


_SCENE_REVIEW_DIMENSIONS = {
    PhotographySceneDomain.PORTRAIT: ["identity", "face_body_realism", "expression_pose_and_skin_finish"],
    PhotographySceneDomain.LANDSCAPE: ["depth_atmosphere_and_natural_material_realism"],
    PhotographySceneDomain.STILL_LIFE: ["material_edge_reflection_and_set_light_control"],
    PhotographySceneDomain.ANIMAL: ["individual_identity_anatomy_behavior_and_surface_detail"],
}


class PhotographyProviderAcceptanceDirector:
    """Prepare frozen real-output review cases without activating the Provider."""

    def baseline_single_hero_matrix(self) -> PhotographyProviderAcceptanceMatrix:
        """Gate-on M003 smoke/quality matrix: four scenes x text/reference."""
        return self._matrix(
            matrix_kind="p6_single_hero_provider_baseline",
            delivery_mode=PhotographyDeliveryMode.SINGLE_HERO,
            required_mainline_contracts=["PHOTOGRAPHY-MAINLINE-003"],
        )

    def release_professional_set_matrix(self) -> PhotographyProviderAcceptanceMatrix:
        """Release matrix, intentionally blocked until shared role execution lands."""
        return self._matrix(
            matrix_kind="p6_professional_set_provider_release",
            delivery_mode=PhotographyDeliveryMode.PROFESSIONAL_SET,
            required_mainline_contracts=["PHOTOGRAPHY-MAINLINE-003", "PHOTOGRAPHY-MAINLINE-004"],
        )

    def _matrix(
        self,
        *,
        matrix_kind: str,
        delivery_mode: PhotographyDeliveryMode,
        required_mainline_contracts: list[str],
    ) -> PhotographyProviderAcceptanceMatrix:
        cases: list[PhotographyProviderAcceptanceCase] = []
        for scene, text_prompt, reference_prompt, preservation, capabilities in _SCENE_CASES:
            cases.append(
                self._case(
                    matrix_kind=matrix_kind,
                    scene=scene,
                    input_mode=PhotographyInputMode.TEXT_TO_PHOTO,
                    delivery_mode=delivery_mode,
                    prompt=text_prompt,
                    preservation_controls={},
                    capabilities=capabilities,
                    required_mainline_contracts=required_mainline_contracts,
                )
            )
            cases.append(
                self._case(
                    matrix_kind=matrix_kind,
                    scene=scene,
                    input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
                    delivery_mode=delivery_mode,
                    prompt=reference_prompt,
                    preservation_controls=preservation,
                    capabilities=capabilities,
                    required_mainline_contracts=required_mainline_contracts,
                )
            )
        return PhotographyProviderAcceptanceMatrix(
            matrix_id=stable_id("photography_provider_acceptance", matrix_kind, *[case.case_id for case in cases]),
            matrix_kind=matrix_kind,
            cases=cases,
            shared_execution_contract={
                "provider_owner": "shared_v3_runtime",
                "review_owner": "shared_visual_review",
                "retry_owner": "shared_frozen_plan_retry",
                "final_delivery_owner": "shared_final_delivery_resolver",
                "photography_private_provider_or_retry": False,
            },
            human_review_contract={
                "reviewer_must_compare": ["raw_renderer", "foundation_only", "foundation_plus_photography"],
                "candidate_history": "append_only",
                "beginner_delivery": "final_delivery_only",
                "named_profile_score_cannot_override_truth_or_artifact_failures": True,
            },
            metadata={
                "owner": "photography_module",
                "direct_provider_call": False,
                "deployment_gate_required": True,
                "human_pixel_review_required": True,
                "professional_set_requires_mainline_004": delivery_mode == PhotographyDeliveryMode.PROFESSIONAL_SET,
            },
        )

    def _case(
        self,
        *,
        matrix_kind: str,
        scene: PhotographySceneDomain,
        input_mode: PhotographyInputMode,
        delivery_mode: PhotographyDeliveryMode,
        prompt: str,
        preservation_controls: dict[str, str],
        capabilities: list[str],
        required_mainline_contracts: list[str],
    ) -> PhotographyProviderAcceptanceCase:
        reference_role = None
        if input_mode == PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT:
            reference_role = {
                PhotographySceneDomain.PORTRAIT: "face_reference",
                PhotographySceneDomain.LANDSCAPE: "background_reference",
                PhotographySceneDomain.STILL_LIFE: "product_reference",
                PhotographySceneDomain.ANIMAL: "nonhuman_identity_reference",
            }[scene]
        required_capabilities = list(capabilities)
        if input_mode == PhotographyInputMode.TEXT_TO_PHOTO:
            required_capabilities = [item for item in required_capabilities if item != "reference_channel_policy"]
        return PhotographyProviderAcceptanceCase(
            case_id=stable_id("photography_provider_case", matrix_kind, scene.value, input_mode.value, delivery_mode.value),
            scene_domain=scene,
            input_mode=input_mode,
            delivery_mode=delivery_mode,
            user_prompt=prompt,
            required_reference_role=reference_role,
            preservation_controls=preservation_controls,
            required_shared_capabilities=required_capabilities,
            expected_review_dimensions=[*_UNIVERSAL_REVIEW_DIMENSIONS, *_SCENE_REVIEW_DIMENSIONS[scene]],
            required_mainline_contracts=list(required_mainline_contracts),
            metadata={
                "requires_high_fidelity_reference": reference_role == "nonhuman_identity_reference",
                "must_block_without_high_fidelity": reference_role == "nonhuman_identity_reference",
                "named_profile_selection": "general_default_or_user_explicit_ui_only",
                "reference_truth_owner": "shared_reference_channel_policy",
            },
        )
