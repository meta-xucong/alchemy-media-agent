"""Phase 0 red contracts for Doc281 unified source-library activation.

These tests use only local in-memory stores and deterministic uploaded image
fixtures. They intentionally assert the next server-owned behavior before its
runtime implementation exists. They never select a live Provider, contact MCP
or ImageGen, write a real Job, or deploy a service.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue, V3AssetUploadStatusValue
from alchemy_creative_agent_3_0.app.project_mode import (
    PersistentProjectStore,
    V3ProjectModeService,
    source_library,
)
from alchemy_creative_agent_3_0.app.project_mode.service import Doc281GeneralSourceRegistry
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _job_payload,
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase3_general_activation_contract import (
    _general_payload,
    _general_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase2_shadow_matcher_contract import (
    _entry as _shadow_entry,
    _evidence as _shadow_evidence,
    _requirement as _shadow_requirement,
    _resolve as _shadow_resolve,
    _server_context as _shadow_server_context,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase4_ecommerce_view_activation_contract import (
    _count_planning_and_dispatch,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_project_source_library_reference_matching import (
    _public_library_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _ready_product_upload,
)


def _public_safe(value: Any) -> None:
    forbidden = (
        "asset_id",
        "reference_id",
        "sha",
        "digest",
        "path",
        "file",
        "prompt",
        "provider",
        "exception",
        "traceback",
    )
    if isinstance(value, dict):
        for key, nested in value.items():
            assert not any(fragment in str(key).lower() for fragment in forbidden)
            _public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _public_safe(nested)


class _Doc281GeneralSourceRegistryFixture:
    """Private `doc281_general_source_registry_v1` authority for red contracts."""

    protocol = "doc281_general_source_registry_v1"
    enabled = True

    def __init__(self, *, project_id: str, receipt: dict[str, Any]) -> None:
        resolved = receipt.get("state") == "resolved"
        output_plan = [{"output_index": 1, "output_nonce": "a" * 64}] if resolved else []
        self.identity = {
            "schema_version": "doc281_general_command_identity_v1",
            "issuer": "v3_doc281_general_command_registry",
            "protocol": self.protocol,
            "project_id": project_id,
            "template_id": "general_template",
            "command_id": f"doc281-command-{project_id}",
            "plan_binding_digest": receipt["command_plan_binding_digest"],
            "coalescing_nonce": f"doc281-nonce-{project_id}",
            **(
                {
                    "requested_output_count": 1,
                    "output_plan_digest": source_library.canonical_digest(output_plan),
                }
                if resolved
                else {}
            ),
        }
        self.identity["identity_digest"] = source_library.canonical_digest(self.identity)
        self._issued_identities: dict[str, dict[str, Any]] = {}
        self.receipt = deepcopy(receipt)
        if resolved:
            binding = {
                "output_index": 1,
                "output_nonce": output_plan[0]["output_nonce"],
                "matched_references": deepcopy(self.receipt.get("matched_references") or []),
            }
            binding["output_binding_digest"] = source_library.canonical_digest({
                "project_id": project_id,
                "command_plan_binding_digest": self.identity["plan_binding_digest"],
                "requirement_digest": self.receipt["requirement_digest"],
                "source_library_snapshot_digest": self.receipt["source_library_snapshot_digest"],
                **binding,
            })
            self.receipt["output_bindings"] = [binding]
            self.receipt["receipt_digest"] = source_library.canonical_digest({
                key: value for key, value in self.receipt.items() if key != "receipt_digest"
            })
            receipt.clear()
            receipt.update(deepcopy(self.receipt))

    def issue_command_identity(self, *, project_id: str, template_id: str, command_direction: str, **_kwargs: Any) -> dict[str, Any] | None:
        if project_id != self.identity["project_id"] or template_id != self.identity["template_id"]:
            return None
        identity = deepcopy(self.identity)
        direction_digest = source_library.canonical_digest({"command_direction": command_direction})
        identity["command_id"] = f"doc281-command-{direction_digest[:16]}"
        identity["coalescing_nonce"] = direction_digest
        identity["identity_digest"] = source_library.canonical_digest({
            key: value for key, value in identity.items() if key != "identity_digest"
        })
        self._issued_identities[identity["identity_digest"]] = deepcopy(identity)
        return identity

    def lookup_registered_receipt(self, *, project_id: str, command_identity: dict[str, Any]) -> dict[str, Any] | None:
        if (
            project_id != self.identity["project_id"]
            or self._issued_identities.get(str(command_identity.get("identity_digest") or "")) != command_identity
        ):
            return None
        return {
            "protocol": self.protocol,
            "schema_version": "doc281_general_registered_receipt_v1",
            "command_identity": deepcopy(command_identity),
            "receipt": deepcopy(self.receipt),
        }

    def requirement_for_identity(self, _identity: dict[str, Any]) -> dict[str, Any] | None:
        return None

    def observations_for_identity(self, _identity: dict[str, Any]) -> list[dict[str, Any]]:
        return []


def _count_brain_and_review(monkeypatch, handlers: Any) -> dict[str, int]:
    """Prove terminal input closure precedes both creative and pixel review work."""

    calls = {"brain": 0, "review": 0}
    runtime = handlers.service.scenario_runtime
    original_brain_run = runtime.llm_brain_adapter.run
    original_review = handlers.service._attach_post_generation_review  # noqa: SLF001

    def brain_run(*args: Any, **kwargs: Any) -> Any:
        calls["brain"] += 1
        return original_brain_run(*args, **kwargs)

    def review(*args: Any, **kwargs: Any) -> Any:
        calls["review"] += 1
        return original_review(*args, **kwargs)

    monkeypatch.setattr(runtime.llm_brain_adapter, "run", brain_run)
    monkeypatch.setattr(handlers.service, "_attach_post_generation_review", review)
    return calls


def _persistent_project_mode_for_doc281(handlers: Any, storage_root: Path) -> None:
    """Use a restartable Project Mode store; the test never shares a reader."""

    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=PersistentProjectStore(storage_root),
        project_visual_asset_binding_service=handlers.project_visual_asset_binding_service,
    )


def _general_server_held_match(
    handlers: Any,
    project: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    asset_id: str,
    kind: str,
    affordance: str,
    view_kind: str,
    subject_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build trusted test evidence and prove its matcher selection before activation."""

    candidate = _shadow_entry(snapshot, asset_id)
    requirement = _shadow_requirement(
        project_id=project["project_id"],
        output_index=1,
        kind=kind,
        source_snapshot_digest=snapshot["snapshot_digest"],
    )
    evidence = {
        candidate["reference_id"]: _shadow_evidence(
            candidate,
            project_id=project["project_id"],
            affordance=affordance,
            view_kind=view_kind,
            subject_kind=subject_kind,
        )
    }
    context = _shadow_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference=evidence,
    )
    receipt = _shadow_resolve(server_context=context)
    assert receipt["state"] == "resolved"
    assert [item["asset_id"] for item in receipt["matched_references"]] == [asset_id]
    registry = _Doc281GeneralSourceRegistryFixture(project_id=project["project_id"], receipt=receipt)
    previous_service = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        doc281_general_source_registry=registry,
        product_service=handlers.service,
        project_store=previous_service.project_store,
        template_registry=previous_service.template_registry,
        reference_channel_policy_module=previous_service.reference_channel_policy_module,
        project_visual_asset_binding_service=previous_service.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=previous_service.ecommerce_view_activation_issuer,
    )
    return candidate, receipt, registry


