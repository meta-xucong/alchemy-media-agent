from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.product_api.contracts import SelectResultRequest
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatus, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.contracts import CreateProjectJobRequest
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.variation_modes import (
    canonical_general_variation_mode,
    resolve_general_variation_mode,
)


def test_selection_request_accepts_plural_ids_and_legacy_singular_ids() -> None:
    request = SelectResultRequest.model_validate(
        {
            "selected_candidate_id": "candidate-legacy",
            "selected_candidate_ids": ["candidate-a", "candidate-legacy", "candidate-a"],
            "selected_asset_id": "asset-legacy",
            "selected_asset_ids": ["asset-a", "asset-legacy", "asset-a"],
        }
    )

    assert request.selected_candidate_ids == ["candidate-legacy", "candidate-a"]
    assert request.selected_asset_ids == ["asset-legacy", "asset-a"]


def test_product_selection_keeps_all_requested_candidate_branches() -> None:
    result = SimpleNamespace(
        asset_pack=SimpleNamespace(
            assets=[
                SimpleNamespace(asset_id="asset-a", metadata={"selected_candidate_id": "candidate-a"}),
                SimpleNamespace(asset_id="asset-b", metadata={"selected_candidate_id": "candidate-b"}),
                SimpleNamespace(asset_id="asset-c", metadata={"selected_candidate_id": "candidate-c"}),
            ]
        )
    )
    request = SelectResultRequest(selected_candidate_ids=["candidate-a", "candidate-c"])

    selected = V3ProductApiService._selected_assets(V3ProductApiService.__new__(V3ProductApiService), result, request)

    assert [asset.asset_id for asset in selected] == ["asset-a", "asset-c"]


def test_mixed_selection_uses_union_without_falling_back_to_unrelated_assets() -> None:
    result = SimpleNamespace(
        asset_pack=SimpleNamespace(
            assets=[
                SimpleNamespace(asset_id="asset-a", metadata={"selected_candidate_id": "candidate-a"}),
                SimpleNamespace(asset_id="asset-b", metadata={"selected_candidate_id": "candidate-b"}),
            ]
        )
    )
    request = SelectResultRequest(
        selected_candidate_ids=["missing-candidate"],
        selected_asset_ids=["asset-b"],
    )

    selected = V3ProductApiService._selected_assets(V3ProductApiService.__new__(V3ProductApiService), result, request)

    assert [asset.asset_id for asset in selected] == ["asset-b"]


def test_project_output_reference_resolution_keeps_mixed_selection_union() -> None:
    service = V3ProjectModeService.__new__(V3ProjectModeService)
    service._canonical_selected_output_ref = lambda _project, ref: ref
    project = SimpleNamespace(project_id="project-1")
    status = SimpleNamespace(
        job_id="job-1",
        candidates=[
            SimpleNamespace(
                candidate_id="candidate-a",
                asset_id="asset-a",
                output_id="output-a",
                preview_url=None,
                preview_uri=None,
                thumbnail_url=None,
                download_url=None,
                recommendation=None,
            ),
            SimpleNamespace(
                candidate_id="candidate-b",
                asset_id="asset-b",
                output_id="output-b",
                preview_url=None,
                preview_uri=None,
                thumbnail_url=None,
                download_url=None,
                recommendation=None,
            ),
        ],
        asset_series=[
            SimpleNamespace(
                asset_id="asset-a",
                selected_candidate_id="candidate-a",
                output_id="output-a",
                preview_url=None,
                preview_uri=None,
                thumbnail_url=None,
                download_url=None,
            ),
            SimpleNamespace(
                asset_id="asset-b",
                selected_candidate_id="candidate-b",
                output_id="output-b",
                preview_url=None,
                preview_uri=None,
                thumbnail_url=None,
                download_url=None,
            ),
        ],
    )

    refs, unresolved = service._resolved_output_refs_for_status(
        project,
        status,
        selected_candidate_ids={"candidate-a"},
        selected_asset_ids={"asset-b"},
    )

    # Both selectors are already represented by the status projection.  The
    # recovery adapter must not require an unrelated output store in this
    # branch; canonical materialization remains the next gate in production.
    assert unresolved == []
    assert [ref.output_id for ref in refs] == ["output-a", "output-b"]


