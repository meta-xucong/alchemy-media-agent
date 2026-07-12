"""Metadata-only professional Photography review profile."""

from __future__ import annotations

from ....creative_core.rules import stable_id
from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographerProfileBinding,
    PhotoShotSpec,
    PhotographyBrief,
    PhotographyReviewReport,
    PhotographySceneDomain,
)


SCENE_CAPABILITY_IDS = {
    PhotographySceneDomain.PORTRAIT: "portrait_photography_direction",
    PhotographySceneDomain.LANDSCAPE: "landscape_photography_direction",
    PhotographySceneDomain.STILL_LIFE: "still_life_photography_direction",
    PhotographySceneDomain.ANIMAL: "animal_photography_direction",
}


class PhotographyProfessionalReviewer:
    """Review planned Photography metadata before any production renderer exists."""

    def review(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        shot_specs: list[PhotoShotSpec],
        contributions: list[CapabilityContribution],
        job_key: str,
    ) -> PhotographyReviewReport:
        checks: list[dict] = []
        warnings = list(brief.warnings)
        checks.append(
            self._check(
                "general_profile_default",
                profile_binding.binding_mode == "general"
                and profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID,
                "General Photography is the only active P4 shadow profile binding.",
            )
        )
        scene_contributions = [
            item for item in contributions if item.facts.get("scene_owned_scope") is True
        ]
        expected_scene_capability = SCENE_CAPABILITY_IDS.get(brief.scene_domain)
        checks.append(
            self._check(
                "scene_contribution_scope",
                (
                    not scene_contributions
                    if expected_scene_capability is None
                    else len(scene_contributions) == 1
                    and scene_contributions[0].capability_id == expected_scene_capability
                ),
                "Exactly the evidenced Photography scene director contributes; General stays neutral.",
            )
        )
        checks.append(
            self._check(
                "single_hero_scope",
                len(shot_specs) == 1 and shot_specs[0].role == "hero_photograph",
                "P3 shadow runtime creates exactly one hero photograph spec.",
            )
        )
        required_contribution_ids = {
            "photography_camera_optics",
            "photography_lighting_direction",
            "photography_composition_direction",
            "photography_color_finish",
            "photography_retouch_direction",
        }
        checks.append(
            self._check(
                "technique_contribution_coverage",
                required_contribution_ids <= {item.capability_id for item in contributions},
                "Camera, lighting, composition, color and retouch contributions are present.",
            )
        )
        checks.append(
            self._check(
                "no_provider_requirements",
                all(not item.provider_input_requirements for item in contributions),
                "Photography P3 planning does not call providers or create provider requirements.",
            )
        )
        checks.append(
            self._check(
                "named_profile_review_inactive",
                not any(item.review_contract.get("named_profile_fidelity_active") for item in contributions),
                "Named-profile technique review remains inactive.",
            )
        )
        checks.append(
            self._check(
                "reference_truth_channel_separation",
                bool(brief.reference_policy_summary),
                "Reference truth and prompt-owned channels are summarized separately.",
            )
        )
        issue_codes = sorted(
            {
                str(issue_code)
                for contribution in contributions
                for issue_code in contribution.review_contract.get("issue_codes", [])
            }
        )
        failed = [item["id"] for item in checks if item["status"] != "done"]
        if failed:
            warnings.append("photography_planning_review_attention:" + ",".join(failed))
        return PhotographyReviewReport(
            review_id=stable_id("photography_review", job_key, brief.brief_id, len(shot_specs)),
            status="attention" if failed else "ready",
            checks=checks,
            issue_codes=issue_codes,
            retryable_issue_codes=[
                code
                for code in issue_codes
                if code
                not in {
                    "named_profile_not_explicitly_selected",
                    "named_profile_binding_mismatch",
                    "named_profile_unavailable",
                }
            ],
            warnings=list(dict.fromkeys(warnings)),
            metadata={
                "source": "PhotographyProfessionalReviewer",
                "metadata_only_review": True,
                "phase": "P4_shadow_scene_directors",
                "scene_domain": brief.scene_domain.value,
                "profile_id": profile_binding.profile_id,
                "real_output_review_status": "not_run_until_production_activation",
            },
        )

    def _check(self, check_id: str, passed: bool, detail: str) -> dict:
        return {
            "id": check_id,
            "label": check_id.replace("_", " ").title(),
            "status": "done" if passed else "attention",
            "detail": detail,
        }
