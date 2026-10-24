from __future__ import annotations

from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.llm_brain.prompts import GENERAL_VARIATION_MATERIALIZATION_INSTRUCTIONS
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.general_suite_director import GeneralSuiteDirector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import ModeAwareRoleDirector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import RoleSpecificGenerationPlan


def _role_recipe(role_key: str, mode: str) -> dict:
    return {"role_key": role_key, "metadata": {"mode": mode}}


def test_project_route_history_uses_all_jobs_and_only_final_deliveries() -> None:
    records = {
        "job_first": [
            SimpleNamespace(output_id="delivered-hero", created_at="1", metadata={"mode_role_recipe": _role_recipe("cover_hero", "delivery_suite")}),
            SimpleNamespace(output_id="retry-only", created_at="2", metadata={"mode_role_recipe": _role_recipe("subject_focus", "delivery_suite")}),
            SimpleNamespace(output_id="other-mode", created_at="3", metadata={"mode_role_recipe": _role_recipe("concept_clean_bright", "creative_exploration")}),
        ],
        "job_second": [
            SimpleNamespace(output_id="delivered-angle", created_at="4", metadata={"mode_role_recipe": _role_recipe("side_or_three_quarter_angle", "delivery_suite")}),
            SimpleNamespace(output_id="delivered-hero", created_at="5", metadata={"mode_role_recipe": _role_recipe("cover_hero", "delivery_suite")}),
        ],
        "job_legacy": [
            SimpleNamespace(output_id="legacy-unreviewed", created_at="6", metadata={"mode_role_recipe": _role_recipe("wide_scene_or_context", "delivery_suite")}),
        ],
        "job_failed": [
            SimpleNamespace(output_id="failed-attempt", created_at="7", metadata={"mode_role_recipe": _role_recipe("detail_focus", "delivery_suite")}),
        ],
    }
    statuses = {
        "job_first": SimpleNamespace(
            status="generated",
            metadata={
                "final_delivery": {"delivery_gate_applies": True, "automatic_delivery_available": True},
                "post_generation_review": {"recommended_output_ids": ["delivered-hero", "other-mode"]},
            },
        ),
        "job_second": SimpleNamespace(
            status="generated",
            metadata={
                "final_delivery": {"delivery_gate_applies": True, "automatic_delivery_available": True},
                "post_generation_review": {"recommended_output_ids": ["delivered-angle", "delivered-hero"]},
            },
        ),
        "job_legacy": SimpleNamespace(status="generated", metadata={}),
        "job_failed": SimpleNamespace(status="failed", metadata={}),
    }
    service = V3ProjectModeService.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(list_by_job=lambda job_id: records[job_id]),
        get_job=lambda job_id: statuses[job_id],
    )
    service._delivery_annotations_for_records = lambda job_records, *, final_output_ids=None: {
            item.output_id: {
                "delivery_state": "final_delivery" if final_output_ids is None or item.output_id in final_output_ids else "process_only"
            }
            for item in job_records
        }
    project = SimpleNamespace(
        project_id="project_doc347_history",
        job_ids=["job_first", "job_second", "job_legacy", "job_failed"],
        selected_output_refs=[],
        user_goal="Continue the same image set",
    )

    completed = V3ProjectModeService._project_completed_general_suite_role_keys(  # noqa: SLF001
        service,
        project=project,
        mode="delivery_suite",
    )

    assert completed == ["cover_hero", "side_or_three_quarter_angle"]
    plan = V3ProjectModeService._project_general_suite_role_plan(  # noqa: SLF001
        service,
        project=project,
        template_id="general_template",
        continuation_instruction=None,
        metadata={"effective_variation_mode": "delivery_suite", "requested_image_count": 2},
    )
    assert plan["metadata"]["completed_role_keys"] == completed
    project.selected_output_refs = ["selected-ai-output"]
    generated_anchor_plan = V3ProjectModeService._project_general_suite_role_plan(  # noqa: SLF001
        service,
        project=project,
        template_id="general_template",
        continuation_instruction=None,
        metadata={"effective_variation_mode": "delivery_suite", "requested_image_count": 2},
    )
    assert generated_anchor_plan["metadata"]["has_generated_reference_anchor"] is True