def test_project_reopens_with_server_resolved_general_generation_preferences() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a visual set"})["project"]

    request = CreateProjectJobRequest.model_validate(
        {
            "template_id": "general_template",
            "user_input": "沿这个方向做一组图",
            "metadata": {
                "variation_mode": "auto",
                "inferred_variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
                "variation_mode_source": "auto",
                "requested_image_count": 3,
                "requested_image_size": "1536x1024",
            },
        }
    )
    operation = handlers.begin_project_planning_operation(project["project_id"], request.model_dump(mode="json"))
    assert operation["state"] == "planning"

    reopened = handlers.get_project(project["project_id"], view="summary")["project"]
    preferences = reopened["generation_preferences"]["general"]
    assert preferences["variation_mode"] == "auto"
    assert preferences["effective_variation_mode"] == "delivery_suite"
    assert preferences["requested_image_count"] == 3
    assert preferences["requested_image_size"] == "1536x1024"


@pytest.mark.parametrize(
    ("user_input", "requested_count", "expected_mode"),
    [
        ("同一个人物，多给几张相似备选", 3, "selection_candidates"),
        ("沿这个方向做一组图", 3, "delivery_suite"),
        ("探索不同方向，尝试新风格", 3, "creative_exploration"),
        ("做一张横版封面，留出标题空间", 1, "format_layout_adaptation"),
    ],
)
def test_server_resolves_general_mode_from_raw_request_without_metadata(
    user_input: str,
    requested_count: int,
    expected_mode: str,
) -> None:
    handlers = V3ProductRouteHandlers()
    service = handlers.project_service

    contract = service._general_variation_contract(  # noqa: SLF001
        {"requested_image_count": requested_count},
        user_input=user_input,
        requested_count=requested_count,
    )

    assert contract["variation_mode"] == "auto"
    assert contract["inferred_variation_mode"] == expected_mode
    assert contract["effective_variation_mode"] == expected_mode
    assert contract["continuation_mode"] == expected_mode


def test_explicit_general_override_wins_over_stale_effective_mode() -> None:
    handlers = V3ProductRouteHandlers()
    service = handlers.project_service

    contract = service._general_variation_contract(  # noqa: SLF001
        {
            "variation_mode_override": "creative_exploration",
            "variation_mode": "auto",
            "effective_variation_mode": "selection_candidates",
            "inferred_variation_mode": "selection_candidates",
            "requested_image_count": 2,
        },
        user_input="Create the next image set.",
        requested_count=2,
    )

    assert contract["variation_mode"] == "creative_exploration"
    assert contract["effective_variation_mode"] == "creative_exploration"
    assert contract["continuation_mode"] == "creative_exploration"


def test_general_mode_aliases_are_canonical_across_shared_resolver() -> None:
    expected = {
        "similar_options": "selection_candidates",
        "suite_expansion": "delivery_suite",
        "creative_explore": "creative_exploration",
        "layout_adaptation": "format_layout_adaptation",
        "format_adaptation": "format_layout_adaptation",
    }

    for alias, mode in expected.items():
        assert canonical_general_variation_mode(alias) == mode
        resolved = resolve_general_variation_mode(
            {"variation_mode_override": alias},
            user_input="Create a set.",
            requested_count=2,
        )
        assert resolved["effective_variation_mode"] == mode


def test_auto_browser_derived_continuation_does_not_become_manual_mode() -> None:
    resolved = resolve_general_variation_mode(
        {
            "variation_mode": "auto",
            "effective_variation_mode": "selection_candidates",
            "continuation_mode": "selection_candidates",
            "inferred_variation_mode": "creative_exploration",
            "variation_mode_source": "auto",
        },
        user_input="Explore different directions and try a new style.",
        requested_count=2,
    )

    assert resolved["variation_mode"] == "auto"
    assert resolved["effective_variation_mode"] == "creative_exploration"
    assert resolved["variation_mode_source"] == "auto"


def test_current_inferred_mode_wins_over_a_reused_frozen_contract() -> None:
    resolved = resolve_general_variation_mode(
        {
            "variation_mode": "auto",
            "inferred_variation_mode": "creative_exploration",
            "variation_execution_mode": "selection_candidates",
            "variation_execution_contract": {"mode": "selection_candidates"},
        },
        user_input="Explore different directions and try a new style.",
        requested_count=2,
    )

    assert resolved["effective_variation_mode"] == "creative_exploration"
    assert resolved["variation_mode_source"] == "auto"


def test_project_context_override_suppresses_persisted_effective_mode() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a visual set"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])

    context = handlers.project_service._build_context(  # noqa: SLF001
        project_record,
        template_id="general_template",
        continuation_instruction="Create the next image set.",
        generation_overrides={
            "variation_mode_override": "format_adaptation",
            "variation_mode": "auto",
            "effective_variation_mode": "selection_candidates",
            "requested_image_count": 2,
        },
    )

    assert context.general_suite_role_plan["variation_mode"] == "format_layout_adaptation"
    assert context.metadata["effective_variation_mode"] == "format_layout_adaptation"


