from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatus, ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.contracts import OutputRef, ProjectContextPackage, ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _save_output(store: V3GeneratedOutputStore, *, job_id: str):
    return store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_shared",
        asset_id="asset_shared",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000001",
        mime_type="image/png",
        output_format="png",
        metadata={"requested_image_count": 1},
    )


def _bind_closure(store: V3GeneratedOutputStore, record: object, *, delivery_state: str) -> None:
    envelope = {
        "execution_fingerprint": "fingerprint_fixture",
        "envelope_id": "envelope_fixture",
        "resolved_constraint_ledger": {
            "ledger_id": "ledger_fixture",
            "provider_projection": {"capability_projection": {"effective_variation_mode": "delivery_suite"}},
        },
    }
    updated = store.update_metadata(record.output_id, {"capability_execution_envelope": envelope})
    assert updated is not None
    store.save_job_closure(
        record.job_id,
        {
            "schema_version": "v3_output_delivery_closure_v1",
            "job_id": record.job_id,
            "status": "complete",
            "review_evidence_receipt_status": "complete",
            "final_delivery_status": delivery_state,
            "automatic_delivery_available": delivery_state == "ready",
            "eligible_output_ids": [record.output_id] if delivery_state == "ready" else [],
            "execution_fingerprint": "fingerprint_fixture",
            "envelope_id": "envelope_fixture",
            "ledger_id": "ledger_fixture",
            "outputs": [
                {
                    "output_id": record.output_id,
                    "asset_id": record.asset_id,
                    "candidate_id": record.candidate_id,
                    "content_sha256": record.metadata["content_sha256"],
                }
            ],
        },
    )


def _project(service: V3ProjectModeService, *, project_id: str, job_id: str) -> ProjectRecord:
    project = ProjectRecord(
        project_id=project_id,
        title="Persisted output closure",
        user_goal="Keep persisted output recovery safe",
        short_summary="Keep persisted output recovery safe",
        job_ids=[job_id],
        created_at="2026-09-11T00:00:00+00:00",
        updated_at="2026-09-11T00:00:00+00:00",
    )
    service.project_store.save_project(project)
    return project


@pytest.mark.parametrize(
    ("restore_state", "closure_delivery_state"),
    [
        ("needs_recovery", None),
        ("delivery_withheld", "withheld_manual_confirmation"),
    ],
)
def test_project_mode_keeps_unclosed_restore_outputs_review_only(
    tmp_path,
    restore_state: str,
    closure_delivery_state: str | None,
) -> None:
    job_id = f"job_{restore_state}"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(output_store, job_id=job_id)
    if closure_delivery_state is not None:
        _bind_closure(output_store, record, delivery_state=closure_delivery_state)

    product_service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    project_service = V3ProjectModeService(product_service=product_service)
    project = _project(project_service, project_id=f"project_{restore_state}", job_id=job_id)

    status = product_service.get_job(job_id)
    assert status.status == ProductJobStatusValue.BLOCKED
    assert status.metadata["output_store_restore_state"] == restore_state
    assert project_service._job_delivery_is_settled(status) is False  # noqa: SLF001

    outputs = project_service.list_project_outputs(project_id=project.project_id)

    assert outputs["items"] == []
    assert len(outputs["review_items"]) == 1
    review_item = outputs["review_items"][0]
    assert review_item["output_id"] == record.output_id
    assert review_item["review_only"] is True
    assert review_item["recovery_required"] is True
    assert review_item["output_store_restore_state"] == restore_state
    assert review_item["delivery_state"] == "review_only"
    assert review_item["metadata"]["review_only"] is True
    assert review_item["metadata"]["output_store_restore_state"] == restore_state

    delivery_preview = project_service.list_project_outputs(
        project_id=project.project_id,
        surface="delivery_preview",
    )
    assert delivery_preview["items"] == []

    timeline = project_service.list_timeline(project.project_id)
    item_types = [item.item_type.value for item in timeline.items]
    assert "job_generated" not in item_types
    assert "visual_review" not in item_types
    recovery_notes = [
        item
        for item in timeline.items
        if item.item_type.value == "note_added"
        and item.metadata.get("output_store_restore_state") == restore_state
    ]
    assert len(recovery_notes) == 1
    assert recovery_notes[0].metadata["review_only"] is True
    assert recovery_notes[0].metadata["recovery_required"] is True

    timeline_again = project_service.list_timeline(project.project_id)
    recovery_notes_again = [
        item
        for item in timeline_again.items
        if item.item_type.value == "note_added"
        and item.metadata.get("output_store_restore_state") == restore_state
    ]
    assert len(recovery_notes_again) == 1