@pytest.mark.parametrize(
    ("user_input", "asset_index", "kind", "affordance", "view_kind", "subject_kind"),
    [
        ("Create an object image that needs the detail original.", 0, "object_rear_structure", "object_back_or_structure", "rear", "object_or_product"),
        ("Create a person image with optional environment inspiration.", 1, "person_environment_context", "environment", "environment_wide", "person"),
        ("Create a scene image using a brand or graphic source.", 2, "brand_scene_material", "logo_or_mark", "packaging", "brand_or_graphic"),
    ],
)
def test_doc281_general_command_freezes_the_server_held_smart_match_across_domains(
    tmp_path,
    user_input: str,
    asset_index: int,
    kind: str,
    affordance: str,
    view_kind: str,
    subject_kind: str,
) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    candidate, receipt, _registry = _general_server_held_match(
        handlers,
        project,
        snapshot,
        asset_id=asset_ids[asset_index],
        kind=kind,
        affordance=affordance,
        view_kind=view_kind,
        subject_kind=subject_kind,
    )

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": user_input,
            "metadata": {
                "selected_original_asset_ids": ["browser-never-selects"],
                "source_evidence_profile": {"view_kind": "browser-never-certifies"},
            },
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = record.request.metadata["doc270_general_source_activation_receipts"][0]
    assert activation["state"] == "activated_resolved"
    assert activation["source_receipt_digest"] == receipt["receipt_digest"]
    projection = record.request.metadata["doc270_general_original_source_projection"]
    assert [item["reference_id"] for item in projection["sources"]] == [candidate["reference_id"]]
    assert record.request.uploaded_asset_ids == [candidate["asset_id"]]
    assert "browser-never-selects" not in record.request.uploaded_asset_ids


def test_doc281_general_smart_match_is_invariant_to_source_order_filename_prose_and_browser_labels(
    tmp_path,
) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    candidate, receipt, _registry = _general_server_held_match(
        handlers,
        project,
        snapshot,
        asset_id=asset_ids[2],
        kind="object_rear_structure",
        affordance="object_back_or_structure",
        view_kind="rear",
        subject_kind="object_or_product",
    )
    durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    durable.reference_assets = list(reversed(durable.reference_assets))
    handlers.project_service.project_store.save_project(durable)
    renamed = handlers.service.get_uploaded_asset(asset_ids[2])
    assert renamed is not None
    handlers.service.asset_store._save_record(renamed.model_copy(update={"filename": "misleading-front-name.png"}))  # noqa: SLF001
    permuted_snapshot = handlers.project_service._doc270_project_source_library(durable)  # noqa: SLF001
    assert permuted_snapshot["snapshot_digest"] == snapshot["snapshot_digest"]
    permuted_candidate = _shadow_entry(permuted_snapshot, candidate["asset_id"])
    permuted_requirement = _shadow_requirement(
        project_id=project["project_id"],
        output_index=1,
        kind="object_rear_structure",
        source_snapshot_digest=snapshot["snapshot_digest"],
    )
    permuted_context = _shadow_server_context(
        handlers=handlers,
        project=project,
        requirement=permuted_requirement,
        evidence_by_reference={
            permuted_candidate["reference_id"]: _shadow_evidence(
                permuted_candidate,
                project_id=project["project_id"],
                affordance="object_back_or_structure",
                view_kind="rear",
                subject_kind="object_or_product",
            )
        },
    )
    permuted_receipt = _shadow_resolve(server_context=permuted_context)
    assert [item["asset_id"] for item in permuted_receipt["matched_references"]] == [candidate["asset_id"]]

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Completely different wording with a browser rear label.",
            "metadata": {
                "browser_source_order": list(reversed(asset_ids)),
                "browser_reference_labels": {asset_ids[0]: "rear", asset_ids[2]: "front"},
            },
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = record.request.metadata["doc270_general_source_activation_receipts"][0]
    assert activation["source_receipt_digest"] == receipt["receipt_digest"]
    assert record.request.uploaded_asset_ids == [candidate["asset_id"]]