def test_project_job_carries_server_resolved_mode_through_context_and_brain_request(monkeypatch) -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a visual set"})["project"]
    captured: dict[str, object] = {}

    def capture_create_job(payload: dict, **_kwargs):
        captured["payload"] = payload
        return ProductJobStatus(
            job_id="job_mode_contract",
            status=ProductJobStatusValue.PLANNED,
            api_namespace="v3_product_api",
            ui_entry_route="/api/v3/projects/job_mode_contract",
        )

    monkeypatch.setattr(handlers.service, "create_project_visual_asset_bound_job", capture_create_job)
    job = handlers.post_project_job(
        project["project_id"],
        {
            "user_input": "探索不同方向，尝试新风格",
            "template_id": "general_template",
            "metadata": {"requested_image_count": 3},
        },
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    metadata = payload["metadata"]
    scenario_parameters = metadata["scenario_parameters"]
    context_metadata = metadata["project_context_snapshot"]["metadata"]
    assert metadata["effective_variation_mode"] == "creative_exploration"
    assert scenario_parameters["effective_variation_mode"] == "creative_exploration"
    assert context_metadata["effective_variation_mode"] == "creative_exploration"
    assert metadata["requested_image_count"] == 3
    assert scenario_parameters["requested_image_count"] == 3
    assert context_metadata["requested_image_count"] == 3
    assert job["metadata"]["effective_variation_mode"] == "creative_exploration"

    brain_request = V3LLMBrainAdapter().build_request(
        user_input=payload["user_input"],
        stage="generate",
        scenario_id=payload["scenario_selection"]["scenario_id"],
        template_id="general_template",
        metadata=metadata,
    )
    assert brain_request.metadata["effective_variation_mode"] == "creative_exploration"
    assert brain_request.metadata["variation_mode_binding"]["effective_mode"] == "creative_exploration"
    assert brain_request.requested_image_count == 3


def test_project_context_uses_current_request_mode_and_count_for_role_plan() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a visual set"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])

    context = handlers.project_service._build_context(
        project_record,
        template_id="general_template",
        continuation_instruction="沿这个方向做一组图",
        generation_overrides={
            "variation_mode": "auto",
            "effective_variation_mode": "delivery_suite",
            "requested_image_count": 3,
        },
    )

    assert context.general_suite_role_plan["variation_mode"] == "delivery_suite"
    assert context.general_suite_role_plan["requested_image_count"] == 3
    assert len(context.general_suite_role_plan["roles"]) == 3
    assert context.metadata["effective_variation_mode"] == "delivery_suite"
    assert context.metadata["requested_image_count"] == 3


def test_project_context_keeps_all_general_mode_contracts_distinct() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a visual set"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])
    modes = (
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    )

    plans = {}
    for mode in modes:
        context = handlers.project_service._build_context(
            project_record,
            template_id="general_template",
            continuation_instruction="test mode",
            generation_overrides={
                "variation_mode": mode,
                "effective_variation_mode": mode,
                "requested_image_count": 2,
            },
        )
        plans[mode] = context.general_suite_role_plan

    assert {plan["variation_mode"] for plan in plans.values()} == set(modes)
    assert len({plans[mode]["roles"][0]["label"] for mode in modes}) == len(modes)


def test_photography_project_request_preserves_all_delivery_modes() -> None:
    handlers = V3ProductRouteHandlers()
    service = handlers.project_service
    manifest = SimpleNamespace(template_id="photographer_template", scenario_pack_id="photography")
    context = SimpleNamespace(context_version="context-1")

    for mode in ("single_hero", "reference_reshoot", "professional_set"):
        request = CreateProjectJobRequest.model_validate(
            {
                "template_id": "photographer_template",
                "user_input": "A photography request",
                "metadata": {"selected_mode_id": mode, "selected_preset_id": mode},
            }
        )
        selection = service._scenario_selection_for_template(manifest, request, context)
        assert selection["mode_id"] == mode
        assert selection["parameters"]["delivery_mode"] == mode


def test_generated_outputs_with_same_content_hash_remain_distinct_references() -> None:
    handlers = V3ProductRouteHandlers()
    service = handlers.project_service
    references = [
        {
            "source_type": "selected_output",
            "output_id": "output-a",
            "source_integrity_id": "same-pixels",
        },
        {
            "source_type": "selected_output",
            "output_id": "output-b",
            "source_integrity_id": "same-pixels",
        },
    ]

    deduped = service._dedupe_visual_reference_payloads(references)

    assert [item["output_id"] for item in deduped] == ["output-a", "output-b"]
