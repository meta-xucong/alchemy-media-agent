from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import settings
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue, V3JobHistoryItem
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputRecord
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas.models import CommercialAssetPack, PackagedAsset, PlanningResult
from alchemy_creative_agent_3_0.app.project_mode.contracts import OutputRef, ProjectRecord, ProjectTimelineItem
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


def _request() -> object:
    return object()


def _job_record(owner_id: int | None):
    metadata = {} if owner_id is None else {"veyra_user_id": owner_id}
    return SimpleNamespace(request=SimpleNamespace(metadata=metadata))


def _upload_record(owner_id: int | None):
    return SimpleNamespace(veyra_user_id=owner_id)


def test_authenticated_job_visibility_rejects_foreign_and_ownerless_records(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)

    for record in (_job_record(202), _job_record(None)):
        monkeypatch.setattr(main_module.v3_route_handlers.service, "get_job_record", lambda job_id, record=record: record)
        with pytest.raises(HTTPException) as exc_info:
            main_module._require_v3_job_visible(_request(), "job_foreign")
        assert exc_info.value.status_code == 404


def test_authenticated_job_visibility_allows_only_matching_owner(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_job_record",
        lambda job_id: _job_record(101),
    )

    assert main_module._require_v3_job_visible(_request(), "job_owned") == 101


def test_authenticated_upload_visibility_rejects_foreign_and_ownerless_records(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)

    for record in (_upload_record(202), _upload_record(None)):
        monkeypatch.setattr(main_module.v3_route_handlers.service, "get_uploaded_asset", lambda asset_id, record=record: record)
        with pytest.raises(HTTPException) as exc_info:
            main_module._require_v3_uploaded_asset_visible(_request(), "asset_foreign")
        assert exc_info.value.status_code == 404