def test_doc281_general_optional_uncertainty_is_prompt_only_and_never_needs_input(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a prompt-only General image without project originals.",
            "primary_template_id": "general_template",
        }
    )["project"]
    receipt = {
        "state": "optional_uncertain",
        "requirement_digest": source_library.canonical_digest(
            {"authority": "doc281_general_source_registry_v1", "case": "optional_uncertain"}
        ),
        "command_plan_binding_digest": "doc281-optional-uncertain-command",
    }
    receipt["receipt_digest"] = source_library.canonical_digest(receipt)
    registry = _Doc281GeneralSourceRegistryFixture(project_id=project["project_id"], receipt=receipt)
    previous_service = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        doc281_general_source_registry=registry,
        product_service=handlers.service,
        project_store=previous_service.project_store,
        template_registry=previous_service.template_registry,
        reference_channel_policy_module=previous_service.reference_channel_policy_module,
        project_visual_asset_binding_service=previous_service.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=previous_service.ecommerce_view_activation_issuer,
    )


def _materialize_doc281_bound_outputs(handlers: Any, *, job_id: str, output_count: int = 1) -> list[Any]:
    """Exercise Product API's output persistence boundary, never client metadata."""

    record = handlers.service.get_job_record(job_id)
    assert record is not None and record.planning_result is not None
    source_assets = list(record.planning_result.asset_pack.assets)
    assert source_assets
    base_metadata = dict(source_assets[0].metadata or {})
    base_metadata["selected_candidate_id"] = "candidate-doc281-output-1"
    base_metadata["candidate_metadata"] = {
        **dict(base_metadata.get("candidate_metadata") or {}),
        "candidate_id": "candidate-doc281-output-1",
    }
    base_asset = source_assets[0].model_copy(update={"metadata": base_metadata})
    assets = [base_asset]
    for index in range(2, output_count + 1):
        metadata = dict(base_asset.metadata or {})
        metadata["selected_candidate_id"] = f"candidate-doc281-output-{index}"
        metadata["candidate_metadata"] = {"candidate_id": f"candidate-doc281-output-{index}"}
        assets.append(base_asset.model_copy(update={
            "asset_id": f"{base_asset.asset_id}-doc281-{index}", "metadata": metadata,
        }))
    generation_result = record.planning_result.model_copy(
        update={"asset_pack": record.planning_result.asset_pack.model_copy(update={"assets": assets})}
    )
    record.generation_result = handlers.service._materialize_mock_output_records(record, generation_result)  # noqa: SLF001
    record.status = ProductJobStatusValue.GENERATED
    handlers.service.job_store.save(record)
    return handlers.service.output_store.list_by_job(job_id)

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Use an optional uncertain scene original when appropriate.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata.get("doc270_general_source_activation_receipts") == [
        {"state": "prompt_only"}
    ]
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


def test_doc281_normal_service_composes_shared_registry_for_real_bounded_general_match(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    selected_asset_id = asset_ids[1]
    selected_reference_id = next(
        item.reference_id
        for item in handlers.project_service._require_project(project["project_id"]).reference_assets  # noqa: SLF001
        if item.asset_ref_id == selected_asset_id
    )

    def requirement_issuer(**_kwargs: Any) -> dict[str, Any]:
        value = {"kind": "object_rear_structure", "maximum_sources": 1}
        return {**value, "requirement_digest": source_library.canonical_digest(value)}

    class EvidenceAnalyzer:
        def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
            assert project_id == project["project_id"] and len(entries) == 1
            if entries[0]["reference_id"] != selected_reference_id:
                return [{
                    "evidence_state": "observed", "subject_kind": "object_or_product",
                    "view_kind": "front", "affordances": ["object_front_presentation"],
                }]
            return [{
                "evidence_state": "observed", "subject_kind": "object_or_product",
                "view_kind": "rear", "affordances": ["object_back_or_structure"],
            }]

    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=previous.project_store,
        template_registry=previous.template_registry,
        reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=previous.ecommerce_view_activation_issuer,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(
                evidence_analyzer=EvidenceAnalyzer(),
            requirement_issuer=requirement_issuer,
        ),
    )
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.uploaded_asset_ids == [selected_asset_id]
    assert record.request.metadata["doc270_general_source_activation_receipts"][0]["state"] == "activated_resolved"
    public_project = handlers.get_project(project["project_id"])["project"]
    assert "doc281_used_source_disclosures" not in public_project["metadata"]