def test_legacy_route_mode_comes_from_source_job_before_delivery_projection() -> None:
    service = V3ProjectModeService.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_job=lambda _job_id: [
                SimpleNamespace(
                    output_id="legacy-route",
                    created_at="1",
                    metadata={"mode_role_recipe": {"role_key": "cover_hero"}},
                )
            ]
        ),
        get_job=lambda _job_id: SimpleNamespace(
            job_id="job_legacy_route",
            status="generated",
            metadata={
                "effective_variation_mode": "delivery_suite",
                "final_delivery": {
                    "delivery_gate_applies": True,
                    "automatic_delivery_available": True,
                },
                "post_generation_review": {"recommended_output_ids": ["legacy-route"]},
            },
        ),
    )
    service._delivery_annotations_for_records = lambda records, *, final_output_ids=None: {
        item.output_id: {"delivery_state": "final_delivery"}
        for item in records
    }
    project = SimpleNamespace(job_ids=["job_legacy_route"], selected_output_refs=[])

    completed = V3ProjectModeService._project_completed_general_suite_role_keys(  # noqa: SLF001
        service,
        project=project,
        mode="delivery_suite",
    )

    assert completed == ["cover_hero"]


def test_selected_cross_mode_output_flows_from_project_plan_to_runtime_first_row() -> None:
    service = V3ProjectModeService.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_job=lambda _job_id: [
                SimpleNamespace(
                    output_id="selected-ai-output",
                    created_at="1",
                    metadata={
                        "mode_role_recipe": _role_recipe("vertical_cover", "format_layout_adaptation")
                    },
                )
            ]
        ),
        get_job=lambda _job_id: SimpleNamespace(
            job_id="job_previous_mode",
            status="generated",
            metadata={
                "effective_variation_mode": "format_layout_adaptation",
                "final_delivery": {
                    "delivery_gate_applies": True,
                    "automatic_delivery_available": True,
                },
                "post_generation_review": {"recommended_output_ids": ["selected-ai-output"]},
            },
        ),
    )
    service._delivery_annotations_for_records = lambda records, *, final_output_ids=None: {
        item.output_id: {"delivery_state": "final_delivery"}
        for item in records
    }
    project = SimpleNamespace(
        project_id="project_doc347_integrated",
        job_ids=["job_previous_mode"],
        selected_output_refs=["selected-ai-output"],
        user_goal="Continue this image set",
    )
    project_plan = V3ProjectModeService._project_general_suite_role_plan(  # noqa: SLF001
        service,
        project=project,
        template_id="general_template",
        continuation_instruction=None,
        metadata={"effective_variation_mode": "delivery_suite", "requested_image_count": 2},
    )

    runtime_request = ScenarioRuntime()._bind_initial_general_variation_contract(  # noqa: SLF001
        ScenarioRuntimeRequest(
            user_input="Continue this image set",
            metadata={
                "requested_image_count": 2,
                "project_id": project.project_id,
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
                "variation_mode_source": "project_context",
                "resolved_scenario_id": "general_creative",
                "resolved_template_id": "general_template",
                "project_context_snapshot": {
                    "template_id": "general_template",
                    "general_suite_role_plan": project_plan,
                },
            },
        ),
        SimpleNamespace(
            manifest=SimpleNamespace(scenario_id="general_creative"),
            selected_mode_id=None,
            selected_preset_id=None,
        ),
        SimpleNamespace(effective_image_count=2),
    )

    role_plan = RoleSpecificGenerationPlan.model_validate(
        runtime_request.metadata["variation_execution_role_plan"]
    )
    axes = set(role_plan.role_recipes[0].variation_axes)
    assert role_plan.metadata["completed_role_keys"] == []
    assert role_plan.metadata["has_generated_reference_anchor"] is True
    assert {"viewpoint", "pose", "gesture", "context"}.intersection(axes)


