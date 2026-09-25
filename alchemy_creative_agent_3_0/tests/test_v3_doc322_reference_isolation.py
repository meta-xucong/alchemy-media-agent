"""Doc322: explicit job inputs, not a cross-job original-source pool."""
from copy import deepcopy
import pytest
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project, _selection_registry


def test_standard_does_not_recover_old_sources_or_invoke_source_matching(tmp_path, monkeypatch):
    handlers, project, ids, snapshot = _general_project(tmp_path)
    calls = {}
    handlers.project_service.doc281_general_source_registry = _selection_registry(snapshot, target_asset_id=ids[0], calls=calls)
    captured = []
    original = handlers.service.scenario_runtime.plan_job
    def plan(request):
        captured.append(deepcopy(request))
        return original(request)
    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", plan)
    handlers.post_project_job(project["project_id"], {"user_input":"A new landscape; no inherited product input.",
        "uploaded_asset_ids":[], "metadata":{"requested_image_count":1}})
    assert captured[0]["uploaded_asset_ids"] == []
    assert calls == {}
    context = captured[0]["metadata"]["project_context_snapshot"]
    assert not context["uploaded_reference_assets"]
    assert not context["selected_visual_references"]


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
