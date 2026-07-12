"""Planning-only Photography Scenario Pack planner."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .brief_director import PhotographyBriefDirector
from .contracts import (
    PhotographyPackOutput,
    PhotographyUserControls,
)
from .profile_catalog import PhotographerProfileCatalog
from .review import PhotographyProfessionalReviewer
from .shot_list_director import PhotographyShotListDirector
from .technique_modules.general import GeneralPhotographyTechniqueDirector


class PhotographyScenarioPackPlanner:
    """Compose module-owned Photography planning stages without production activation."""

    def __init__(
        self,
        *,
        profile_catalog: PhotographerProfileCatalog | None = None,
        brief_director: PhotographyBriefDirector | None = None,
        technique_director: GeneralPhotographyTechniqueDirector | None = None,
        shot_list_director: PhotographyShotListDirector | None = None,
        reviewer: PhotographyProfessionalReviewer | None = None,
        named_profiles_enabled: bool = False,
    ) -> None:
        self.profile_catalog = profile_catalog or PhotographerProfileCatalog()
        self.brief_director = brief_director or PhotographyBriefDirector()
        self.technique_director = technique_director or GeneralPhotographyTechniqueDirector()
        self.shot_list_director = shot_list_director or PhotographyShotListDirector()
        self.reviewer = reviewer or PhotographyProfessionalReviewer()
        self.named_profiles_enabled = named_profiles_enabled

    def plan(
        self,
        *,
        user_input: str,
        controls: PhotographyUserControls | dict[str, Any] | None = None,
        uploaded_asset_ids: list[str] | None = None,
        job_key: str = "photography_shadow_job",
        llm_profile_proposal: str | None = None,
    ) -> PhotographyPackOutput:
        controls_model = self._controls(controls)
        uploaded = list(uploaded_asset_ids or [])
        profile_binding = self.profile_catalog.resolve_binding(controls_model)
        if profile_binding.binding_mode == "named" and not self.named_profiles_enabled:
            raise ValueError("named_profiles_not_active_in_p3_general_photography_runtime")
        brief = self.brief_director.build(
            user_input=user_input,
            controls=controls_model,
            uploaded_asset_ids=uploaded,
            profile_binding=profile_binding,
            job_key=job_key,
            llm_profile_proposal=llm_profile_proposal,
        )
        activation_plan_id = stable_id(
            "photography_shadow_plan",
            job_key,
            profile_binding.profile_id,
            profile_binding.technique_package_checksum,
            brief.brief_id,
        )
        contributions = self.technique_director.build_contributions(
            brief=brief,
            profile_binding=profile_binding,
            activation_plan_id=activation_plan_id,
        )
        shot_specs = self.shot_list_director.plan(
            brief=brief,
            controls=controls_model,
            contributions=contributions,
            job_key=job_key,
        )
        review = self.reviewer.review(
            brief=brief,
            profile_binding=profile_binding,
            shot_specs=shot_specs,
            contributions=contributions,
            job_key=job_key,
        )
        warnings = list(
            dict.fromkeys(
                [
                    *brief.warnings,
                    *review.warnings,
                ]
            )
        )
        return PhotographyPackOutput(
            profile_binding=profile_binding,
            brief=brief,
            technique_contributions=contributions,
            shot_specs=shot_specs,
            review=review,
            warnings=warnings,
            metadata={
                "source": "PhotographyScenarioPackPlanner",
                "scenario_id": "photography",
                "template_id": "photography_template",
                "phase": "P3_shadow_general_runtime",
                "planning_only": True,
                "production_activation_ready": False,
                "registered_in_default_scenario_registry": False,
                "direct_provider_call": False,
                "imports_v1_v2_runtime": False,
                "named_profiles_enabled": self.named_profiles_enabled,
                "llm_profile_proposal_ignored": bool(llm_profile_proposal),
                "activation_plan_id": activation_plan_id,
                "catalog_version": profile_binding.catalog_version,
            },
        )

    def _controls(self, controls: PhotographyUserControls | dict[str, Any] | None) -> PhotographyUserControls:
        if controls is None:
            return PhotographyUserControls()
        if isinstance(controls, PhotographyUserControls):
            return controls
        return PhotographyUserControls.model_validate(controls)