def test_doc281_environment_composition_uses_openai_protocol_per_verified_source(tmp_path, monkeypatch) -> None:
    """The ordinary service must compose a real analyzer protocol, not a test callback."""

    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    selected_asset_id = asset_ids[1]
    policy_path = tmp_path / "doc281-general-policy.json"
    policy_path.write_text(json.dumps({
        "enabled": True,
        "intent_requirements": {
            "faithful source-aware": {"kind": "object_rear_structure", "maximum_sources": 1},
        },
    }), encoding="utf-8")
    calls: list[str] = []

    class OpenAICompatibleAnalyzerMock:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def available(self) -> bool:
            return True

        def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
            assert project_id == project["project_id"] and len(entries) == 1
            entry = entries[0]
            assert isinstance(entry.get("analysis_bytes"), bytes)
            calls.append(str(entry["asset_id"]))
            if entry["asset_id"] == selected_asset_id:
                return [{
                    "evidence_state": "observed", "subject_kind": "object_or_product",
                    "view_kind": "rear", "affordances": ["object_back_or_structure"],
                }]
            return [{
                "evidence_state": "observed", "subject_kind": "object_or_product",
                "view_kind": "front", "affordances": ["object_front_presentation"],
            }]

    from alchemy_creative_agent_3_0.app.project_mode import service as project_mode_service
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_provider

    monkeypatch.setenv("ALCHEMY_DOC281_GENERAL_SOURCE_POLICY_PATH", str(policy_path))
    monkeypatch.setattr(project_mode_service, "OpenAICompatibleSourceEvidenceAnalyzer", OpenAICompatibleAnalyzerMock)
    monkeypatch.setattr(vision_provider, "_lab_vision_enabled", lambda: True)
    monkeypatch.setattr(vision_provider, "_lab_vision_setting", lambda _field: "private-test-route")
    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=previous.project_store,
        template_registry=previous.template_registry,
        reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=previous.ecommerce_view_activation_issuer,
    )
    assert handlers.project_service.doc281_general_source_registry.enabled is True
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == [selected_asset_id]
    assert calls == asset_ids


@pytest.mark.parametrize("invalid_result", [None, [], [{"subject_kind": "person"}]])
def test_doc281_partial_or_invalid_single_source_analysis_is_prompt_only(tmp_path, invalid_result: Any) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)

    def requirement_issuer(**_kwargs: Any) -> dict[str, Any]:
        value = {"kind": "object_rear_structure", "maximum_sources": 1}
        return {**value, "requirement_digest": source_library.canonical_digest(value)}

    class PartiallyUnavailableAnalyzer:
        def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
            assert project_id == project["project_id"] and len(entries) == 1
            if entries[0]["asset_id"] == asset_ids[-1]:
                return invalid_result
            return [{
                "evidence_state": "observed", "subject_kind": "object_or_product",
                "view_kind": "rear", "affordances": ["object_back_or_structure"],
            }]

    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service, project_store=previous.project_store,
        template_registry=previous.template_registry, reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(
            evidence_analyzer=PartiallyUnavailableAnalyzer(), requirement_issuer=requirement_issuer,
        ),
    )
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == []
    assert record.request.metadata["doc270_general_source_activation_receipts"] == [{"state": "prompt_only"}]


def test_doc281_normal_service_registry_optional_match_stays_prompt_only(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = handlers.post_projects({
        "user_goal": "Create a General prompt-only image.",
        "primary_template_id": "general_template",
    })["project"]

    def requirement_issuer(**_kwargs: Any) -> dict[str, Any]:
        value = {"kind": "brand_scene_material", "maximum_sources": 1}
        return {**value, "requirement_digest": source_library.canonical_digest(value)}

    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=previous.project_store,
        template_registry=previous.template_registry,
        reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=previous.ecommerce_view_activation_issuer,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(
            evidence_analyzer=lambda **_kwargs: {},
            requirement_issuer=requirement_issuer,
        ),
    )
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and created["status"] == "planned"
    assert record.request.uploaded_asset_ids == []
    assert record.request.metadata["doc270_general_source_activation_receipts"] == [{"state": "prompt_only"}]
    assert "current_operation" not in created["metadata"]


def test_doc281_general_registry_replays_durable_receipt_after_fresh_service_and_rematches_source_mutation(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    calls = {"analyzer": 0}

    def requirement_issuer(**_kwargs: Any) -> dict[str, Any]:
        value = {"kind": "object_rear_structure", "maximum_sources": 1}
        return {**value, "requirement_digest": source_library.canonical_digest(value)}

    class EvidenceAnalyzer:
        def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
            assert project_id == project["project_id"] and len(entries) == 1
            entry = entries[0]
            calls["analyzer"] += 1
            if entry["asset_id"] != asset_ids[0]:
                return [{
                    "evidence_state": "observed", "subject_kind": "object_or_product",
                    "view_kind": "front", "affordances": ["object_front_presentation"],
                }]
            return [{
                "evidence_state": "observed", "subject_kind": "object_or_product",
                "view_kind": "rear", "affordances": ["object_back_or_structure"],
            }]

    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service, project_store=previous.project_store,
        template_registry=previous.template_registry, reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(evidence_analyzer=EvidenceAnalyzer(), requirement_issuer=requirement_issuer),
    )
    first = handlers.post_project_job(project["project_id"], _general_payload())
    assert first["job_id"] and calls == {"analyzer": len(asset_ids)}
    # A restart has no in-memory receipt. It must reissue identity, read the
    # durable receipt, and return the one existing Job without analysis.
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service, project_store=previous.project_store,
        template_registry=previous.template_registry, reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(evidence_analyzer=EvidenceAnalyzer(), requirement_issuer=requirement_issuer),
    )
    replay = handlers.post_project_job(project["project_id"], _general_payload())
    assert replay["job_id"] == first["job_id"] and calls == {"analyzer": len(asset_ids)}
    upload = handlers.service.get_uploaded_asset(asset_ids[0])
    assert upload is not None
    mutated_bytes = Path(str(upload.file_path)).read_bytes() + b"doc281-mutation"
    Path(str(upload.file_path)).write_bytes(mutated_bytes)
    handlers.service.asset_store._save_record(upload.model_copy(update={"content_sha256": hashlib.sha256(mutated_bytes).hexdigest()}))  # noqa: SLF001
    mutated = handlers.post_project_job(project["project_id"], _general_payload())
    assert mutated["job_id"] != first["job_id"] and calls == {"analyzer": len(asset_ids) * 2}