@pytest.mark.parametrize(
    ("selector_kind", "selector_value", "should_match"),
    [
        ("candidate", "candidate_shared", True),
        ("asset", "asset_shared", True),
        ("output", "v3_output_00000000000000000001", True),
        ("candidate", "asset_shared", False),
        ("asset", "candidate_shared", False),
        ("output", "candidate_shared", False),
        ("output", "asset_shared", False),
    ],
)
def test_persisted_output_selector_matches_only_its_declared_identifier_type(
    tmp_path,
    selector_kind: str,
    selector_value: str,
    should_match: bool,
) -> None:
    job_id = "job_typed_selector"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = _save_output(output_store, job_id=job_id)
    product_service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    project_service = V3ProjectModeService(product_service=product_service)
    project = _project(project_service, project_id=f"project_{selector_kind}_{should_match}", job_id=job_id)
    status = product_service.get_job(job_id)

    selector_kwargs = {
        "selected_candidate_ids": {selector_value} if selector_kind == "candidate" else set(),
        "selected_asset_ids": {selector_value} if selector_kind == "asset" else set(),
        "selected_output_ids": {selector_value} if selector_kind == "output" else set(),
    }
    refs, unresolved = project_service._resolved_output_refs_for_status(  # noqa: SLF001
        project,
        status,
        **selector_kwargs,
    )

    if should_match:
        assert [ref.output_id for ref in refs] == [record.output_id]
        assert unresolved == []
    else:
        assert refs == []
        assert unresolved
        assert unresolved[0]["selector"] == selector_value


def _public_boundary_fixture() -> tuple[ProjectRecord, ProjectContextPackage]:
    ref = OutputRef(
        output_ref_id="output_ref_safe",
        source_type="generated_output",
        project_id="project_public",
        job_id="job_public",
        asset_id="asset_public",
        candidate_id="candidate_public",
        output_id="output_public",
        preview_url="/preview/output_public",
        thumbnail_url="/thumbnail/output_public",
        download_url="/download/output_public",
        selected_at="2026-09-12T00:00:00+00:00",
        metadata={
            "recommendation": "keep this user-facing suggestion",
            "file_path": "C:/private/output.png",
            "final_provider_prompt": "private final prompt",
            "llm_brain": {"optimized_direction": "private brain direction"},
            "reasoning": "private reasoning",
            "retry_patch": {"provider_prompt": "private retry prompt"},
        },
    )
    context = ProjectContextPackage(
        project_id="project_public",
        context_version="context_public",
        goal_summary="Safe public projection",
        created_at="2026-09-12T00:00:00+00:00",
        selected_output_assets=[ref],
        selected_visual_references=[
            {
                "output_id": "output_public",
                "file_path": "C:/private/reference.png",
                "metadata": {"provider_prompt": "private nested prompt"},
            }
        ],
        metadata={
            "source": "project_api",
            "reference_resolution_audit": {
                "retained_selected_output_ids": ["output_public"],
                "retry_patch": {"final_provider_prompt": "private audit prompt"},
            },
            "compiled_visual_direction": "private context direction",
            "llm_brain": {"provider_prompt": "private context brain prompt"},
        },
    )
    project = ProjectRecord(
        project_id="project_public",
        title="Public boundary",
        user_goal="Public boundary",
        short_summary="Public boundary",
        selected_output_refs=[ref],
        latest_context=context,
        created_at="2026-09-12T00:00:00+00:00",
        updated_at="2026-09-12T00:00:00+00:00",
        metadata={
            "source": "project_api",
            "selected_template_id": "general_template",
            "compiled_visual_direction": "private project direction",
            "doc90_advanced_reference_controls": {
                "enabled": True,
                "file_path": "C:/private/project.png",
            },
        },
    )
    return project, context


def _assert_execution_secrets_are_absent(value: object) -> None:
    rendered = repr(value)
    for secret in (
        "file_path",
        "final_provider_prompt",
        "compiled_visual_direction",
        "optimized_direction",
        "provider_prompt",
        "llm_brain",
        "reasoning",
        "retry_patch",
        "C:/private",
        "private final prompt",
    ):
        assert secret not in rendered


def test_project_job_route_statuses_use_public_projection(monkeypatch) -> None:
    handlers = V3ProductRouteHandlers()
    leaked_status = ProductJobStatus(
        job_id="job_public_route",
        status=ProductJobStatusValue.GENERATED,
        api_namespace="/api/v3",
        ui_entry_route="/projects/project_public_route",
        metadata={
            "final_provider_prompt": "private route prompt",
            "compiled_visual_direction": "private route direction",
            "reasoning": "private route reasoning",
            "provider_payload": {"secret": True},
            "file_path": "C:/private/route.png",
        },
    )

    monkeypatch.setattr(
        handlers.project_service,
        "create_project_job",
        lambda *_args, **_kwargs: leaked_status,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "generate_project_job",
        lambda *_args, **_kwargs: leaked_status,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "mark_project_job_generating",
        lambda *_args, **_kwargs: leaked_status,
    )

    outputs = [
        handlers.post_project_job("project_public_route", {}),
        handlers.post_project_job_generate("project_public_route", "job_public_route", {}),
        handlers.mark_project_job_generating("project_public_route", "job_public_route"),
    ]

    for output in outputs:
        assert output["metadata"] == {}
        _assert_execution_secrets_are_absent(output)


