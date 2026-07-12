"""Planning-only Photography Scenario Pack planner."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .brief_director import PhotographyBriefDirector
from .contracts import (
    PhotographerProfileBinding,
    PhotographyPackOutput,
    PhotographyUserControls,
)
from .profile_catalog import PhotographerProfileCatalog
from .review import PhotographyProfessionalReviewer
from .scene_directors import FirstWavePhotographySceneDirectorRouter
from .shot_list_director import PhotographyShotListDirector
from .technique_modules.general import GeneralPhotographyTechniqueDirector
from .technique_modules.named_profile import NamedPhotographerTechniqueCompiler


class PhotographyScenarioPackPlanner:
    """Compose module-owned Photography planning stages without production activation."""

    def __init__(
        self,
        *,
        profile_catalog: PhotographerProfileCatalog | None = None,
        brief_director: PhotographyBriefDirector | None = None,
        scene_director_router: FirstWavePhotographySceneDirectorRouter | None = None,
        technique_director: GeneralPhotographyTechniqueDirector | None = None,
        named_profile_compiler: NamedPhotographerTechniqueCompiler | None = None,
        shot_list_director: PhotographyShotListDirector | None = None,
        reviewer: PhotographyProfessionalReviewer | None = None,
        named_profiles_enabled: bool = False,
    ) -> None:
        self.profile_catalog = profile_catalog or PhotographerProfileCatalog()
        self.brief_director = brief_director or PhotographyBriefDirector()
        self.scene_director_router = (
            scene_director_router or FirstWavePhotographySceneDirectorRouter()
        )
        self.technique_director = technique_director or GeneralPhotographyTechniqueDirector()
        self.named_profile_compiler = named_profile_compiler or NamedPhotographerTechniqueCompiler()
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
        return self._plan_with_pinned_binding(
            user_input=user_input,
            controls=controls_model,
            uploaded_asset_ids=uploaded,
            job_key=job_key,
            llm_profile_proposal=llm_profile_proposal,
            profile_binding=profile_binding,
            binding_source="shadow_local_controls",
        )

    def plan_from_pinned_binding(
        self,
        *,
        user_input: str,
        profile_binding: Any,
        controls: PhotographyUserControls | dict[str, Any] | None = None,
        uploaded_asset_ids: list[str] | None = None,
        job_key: str = "photography_pinned_job",
        llm_profile_proposal: str | None = None,
    ) -> PhotographyPackOutput:
        """Plan from the immutable mainline binding, without reselecting a profile.

        This is the only entry point intended for a future activated runtime.
        ``plan`` remains a P1-P4 shadow-test helper and is never a public API.
        """
        controls_model = self._controls(controls)
        local_binding = self._coerce_pinned_binding(profile_binding)
        return self._plan_with_pinned_binding(
            user_input=user_input,
            controls=controls_model,
            uploaded_asset_ids=list(uploaded_asset_ids or []),
            job_key=job_key,
            llm_profile_proposal=llm_profile_proposal,
            profile_binding=local_binding,
            binding_source="mainline_immutable_binding",
        )

    def _plan_with_pinned_binding(
        self,
        *,
        user_input: str,
        controls: PhotographyUserControls,
        uploaded_asset_ids: list[str],
        job_key: str,
        llm_profile_proposal: str | None,
        profile_binding: Any,
        binding_source: str,
    ) -> PhotographyPackOutput:
        if profile_binding.binding_mode == "named" and not self.named_profiles_enabled:
            raise ValueError("named_profiles_not_active_in_p3_general_photography_runtime")
        brief = self.brief_director.build(
            user_input=user_input,
            controls=controls,
            uploaded_asset_ids=uploaded_asset_ids,
            profile_binding=profile_binding,
            job_key=job_key,
            llm_profile_proposal=llm_profile_proposal,
            named_profiles_enabled=self.named_profiles_enabled,
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
        named_contributions = []
        if profile_binding.binding_mode == "named":
            named_contributions = [
                self.named_profile_compiler.build_contribution(
                    brief=brief,
                    profile_binding=profile_binding,
                    profile_catalog=self.profile_catalog,
                    activation_plan_id=activation_plan_id,
                )
            ]
        scene_contributions = self.scene_director_router.build_contributions(
            brief=brief,
            profile_binding=profile_binding,
            activation_plan_id=activation_plan_id,
        )
        planning_contributions = [*contributions, *named_contributions, *scene_contributions]
        shot_specs = self.shot_list_director.plan(
            brief=brief,
            controls=controls,
            contributions=planning_contributions,
            job_key=job_key,
        )
        review = self.reviewer.review(
            brief=brief,
            profile_binding=profile_binding,
            shot_specs=shot_specs,
            contributions=planning_contributions,
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
            technique_contributions=[*contributions, *named_contributions],
            scene_contributions=scene_contributions,
            shot_specs=shot_specs,
            review=review,
            warnings=warnings,
            metadata={
                "source": "PhotographyScenarioPackPlanner",
                "scenario_id": "photography",
                "template_id": "photography_template",
                "phase": "P5_named_profile_shadow_runtime" if profile_binding.binding_mode == "named" else "P4_shadow_scene_directors",
                "planning_only": True,
                "production_activation_ready": False,
                "registered_in_default_scenario_registry": False,
                "direct_provider_call": False,
                "imports_v1_v2_runtime": False,
                "named_profiles_enabled": self.named_profiles_enabled,
                "llm_profile_proposal_ignored": bool(llm_profile_proposal),
                "activation_plan_id": activation_plan_id,
                "catalog_version": profile_binding.catalog_version,
                "profile_binding_source": binding_source,
            },
        )

    def _controls(self, controls: PhotographyUserControls | dict[str, Any] | None) -> PhotographyUserControls:
        if controls is None:
            return PhotographyUserControls()
        if isinstance(controls, PhotographyUserControls):
            return controls
        return PhotographyUserControls.model_validate(controls)

    def _coerce_pinned_binding(self, binding: Any) -> PhotographerProfileBinding:
        """Adapt a mainline server binding for module-local planning output.

        The source binding stays authoritative; `pinned_at` and public display
        metadata are retained as opaque audit facts because the P1 local model
        predates the mainline contract.
        """
        if isinstance(binding, PhotographerProfileBinding):
            return binding
        payload = binding.model_dump(mode="json") if hasattr(binding, "model_dump") else dict(binding)
        metadata = dict(payload.get("metadata") or {})
        for key in ("profile_display_name", "pinned_at"):
            if payload.get(key) is not None:
                metadata[f"mainline_{key}"] = payload[key]
        payload["metadata"] = {
            **metadata,
            "binding_authority": "mainline_immutable_binding",
        }
        return PhotographerProfileBinding.model_validate(payload)