def test_doc281_used_source_disclosure_requires_exact_visible_output_binding(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    created = handlers.post_project_job(project["project_id"], _general_payload())
    before = handlers.get_project(project["project_id"])["project"]
    assert "doc281_used_source_disclosures" not in before["metadata"]
    outputs = _materialize_doc281_bound_outputs(handlers, job_id=created["job_id"])
    assert len(outputs) == 1 and "doc281_output_plan_binding" in outputs[0].metadata
    after = handlers.get_project(project["project_id"])["project"]
    disclosure = after["metadata"]["doc281_used_source_disclosures"]
    assert disclosure == [{
        "output_label": "Output 1",
        "sources": [{"category": "project_original", "label": "Selected original"}],
    }]
    _public_safe(disclosure)


def test_doc281_used_source_disclosure_binds_each_actual_output_and_excludes_foreign_jobs(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)

    def requirement_issuer(**_kwargs: Any) -> dict[str, Any]:
        value = {"kind": "object_rear_structure", "maximum_sources": 1}
        return {**value, "requirement_digest": source_library.canonical_digest(value)}

    class EvidenceAnalyzer:
        def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
            assert project_id == project["project_id"] and len(entries) == 1
            rear = entries[0]["asset_id"] == asset_ids[0]
            return [{
                "evidence_state": "observed", "subject_kind": "object_or_product",
                "view_kind": "rear" if rear else "front",
                "affordances": ["object_back_or_structure"] if rear else ["object_front_presentation"],
            }]

    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service, project_store=previous.project_store,
        template_registry=previous.template_registry, reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        doc281_general_source_registry=Doc281GeneralSourceRegistry(
            evidence_analyzer=EvidenceAnalyzer(), requirement_issuer=requirement_issuer,
        ),
    )
    created = handlers.post_project_job(project["project_id"], _general_payload(metadata={"requested_image_count": 2}))
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata["doc281_general_output_source_bindings_v1"]
    assert len(record.request.metadata["doc281_general_output_source_bindings_v1"]) == 2
    outputs = _materialize_doc281_bound_outputs(handlers, job_id=created["job_id"], output_count=2)
    assert len(outputs) == 2
    _save_history_output(handlers, job_id="job_foreign_doc281", index=283)
    disclosures = handlers.get_project(project["project_id"])["project"]["metadata"]["doc281_used_source_disclosures"]
    assert len(disclosures) == 2
    assert {item["output_label"] for item in disclosures} == {"Output 1", "Output 2"}
    assert all(item["sources"] == [{"category": "project_original", "label": "Selected original"}] for item in disclosures)
    _public_safe(disclosures)
    # A process/retry output without the persistence-bound plan envelope does
    # not become a disclosed source just because it shares the same Job.
    _save_history_output(handlers, job_id=created["job_id"], index=285)
    assert len(handlers.get_project(project["project_id"])["project"]["metadata"]["doc281_used_source_disclosures"]) == 2

    store = handlers.service.output_store
    first, second = outputs
    swapped = dict(first.metadata or {})
    swapped["doc281_output_plan_binding"] = deepcopy(second.metadata["doc281_output_plan_binding"])
    store._write_record(replace(first, metadata=swapped))  # noqa: SLF001
    store._invalidate_cache()  # noqa: SLF001
    # A swapped envelope names the other output ID and fails exact binding.
    assert len(handlers.get_project(project["project_id"])["project"]["metadata"]["doc281_used_source_disclosures"]) == 1

    missing = dict(second.metadata or {})
    missing.pop("doc281_output_plan_binding", None)
    store._write_record(replace(second, metadata=missing))  # noqa: SLF001
    store._invalidate_cache()  # noqa: SLF001
    assert "doc281_used_source_disclosures" not in handlers.get_project(project["project_id"])["project"]["metadata"]