def test_http_upload_creation_passes_only_server_owner_to_storage(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    captured = {}

    def fake_run(handler, *args, **kwargs):
        captured["handler"] = handler
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(main_module, "_run_v3_handler", fake_run)
    response = TestClient(main_module.app).post(
        "/api/v3/creative-agent/uploads",
        headers={"Authorization": "Bearer account-a"},
        json={
            "filename": "reference.png",
            "mime_type": "image/png",
            "size_bytes": 0,
            "metadata": {"veyra_user_id": 202},
        },
    )

    assert response.status_code == 200
    assert captured["kwargs"]["owner_user_id"] == 101
    assert captured["handler"].__name__ == "post_uploads"


def test_http_foreign_job_is_rejected_before_handler_execution(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_job_record",
        lambda job_id: _job_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign job reached the product handler")

    monkeypatch.setattr(main_module, "_run_v3_handler", unexpected_handler)
    response = TestClient(main_module.app).get(
        "/api/v3/creative-agent/jobs/job_foreign",
        headers={"Authorization": "Bearer account-a"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_foreign_upload_content_is_rejected_before_storage(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_uploaded_asset",
        lambda asset_id: _upload_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign upload reached the content handler")

    monkeypatch.setattr(main_module, "_run_v3_handler", unexpected_handler)
    response = TestClient(main_module.app).put(
        "/api/v3/creative-agent/uploads/asset_foreign/content",
        headers={"Authorization": "Bearer account-a"},
        json={"content_base64": "not-used"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_project_creation_rejects_foreign_upload_before_handler(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_uploaded_asset",
        lambda asset_id: _upload_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign upload reached project creation")

    monkeypatch.setattr(main_module, "_run_v3_handler", unexpected_handler)
    response = TestClient(main_module.app).post(
        "/api/v3/creative-agent/projects",
        headers={"Authorization": "Bearer account-a"},
        json={"user_goal": "project", "uploaded_asset_ids": ["asset_foreign"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_project_job_rejects_foreign_upload_before_handler(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(main_module, "_v3_project_owner_id", lambda project_id: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_uploaded_asset",
        lambda asset_id: _upload_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign upload reached project job creation")

    monkeypatch.setattr(main_module, "_run_v3_handler", unexpected_handler)
    monkeypatch.setattr(main_module, "_run_v3_handler_threaded", unexpected_handler)
    response = TestClient(main_module.app).post(
        "/api/v3/creative-agent/projects/project_owned/jobs",
        headers={"Authorization": "Bearer account-a"},
        json={"user_input": "generate", "uploaded_asset_ids": ["asset_foreign"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_direct_job_create_rejects_foreign_upload_before_handler(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_uploaded_asset",
        lambda asset_id: _upload_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign upload reached direct job creation")

    monkeypatch.setattr(main_module, "_run_v3_handler", unexpected_handler)
    response = TestClient(main_module.app).post(
        "/api/v3/creative-agent/jobs",
        headers={"Authorization": "Bearer account-a"},
        json={"user_input": "generate", "uploaded_asset_ids": ["asset_foreign"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_direct_job_generation_rejects_foreign_upload_before_handler(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_job_record",
        lambda job_id: _job_record(101),
    )
    monkeypatch.setattr(
        main_module.v3_route_handlers.service,
        "get_uploaded_asset",
        lambda asset_id: _upload_record(202),
    )

    def unexpected_handler(*args, **kwargs):
        raise AssertionError("foreign upload reached direct generation")

    monkeypatch.setattr(main_module, "_run_v3_handler_threaded", unexpected_handler)
    response = TestClient(main_module.app).post(
        "/api/v3/creative-agent/jobs/job_owned/generate",
        headers={"Authorization": "Bearer account-a"},
        json={"uploaded_asset_ids": ["asset_foreign"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "v3_resource_not_found"


def test_http_history_passes_authenticated_owner_scope_to_v3_service(monkeypatch):
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main_module, "_veyra_user_id_from_request", lambda request, authorization: 101)
    captured = {}

    def fake_run(handler, *args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"items": []}

    monkeypatch.setattr(main_module, "_run_v3_handler", fake_run)
    response = TestClient(main_module.app).get(
        "/api/v3/creative-agent/history?limit=20",
        headers={"Authorization": "Bearer account-a"},
    )

    assert response.status_code == 200
    assert captured["args"] == (20, 101)
    assert captured["kwargs"] == {}


def test_uploaded_asset_owner_is_server_owned_and_public_record_hides_private_path(tmp_path):
    store = V3UploadedAssetStore(tmp_path)
    record = store.create_upload(
        {
            "filename": "reference.png",
            "mime_type": "image/png",
            "size_bytes": 0,
            "metadata": {"veyra_user_id": 999, "client_note": "kept"},
        },
        owner_user_id=101,
    )

    assert record.veyra_user_id == 101
    assert "veyra_user_id" not in record.metadata

    public = main_module._public_uploaded_asset_record(record)
    assert "file_path" not in public
    assert "veyra_user_id" not in public
    assert public["asset_id"] == record.asset_id


def _output_ref(output_id: str, *, metadata: dict | None = None, thumbnail_url: str = "") -> OutputRef:
    return OutputRef(
        output_ref_id=f"ref-{output_id}",
        source_type="generated_output",
        project_id="project_owned",
        job_id=f"job-{output_id}",
        asset_id=f"asset-{output_id}",
        candidate_id=f"candidate-{output_id}",
        output_id=output_id,
        thumbnail_url=thumbnail_url or f"/thumb/{output_id}",
        selected_at="2026-08-30T00:00:00+00:00",
        metadata=metadata or {},
    )


def test_authenticated_project_summary_and_record_ignore_nonvisible_selected_outputs():
    project = ProjectRecord(
        project_id="project_owned",
        title="Owned",
        user_goal="goal",
        short_summary="goal",
        created_at="2026-08-30T00:00:00+00:00",
        updated_at="2026-08-30T00:00:00+00:00",
        selected_output_refs=[
            _output_ref("output-foreign", thumbnail_url="foreign"),
            _output_ref(
                "output-owned",
                thumbnail_url="owned",
                metadata={"file_path": "D:/private/owned.png", "canonical_output_binding": True},
            ),
        ],
        metadata={"veyra_user_id": 101},
    )
    service = object.__new__(V3ProjectModeService)
    service.project_store = SimpleNamespace(list_timeline=lambda project_id: [])
    service._selected_output_state_map = lambda value: {}
    service._project_output_items = lambda *args, **kwargs: [
        {
            "output_id": "output-owned",
            "asset_id": "asset-output-owned",
            "candidate_id": "candidate-output-owned",
            "thumbnail_url": "owned",
        }
    ]
    service._latest_project_job_status = lambda *args, **kwargs: "generated"
    service._style_chips = lambda value: []
    service._next_actions = lambda value: []
    service._scenario_id_for_template = lambda value: "general"
    service._template_label = lambda value: "通用模板"

    summary = service._memory_summary(project, owner_user_id=101)
    public = service._public_project_record(
        project,
        owner_user_id=101,
        visible_output_items=service._project_output_items(project, owner_user_id=101),
    )

    assert summary.latest_thumbnail_urls == ["owned"]
    assert summary.selected_asset_count == 1
    assert [ref.output_id for ref in public.selected_output_refs] == ["output-owned"]
    assert public.selected_output_refs[0].metadata == {}


def _history_record(job_id: str, owner_id: int | None):
    metadata = {} if owner_id is None else {"veyra_user_id": owner_id}
    return SimpleNamespace(
        job_id=job_id,
        status=ProductJobStatusValue.GENERATED,
        updated_at="2026-08-30T00:00:00+00:00",
        request=SimpleNamespace(metadata=metadata),
    )


def _history_item(record):
    return V3JobHistoryItem(
        job_id=record.job_id,
        status=ProductJobStatusValue.GENERATED,
        user_input=record.job_id,
        created_at=record.updated_at,
        updated_at=record.updated_at,
        route="/v3",
    )


def test_authenticated_v3_history_is_owner_scoped_for_jobs_and_restored_outputs():
    service = object.__new__(V3ProductApiService)
    service.job_store = SimpleNamespace(
        list_recent=lambda limit: [
            _history_record("job-owned", 101),
            _history_record("job-foreign", 202),
            _history_record("job-ownerless", None),
        ]
    )
    service.output_store = SimpleNamespace(list_outputs=lambda limit: [])
    service._history_item_from_record = _history_item

    history = service.list_history(limit=10, owner_user_id=101)

    assert [item.job_id for item in history.items] == ["job-owned"]

    service.job_store = SimpleNamespace(list_recent=lambda limit: [])
    service.output_store = SimpleNamespace(
        list_outputs=lambda limit: [
            V3GeneratedOutputRecord(
                output_id="v3_output_aaaaaaaaaaaaaaaaaaaa",
                job_id="restored-owned",
                candidate_id="candidate-owned",
                asset_id="asset-owned",
                provider="test",
                created_at="2026-08-30T00:00:00+00:00",
                metadata={"veyra_user_id": 101},
            ),
            V3GeneratedOutputRecord(
                output_id="v3_output_bbbbbbbbbbbbbbbbbbbb",
                job_id="restored-foreign",
                candidate_id="candidate-foreign",
                asset_id="asset-foreign",
                provider="test",
                created_at="2026-08-30T00:00:00+00:00",
                metadata={"veyra_user_id": 202},
            ),
            V3GeneratedOutputRecord(
                output_id="v3_output_cccccccccccccccccccc",
                job_id="restored-ownerless",
                candidate_id="candidate-ownerless",
                asset_id="asset-ownerless",
                provider="test",
                created_at="2026-08-30T00:00:00+00:00",
                metadata={},
            ),
        ]
    )

    restored = service.list_history(limit=10, owner_user_id=101)

    assert [item.job_id for item in restored.items] == ["restored-owned"]


def test_mock_materialized_output_inherits_server_job_owner():
    captured: dict[str, object] = {}
    output = V3GeneratedOutputRecord(
        output_id="v3_output_aaaaaaaaaaaaaaaaaaaa",
        job_id="job_owned",
        candidate_id="candidate-owned",
        asset_id="asset-owned",
        provider="v3_mock_contract_fixture",
        created_at="2026-08-30T00:00:00+00:00",
        metadata={"veyra_user_id": 101},
        download_url="/download",
        preview_url="/preview",
        thumbnail_url="/thumbnail",
    )
    service = object.__new__(V3ProductApiService)
    service.output_store = SimpleNamespace(
        get_output=lambda output_id: None,
        save_base64_output=lambda **kwargs: captured.update(kwargs) or output,
    )
    asset = PackagedAsset.model_construct(
        asset_id="asset-owned",
        metadata={"selected_candidate_id": "candidate-owned"},
    )
    asset_pack = CommercialAssetPack.model_construct(assets=[asset], metadata={})
    generation_result = PlanningResult.model_construct(
        asset_pack=asset_pack,
        metadata={},
    )
    record = SimpleNamespace(
        job_id="job_owned",
        request=SimpleNamespace(
            metadata={
                "project_id": "project_owned",
                "template_id": "general_template",
                "veyra_user_id": 101,
            }
        ),
    )

    service._materialize_mock_output_records(record, generation_result)

    assert captured["metadata"]["veyra_user_id"] == 101


def test_project_detail_forwards_authenticated_owner_to_summary_and_output_projection():
    project = ProjectRecord(
        project_id="project_owned",
        title="Owned",
        user_goal="goal",
        short_summary="goal",
        created_at="2026-08-30T00:00:00+00:00",
        updated_at="2026-08-30T00:00:00+00:00",
        metadata={"veyra_user_id": 101},
    )
    service = object.__new__(V3ProjectModeService)
    service.project_store = SimpleNamespace(
        get_project=lambda project_id: project,
        save_project=lambda value: value,
    )
    service._reconcile_project_outputs = lambda value: False
    service._ensure_project_product_reference_integrity = lambda value: None
    service._build_context = lambda value, **kwargs: None
    captured: dict[str, int | None] = {}

    def fake_summary(value, *, owner_user_id=None):
        captured["summary"] = owner_user_id
        return None

    def fake_response(value, *, owner_user_id=None, context_override=None):
        captured["response"] = owner_user_id
        captured["context_override"] = context_override
        return {"project_id": value.project_id}

    service._memory_summary = fake_summary
    service._project_response = fake_response

    assert service.get_project(project.project_id, owner_user_id=101) == {
        "project_id": project.project_id,
    }
    assert captured == {"summary": 101, "response": 101, "context_override": None}


def test_authenticated_context_rebuild_is_owner_scoped_without_replacing_private_context():
    project = ProjectRecord(
        project_id="project_owned",
        title="Owned",
        user_goal="goal",
        short_summary="goal",
        created_at="2026-08-30T00:00:00+00:00",
        updated_at="2026-08-30T00:00:00+00:00",
        metadata={"veyra_user_id": 101},
    )
    service = object.__new__(V3ProjectModeService)
    service.project_store = SimpleNamespace(
        get_project=lambda project_id: project,
    )
    service._ensure_project_product_reference_integrity = lambda value: None
    private_context = object()
    public_context = object()
    captured: dict[str, object] = {}

    service._refresh_project_context = lambda value: private_context

    def fake_build(value, **kwargs):
        captured.update(kwargs)
        return public_context

    service._build_context = fake_build

    assert service.get_project_context(project.project_id, owner_user_id=101) is public_context
    assert captured == {"owner_user_id": 101}


def test_project_output_projection_requires_both_job_and_output_owner():
    project = ProjectRecord(
        project_id="project_owned",
        title="Owned",
        user_goal="goal",
        short_summary="goal",
        created_at="2026-08-30T00:00:00+00:00",
        updated_at="2026-08-30T00:00:00+00:00",
        job_ids=["job_owned", "job_foreign"],
        metadata={"veyra_user_id": 101},
    )
    owned_output = V3GeneratedOutputRecord(
        output_id="v3_output_aaaaaaaaaaaaaaaaaaaa",
        job_id="job_owned",
        candidate_id="candidate-owned",
        asset_id="asset-owned",
        provider="test",
        created_at="2026-08-30T00:00:00+00:00",
        metadata={"veyra_user_id": 101},
    )
    ownerless_output = V3GeneratedOutputRecord(
        output_id="v3_output_bbbbbbbbbbbbbbbbbbbb",
        job_id="job_owned",
        candidate_id="candidate-ownerless",
        asset_id="asset-ownerless",
        provider="test",
        created_at="2026-08-30T00:00:01+00:00",
        metadata={},
    )
    cross_linked_output = V3GeneratedOutputRecord(
        output_id="v3_output_cccccccccccccccccccc",
        job_id="job_foreign",
        candidate_id="candidate-cross-linked",
        asset_id="asset-cross-linked",
        provider="test",
        created_at="2026-08-30T00:00:02+00:00",
        metadata={"veyra_user_id": 101},
    )
    service = object.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(
        get_job=lambda job_id: SimpleNamespace(metadata={}, status="generated"),
        get_job_record=lambda job_id: SimpleNamespace(
            request=SimpleNamespace(
                metadata={"veyra_user_id": 101 if job_id == "job_owned" else 202}
            )
        ),
        output_store=SimpleNamespace(
            list_by_job=lambda job_id: {
                "job_owned": [owned_output, ownerless_output],
                "job_foreign": [cross_linked_output],
            }.get(job_id, [])
        ),
    )
    service._selected_output_state_map = lambda value: {}
    service._job_delivery_is_settled = lambda value: True
    service._public_output_review_projection = lambda *args: {}
    service._review_projection_allows_project_delivery = lambda value: True
    service._delivery_annotations_for_records = lambda records: {
        record.output_id: {"delivery_state": "final_delivery"}
        for record in records
    }
    service._output_item_from_record = lambda project, record, state, **kwargs: {
        "output_id": record.output_id,
        "job_id": record.job_id,
    }

    items = service._project_output_items(project, owner_user_id=101)

    assert items == [{"output_id": owned_output.output_id, "job_id": "job_owned"}]


def test_authenticated_timeline_filters_foreign_job_items():
    service = object.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(
        get_job_record=lambda job_id: _job_record(101 if job_id == "job_owned" else 202),
    )
    items = [
        ProjectTimelineItem.model_construct(
            timeline_item_id="timeline-owned",
            project_id="project_owned",
            item_type="job_created",
            title="owned",
            summary="owned",
            job_id="job_owned",
            related_job_id="job_owned",
            created_at="2026-08-30T00:00:00+00:00",
            selected_output_refs=[],
        ),
        ProjectTimelineItem.model_construct(
            timeline_item_id="timeline-foreign",
            project_id="project_owned",
            item_type="job_created",
            title="foreign",
            summary="foreign",
            job_id="job_foreign",
            related_job_id="job_foreign",
            created_at="2026-08-30T00:00:01+00:00",
            selected_output_refs=[],
        ),
    ]

    visible = service._timeline_items_for_owner(items, 101)

    assert [item.timeline_item_id for item in visible] == ["timeline-owned"]