def test_role_director_skips_completed_routes_and_renumbers_current_batch() -> None:
    plan = ModeAwareRoleDirector().build(
        project_id="project_doc347",
        job_id="job_continuation",
        user_input="Continue the same image set",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        completed_role_keys=["cover_hero", "subject_focus"],
    )

    assert {"viewpoint", "pose"}.intersection(plan.role_recipes[0].variation_axes)
    assert [item.role_key for item in plan.role_recipes] == [
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    ]
    assert [item.index for item in plan.role_recipes] == [1, 2]
    contract = ModeAwareRoleDirector().build_variation_execution_contract(
        role_plan=plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    assert {"viewpoint", "pose"}.intersection(contract.outputs[0].variation_axes)


def test_uploaded_reference_without_prior_delivery_starts_at_first_route() -> None:
    plan = ModeAwareRoleDirector().build(
        project_id="project_doc347_uploaded",
        job_id="job_first_batch",
        user_input="Create the first image from this uploaded reference",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
    )

    assert plan.role_recipes[0].role_key == "cover_hero"
    assert plan.metadata["completed_role_keys"] == []
    assert not {"viewpoint", "pose", "gesture", "context"}.intersection(
        plan.role_recipes[0].variation_axes
    )


def test_generated_reference_from_another_mode_changes_first_delivery_suite_shot() -> None:
    director = ModeAwareRoleDirector()
    plan = director.build(
        project_id="project_doc347_cross_mode_anchor",
        job_id="job_doc347_cross_mode_anchor",
        user_input="Continue from this generated reference in a delivery suite",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_generated_reference_anchor=True,
    )

    assert plan.metadata["completed_role_keys"] == []
    assert plan.metadata["has_generated_reference_anchor"] is True
    assert {"viewpoint", "pose", "gesture", "context"}.intersection(
        plan.role_recipes[0].variation_axes
    )
    contract = director.build_variation_execution_contract(
        role_plan=plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    assert {"viewpoint", "pose", "gesture", "context"}.intersection(
        contract.outputs[0].variation_axes
    )


def test_all_general_modes_continue_after_their_own_completed_first_route() -> None:
    director = ModeAwareRoleDirector()
    for mode in (
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    ):
        original = director.build(
            project_id="project_doc347_modes",
            job_id=f"job_{mode}_first",
            user_input="Continue this image set",
            mode=mode,
            requested_image_count=2,
            scenario_id="general_creative",
            template_id="general_template",
        )
        continued = director.build(
            project_id="project_doc347_modes",
            job_id=f"job_{mode}_next",
            user_input="Continue this image set",
            mode=mode,
            requested_image_count=2,
            scenario_id="general_creative",
            template_id="general_template",
            completed_role_keys=[original.role_recipes[0].role_key],
        )
        assert continued.role_recipes[0].role_key == original.role_recipes[1].role_key
        assert [item.index for item in continued.role_recipes] == [1, 2]


def test_suite_projection_reuses_the_runtime_role_plan() -> None:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc347_projection",
        job_id="job_doc347_projection",
        user_input="Continue the set",
        mode="creative_exploration",
        requested_image_count=2,
        scenario_id="general_creative",
        template_id="general_template",
        completed_role_keys=["concept_clean_bright"],
    )
    suite = GeneralSuiteDirector(director).build(
        project_id=role_plan.project_id,
        job_id=role_plan.job_id,
        user_input="Continue the set",
        variation_mode=role_plan.mode,
        requested_image_count=role_plan.requested_image_count,
        has_identity_anchor=False,
        role_plan=role_plan,
    )

    projected = RoleSpecificGenerationPlan.model_validate(suite.metadata["role_specific_generation_plan"])
    assert projected == role_plan
    assert [role.metadata["mode_role_recipe"]["role_key"] for role in suite.roles] == [
        recipe.role_key for recipe in role_plan.role_recipes
    ]


def test_brain_applies_the_frozen_route_to_the_first_continuation_row() -> None:
    assert "output 1 is the baseline" not in GENERAL_VARIATION_MATERIALIZATION_INSTRUCTIONS
    assert "including output 1" in GENERAL_VARIATION_MATERIALIZATION_INSTRUCTIONS


def test_runtime_freezes_and_reuses_one_continuation_role_plan() -> None:
    runtime = ScenarioRuntime()
    module = runtime.shared_capability_registry.get("visual_capability_cluster")
    director = module.mode_role_director
    original_build = director.build
    calls: list[dict] = []

    def tracked_build(**kwargs):
        calls.append(dict(kwargs))
        return original_build(**kwargs)

    director.build = tracked_build
    request = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        ScenarioRuntimeRequest(
            user_input="Continue the same image set",
            metadata={
                "requested_image_count": 2,
                "project_id": "project_doc347_runtime",
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
                "variation_mode_source": "project_context",
                "resolved_scenario_id": "general_creative",
                "resolved_template_id": "general_template",
                "project_context_snapshot": {
                    "template_id": "general_template",
                    "general_suite_role_plan": {
                        "variation_mode": "delivery_suite",
                        "metadata": {
                            "completed_role_keys": ["hero_subject"],
                            "has_generated_reference_anchor": True,
                        },
                    },
                },
            },
        ),
        SimpleNamespace(
            manifest=SimpleNamespace(scenario_id="general_creative"),
            selected_mode_id=None,
            selected_preset_id=None,
        ),
        SimpleNamespace(effective_image_count=2),
    )

    saved_plan = RoleSpecificGenerationPlan.model_validate(request.metadata["variation_execution_role_plan"])
    assert len(calls) == 1
    assert calls[0]["completed_role_keys"] == ["hero_subject"]
    assert calls[0]["has_generated_reference_anchor"] is True
    assert saved_plan.metadata["has_generated_reference_anchor"] is True
    assert [item.role_key for item in saved_plan.role_recipes] == ["detail_focus", "alternate_angle"]
    projected_plan = request.metadata["project_context_snapshot"]["general_suite_role_plan"]
    assert projected_plan["metadata"]["role_specific_generation_plan"] == saved_plan.model_dump(mode="json")
    assert projected_plan["metadata"]["role_specific_generation_plan"]["metadata"]["has_generated_reference_anchor"] is True
    assert request.metadata["variation_execution_contract"]["outputs"][0]["output_index"] == 1


