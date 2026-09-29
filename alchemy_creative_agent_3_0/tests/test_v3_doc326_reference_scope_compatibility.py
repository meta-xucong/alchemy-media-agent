"""Doc326: generation-only reference isolation with public-history compatibility."""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    OutputRef,
    ProjectReferenceAsset,
    ProjectReferenceSourceType,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import (
    _general_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_project_mode import (
    _project_handlers_with_output_store,
    _ready_upload,
    _save_project_output,
)


def _legacy_selected_refs(project_id: str, records: list) -> tuple[list[OutputRef], list[ProjectReferenceAsset]]:
    selected = []
    generated = []
    for index, record in enumerate(records, start=1):
        selected.append(
            OutputRef(
                output_ref_id=f"doc326-output-ref-{index}",
                source_type="generated_output",
                project_id=project_id,
                job_id=record.job_id,
                asset_id=record.asset_id,
                candidate_id=record.candidate_id,
                output_id=record.output_id,
                preview_url=record.preview_url,
                thumbnail_url=record.thumbnail_url,
                download_url=record.download_url,
                selection_reason="legacy selected continuation",
                selected_at=f"2026-08-31T00:0{index}:00+00:00",
                metadata={"file_path": record.file_path},
            )
        )
        generated.append(
            ProjectReferenceAsset(
                reference_id=f"doc326-generated-reference-{index}",
                project_id=project_id,
                source_type=ProjectReferenceSourceType.GENERATED_SELECTED,
                asset_ref_id=record.output_id,
                created_at="2026-08-31T00:00:00+00:00",
                created_from_job_id=record.job_id,
                created_from_output_id=record.output_id,
                use_policy=ProjectReferenceUsePolicy.STYLE,
                metadata={"canonical_output_binding": True},
            )
        )
    return selected, generated


def test_generation_scope_hides_legacy_history_without_mutating_public_project(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "A general visual series"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])
    records = [
        _save_project_output(
            handlers,
            job_id=f"doc326-legacy-job-{index}",
            candidate_id=f"doc326-legacy-candidate-{index}",
            asset_id=f"doc326-legacy-asset-{index}",
        )
        for index in (1, 2)
    ]
    selected, generated = _legacy_selected_refs(project_record.project_id, records)
    project_record.selected_output_refs = selected
    project_record.reference_assets = generated
    handlers.project_service.project_store.save_project(project_record)

    public_context = handlers.project_service._build_context(project_record)
    generation_context = handlers.project_service._build_context(
        project_record,
        template_id="general_template",
        generation_scope=True,
    )

    assert [item.output_id for item in public_context.selected_output_assets] == [
        record.output_id for record in records
    ]
    assert [item["output_id"] for item in public_context.selected_reference_assets] == [
        record.output_id for record in records
    ]
    assert generation_context.selected_output_assets == []
    assert generation_context.selected_reference_assets == []
    assert generation_context.selected_visual_references == []
    assert generation_context.metadata["reference_scope"] == "generation_job_strict"

    persisted = handlers.project_service.project_store.get_project(project_record.project_id)
    assert [ref.output_id for ref in persisted.selected_output_refs] == [
        record.output_id for record in records
    ]
    assert len(persisted.reference_assets) == 2


def test_generation_scope_keeps_only_current_standard_uploads_in_job_clone(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "A direct reference test"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])
    asset_id = _ready_upload(handlers, tmp_path, role="style_reference")

    generation_scope = handlers.project_service._generation_reference_scoped_project(
        project_record,
        "general_template",
        [asset_id],
        {"state": "none", "version": 0, "auto_enabled": True, "active_continuity_anchor": None},
    )

    assert [reference.asset_ref_id for reference in generation_scope.reference_assets] == [asset_id]
    assert [item["asset_id"] for item in generation_scope.uploaded_asset_refs] == [asset_id]
    assert generation_scope.selected_output_refs == []
    assert project_record.reference_assets == []
    assert project_record.uploaded_asset_refs == []


def test_generation_scope_keeps_one_valid_continuity_anchor(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    project = handlers.post_projects({"user_goal": "A continuity test"})["project"]
    project_record = handlers.project_service._require_project(project["project_id"])
    record = _save_project_output(
        handlers,
        job_id="doc326-anchor-job",
        candidate_id="doc326-anchor-candidate",
        asset_id="doc326-anchor-asset",
    )
    state = {
        "state": "active",
        "version": 4,
        "auto_enabled": False,
        "created_at": "2026-09-28T00:00:00+00:00",
        "active_continuity_anchor": {
            "binding_id": "doc326-anchor-binding",
            "output_id": record.output_id,
            "source_job_id": record.job_id,
            "source_candidate_id": record.candidate_id,
            "source_asset_id": record.asset_id,
            "source_content_sha256": record.metadata["content_sha256"],
            "binding_mode": "manual",
            "state": "active",
            "reference": {"asset_id": record.asset_id, "output_id": record.output_id},
        },
    }

    generation_scope = handlers.project_service._generation_reference_scoped_project(
        project_record,
        "general_template",
        [],
        state,
    )

    assert [ref.output_id for ref in generation_scope.selected_output_refs] == [record.output_id]
    assert not any(
        reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED
        for reference in generation_scope.reference_assets
    )


def test_project_job_freezes_zero_implicit_general_sources(tmp_path) -> None:
    handlers, project, _asset_ids, _snapshot = _general_project(tmp_path)

    created = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Create a new general image without using historical references."},
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    plan = record.request.metadata[PLAN_KEY]

    assert plan["continuity_anchor"] is None
    assert plan["direct_references"] == []
    assert record.request.uploaded_asset_ids == []
    assert record.request.metadata["project_context_snapshot"]["metadata"]["reference_scope"] == (
        "generation_job_strict"
    )


def test_general_project_creation_uploads_are_reused_by_first_job(tmp_path) -> None:
    handlers = _project_handlers_with_output_store(tmp_path)
    asset_id = _ready_upload(handlers, tmp_path, role="style_reference")
    project = handlers.post_projects(
        {
            "user_goal": "A project created with an original source image",
            "uploaded_asset_ids": [asset_id],
        }
    )["project"]

    created = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue using the original project source."},
    )
    record = handlers.service.get_job_record(created["job_id"])
    plan = record.request.metadata[PLAN_KEY]
    assert [item["asset_id"] for item in plan["direct_references"]] == [asset_id]
