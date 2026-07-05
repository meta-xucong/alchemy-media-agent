"""Doc58/Doc59 General Template suite role director."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import GeneralSuiteRole, GeneralSuiteRolePlan
from .mode_role_director import ModeAwareRoleDirector, normalize_mode


class GeneralSuiteDirector:
    """Plan purposeful image roles for General Template batches."""

    def __init__(self, mode_role_director: ModeAwareRoleDirector | None = None) -> None:
        self.mode_role_director = mode_role_director or ModeAwareRoleDirector()

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        variation_mode: str,
        requested_image_count: int,
        has_identity_anchor: bool,
        subject_type: str = "generic",
        scenario_id: str | None = None,
        template_id: str | None = None,
    ) -> GeneralSuiteRolePlan:
        mode = normalize_mode(variation_mode)
        count = max(1, min(4, int(requested_image_count or 1)))
        role_plan = self.mode_role_director.build(
            project_id=project_id,
            job_id=job_id,
            user_input=user_input,
            mode=mode,
            requested_image_count=count,
            subject_type=subject_type,
            scenario_id=scenario_id,
            template_id=template_id,
            has_identity_anchor=has_identity_anchor,
        )
        role_models = [
            GeneralSuiteRole(
                role_id=stable_id("general_suite_role", project_id, job_id, mode, recipe.index, recipe.role_key),
                label=recipe.role_key,
                purpose=recipe.purpose,
                shot_instruction=recipe.prompt_pressure,
                variation_axes=list(recipe.variation_axes),
                keep_rules=list(recipe.must_keep_rules),
                avoid_rules=list(recipe.must_not_rules),
                metadata={
                    "index": recipe.index,
                    "has_identity_anchor": has_identity_anchor,
                    "mode_role_recipe": recipe.model_dump(mode="json"),
                    "mode": mode,
                    "subject_type": subject_type,
                    "doc": "59",
                },
            )
            for recipe in role_plan.role_recipes
        ]
        prompt_additions = [
            f"Image {index}: {role.label} - {role.shot_instruction}"
            for index, role in enumerate(role_models, 1)
        ]
        return GeneralSuiteRolePlan(
            plan_id=stable_id("general_suite_role_plan", project_id, job_id, mode, count, user_input),
            project_id=project_id,
            job_id=job_id,
            variation_mode=mode,
            requested_image_count=count,
            roles=role_models,
            prompt_additions=prompt_additions,
            batch_review_rules=[
                role_plan.policy.review_priority,
                role_plan.policy.role_difference_requirement,
                "preserve the shared visual direction across all roles",
            ],
            user_visible_summary=role_plan.user_visible_summary,
            metadata={
                "doc": "59",
                "role_count": len(role_models),
                "mode_execution_policy": role_plan.policy.model_dump(mode="json"),
                "role_specific_generation_plan": role_plan.model_dump(mode="json"),
            },
        )