def test_project_mutation_response_projects_nested_records(monkeypatch) -> None:
    service = V3ProjectModeService(product_service=V3ProductApiService())
    project, context = _public_boundary_fixture()
    service.project_store.save_project(project)
    monkeypatch.setattr(service, "_refresh_project_context", lambda _project: context)
    monkeypatch.setattr(service, "_project_output_items", lambda *_args, **_kwargs: [])

    response = service.add_project_feedback(
        project.project_id,
        {
            "plain_text": "Keep the selected direction",
            "metadata": {"provider_payload": {"secret": True}},
        },
    )
    payload = response.model_dump(mode="json")

    assert payload["feedback"]["metadata"] == {}
    assert payload["project"]["metadata"] == {
        "source": "project_api",
        "selected_template_id": "general_template",
        "doc90_advanced_reference_controls": {"enabled": True},
    }
    _assert_execution_secrets_are_absent(payload)

    unsafe_feedback = response.feedback.model_copy(
        update={"metadata": {"provider_payload": {"secret": True}}}
    )
    state_change = service._state_change_response(  # noqa: SLF001
        project,
        context,
        feedback=unsafe_feedback,
    )
    assert state_change["feedback"]["metadata"] == {}
    _assert_execution_secrets_are_absent(state_change)


def test_public_project_projection_keeps_owner_none_selection_but_scrubs_output_and_metadata() -> None:
    service = V3ProjectModeService(product_service=V3ProductApiService())
    project, _context = _public_boundary_fixture()

    public = service._public_project_record(project)  # noqa: SLF001
    payload = public.model_dump(mode="json")

    assert [ref["output_id"] for ref in payload["selected_output_refs"]] == ["output_public"]
    assert payload["selected_output_refs"][0]["metadata"] == {
        "recommendation": "keep this user-facing suggestion"
    }
    assert payload["metadata"] == {
        "source": "project_api",
        "selected_template_id": "general_template",
        "doc90_advanced_reference_controls": {"enabled": True},
    }
    _assert_execution_secrets_are_absent(payload)


def test_selection_hold_projects_the_same_public_record_and_context(monkeypatch) -> None:
    service = V3ProjectModeService(product_service=V3ProductApiService())
    project, context = _public_boundary_fixture()
    status = ProductJobStatus(
        job_id="job_public",
        status=ProductJobStatusValue.BLOCKED,
        api_namespace="/api/v3",
        ui_entry_route="/projects/project_public",
        metadata={
            "final_provider_prompt": "private job prompt",
            "compiled_visual_direction": "private job direction",
            "reasoning": "private job reasoning",
            "file_path": "C:/private/job.png",
        },
    )
    monkeypatch.setattr(service, "_refresh_project_context", lambda _project: context)
    monkeypatch.setattr(service, "_project_output_items", lambda *_args, **_kwargs: [])

    response = service._selection_hold_response(  # noqa: SLF001
        project,
        template_id="general_template",
        status=status,
        reason="output_unavailable",
        message="hold",
    )

    assert response["project"]["selected_output_refs"][0]["output_id"] == "output_public"
    assert response["context"]["selected_output_assets"][0]["output_id"] == "output_public"
    _assert_execution_secrets_are_absent(
        {"job_status": response["job_status"], "project": response["project"], "context": response["context"]}
    )


def test_public_context_projection_preserves_recovered_output_identity_without_internal_metadata() -> None:
    service = V3ProjectModeService(product_service=V3ProductApiService())
    _project, context = _public_boundary_fixture()
    recovered = context.selected_output_assets[0].model_copy(
        update={
            "metadata": {
                "restored_from_output_store": True,
                "output_store_restore_state": "needs_recovery",
                "file_path": "C:/private/recovered.png",
            }
        }
    )
    context = context.model_copy(update={"selected_output_assets": [recovered]})

    public = service._public_project_context(context)  # noqa: SLF001
    payload = public.model_dump(mode="json")

    assert payload["selected_output_assets"][0]["output_id"] == "output_public"
    assert payload["selected_output_assets"][0]["metadata"] == {
        "restored_from_output_store": True,
        "output_store_restore_state": "needs_recovery",
    }
    _assert_execution_secrets_are_absent(payload)
