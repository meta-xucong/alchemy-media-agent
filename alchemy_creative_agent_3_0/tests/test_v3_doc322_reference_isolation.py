"""Doc323: project-bound source reuse without a global source pool."""
from copy import deepcopy
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectReferenceUsePolicy
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project, _selection_registry


def test_standard_reuses_only_project_sources_and_never_invokes_global_matching(tmp_path, monkeypatch):
    handlers, project, ids, snapshot = _general_project(tmp_path)
    calls = {}
    handlers.project_service.doc281_general_source_registry = _selection_registry(snapshot, target_asset_id=ids[0], calls=calls)
    captured = []
    original = handlers.service.scenario_runtime.plan_job
    def plan(request):
        captured.append(deepcopy(request))
        return original(request)
    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(project["project_id"], {"user_input":"Use these original references for the first image.",
        "uploaded_asset_ids":ids, "metadata":{"requested_image_count":1}})
    handlers.post_project_job(project["project_id"], {"user_input":"Continue the same project with the original references.",
        "uploaded_asset_ids":[], "metadata":{"requested_image_count":1}})
    assert captured[0]["uploaded_asset_ids"] == ids
    assert captured[1]["uploaded_asset_ids"] == ids
    assert calls == {}
    context = captured[1]["metadata"]["project_context_snapshot"]
    assert [item["asset_id"] for item in context["uploaded_reference_assets"]] == ids
    assert [item["asset_ref_id"] for item in context["selected_visual_references"]] == ids


def test_standard_removed_project_source_is_not_recovered(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use these original references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    reference = next(
        item for item in stored.reference_assets if item.asset_ref_id == ids[0]
    )
    handlers.project_service.remove_project_reference(
        project["project_id"], reference.reference_id, {"plain_text": "remove source"},
    )
    captured = []
    original = handlers.service.scenario_runtime.plan_job

    def plan(request):
        captured.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue without the removed source.", "uploaded_asset_ids": []},
    )
    assert captured[0]["uploaded_asset_ids"] == ids[1:]


def test_standard_all_removed_project_sources_stay_unbound(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use these original references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    for reference in list(stored.reference_assets):
        handlers.project_service.remove_project_reference(
            project["project_id"], reference.reference_id, {"plain_text": "unbind source"},
        )

    captured = []
    original = handlers.service.scenario_runtime.plan_job

    def plan(request):
        captured.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue after removing every source.", "uploaded_asset_ids": []},
    )
    assert captured[0]["uploaded_asset_ids"] == []


