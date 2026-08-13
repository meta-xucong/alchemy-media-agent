"""Phase 4A red contracts for Doc270 E-Commerce view-aware activation.

The fixtures use local Project Mode/Product API planning only.  They never
select a Provider, generate pixels, contact MCP, or mutate live records.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, PersistentProjectStore, source_library
from alchemy_creative_agent_3_0.app.project_mode import service as project_mode_service
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.project_mode.ecommerce_view_activation import (
    ConfiguredEcommerceViewActivationIssuer,
    DisabledEcommerceViewActivationIssuer,
    OpenAICompatibleEcommerceSourceEvidenceAnalyzer,
    ecommerce_view_activation_health,
    issuer_from_environment,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    V3ProductRouteHandlers,
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _bind_locked_person_identity,
    _job_payload,
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    MOBILE_HTML,
    MOBILE_JS,
    DESKTOP_HTML,
    DESKTOP_JS,
    _browser_page,
    _needs_input_job,
    _needs_input_project,
)


_CAPABILITY = {
    "schema_version": "doc270_ecommerce_view_activation_capability_v1",
    "issuer": "v3_doc270_ecommerce_activation_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": "doc270_phase4_ecommerce_view_activation_v1",
    "template_id": "ecommerce_template",
    "enabled": True,
}


def _fixture(tmp_path, *, count: int = 3):
    handlers, catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"phase4-source-{index}.png",
            color=(50 + 35 * index, 105 + 10 * index, 150 - 10 * index),
        )
        for index in range(count)
    ]
    _add_product_references(handlers, project["project_id"], product_ids)
    return handlers, catalog, project, product_ids


class _DeterministicServerAnalyzer:
    """Composition-root fake: semantic evidence is server adapter output only."""

    def __init__(self, profiles: dict[str, tuple[str, str]]) -> None:
        self.profiles = dict(profiles)
        self.calls: list[dict[str, Any]] = []

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        assert project_id
        assert len(entries) == 1
        entry = dict(entries[0])
        assert isinstance(entry.get("analysis_bytes"), bytes)
        assert entry["analysis_bytes"]
        assert "filename" not in entry
        assert "user_input" not in entry
        self.calls.append(entry)
        semantic = self.profiles.get(str(entry.get("reference_id") or ""))
        if semantic is None:
            return None
        view_kind, affordance = semantic
        return [{
            "evidence_state": "observed",
            "subject_kind": "object_or_product",
            "view_kind": view_kind,
            "affordances": [affordance],
        }]


def _real_issuer(
    profiles: dict[str, tuple[str, str]],
    *,
    expected_output_count: int,
) -> tuple[ConfiguredEcommerceViewActivationIssuer, _DeterministicServerAnalyzer]:
    analyzer = _DeterministicServerAnalyzer(profiles)
    requirements = {
        1: ({"output_index": 1, "kind": "object_front_presentation"},),
        2: (
            {"output_index": 1, "kind": "object_front_presentation"},
            {"output_index": 2, "kind": "object_rear_structure"},
        ),
        3: (
            {"output_index": 1, "kind": "object_front_presentation"},
            {"output_index": 2, "kind": "object_rear_structure"},
            {"output_index": 3, "kind": "object_detail"},
        ),
    }
    return (
        ConfiguredEcommerceViewActivationIssuer(
            requirements_by_output_count={expected_output_count: requirements[expected_output_count]},
            analyzer=analyzer,
        ),
        analyzer,
    )


def _composition_fixture(tmp_path, *, count: int = 3, policy_count: int | None = None):
    """Build normal uploads first, then a fresh composition root with issuer."""

    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    project_store = InMemoryProjectStore()
    catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(catalog)
    bootstrap = V3ProductRouteHandlers(
        service=service,
        project_store=project_store,
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=bindings,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
    )
    project = _project(bootstrap)
    product_ids = [
        _ready_product_upload(
            bootstrap,
            filename=f"composition-source-{index}.png",
            color=(65 + 30 * index, 105 + 8 * index, 150 - 8 * index),
        )
        for index in range(count)
    ]
    _add_product_references(bootstrap, project["project_id"], product_ids)
    associations = {
        _association_id(bootstrap, project["project_id"], asset_id): profile
        for asset_id, profile in zip(
            product_ids,
            [
                ("front", "object_front_presentation"),
                ("rear", "object_back_or_structure"),
                ("detail_or_macro", "object_detail"),
            ],
            strict=False,
        )
    }
    issuer, analyzer = _real_issuer(
        associations,
        expected_output_count=policy_count or count,
    )
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=project_store,
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=bindings,
        ecommerce_view_activation_issuer=issuer,
    )
    return handlers, catalog, project, product_ids, analyzer


def _snapshot(handlers: Any, project_id: str) -> dict[str, Any]:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return source_library.build_project_source_library(
        project_id=project.project_id,
        references=project.reference_assets,
        upload_lookup=handlers.service.get_uploaded_asset,
    )


def _association_id(handlers: Any, project_id: str, asset_id: str) -> str:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return next(item.reference_id for item in project.reference_assets if item.asset_ref_id == asset_id)


def _identity(project_id: str, *, command_id: str = "phase4-command-1") -> dict[str, str]:
    value = {
        "schema_version": "doc270_ecommerce_command_identity_v1",
        "issuer": "v3_project_mode_ecommerce_command_registry",
        "capability_id": _CAPABILITY["capability_id"],
        "capability_version": _CAPABILITY["capability_version"],
        "project_id": project_id,
        "template_id": "ecommerce_template",
        "command_id": command_id,
        "command_plan_binding_digest": f"phase4-plan-{command_id}",
        "coalescing_nonce": f"phase4-nonce-{command_id}",
    }
    value["identity_digest"] = source_library.canonical_digest(value)
    return value


def _entry(
    *,
    project_id: str,
    snapshot: dict[str, Any],
    identity: dict[str, Any],
    selections: list[tuple[int, str, str]],
) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    for output_index, reference_id, asset_id in selections:
        source = next(item for item in snapshot["entries"] if item["reference_id"] == reference_id)
        receipt = {
            "schema_version": "doc270_reference_resolution_receipt_v1",
            "issuer": "v3_doc270_shadow_matcher",
            "project_id": project_id,
            "command_identity": deepcopy(identity),
            "command_plan_binding_digest": identity["command_plan_binding_digest"],
            "output_index": output_index,
            "output_identity": f"phase4-output-{output_index}",
            "requirement_nonce": f"phase4-nonce-{output_index}",
            "requirement_digest": f"phase4-requirement-{output_index}",
            "source_library_snapshot_digest": snapshot["snapshot_digest"],
            "state": "resolved",
            "maximum_sources": 1,
            "matched_references": [{
                "reference_id": reference_id,
                "asset_id": asset_id,
                "content_sha256": source["content_sha256"],
                "profile_digest": f"phase4-profile-{output_index}",
            }],
            "evidence_profile_digests": [f"phase4-profile-{output_index}"],
            "requirement_kind": {1: "object_front_presentation", 2: "object_rear_structure", 3: "object_detail"}.get(
                output_index,
                "object_rear_structure",
            ),
            "evidence_profile": {
                "subject_kind": "object_or_product",
                "view_kind": {1: "front", 2: "rear", 3: "detail_or_macro"}.get(output_index, "rear"),
                "affordances": [
                    {1: "object_shape", 2: "object_back_or_structure", 3: "object_detail"}.get(
                        output_index,
                        "object_back_or_structure",
                    )
                ],
            },
            "shadow_only": True,
        }
        receipt["receipt_digest"] = source_library.canonical_digest(receipt)
        receipts.append(receipt)
    value = {
        "schema_version": "doc270_ecommerce_phase4_registry_entry_v1",
        "issuer": "v3_doc270_ecommerce_view_registry",
        "capability_id": _CAPABILITY["capability_id"],
        "capability_version": _CAPABILITY["capability_version"],
        "project_id": project_id,
        "template_id": "ecommerce_template",
        "command_identity": deepcopy(identity),
        "source_library_snapshot_digest": snapshot["snapshot_digest"],
        "receipts": receipts,
    }
    value["registry_entry_digest"] = source_library.canonical_digest(value)
    return value


def _install_future_gate(monkeypatch, handlers: Any, value: dict[str, Any], identity: dict[str, Any]) -> None:
    """Future private seams; Phase 4A deliberately leaves them unconsumed."""

    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_view_activation_capability_lookup",
        lambda: deepcopy(_CAPABILITY),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_command_identity_lookup",
        lambda **_kwargs: deepcopy(identity),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_phase2_receipt_registry_lookup",
        lambda **_kwargs: deepcopy(value),
        raising=False,
    )


def _payload(product_ids: list[str], *, key: str, count: int = 1, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _job_payload(uploaded_asset_ids=product_ids, key=key)
    payload["metadata"] = {
        **payload["metadata"],
        "requested_image_count": count,
        **(metadata or {}),
    }
    return payload


def _admitted_ids(record: Any) -> list[str]:
    return [item["asset_id"] for item in record.request.metadata["professional_ecommerce_product_truth_admission"]["sources"]]


def _count_planning_and_dispatch(monkeypatch, handlers: V3ProductRouteHandlers) -> dict[str, int]:
    calls = {"plan": 0, "dispatch": 0}
    original_plan = handlers.service.scenario_runtime.plan_job
    original_dispatch = handlers.service.scenario_runtime.generate_job

    def counting_plan(*args: Any, **kwargs: Any):
        calls["plan"] += 1
        return original_plan(*args, **kwargs)

    def counting_dispatch(*args: Any, **kwargs: Any):
        calls["dispatch"] += 1
        return original_dispatch(*args, **kwargs)

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", counting_plan)
    monkeypatch.setattr(handlers.service.scenario_runtime, "generate_job", counting_dispatch)
    return calls


def test_doc270_phase4_absent_gate_preserves_complete_doc263_admission(tmp_path) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-no-gate"))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert _admitted_ids(record) == product_ids
    assert "doc270_ecommerce_view_activation_receipts" not in record.request.metadata


def test_doc270_phase4_resolved_views_freeze_one_product_per_output_without_reducing_pool(tmp_path, monkeypatch) -> None:
    handlers, catalog, project, product_ids = _fixture(tmp_path)
    face_ids = _bind_locked_person_identity(handlers, catalog, project_id=project["project_id"])
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[
            (1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0]),
            (2, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1]),
            (3, _association_id(handlers, project["project_id"], product_ids[2]), product_ids[2]),
        ],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)
    calls = _count_planning_and_dispatch(monkeypatch, handlers)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-front-rear-detail", count=3))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert _admitted_ids(record) == product_ids
    receipts = record.request.metadata["doc270_ecommerce_view_activation_receipts"]
    assert [item["output_index"] for item in receipts] == [1, 2, 3]
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    assert projections["1"]["selected_product_asset_ids"] == [product_ids[0]]
    assert projections["2"]["selected_product_asset_ids"] == [product_ids[1]]
    assert projections["3"]["selected_product_asset_ids"] == [product_ids[2]]
    plans = record.request.metadata["physical_renderer_reference_plans"]
    assert plans["1"]["reference_image_asset_ids"][0] == product_ids[0]
    assert plans["2"]["reference_image_asset_ids"][0] == product_ids[1]
    assert plans["3"]["reference_image_asset_ids"][0] == product_ids[2]
    assert all(face_id not in str(receipts) for face_id in face_ids)


def test_doc270_phase4_real_server_registry_freezes_front_rear_detail_without_lookup_patches(tmp_path) -> None:
    """The enabled production registry, not test lookup seams, owns E31."""

    handlers, catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    face_ids = _bind_locked_person_identity(handlers, catalog, project_id=project["project_id"])

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-real-front-rear-detail", count=3))

    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None, {
        "created": created,
        "project_job_ids": handlers.project_service._require_project(project["project_id"]).job_ids,  # noqa: SLF001
    }
    assert _admitted_ids(record) == product_ids
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    plans = record.request.metadata["physical_renderer_reference_plans"]
    for index, asset_id in enumerate(product_ids, start=1):
        assert projections[str(index)]["selected_product_asset_ids"] == [asset_id]
        assert plans[str(index)]["reference_image_asset_ids"][0] == asset_id
    assert all(face_id not in str(record.request.metadata["doc270_ecommerce_view_activation_receipts"]) for face_id in face_ids)
    assert len(analyzer.calls) == len(product_ids)
    assert all(isinstance(item.get("analysis_bytes"), bytes) for item in analyzer.calls)
    assert "analysis_bytes" not in str(record.request.metadata)
    assert "analysis_bytes" not in str(handlers.get_project(project["project_id"]))
    public_job = handlers.get_job(created["job_id"])
    assert public_job["metadata"]["doc270_ecommerce_view_activation"] == {"state": "activated_resolved"}
    # E31 redaction is additive. It must not replace the ordinary job result
    # surface that later carries generated/review/final-delivery lifecycle.
    assert isinstance(public_job["asset_series"], list)
    assert isinstance(public_job["candidates"], list)
    assert isinstance(public_job["metadata"]["post_generation_review"], dict)
    assert isinstance(public_job["metadata"]["final_delivery"], dict)
    public_text = str(public_job)
    for private in [
        *product_ids,
        *(
            item["matched_references"][0]["content_sha256"]
            for item in record.request.metadata["doc270_ecommerce_view_activation_receipts"]
        ),
        "registry_entry_digest",
        "source_library_snapshot_digest",
    ]:
        assert private not in public_text


def test_doc270_phase4_activated_public_status_preserves_generated_review_lifecycle(tmp_path) -> None:
    handlers, _catalog, project, product_ids, _analyzer = _composition_fixture(tmp_path)
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="phase4-public-generated", count=3),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    record.status = ProductJobStatusValue.GENERATED
    record.generation_result = record.planning_result
    handlers.service.job_store.save(record)
    _save_history_output(handlers, job_id=created["job_id"], index=73)

    public_job = handlers.get_job(created["job_id"])

    assert public_job["status"] == "generated"
    assert public_job["metadata"]["doc270_ecommerce_view_activation"] == {"state": "activated_resolved"}
    assert public_job["asset_series"]
    assert isinstance(public_job["candidates"], list)
    assert isinstance(public_job["metadata"]["post_generation_review"], dict)
    assert isinstance(public_job["metadata"]["final_delivery"], dict)
    public_text = str(public_job)
    for private in [
        *product_ids,
        *(
            item["matched_references"][0]["content_sha256"]
            for item in record.request.metadata["doc270_ecommerce_view_activation_receipts"]
        ),
        "registry_entry_digest",
        "source_library_snapshot_digest",
    ]:
        assert private not in public_text


def test_doc270_phase4_real_registry_replay_is_frozen_without_second_analysis(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    first = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-real-replay", count=3))
    assert first["status"] == "planned"
    analysis_calls = len(analyzer.calls)
    second = handlers.post_project_job(
        project["project_id"],
        _payload(
            product_ids,
            key="phase4-real-replay-different-browser-key",
            count=3,
            metadata={
                "doc270_ecommerce_command_facts": {"selected_ids": ["browser-forged"]},
                "doc270_ecommerce_view_activation_receipts": {"forged": True},
            },
        ),
    )
    assert second["job_id"] == first["job_id"]
    assert len(analyzer.calls) == analysis_calls
    handlers.get_project(project["project_id"])
    handlers.get_job(first["job_id"])
    assert len(analyzer.calls) == analysis_calls


def test_doc270_phase4_incomplete_observation_does_not_become_product_input_failure(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    first = next(iter(analyzer.profiles))
    analyzer.profiles.pop(first)
    analyzer.profiles["not-current-association"] = ("front", "object_front_presentation")
    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-analyzer-binding-mismatch", count=3))
    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before  # noqa: SLF001
    assert created["metadata"]["current_operation"] == {
        "state": "source_analysis_unavailable",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "retry_source_analysis"}],
    }
    assert handlers.project_service.project_store.list_private_records(  # noqa: SLF001
        project["project_id"], "doc270_phase4_resolution_decisions"
    ) == []
    assert "not-current-association" not in str(created)


def test_doc270_phase4_analyzer_unavailable_is_not_frozen_and_manual_recovery_reanalyzes(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    original_profiles = dict(analyzer.profiles)
    analyzer.profiles.clear()
    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    first = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-analysis-failure", count=3))
    assert first["status"] == "blocked"
    assert first.get("job_id") in (None, "")
    assert first["metadata"]["current_operation"] == {
        "state": "source_analysis_unavailable",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "retry_source_analysis"}],
    }
    analysis_calls = len(analyzer.calls)
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before  # noqa: SLF001
    assert handlers.project_service.project_store.list_private_records(  # noqa: SLF001
        project["project_id"], "doc270_phase4_resolution_decisions"
    ) == []
    analyzer.profiles.update(original_profiles)
    second = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-analysis-failure-replay", count=3))
    assert second["status"] == "planned"
    assert second.get("job_id")
    assert len(analyzer.calls) == analysis_calls + len(product_ids)


def test_doc270_phase4_malformed_analyzer_response_is_retryable_not_product_input_failure(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    first_reference = next(iter(analyzer.profiles))
    analyzer.profiles[first_reference] = ("front", "object_back_or_structure")
    original_analyze = analyzer.analyze

    def malformed(*, project_id: str, entries: list[dict[str, Any]]):
        result = original_analyze(project_id=project_id, entries=entries)
        if result and entries[0]["reference_id"] == first_reference:
            return [{"evidence_state": "observed", "subject_kind": "object_or_product"}]
        return result

    analyzer.analyze = malformed  # type: ignore[method-assign]
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="phase4-malformed-analyzer", count=3),
    )

    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert created["metadata"]["current_operation"]["state"] == "source_analysis_unavailable"
    assert handlers.project_service.project_store.list_private_records(  # noqa: SLF001
        project["project_id"], "doc270_phase4_resolution_decisions"
    ) == []


def test_doc270_phase4_durable_original_drift_remains_product_input_failure(tmp_path) -> None:
    handlers, _catalog, project, product_ids, _analyzer = _composition_fixture(tmp_path)
    upload = handlers.service.get_uploaded_asset(product_ids[0])
    assert upload is not None
    Path(upload.file_path).unlink()

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="phase4-original-file-drift", count=3),
    )

    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert created["metadata"]["current_operation"] == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }


def test_doc270_phase4_unsupported_output_count_is_legacy_without_analysis_or_private_records(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(tmp_path)
    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="phase4-unsupported-count", count=4),
    )

    assert created["status"] == "planned"
    assert created.get("job_id")
    assert len(analyzer.calls) == 0
    assert handlers.project_service._require_project(project["project_id"]).job_ids != before  # noqa: SLF001
    for namespace in (
        "doc270_phase4_commands",
        "doc270_phase4_activation_policy",
        "doc270_phase4_registry_entries",
        "doc270_phase4_resolution_decisions",
    ):
        assert handlers.project_service.project_store.list_private_records(project["project_id"], namespace) == []  # noqa: SLF001


def test_doc270_phase4_partial_unavailable_original_does_not_block_satisfiable_mapping(tmp_path) -> None:
    handlers, _catalog, project, product_ids, analyzer = _composition_fixture(
        tmp_path,
        count=3,
        policy_count=2,
    )
    unavailable_reference = _association_id(handlers, project["project_id"], product_ids[2])
    analyzer.profiles.pop(unavailable_reference)

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key="phase4-partial-analysis", count=2),
    )

    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    selections = record.request.metadata["doc270_ecommerce_view_activation_selection"]
    assert len(selections) == 2
    assert all(item["selected_product_asset_id"] != product_ids[2] for item in selections)


def test_doc270_phase4_environment_policy_rejects_static_profiles_and_missing_dynamic_analyzer(tmp_path, monkeypatch) -> None:
    from app.config import settings

    original = {
        "lab_vision_enabled": settings.lab_vision_enabled,
        "lab_vision_provider": settings.lab_vision_provider,
        "lab_doubao_vision_api_key": settings.lab_doubao_vision_api_key,
        "lab_doubao_vision_base_url": settings.lab_doubao_vision_base_url,
        "lab_doubao_vision_model": settings.lab_doubao_vision_model,
    }
    policy_path = tmp_path / "ecommerce-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "requirements_by_output_count": {"1": [{"output_index": 1, "kind": "object_front_presentation"}]},
                "profiles": [{"reference_id": "browser-or-static", "asset_id": "v3_asset_static", "content_sha256": "f" * 64}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALCHEMY_DOC270_ECOMMERCE_VIEW_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY", "test-key")
    monkeypatch.setenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_MODEL", "test-model")
    assert isinstance(issuer_from_environment(), DisabledEcommerceViewActivationIssuer)

    policy_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "requirements_by_output_count": {"1": [{"output_index": 1, "kind": "object_front_presentation"}]},
            }
        ),
        encoding="utf-8",
    )
    try:
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY")
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_BASE_URL")
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_MODEL")
        settings.lab_vision_enabled = False
        assert isinstance(issuer_from_environment(), DisabledEcommerceViewActivationIssuer)

        settings.lab_vision_enabled = True
        settings.lab_vision_provider = "doubao"
        settings.lab_doubao_vision_api_key = "test-lab-key"
        settings.lab_doubao_vision_base_url = "https://vision.example.test/v1"
        settings.lab_doubao_vision_model = "vision-test-model"
        configured = issuer_from_environment()
        health = ecommerce_view_activation_health()
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
    assert isinstance(configured, ConfiguredEcommerceViewActivationIssuer)
    assert configured.capability(project_id="project_configured") == _CAPABILITY
    assert configured.analyzer.preferred_protocol == "chat"
    assert health == {
        "component": "doc270_ecommerce_source_analysis",
        "configured": True,
        "enabled": True,
        "network_checked": False,
    }


def test_doc270_phase4_bundled_policy_activates_only_supported_output_counts(monkeypatch) -> None:
    from app.config import settings

    original = {
        "lab_vision_enabled": settings.lab_vision_enabled,
        "lab_vision_provider": settings.lab_vision_provider,
        "lab_doubao_vision_api_key": settings.lab_doubao_vision_api_key,
        "lab_doubao_vision_base_url": settings.lab_doubao_vision_base_url,
        "lab_doubao_vision_model": settings.lab_doubao_vision_model,
    }
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "project_mode"
        / "policies"
        / "doc270_ecommerce_view_policy_v1.json"
    )
    try:
        monkeypatch.setenv("ALCHEMY_DOC270_ECOMMERCE_VIEW_POLICY_PATH", str(policy_path))
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY", raising=False)
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_BASE_URL", raising=False)
        monkeypatch.delenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_MODEL", raising=False)
        settings.lab_vision_enabled = True
        settings.lab_vision_provider = "doubao"
        settings.lab_doubao_vision_api_key = "test-lab-key"
        settings.lab_doubao_vision_base_url = "https://vision.example.test/v1"
        settings.lab_doubao_vision_model = "vision-test-model"
        configured = issuer_from_environment()
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
    assert isinstance(configured, ConfiguredEcommerceViewActivationIssuer)
    assert [configured.supports_output_count(expected_output_count=count) for count in range(1, 5)] == [
        True,
        True,
        True,
        False,
    ]


def test_doc270_phase4_analyzer_uses_chat_only_for_non_timeout_responses_rejection(monkeypatch) -> None:
    calls: list[str] = []

    class BadRequestError(RuntimeError):
        pass

    class _Responses:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("responses")
            raise BadRequestError("responses endpoint unsupported")

    class _ChatCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            calls.append("chat")
            assert kwargs["response_format"] == {"type": "json_object"}
            message = kwargs["messages"][0]["content"][0]["text"]
            assert "exactly these four fields" in message
            for field in ("evidence_state", "subject_kind", "view_kind", "affordances"):
                assert field in message
            for value in (
                "object_or_product",
                "person",
                "brand_or_graphic",
                "front",
                "rear",
                "detail_or_macro",
                "environment_wide",
                "packaging",
                "object_front_presentation",
                "object_back_or_structure",
                "object_detail",
                "environment",
                "logo_or_mark",
            ):
                assert value in message
            assert "project_doc270" not in message
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "evidence_state": "observed",
                    "subject_kind": "object_or_product",
                    "view_kind": "front",
                    "affordances": ["object_front_presentation"],
                })))]
            )

    class _Client:
        responses = _Responses()
        chat = SimpleNamespace(completions=_ChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    analyzer = OpenAICompatibleEcommerceSourceEvidenceAnalyzer(
        api_key="test-key", base_url="https://vision.example.test/v1", model="vision-test"
    )
    result = analyzer.analyze(
        project_id="project_doc270",
        entries=[{"analysis_bytes": b"source", "mime_type": "image/png"}],
    )
    assert calls == ["responses", "chat"]
    assert result == [{
        "evidence_state": "observed",
        "subject_kind": "object_or_product",
        "view_kind": "front",
        "affordances": ["object_front_presentation"],
    }]


def test_doc270_phase4_analyzer_does_not_resubmit_timeout_through_chat(monkeypatch) -> None:
    calls: list[str] = []

    class _Responses:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("responses")
            raise TimeoutError("request timed out")

    class _ChatCompletions:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("chat")
            raise AssertionError("timeout must not be submitted through Chat")

    class _Client:
        responses = _Responses()
        chat = SimpleNamespace(completions=_ChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    analyzer = OpenAICompatibleEcommerceSourceEvidenceAnalyzer(
        api_key="test-key", base_url="https://vision.example.test/v1", model="vision-test"
    )
    assert analyzer.analyze(
        project_id="project_doc270",
        entries=[{"analysis_bytes": b"source", "mime_type": "image/png"}],
    ) is None
    assert calls == ["responses"]


def test_doc270_phase4_analyzer_does_not_resubmit_ordinary_responses_failure(monkeypatch) -> None:
    calls: list[str] = []

    class _Responses:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("responses")
            raise RuntimeError("upstream rejected this request")

    class _ChatCompletions:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("chat")
            raise AssertionError("ordinary failure must not be submitted through Chat")

    class _Client:
        responses = _Responses()
        chat = SimpleNamespace(completions=_ChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    analyzer = OpenAICompatibleEcommerceSourceEvidenceAnalyzer(
        api_key="test-key", base_url="https://vision.example.test/v1", model="vision-test"
    )
    assert analyzer.analyze(
        project_id="project_doc270",
        entries=[{"analysis_bytes": b"source", "mime_type": "image/png"}],
    ) is None
    assert calls == ["responses"]


def test_doc270_phase4_lab_analyzer_uses_certified_chat_without_responses_attempt(monkeypatch) -> None:
    calls: list[str] = []

    class _Responses:
        def create(self, **_kwargs):  # noqa: ANN003
            calls.append("responses")
            raise AssertionError("LAB route must use its certified Chat protocol directly")

    class _ChatCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            calls.append("chat")
            assert kwargs["response_format"] == {"type": "json_object"}
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "evidence_state": "observed",
                    "subject_kind": "object_or_product",
                    "view_kind": "front",
                    "affordances": ["object_front_presentation"],
                })))]
            )

    class _Client:
        responses = _Responses()
        chat = SimpleNamespace(completions=_ChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    analyzer = OpenAICompatibleEcommerceSourceEvidenceAnalyzer(
        api_key="test-key",
        base_url="https://vision.example.test/v1",
        model="vision-test",
        preferred_protocol="chat",
    )
    assert analyzer.analyze(
        project_id="project_doc270",
        entries=[{"analysis_bytes": b"source", "mime_type": "image/png"}],
    ) == [{
        "evidence_state": "observed",
        "subject_kind": "object_or_product",
        "view_kind": "front",
        "affordances": ["object_front_presentation"],
    }]
    assert calls == ["chat"]


@pytest.mark.parametrize(
    "payload",
    [
        {"evidence_state": "observed", "subject_kind": "object_or_product", "view_kind": "front"},
        {
            "evidence_state": "observed",
            "subject_kind": "object_or_product",
            "view_kind": "unsupported_view",
            "affordances": ["object_front_presentation"],
        },
        {
            "evidence_state": "observed",
            "subject_kind": "object_or_product",
            "view_kind": "front",
            "affordances": ["object_front_presentation"],
            "extra": "forged",
        },
        {
            "evidence_state": "observed",
            "subject_kind": "object_or_product",
            "view_kind": "front",
            "affordances": [{"unhashable": "forged"}],
        },
    ],
)
def test_doc270_phase4_lab_chat_analyzer_rejects_noncompliant_json_without_retry(monkeypatch, payload) -> None:  # noqa: ANN001
    calls: list[dict[str, Any]] = []

    class _ChatCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

    class _Client:
        chat = SimpleNamespace(completions=_ChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    analyzer = OpenAICompatibleEcommerceSourceEvidenceAnalyzer(
        api_key="test-key",
        base_url="https://vision.example.test/v1",
        model="vision-test",
        preferred_protocol="chat",
    )
    assert analyzer.analyze(
        project_id="project_doc270",
        entries=[{"analysis_bytes": b"synthetic-64x64-png", "mime_type": "image/png"}],
    ) is None
    assert len(calls) == 1


def test_doc270_phase4_private_store_freezes_nested_records_and_persists_outside_project_json(tmp_path) -> None:
    project_id = "project_doc270_private_store"
    canonical = {
        "identity_digest": "a" * 64,
        "nested": {"receipts": [{"state": "resolved"}]},
    }
    payload = deepcopy(canonical)
    memory = InMemoryProjectStore()
    returned = memory.append_private_record(project_id, "doc270_phase4_registry_entries", payload)
    returned["nested"]["receipts"][0]["state"] = "mutated"
    payload["nested"]["receipts"].append({"state": "forged"})
    reread = memory.list_private_records(project_id, "doc270_phase4_registry_entries")
    assert reread == [{"identity_digest": "a" * 64, "nested": {"receipts": [{"state": "resolved"}]}}]
    reread[0]["nested"]["receipts"][0]["state"] = "mutated-again"
    assert memory.list_private_records(project_id, "doc270_phase4_registry_entries")[0]["nested"]["receipts"][0]["state"] == "resolved"
    assert memory.append_private_record(project_id, "doc270_phase4_registry_entries", canonical) == canonical
    with pytest.raises(ValueError, match="private_record_identity_conflict"):
        memory.append_private_record(
            project_id,
            "doc270_phase4_registry_entries",
            {"identity_digest": "a" * 64, "nested": {"receipts": [{"state": "conflict"}]}},
        )
    with pytest.raises(ValueError, match="private_record_namespace_invalid"):
        memory.append_private_record(project_id, "browser-selected-namespace", payload)

    persistent = PersistentProjectStore(tmp_path / "projects")
    persistent.append_private_record(project_id, "doc270_phase4_registry_entries", canonical)
    reloaded = PersistentProjectStore(tmp_path / "projects")
    assert reloaded.list_private_records(project_id, "doc270_phase4_registry_entries") == [
        {"identity_digest": "a" * 64, "nested": {"receipts": [{"state": "resolved"}]}}
    ]
    private_path = tmp_path / "projects" / project_id / "private_records.json"
    assert private_path.exists()
    assert not (tmp_path / "projects" / project_id / "project.json").exists()
    with pytest.raises(ValueError, match="private_record_identity_conflict"):
        reloaded.append_private_record(
            project_id,
            "doc270_phase4_registry_entries",
            {"identity_digest": "a" * 64, "nested": {"receipts": [{"state": "conflict-after-reload"}]}},
        )


def test_doc270_phase4_private_records_survive_reload_without_public_project_leak(tmp_path) -> None:
    storage_root = tmp_path / "projects"
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    store = PersistentProjectStore(storage_root)
    handlers = V3ProductRouteHandlers(service=service, project_store=store)
    project = _project(handlers)
    private = {
        "identity_digest": "b" * 64,
        "nested": {"registry": [{"source_sha": "c" * 64, "asset_id": "v3_asset_private"}]},
    }
    store.append_private_record(project["project_id"], "doc270_phase4_registry_entries", private)
    reloaded = PersistentProjectStore(storage_root)
    assert reloaded.list_private_records(project["project_id"], "doc270_phase4_registry_entries") == [private]
    project_json = (storage_root / project["project_id"] / "project.json").read_text(encoding="utf-8")
    assert "doc270_phase4_registry_entries" not in project_json
    assert "v3_asset_private" not in project_json
    restarted = V3ProductRouteHandlers(service=service, project_store=reloaded)
    public = restarted.get_project(project["project_id"])
    assert "doc270_phase4" not in str(public)
    assert "v3_asset_private" not in str(public)



@pytest.mark.parametrize("mutation", ["stale_sha", "missing_file", "generated", "cross_project", "duplicate_output"])
def test_doc270_phase4_invalid_hard_receipt_closes_before_job_or_plan(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    if mutation == "stale_sha":
        value["receipts"][0]["matched_references"][0]["content_sha256"] = "f" * 64
    elif mutation == "missing_file":
        upload = handlers.service.get_uploaded_asset(product_ids[0])
        assert upload is not None
        Path(upload.file_path).unlink()
    elif mutation == "generated":
        value["receipts"][0]["matched_references"][0]["asset_id"] = "generated-review-output"
    elif mutation == "cross_project":
        value["project_id"] = "project_other"
    else:
        value["receipts"].append(deepcopy(value["receipts"][0]))
    _install_future_gate(monkeypatch, handlers, value, identity)
    calls = _count_planning_and_dispatch(monkeypatch, handlers)

    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"phase4-invalid-{mutation}", metadata={
            "doc270_ecommerce_view_activation": True,
            "doc270_reference_resolution_receipts": value,
        }),
    )
    assert created["status"] == "blocked"
    assert created["metadata"]["current_operation"] == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before  # noqa: SLF001
    assert calls == {"plan": 0, "dispatch": 0}
    project_readback = handlers.get_project(project["project_id"])
    project_operation = project_readback.get("metadata", {}).get("current_operation")
    assert project_operation == created["metadata"]["current_operation"]
    assert "job_id" not in str(project_operation)
    assert all(word not in str(project_operation).lower() for word in ("planning", "generating", "preparing"))
    assert "doc270_ecommerce_view_activation" not in str(project_readback)
    assert "registry_entry_digest" not in str(project_readback)
    public_text = str(created)
    for private in [product_ids[0], "f" * 64, "generated-review-output", "project_other"]:
        assert private not in public_text


def test_doc270_phase4_malformed_private_identity_closes_without_a_job(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_view_activation_capability_lookup",
        lambda: deepcopy(_CAPABILITY),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_command_identity_lookup",
        lambda **_kwargs: {"issuer": "untrusted"},
        raising=False,
    )
    calls = _count_planning_and_dispatch(monkeypatch, handlers)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-bad-identity"))

    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert calls == {"plan": 0, "dispatch": 0}
    assert handlers.get_project(project["project_id"])["metadata"]["current_operation"] == created["metadata"]["current_operation"]
    assert "untrusted" not in str(created)


def _register_real_phase4_policy(
    handlers: Any,
    *,
    project_id: str,
    selections: list[tuple[int, str, str]],
) -> None:
    """Register server-held E31 policy/evidence without a lookup monkeypatch."""

    snapshot = _snapshot(handlers, project_id)
    requirements: list[dict[str, Any]] = []
    evidence_profiles: list[dict[str, Any]] = []
    for output_index, reference_id, asset_id in selections:
        entry = next(item for item in snapshot["entries"] if item["reference_id"] == reference_id)
        kind, view_kind, affordance = {
            1: ("object_front_presentation", "front", "object_front_presentation"),
            2: ("object_rear_structure", "rear", "object_back_or_structure"),
            3: ("object_detail", "detail_or_macro", "object_detail"),
        }.get(output_index, ("object_rear_structure", "rear", "object_back_or_structure"))
        requirements.append({"output_index": output_index, "kind": kind})
        evidence = {
            "schema_version": "doc270_source_evidence_profile_v2",
            "analyzer": deepcopy(project_mode_service._DOC270_PHASE4_ANALYZER),  # noqa: SLF001
            "project_id": project_id,
            "reference_id": reference_id,
            "asset_id": asset_id,
            "content_sha256": entry["content_sha256"],
            "evidence_state": "observed",
            "subject_kind": "object_or_product",
            "view_kind": view_kind,
            "affordances": [affordance],
        }
        evidence["profile_digest"] = source_library.canonical_digest(evidence)
        evidence_profiles.append(evidence)
    handlers.project_service._register_doc270_ecommerce_view_activation_policy(  # noqa: SLF001
        project_id=project_id,
        requirements=requirements,
        evidence_profiles=evidence_profiles,
        provenance={"authority": "controlled_test_policy", "version": "v1"},
    )


def test_doc270_phase4_new_real_command_clears_prior_no_job_closure(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    value["receipts"][0]["matched_references"][0]["content_sha256"] = "f" * 64
    _install_future_gate(monkeypatch, handlers, value, identity)
    blocked = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-stale-operation"))
    assert blocked["status"] == "blocked"
    assert handlers.get_project(project["project_id"])["metadata"]["current_operation"]["state"] == "needs_input"

    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_view_activation_capability_lookup",
        lambda: None,
        raising=False,
    )
    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-next-real-command"))

    assert created["status"] == "planned"
    operation = handlers.get_project(project["project_id"]).get("metadata", {}).get("current_operation")
    assert not isinstance(operation, dict) or operation.get("state") != "needs_input"


def test_doc270_phase4_browser_fields_cannot_author_view_activation(tmp_path, monkeypatch) -> None:
    ungated_handlers, _ungated_catalog = _handlers(tmp_path / "ungated")
    ungated_project = _project(ungated_handlers)
    ungated = ungated_handlers.post_project_job(
        ungated_project["project_id"],
        _payload([], key="phase4-browser-only", metadata={
            "doc270_ecommerce_view_activation": True,
            "doc270_reference_resolution_receipts": {"asset_id": "browser-forged-asset"},
            "selected_product_asset_ids": ["browser-forged-asset"],
        }),
    )
    ungated_record = ungated_handlers.service.get_job_record(ungated["job_id"])
    assert ungated_record is not None
    assert "doc270_ecommerce_view_activation_receipts" not in ungated_record.request.metadata

    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-browser-forgery")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)
    created = handlers.post_project_job(
        project["project_id"],
        _payload(
            product_ids,
            key="phase4-browser-forgery",
            metadata={
                "doc270_ecommerce_view_activation": True,
                "doc270_reference_resolution_receipts": {"asset_id": "browser-forged-asset"},
                "selected_product_asset_ids": ["browser-forged-asset"],
            },
        ),
    )
    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert "doc270_ecommerce_view_activation_receipts" in record.request.metadata
    public_text = str(created)
    assert "browser-forged-asset" not in public_text


@pytest.mark.parametrize("output_indexes", [[1, 3], [1, 2, 3, 5], [1, 1, 2]])
def test_doc270_phase4_output_receipts_must_cover_exact_outputs_before_job(tmp_path, monkeypatch, output_indexes: list[int]) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path, count=4)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id=f"phase4-output-set-{''.join(map(str, output_indexes))}")
    selections = [
        (
            index,
            _association_id(handlers, project["project_id"], product_ids[min(index - 1, len(product_ids) - 1)]),
            product_ids[min(index - 1, len(product_ids) - 1)],
        )
        for index in output_indexes
    ]
    value = _entry(project_id=project["project_id"], snapshot=snapshot, identity=identity, selections=selections)
    _install_future_gate(monkeypatch, handlers, value, identity)
    calls = _count_planning_and_dispatch(monkeypatch, handlers)
    before = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001

    created = handlers.post_project_job(
        project["project_id"],
        _payload(product_ids, key=f"phase4-output-set-{output_indexes}", count=4),
    )

    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before  # noqa: SLF001
    assert calls == {"plan": 0, "dispatch": 0}
    project_readback = handlers.get_project(project["project_id"])
    assert project_readback.get("metadata", {}).get("current_operation") == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    assert "doc270_ecommerce_view_activation" not in str(project_readback)
    assert "registry_entry_digest" not in str(project_readback)


@pytest.mark.parametrize("template_id", ["general_template", "photographer_template"])
def test_doc270_phase4_does_not_change_general_or_photography(tmp_path, monkeypatch, template_id: str) -> None:
    handlers, _catalog = _handlers(tmp_path)
    if template_id == "photographer_template":
        with pytest.raises(ValueError):
            handlers.post_projects(
                {"user_goal": "Keep the existing Photography workflow.", "primary_template_id": template_id}
            )
        return
    project = handlers.post_projects(
        {"user_goal": "Keep the existing prompt-only workflow.", "primary_template_id": template_id}
    )["project"]
    calls = _count_planning_and_dispatch(monkeypatch, handlers)
    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": template_id,
            "user_input": "Create an ordinary prompt-only visual.",
            "uploaded_asset_ids": [],
            "metadata": {
                "idempotency_key": f"phase4-isolation-{template_id}",
                "doc270_ecommerce_view_activation": True,
                "doc270_reference_resolution_receipts": {"selected_asset_ids": ["browser-forged"]},
            },
        },
    )
    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert "doc270_ecommerce_view_activation_receipts" not in record.request.metadata
    assert "browser-forged" not in str(created)
    assert calls["dispatch"] == 0


def test_doc270_phase4_same_identity_returns_one_frozen_job_without_rematch(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"])
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[2]), product_ids[2])],
    )
    calls = {"registry": 0}
    _install_future_gate(monkeypatch, handlers, value, identity)
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_ecommerce_phase2_receipt_registry_lookup",
        lambda **_kwargs: calls.__setitem__("registry", calls["registry"] + 1) or deepcopy(value),
        raising=False,
    )

    first = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-replay"))
    second = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-replay", metadata={"forged_selected_product_ids": product_ids[:2]}))
    assert second["job_id"] == first["job_id"]
    assert calls["registry"] == 1
    handlers.get_project(project["project_id"])
    handlers.get_job(first["job_id"])
    assert calls["registry"] == 1


def test_doc270_phase4_keeps_generated_continuation_separate_and_no_product_prompt_only(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    initial = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-history"))
    output = _save_history_output(handlers, job_id=initial["job_id"], index=41)
    selected = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": output.output_id,
            "source_type": ProjectReferenceSourceType.GENERATED_SELECTED,
            "created_from_job_id": initial["job_id"],
            "created_from_output_id": output.output_id,
            "use_policy": "style",
        },
    )

    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-continuation")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1])],
    )
    _install_future_gate(monkeypatch, handlers, value, identity)
    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-continuation"))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert selected["reference"]["source_type"] == "generated_selected"
    assert output.output_id not in str(record.request.metadata.get("doc270_ecommerce_view_activation_receipts", []))
    assert initial["job_id"] in handlers.project_service._require_project(project["project_id"]).job_ids  # noqa: SLF001

    empty_project = _project(handlers)
    prompt_only = handlers.post_project_job(empty_project["project_id"], _payload([], key="phase4-no-product"))
    assert prompt_only["status"] == "planned"
    assert prompt_only["metadata"].get("ecommerce_text_to_image_fallback") is True


def test_doc270_phase4_non_apparel_typed_view_evidence_selects_only_matching_original(tmp_path, monkeypatch) -> None:
    """A non-apparel object uses typed view evidence, never category heuristics."""

    handlers, _catalog, project, product_ids = _fixture(tmp_path, count=3)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-mug-rear")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[1]), product_ids[1])],
    )
    value["receipts"][0]["requirement_kind"] = "object_rear_structure"
    value["receipts"][0]["evidence_profile"] = {
        "subject_kind": "object_or_product",
        "view_kind": "rear",
        "affordances": ["object_back_or_structure"],
        "semantic_domain": "ceramic_mug",
    }
    value["receipts"][0]["receipt_digest"] = source_library.canonical_digest(
        {key: item for key, item in value["receipts"][0].items() if key != "receipt_digest"}
    )
    value["registry_entry_digest"] = source_library.canonical_digest(
        {key: item for key, item in value.items() if key != "registry_entry_digest"}
    )
    _install_future_gate(monkeypatch, handlers, value, identity)

    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-mug-rear"))
    assert created["status"] == "planned"
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipts = record.request.metadata.get("doc270_ecommerce_view_activation_receipts")
    assert receipts is not None
    assert receipts[0]["matched_references"][0]["asset_id"] == product_ids[1]
    assert receipts[0]["evidence_profile"]["subject_kind"] == "object_or_product"
    assert receipts[0]["evidence_profile"]["view_kind"] == "rear"
    assert product_ids[0] not in str(receipts)
    assert product_ids[2] not in str(receipts)


def test_doc270_phase4_typed_requirement_and_profile_are_receipt_digest_bound(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, product_ids = _fixture(tmp_path)
    snapshot = _snapshot(handlers, project["project_id"])
    identity = _identity(project["project_id"], command_id="phase4-typed-digest")
    value = _entry(
        project_id=project["project_id"],
        snapshot=snapshot,
        identity=identity,
        selections=[(1, _association_id(handlers, project["project_id"], product_ids[0]), product_ids[0])],
    )
    receipt = value["receipts"][0]
    original_digest = receipt["receipt_digest"]
    receipt["evidence_profile"]["view_kind"] = "detail_or_macro"
    assert receipt["receipt_digest"] == original_digest
    _install_future_gate(monkeypatch, handlers, value, identity)
    created = handlers.post_project_job(project["project_id"], _payload(product_ids, key="phase4-typed-digest"))
    assert created["status"] == "blocked"
    assert created.get("job_id") in (None, "")
    assert "detail_or_macro" not in str(created)


def test_doc270_phase4_desktop_terminal_product_review_action_is_local_and_not_preparing() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    project["job_ids"] = []
    project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]["failed_attempts"] = []
    created["job_id"] = ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  v3State.currentProject = project;
                  v3State.currentJob = created;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  renderV3ProjectDetail();
                  document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; });
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-v3-project-action='review_product_inputs']").count() == 1
            text_content = page.locator("#v3ProjectNextActions").inner_text()
            assert "准备生成" not in text_content
            assert "生成中" not in text_content
            page.locator("[data-v3-project-action='review_product_inputs']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert "Canonical product original" in page.locator("#v3UsefulReferenceBoard").inner_text()
        finally:
            browser.close()


def test_doc270_phase4_mobile_terminal_product_review_action_is_local_and_not_preparing() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    project["job_ids"] = []
    project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]["failed_attempts"] = []
    created["job_id"] = ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = created;
                  mobileV3State.projects = [project];
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-mobile-v3-project-action='review_product_inputs']").count() == 1
            text_content = page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert "准备中" not in text_content
            assert "进行中" not in text_content
            page.locator("[data-mobile-v3-project-action='review_product_inputs']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert page.evaluate("document.body.dataset.mobileActiveSurface || ''") != ""
        finally:
            browser.close()


def test_doc270_phase4_desktop_analysis_outage_is_terminal_and_retry_is_local() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    operation = {
        "state": "source_analysis_unavailable",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "retry_source_analysis"}],
    }
    project["job_ids"] = []
    project["metadata"]["current_operation"] = operation
    project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]["failed_attempts"] = []
    created["job_id"] = ""
    created["metadata"]["current_operation"] = operation
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  v3State.currentProject = project;
                  v3State.currentJob = created;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  renderV3ProjectDetail();
                  document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; });
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-v3-project-action='retry_source_analysis']").count() == 1
            text_content = page.locator("#v3ProjectNextActions").inner_text()
            assert "准备生成" not in text_content
            assert "生成中" not in text_content
            page.locator("[data-v3-project-action='retry_source_analysis']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


def test_doc270_phase4_mobile_analysis_outage_is_terminal_and_retry_is_local() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    operation = {
        "state": "source_analysis_unavailable",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "retry_source_analysis"}],
    }
    project["job_ids"] = []
    project["metadata"]["current_operation"] = operation
    project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]["failed_attempts"] = []
    created["job_id"] = ""
    created["metadata"]["current_operation"] = operation
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = created;
                  mobileV3State.projects = [project];
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                {"project": project, "created": created},
            )
            assert page.locator("[data-mobile-v3-project-action='retry_source_analysis']").count() == 1
            text_content = page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert "准备中" not in text_content
            assert "进行中" not in text_content
            page.locator("[data-mobile-v3-project-action='retry_source_analysis']").click()
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()


@pytest.mark.parametrize(
    ("html_path", "script_path", "action_selector", "setup", "operation_selector", "post_count"),
    [
        (
            DESKTOP_HTML,
            DESKTOP_JS,
            "[data-v3-project-action='retry_source_analysis']",
            """
              ({ project, created }) => {
                window.__doc263ServerProject = project;
                window.__doc263CreateJobResponse = created;
                v3State.currentProject = project;
                v3State.currentJob = created;
                v3State.selectedScenario = "ecommerce";
                v3State.templateCatalogStatus = "ready";
                v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                v3State.loading = true;
                v3State.progressStageKey = "planning";
                v3State.progressTimer = window.setTimeout(() => {}, 1000);
                document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                renderV3ProjectDetail();
                document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; });
              }
            """,
            "#v3ProjectNextActions",
            "window.__doc263Requests.filter((item) => item.method === 'POST').length",
        ),
        (
            MOBILE_HTML,
            MOBILE_JS,
            "[data-mobile-v3-project-action='retry_source_analysis']",
            """
              ({ project, created }) => {
                ensureMobileLayers();
                setupMobileV3Adapter();
                window.__doc263ServerProject = project;
                window.__doc263CreateJobResponse = created;
                mobileV3State.currentProject = project;
                mobileV3State.currentJob = created;
                mobileV3State.projects = [project];
                mobileV3State.selectedTemplate = "ecommerce_template";
                mobileV3State.busy = true;
                mobileV3State.progressStageKey = "planning";
                mobileV3State.progressTimer = window.setTimeout(() => {}, 1000);
                renderMobileV3ProjectCurrentOperation(project);
                openMobileSurface("v3-project-detail");
              }
            """,
            "#mobileV3ProjectCurrentOperation",
            "window.__doc263Requests.filter((item) => item.method === 'POST').length",
        ),
    ],
)
def test_doc270_phase4_source_analysis_unavailable_action_is_local_and_clears_progress(
    html_path,
    script_path,
    action_selector,
    setup,
    operation_selector,
    post_count,
) -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    operation = {
        "state": "source_analysis_unavailable",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "retry_source_analysis"}],
    }
    project["job_ids"] = []
    project["metadata"]["current_operation"] = operation
    created["job_id"] = ""
    created["metadata"]["current_operation"] = operation
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            page.evaluate(setup, {"project": project, "created": created})
            assert page.locator(action_selector).count() == 1
            text_content = page.locator(operation_selector).inner_text()
            assert "准备" not in text_content
            assert "生成中" not in text_content
            page.locator(action_selector).click()
            assert page.evaluate(post_count) == 0
            if "mobile" in action_selector:
                assert page.evaluate("mobileV3State.busy === false && mobileV3State.progressTimer === null")
            else:
                assert page.evaluate("v3State.loading === false && v3State.progressTimer === null")
        finally:
            browser.close()