def test_doc281_review_visible_output_disclosure_is_exact_but_not_delivery(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    created = handlers.post_project_job(project["project_id"], _general_payload())
    output = _materialize_doc281_bound_outputs(handlers, job_id=created["job_id"])[0]
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.planning_result is not None
    record.status = ProductJobStatusValue.GENERATED
    record.generation_result = record.planning_result.model_copy(update={
        "metadata": {
            **dict(record.planning_result.metadata or {}),
            "post_generation_review": {"inspections": [{
                "output_id": output.output_id,
                "mode": "vision_model",
                "status": "manual_review",
                "verification_state": "verified",
            }]},
            "final_delivery": {
                "delivery_gate_applies": True,
                "final_delivery_status": "withheld_manual_confirmation",
            },
        },
    })
    handlers.service.job_store.save(record)
    response = handlers.get_project(project["project_id"])["project"]
    assert response["metadata"].get("project_outputs", []) == []
    assert response["metadata"]["doc281_used_source_disclosures"] == [{
        "output_label": "Output 1",
        "sources": [{"category": "project_original", "label": "Selected original"}],
    }]


@pytest.mark.parametrize("mutation", ["forged_requirement", "cross_project", "stale_snapshot", "wrong_evidence"])
def test_doc281_general_activation_rejects_forged_server_boundary_inputs(tmp_path, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    candidate, receipt, registry = _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    hostile = deepcopy(receipt)
    if mutation == "forged_requirement":
        hostile["requirement_digest"] = "f" * 64
    elif mutation == "cross_project":
        hostile["project_id"] = "project-other"
    elif mutation == "stale_snapshot":
        hostile["source_library_snapshot_digest"] = "e" * 64
    else:
        hostile["matched_references"][0]["content_sha256"] = "d" * 64
    hostile["receipt_digest"] = source_library.canonical_digest(
        {key: value for key, value in hostile.items() if key != "receipt_digest"}
    )
    registry.receipt = hostile

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata.get("doc270_general_source_activation_receipts") == [
        {"state": "receipt_invalid"}
    ]
    assert record.request.uploaded_asset_ids == []
    assert "doc270_general_original_source_projection" not in record.request.metadata
    assert candidate["asset_id"] not in str(handlers.get_job(created["job_id"]))


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [(DESKTOP_HTML, DESKTOP_JS, False), (MOBILE_HTML, MOBILE_JS, True)],
)
def test_doc281_terminal_ui_clears_stale_progress_and_discloses_only_safe_used_sources(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    project = _public_library_project(ecommerce=True)
    project["metadata"]["current_operation"] = {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    project["metadata"]["doc281_used_source_disclosures"] = [{
        "output_label": "Output 1",
        "sources": [{"category": "project_original", "label": "Selected original"}],
    }]
    created = {"job_id": "", "status": "blocked", "metadata": {"current_operation": project["metadata"]["current_operation"]}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mobile:
                page.evaluate(
                    """({ project, created }) => {
                      ensureMobileLayers(); setupMobileV3Adapter();
                      mobileV3State.currentProject = project; mobileV3State.currentJob = created;
                      mobileV3State.projects = [project]; mobileV3State.selectedTemplate = 'ecommerce_template';
                      mobileV3State.busy = true; mobileV3State.progressStageKey = 'planning';
                      mobileV3State.progressTimer = window.setTimeout(() => {}, 1000);
                      renderMobileV3ProjectCurrentOperation(project); renderMobileV3ReferenceBoard(project);
                    }""",
                    {"project": project, "created": created},
                )
                terminal = page.locator("#mobileV3ProjectCurrentOperation")
                board = page.locator("#mobileV3ReferenceBoard")
                action = "[data-mobile-v3-project-action='review_product_inputs']"
                cleared = "mobileV3State.busy === false && mobileV3State.progressTimer === null"
            else:
                page.evaluate(
                    """({ project, created }) => {
                      v3State.currentProject = project; v3State.currentJob = created;
                      v3State.loading = true; v3State.progressStageKey = 'planning';
                      v3State.progressTimer = window.setTimeout(() => {}, 1000);
                      renderV3ProjectDetail(); renderV3UsefulReferences();
                    }""",
                    {"project": project, "created": created},
                )
                terminal = page.locator("#v3ProjectNextActions")
                board = page.locator("#v3UsefulReferenceBoard")
                action = "[data-v3-project-action='review_product_inputs']"
                cleared = "v3State.loading === false && v3State.progressTimer === null"
            assert page.locator(action).count() == 1
            assert "准备" not in terminal.inner_text()
            assert page.evaluate(cleared) is True
            text = board.inner_text()
            assert "项目原始素材" in text and "人物视觉资产" in text
            assert "已选延续方向" in text and "生成与复核历史" in text
            assert "Selected original" in text
            assert all(token not in text.lower() for token in ("asset_id", "digest", "path", "prompt", "provider"))
        finally:
            browser.close()


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [(DESKTOP_HTML, DESKTOP_JS, False), (MOBILE_HTML, MOBILE_JS, True)],
)
def test_doc281_general_reference_board_renders_only_allowlisted_used_source_disclosure(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    project = _public_library_project(ecommerce=False)
    project["metadata"]["doc281_used_source_disclosures"] = [
        {"output_label": "Output 2", "sources": [{"category": "project_original", "label": "Selected original"}]},
        {"output_label": "Output 3", "sources": [{"category": "history", "label": "unsafe-history"}]},
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mobile:
                page.evaluate(
                    """(project) => { ensureMobileLayers(); setupMobileV3Adapter();
                      mobileV3State.currentProject = project; renderMobileV3ReferenceBoard(project); }""",
                    project,
                )
                board = page.locator("#mobileV3ReferenceBoard")
            else:
                page.evaluate(
                    """(project) => { v3State.currentProject = project; renderV3UsefulReferences(); }""",
                    project,
                )
                board = page.locator("#v3UsefulReferenceBoard")
            text = board.inner_text()
            assert "Output 2: Selected original" in text
            assert "unsafe-history" not in text
            assert all(token not in text.lower() for token in ("asset_id", "digest", "path", "prompt", "provider"))
        finally:
            browser.close()


@pytest.mark.parametrize("fault", ["not_ready", "role_drift", "file_missing", "digest_drift"])
def test_doc281_active_historical_product_drift_closes_once_with_sanitized_terminal_operation(
    tmp_path,
    fault: str,
    monkeypatch,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    store_root = tmp_path / "doc281-terminal-project-store"
    _persistent_project_mode_for_doc281(handlers, store_root)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename=f"doc281-product-{fault}.png",
        color=(95, 125, 165),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    upload = handlers.service.get_uploaded_asset(product_id)
    assert upload is not None
    original_bytes = Path(str(upload.file_path)).read_bytes()
    if fault == "not_ready":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"status": V3AssetUploadStatusValue.STORED})
        )
    elif fault == "role_drift":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"role": "face_reference"})
        )
    if fault == "file_missing":
        Path(str(upload.file_path)).unlink()
    elif fault == "digest_drift":
        Path(str(upload.file_path)).write_bytes(b"doc281-current-sha-drift")

    before_job_ids = list(handlers.project_service._require_project(project["project_id"]).job_ids)  # noqa: SLF001
    calls = _count_planning_and_dispatch(monkeypatch, handlers)
    brain_and_review_calls = _count_brain_and_review(monkeypatch, handlers)
    first = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    second = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    assert first.get("job_id") in (None, "")
    assert second.get("job_id") in (None, "")
    assert first["status"] == "blocked"
    assert handlers.project_service._require_project(project["project_id"]).job_ids == before_job_ids  # noqa: SLF001
    assert calls == {"plan": 0, "dispatch": 0}
    assert brain_and_review_calls == {"brain": 0, "review": 0}
    operation = first["metadata"]["current_operation"]
    assert operation["state"] == "needs_input"
    assert operation["terminal"] is True
    assert operation == second["metadata"]["current_operation"]
    _public_safe(operation)
    fresh_reader = V3ProjectModeService(
        product_service=handlers.service,
        project_store=PersistentProjectStore(store_root),
        project_visual_asset_binding_service=handlers.project_visual_asset_binding_service,
    )
    reloaded = fresh_reader.get_project(project["project_id"]).model_dump(mode="json")
    assert reloaded["metadata"]["current_operation"] == operation
    durable_receipts = fresh_reader.project_store.list_private_records(
        project["project_id"],
        "doc281_source_association_terminal_receipts_v1",
    )
    assert len(durable_receipts) == 1
    assert durable_receipts[0]["schema_version"] == "doc281_source_association_terminal_receipt_v1"
    assert durable_receipts[0]["command_identity"]["project_id"] == project["project_id"]
    assert durable_receipts[0]["public_operation"] == operation

    # A repaired original alone never resurrects an old command. A new explicit
    # command owns the only permitted recovery path and clears the old closure.
    handlers.service.asset_store._save_record(upload)  # noqa: SLF001
    if fault in {"file_missing", "digest_drift"}:
        Path(str(upload.file_path)).write_bytes(original_bytes)
    repaired = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-repaired-{fault}"),
    )
    assert repaired["job_id"]
    assert repaired["status"] == "planned"
    assert repaired["metadata"].get("current_operation") is None