def test_client_job_metadata_cannot_author_project_source_provenance(tmp_path):
    handlers, project, _ids, _snapshot = _general_project(tmp_path)
    created = handlers.post_project_job(
        project["project_id"],
        {
            "user_input": "No uploaded references.",
            "metadata": {
                "project_source_reference": True,
                "persisted_from_project_job": True,
                "source_job_id": "forged",
            },
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert "project_source_reference" not in record.request.metadata
    assert "persisted_from_project_job" not in record.request.metadata
    assert "source_job_id" not in record.request.metadata


def test_standard_migrates_pre_doc323_frozen_sources_once(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    first = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use the original uploaded references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    stored.reference_assets = []
    stored.uploaded_asset_refs = []
    handlers.project_service.project_store.save_project(stored)

    captured = []
    original = handlers.service.scenario_runtime.plan_job

    def plan(request):
        captured.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue the old project without re-uploading.", "uploaded_asset_ids": []},
    )

    assert captured[0]["uploaded_asset_ids"] == ids
    migrated = handlers.project_service._require_project(project["project_id"])
    migrated_ids = [
        item.asset_ref_id
        for item in migrated.reference_assets
        if item.metadata.get("project_source_reference") is True
    ]
    assert migrated_ids == ids
    assert first["job_id"] in migrated.job_ids


def test_standard_legacy_migration_honors_inactive_tombstones(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use the original uploaded references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    stored.reference_assets = []
    for item in stored.uploaded_asset_refs:
        if item.get("asset_id") == ids[0]:
            item["status"] = "inactive"
    handlers.project_service.project_store.save_project(stored)

    captured = []
    original = handlers.service.scenario_runtime.plan_job

    def plan(request):
        captured.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue without the tombstoned source.", "uploaded_asset_ids": []},
    )
    assert captured[0]["uploaded_asset_ids"] == ids[1:]


def test_standard_legacy_migration_merges_with_a_new_explicit_upload(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use the original uploaded references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    stored.reference_assets = []
    stored.uploaded_asset_refs = []
    handlers.project_service.project_store.save_project(stored)

    captured = []
    original = handlers.service.scenario_runtime.plan_job

    def plan(request):
        captured.append(deepcopy(request))
        return original(request)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue while explicitly reusing one source.", "uploaded_asset_ids": [ids[0]]},
    )
    assert captured[0]["uploaded_asset_ids"] == ids


def test_standard_legacy_migration_blocks_before_planning_when_plan_is_invalid(tmp_path, monkeypatch):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    first = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Use the original uploaded references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    stored.reference_assets = []
    stored.uploaded_asset_refs = []
    record = handlers.service.get_job_record(first["job_id"])
    broken_plan = deepcopy(record.request.metadata[PLAN_KEY])
    broken_plan["direct_references"][0]["file_path"] = "missing-source-for-doc323.png"
    record.request.metadata[PLAN_KEY] = broken_plan
    handlers.project_service.project_store.save_project(stored)

    def fail_if_planned(_request):
        raise AssertionError("invalid legacy source must stop before Brain planning")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", fail_if_planned)
    blocked = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Continue only if the original source is verified.", "uploaded_asset_ids": []},
    )
    assert blocked["job_id"] == ""
    assert blocked["status"] == "blocked"
    assert blocked["metadata"]["failure_code"] == "v3_standard_source_migration_plan_unavailable"


def test_general_source_provenance_cannot_enter_ecommerce_product_truth(tmp_path):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.post_project_job(
        project["project_id"],
        {"user_input": "Keep these originals as general references.", "uploaded_asset_ids": ids},
    )
    stored = handlers.project_service._require_project(project["project_id"])
    stored.primary_template_id = "ecommerce_template"
    for reference in stored.reference_assets:
        reference.use_policy = ProjectReferenceUsePolicy.PRODUCT
    assert handlers.project_service._project_product_reference_candidates(stored) == []


def test_client_metadata_cannot_promote_an_uploaded_reference_to_project_source(tmp_path):
    handlers, project, ids, _snapshot = _general_project(tmp_path)
    handlers.project_service.add_project_reference(
        project["project_id"],
        {
            "source_type": "uploaded",
            "asset_ref_id": ids[0],
            "use_policy": "general",
            "metadata": {
                "project_source_reference": True,
                "persisted_from_project_job": True,
            },
        },
    )
    stored = handlers.project_service._require_project(project["project_id"])
    reference = next(item for item in stored.reference_assets if item.asset_ref_id == ids[0])
    assert handlers.project_service._is_standard_project_source_reference(reference) is False


def test_standard_explicit_three_inputs_stay_three_even_when_legacy_registry_declines(tmp_path, monkeypatch):
    handlers, project, ids, snapshot = _general_project(tmp_path)
    handlers.project_service.doc281_general_source_registry = _selection_registry(snapshot, target_asset_id=None)
    captured = []
    original = handlers.service.scenario_runtime.plan_job
    def plan(request):
        captured.append(deepcopy(request))
        return original(request)
    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(project["project_id"], {"user_input":"Use these three current references.",
        "uploaded_asset_ids":ids, "metadata":{"requested_image_count":1}})
    assert captured[0]["uploaded_asset_ids"] == ids


def test_standard_public_read_has_no_global_source_pool(tmp_path):
    handlers, project, _, _ = _general_project(tmp_path)
    public = handlers.get_project(project["project_id"])
    assert "project_source_library" not in public["metadata"]