def test_runtime_reuses_saved_role_plan_when_rebinding_saved_contract() -> None:
    runtime = ScenarioRuntime()
    module = runtime.shared_capability_registry.get("visual_capability_cluster")
    director = module.mode_role_director
    saved_plan = director.build(
        project_id="project_doc347_saved",
        job_id="job_saved",
        user_input="Continue the same image set",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        completed_role_keys=["cover_hero"],
    )
    contract = director.build_variation_execution_contract(
        role_plan=saved_plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    drifted_contract = contract.model_copy(
        update={
            "outputs": (
                contract.outputs[0].model_copy(update={"variation_axes": ("format_vertical",)}),
                *contract.outputs[1:],
            ),
            "contract_digest": "",
        }
    )
    drifted_contract = drifted_contract.model_copy(
        update={"contract_digest": drifted_contract.computed_digest()}
    )

    def unexpected_rebuild(**kwargs):
        raise AssertionError("saved route plan should be reused")

    director.build = unexpected_rebuild
    request = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        ScenarioRuntimeRequest(
            user_input="Continue the same image set",
            metadata={
                "requested_image_count": 2,
                "project_id": "project_doc347_saved",
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
                "variation_mode_source": "project_context",
                "resolved_scenario_id": "general_creative",
                "resolved_template_id": "general_template",
                "variation_execution_contract": drifted_contract.model_dump(mode="json"),
                "variation_execution_role_plan": saved_plan.model_dump(mode="json"),
            },
        ),
        SimpleNamespace(
            manifest=SimpleNamespace(scenario_id="general_creative"),
            selected_mode_id=None,
            selected_preset_id=None,
        ),
        SimpleNamespace(effective_image_count=2),
    )

    rebound_plan = RoleSpecificGenerationPlan.model_validate(request.metadata["variation_execution_role_plan"])
    assert rebound_plan == saved_plan
    rebound_contract = request.metadata["variation_execution_contract"]
    assert rebound_contract == contract.model_dump(mode="json")