def test_doc281_drift_terminal_overrides_an_older_planning_operation_without_erasing_it(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers, filename="doc281-stale-planning-product.png", color=(90, 120, 160),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    old_operation = handlers.project_service.begin_project_planning_operation(
        project["project_id"], _job_payload(uploaded_asset_ids=[], key="doc281-old-planning"),
    )
    upload = handlers.service.get_uploaded_asset(product_id)
    assert upload is not None
    handlers.service.asset_store._save_record(upload.model_copy(update={"status": V3AssetUploadStatusValue.STORED}))  # noqa: SLF001
    closed = handlers.post_project_job(
        project["project_id"], _job_payload(uploaded_asset_ids=[], key="doc281-drift-after-planning"),
    )
    assert closed["job_id"] in (None, "") and closed["status"] == "blocked"
    response = handlers.get_project(project["project_id"])
    assert response["metadata"]["current_operation"] == closed["metadata"]["current_operation"]
    assert response["metadata"]["current_operation"]["state"] == "needs_input"
    durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    assert durable.metadata["doc277_planning_current_operation"]["operation_id"] == old_operation["operation_id"]


def test_doc281_explicit_continuation_and_history_never_enter_general_original_match_projection(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[1], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    history = _save_history_output(handlers, job_id="doc281-history", index=281)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": history.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": "doc281-history",
            "created_from_output_id": history.output_id,
            "use_policy": "style",
        },
    )

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    projection = record.request.metadata["doc270_general_original_source_projection"]
    selected = [item["asset_id"] for item in projection["sources"]]
    assert set(selected).issubset(set(asset_ids))
    assert history.output_id not in selected
    assert all(
        reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED
        or reference.asset_ref_id != history.output_id
        or reference.use_policy == ProjectReferenceUsePolicy.STYLE
        for reference in handlers.project_service._require_project(project["project_id"]).reference_assets  # noqa: SLF001
    )


def test_doc281_new_general_command_replaces_old_terminal_presentation_without_history_reselection(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _general_server_held_match(
        handlers, project, snapshot, asset_id=asset_ids[0], kind="object_rear_structure",
        affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product",
    )
    first = handlers.post_project_job(project["project_id"], _general_payload())
    first_record = handlers.service.get_job_record(first["job_id"])
    assert first_record is not None
    first_projection = deepcopy(first_record.request.metadata["doc270_general_original_source_projection"])

    second = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Create a distinct new image from the current request only.",
        },
    )
    second_record = handlers.service.get_job_record(second["job_id"])
    assert second_record is not None
    assert second["job_id"] != first["job_id"]
    assert handlers.get_project(project["project_id"])["metadata"].get("current_operation") is None
    second_projection = second_record.request.metadata["doc270_general_original_source_projection"]
    assert first_projection["state"] == "activated_resolved"
    assert second_projection["state"] == "activated_resolved"
    assert set(item["asset_id"] for item in second_projection["sources"]).issubset(set(asset_ids))


@pytest.mark.parametrize(
    ("html_path", "script_path", "mobile"),
    [(DESKTOP_HTML, DESKTOP_JS, False), (MOBILE_HTML, MOBILE_JS, True)],
)
def test_doc281_old_terminal_response_cannot_overwrite_a_newer_explicit_command_dom_session(
    html_path: Path,
    script_path: Path,
    mobile: bool,
) -> None:
    """Release a held old terminal response only after the new command owns UI state."""

    old_project = _public_library_project(ecommerce=True)
    old_project["metadata"]["current_operation"] = {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    new_project = deepcopy(old_project)
    new_project["metadata"]["current_operation"] = {
        "state": "planning",
        "terminal": False,
        "pending": True,
        "next_actions": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            result = page.evaluate(
                """
                async ({ oldProject, newProject, mobile }) => {
                  const response = (payload) => new Response(JSON.stringify(payload), {
                    status: 200, headers: { "Content-Type": "application/json" },
                  });
                  if (!mobile) {
                    v3State.currentProject = oldProject;
                    v3State.loading = true;
                    v3State.progressTimer = window.setTimeout(() => {}, 10000);
                    const oldReceipt = v3StartEcommerceGenerationSession(oldProject.project_id);
                    const pending = [];
                    const originalFetch = window.fetch;
                    window.fetch = (input, init = {}) => {
                      const url = String(input);
                      if (String(init.method || "GET").toUpperCase() === "GET" && url.endsWith(`/projects/${oldProject.project_id}`)) {
                        return new Promise((resolve) => pending.push(resolve));
                      }
                      return originalFetch(input, init);
                    };
                    const oldRefresh = refreshV3CurrentProject({
                      silent: true,
                      shouldContinue: () => v3EcommerceGenerationSessionOwns(oldReceipt),
                      sessionReceipt: oldReceipt,
                    });
                    await new Promise((resolve) => window.setTimeout(resolve, 0));
                    v3State.currentProject = newProject;
                    v3StartEcommerceGenerationSession(newProject.project_id);
                    renderV3ProjectDetail();
                    pending.shift()(response({ project: oldProject }));
                    await oldRefresh;
                    return {
                      operation: v3State.currentProject?.metadata?.current_operation?.state || "",
                      oldActionCount: document.querySelectorAll("[data-v3-project-action='review_product_inputs']").length,
                      busy: v3State.loading,
                      progress: v3State.progressTimer === null,
                    };
                  }
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = oldProject;
                  mobileV3State.projects = [oldProject];
                  mobileV3State.busy = true;
                  mobileV3State.progressTimer = window.setTimeout(() => {}, 10000);
                  const oldReceipt = mobileV3StartEcommerceGenerationSession(oldProject.project_id);
                  const pending = [];
                  mobileV3Request = (path) => new Promise((resolve) => pending.push({ path, resolve }));
                  const oldRefresh = refreshMobileV3ProjectDetail(oldProject.project_id, {
                    shouldContinue: () => mobileV3EcommerceGenerationSessionOwns(oldReceipt),
                  });
                  await new Promise((resolve) => window.setTimeout(resolve, 0));
                  mobileV3State.currentProject = newProject;
                  mobileV3State.projects = [newProject];
                  mobileV3StartEcommerceGenerationSession(newProject.project_id);
                  renderMobileV3ProjectCurrentOperation(mobileV3State.currentProject);
                  pending.forEach(({ path, resolve }) => {
                    if (path.endsWith(`/projects/${oldProject.project_id}`)) resolve({ project: oldProject });
                    else if (path.includes("/timeline")) resolve({ items: [] });
                    else resolve({ items: [], review_items: [] });
                  });
                  await oldRefresh;
                  return {
                    operation: mobileV3State.currentProject?.metadata?.current_operation?.state || "",
                    oldActionCount: document.querySelectorAll("[data-mobile-v3-project-action='review_product_inputs']").length,
                    busy: mobileV3State.busy,
                    progress: mobileV3State.progressTimer === null,
                  };
                }
                """,
                {"oldProject": old_project, "newProject": new_project, "mobile": mobile},
            )
            assert result == {
                "operation": "planning",
                "oldActionCount": 0,
                "busy": False,
                "progress": True,
            }
        finally:
            browser.close()


def test_doc281_phase0_contract_keeps_runtime_and_provider_code_unchanged() -> None:
    """Guard the Phase 0 scope: this test module must not imply a provider call."""

    assert Path(__file__).name == "test_v3_doc281_unified_source_library_smart_matching_phase0.py"
