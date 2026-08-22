"""Doc281 General source-selection contracts.

These tests keep the semantic decision in an explicit Brain double. Project
Mode owns only current-source revalidation, opaque-handle binding, durable
replay, and safe public projection. No filename, browser label, source role,
or local semantic taxonomy is used to select a General original.
"""

from __future__ import annotations

from copy import deepcopy
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore, V3ProjectModeService, source_library
from alchemy_creative_agent_3_0.app.project_mode import service as project_mode_service
from alchemy_creative_agent_3_0.app.project_mode.ecommerce_view_activation import DisabledEcommerceViewActivationIssuer
from alchemy_creative_agent_3_0.app.project_mode.service import (
    Doc281GeneralSourceRegistry,
    doc281_general_source_registry_from_environment,
)
from alchemy_creative_agent_3_0.app.project_mode.source_evidence import (
    GENERAL_SOURCE_SELECTION_OUTPUT_TOKEN_BUDGET,
    general_source_selection_response_from_text,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _ready_product_upload,
)


def _candidate_handle(entry: dict[str, Any]) -> str:
    return source_library.canonical_digest(
        {
            "schema_version": "doc281_general_source_candidate_handle_v1",
            "reference_id": str(entry["reference_id"]),
            "asset_id": str(entry["asset_id"]),
            "content_sha256": str(entry["content_sha256"]),
        }
    )


def _general_project(tmp_path: Path) -> tuple[Any, dict[str, Any], list[str], dict[str, Any]]:
    handlers, _catalog = _handlers(tmp_path)
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=handlers.project_service.project_store,
        project_visual_asset_binding_service=handlers.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
        doc281_general_source_registry=Doc281GeneralSourceRegistry(),
    )
    project = handlers.post_projects(
        {
            "user_goal": "Create a source-aware general campaign visual.",
            "primary_template_id": "general_template",
        }
    )["project"]
    asset_ids = [
        _ready_product_upload(
            handlers,
            filename=f"doc281-general-{index}.png",
            color=(50 + index * 35, 90 + index * 20, 135),
        )
        for index in range(1, 4)
    ]
    for asset_id in asset_ids:
        record = handlers.service.get_uploaded_asset(asset_id)
        assert record is not None
        handlers.service.asset_store._save_record(record.model_copy(update={"role": "general"}))  # noqa: SLF001
        handlers.post_project_reference(
            project["project_id"],
            {"asset_ref_id": asset_id, "source_type": "uploaded", "use_policy": "general"},
        )
    durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    snapshot = source_library.build_project_source_library(
        project_id=durable.project_id,
        references=durable.reference_assets,
        upload_lookup=handlers.service.get_uploaded_asset,
    )
    return handlers, project, asset_ids, snapshot


def _replace_general_service(handlers: Any, registry: Doc281GeneralSourceRegistry) -> None:
    previous = handlers.project_service
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=previous.project_store,
        template_registry=previous.template_registry,
        reference_channel_policy_module=previous.reference_channel_policy_module,
        project_visual_asset_binding_service=previous.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
        doc281_general_source_registry=registry,
    )


def _selection_registry(
    snapshot: dict[str, Any],
    *,
    target_asset_id: str | None,
    calls: dict[str, int] | None = None,
) -> Doc281GeneralSourceRegistry:
    target = next(
        (
            item
            for item in snapshot.get("entries", [])
            if isinstance(item, dict) and item.get("asset_id") == target_asset_id
        ),
        None,
    )
    target_handle = _candidate_handle(target) if target is not None else None

    def select(**kwargs: Any) -> dict[str, Any]:
        if calls is not None:
            calls["brain"] = calls.get("brain", 0) + 1
        entries = kwargs["entries"]
        assert entries
        assert all(set(item) == {"candidate_handle", "analysis_bytes", "mime_type"} for item in entries)
        assert all("asset_id" not in item and "reference_id" not in item for item in entries)
        if target_handle is None or target_handle not in {item["candidate_handle"] for item in entries}:
            return {"state": "prompt_only", "output_selections": []}
        count = int(kwargs["requested_output_count"])
        return {
            "state": "selected",
            "output_selections": [
                {"output_index": index, "candidate_handles": [target_handle]}
                for index in range(1, count + 1)
            ],
        }

    return Doc281GeneralSourceRegistry(selection_brain=select, maximum_sources=1)


def _general_payload(*, user_input: str = "Create a source-aware image.", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "user_input": user_input,
        "template_id": "general_template",
        "metadata": {"requested_image_count": 1, **(metadata or {})},
    }


def _png_base64() -> str:
    from PIL import Image

    image = Image.new("RGB", (16, 16), color=(220, 224, 230))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _public_safe(value: Any) -> None:
    forbidden = ("asset_id", "reference_id", "sha", "digest", "path", "file", "prompt", "provider")
    if isinstance(value, dict):
        for key, nested in value.items():
            assert not any(fragment in str(key).lower() for fragment in forbidden)
            _public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _public_safe(nested)


def test_doc281_fixture_reconstruction_ignores_an_enabled_environment_issuer(tmp_path, monkeypatch) -> None:
    class EnabledIssuer:
        def capability(self, *, project_id: str) -> dict[str, Any]:
            return {"enabled": True, "project_id": project_id}

        def supports_output_count(self, *, expected_output_count: int) -> bool:
            return expected_output_count > 0

        def issue(self, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("legacy fixture must not use the environment issuer")

    issuer = EnabledIssuer()
    monkeypatch.setattr(project_mode_service, "issuer_from_environment", lambda: issuer)
    handlers, _project, _asset_ids, _snapshot = _general_project(tmp_path)
    assert isinstance(handlers.project_service.ecommerce_view_activation_issuer, DisabledEcommerceViewActivationIssuer)
    assert handlers.project_service.ecommerce_view_activation_issuer is not issuer


def test_doc281_general_brain_selection_binds_only_current_opaque_handles(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    calls: dict[str, int] = {}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[1], calls=calls))
    created = handlers.post_project_job(
        project["project_id"],
        _general_payload(
            metadata={
                "selected_original_asset_ids": [asset_ids[0]],
                "source_evidence_profile": {"view_kind": "browser-forged"},
                "browser_source_labels": {asset_ids[2]: "front"},
            }
        ),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert calls == {"brain": 1}
    assert record.request.uploaded_asset_ids == [asset_ids[1]]
    activation = record.request.metadata["doc270_general_source_activation_receipts"]
    assert activation[0]["state"] == "activated_resolved"
    assert record.request.metadata["doc270_general_original_source_projection"]["sources"][0]["asset_id"] == asset_ids[1]


def test_doc281_source_order_filename_and_browser_prose_do_not_change_snapshot_or_server_binding(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    calls: dict[str, int] = {}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[2], calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload(user_input="Use the third current original."))
    record = handlers.service.get_job_record(first["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == [asset_ids[2]]

    durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    durable.reference_assets = list(reversed(durable.reference_assets))
    handlers.project_service.project_store.save_project(durable)
    renamed = handlers.service.get_uploaded_asset(asset_ids[2])
    assert renamed is not None
    handlers.service.asset_store._save_record(renamed.model_copy(update={"filename": "misleading-front-name.png"}))  # noqa: SLF001
    permuted = handlers.project_service._doc270_project_source_library(durable)  # noqa: SLF001
    assert permuted["snapshot_digest"] == snapshot["snapshot_digest"]


def test_doc281_prompt_only_has_no_job_source_expansion_or_needs_input(tmp_path) -> None:
    handlers, project, _asset_ids, snapshot = _general_project(tmp_path)
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None))
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == []
    assert record.request.metadata["doc270_general_source_activation_receipts"] == [{"state": "prompt_only"}]
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


def test_doc281_environment_composition_uses_openai_visual_route_and_opaque_selection(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    calls: list[dict[str, Any]] = []

    class Completions:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            content = kwargs["messages"][0]["content"]
            handles = [
                part["text"].split(": ", 1)[1]
                for part in content
                if part.get("type") == "text" and str(part.get("text", "")).startswith("Candidate handle: ")
            ]
            count = int(next(part["text"].split(": ", 1)[1] for part in content if str(part.get("text", "")).startswith("Requested output count: ")))
            target_handle = handles[0]
            payload = {
                "state": "selected",
                "output_selections": [
                    {"output_index": index, "candidate_handles": [target_handle]}
                    for index in range(1, count + 1)
                ],
            }
            assert general_source_selection_response_from_text(
                json.dumps(payload),
                candidate_handles=set(handles),
                requested_output_count=count,
                maximum_sources=2,
            ) is not None
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])

    class Client:
        chat = SimpleNamespace(completions=Completions())

    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_provider

    monkeypatch.delenv("ALCHEMY_DOC281_GENERAL_SOURCE_POLICY_PATH", raising=False)
    monkeypatch.setattr(vision_provider, "_lab_vision_enabled", lambda: True)
    monkeypatch.setattr(vision_provider, "_lab_vision_setting", lambda _field: "private-test-route")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_kwargs: Client()))
    registry = doc281_general_source_registry_from_environment()
    _replace_general_service(handlers, registry)
    assert handlers.project_service.doc281_general_source_registry.enabled is True
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and len(record.request.uploaded_asset_ids) == 1
    selected_asset = record.request.uploaded_asset_ids[0]
    assert selected_asset in asset_ids
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == GENERAL_SOURCE_SELECTION_OUTPUT_TOKEN_BUDGET
    text_parts = [part["text"] for part in calls[0]["messages"][0]["content"] if part.get("type") == "text"]
    assert all(asset_id not in "\n".join(text_parts) for asset_id in asset_ids)
    assert "browser" not in "\n".join(text_parts).lower()


@pytest.mark.parametrize(
    "policy",
    [
        {"enabled": True, "policy_authority": "server", "policy_version": "v1", "maximum_sources": True},
        {"enabled": True, "policy_authority": "server", "policy_version": "v1", "maximum_sources": 2, "extra": True},
        {"enabled": True, "policy_authority": "server", "maximum_sources": 2},
    ],
)
def test_doc281_environment_policy_rejects_invalid_shapes(tmp_path, monkeypatch, policy) -> None:
    policy_path = tmp_path / "invalid-policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setenv("ALCHEMY_DOC281_GENERAL_SOURCE_POLICY_PATH", str(policy_path))
    assert doc281_general_source_registry_from_environment().enabled is False


def test_doc281_openai_selection_response_is_strict_and_semantic_free() -> None:
    handles = {"a" * 64, "b" * 64}
    valid = json.dumps({"state": "selected", "output_selections": [{"output_index": 1, "candidate_handles": ["a" * 64]}]})
    assert general_source_selection_response_from_text(valid, candidate_handles=handles, requested_output_count=1, maximum_sources=1)
    for raw in ("not-json", json.dumps({"state": "selected", "output_selections": [{"output_index": 1, "candidate_handles": ["forged"]}]}), json.dumps({"state": "selected", "output_selections": []})):
        assert general_source_selection_response_from_text(raw, candidate_handles=handles, requested_output_count=1, maximum_sources=1) is None


def test_doc281_invalid_brain_selection_degrades_to_prompt_only(tmp_path) -> None:
    handlers, project, _asset_ids, _snapshot = _general_project(tmp_path)

    def forged_selection(**_kwargs: Any) -> dict[str, Any]:
        return {"state": "selected", "output_selections": [{"output_index": 1, "candidate_handles": ["f" * 64]}]}

    _replace_general_service(handlers, Doc281GeneralSourceRegistry(selection_brain=forged_selection, maximum_sources=1))
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == []
    assert record.request.metadata["doc270_general_source_activation_receipts"] == [{"state": "prompt_only"}]


def test_doc281_selection_receipt_replays_after_fresh_service_and_source_mutation_creates_new_identity(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    assert calls == {"brain": 1}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=calls))
    replay = handlers.post_project_job(project["project_id"], _general_payload())
    assert replay["job_id"] == first["job_id"] and calls == {"brain": 1}

    upload = handlers.service.get_uploaded_asset(asset_ids[0])
    assert upload is not None
    mutated = Path(str(upload.file_path)).read_bytes() + b"doc281-source-mutation"
    Path(str(upload.file_path)).write_bytes(mutated)
    handlers.service.asset_store._save_record(upload.model_copy(update={"content_sha256": hashlib.sha256(mutated).hexdigest()}))  # noqa: SLF001
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=calls))
    changed = handlers.post_project_job(project["project_id"], _general_payload(user_input="Use the current original after mutation."))
    assert changed["job_id"] != first["job_id"] and calls == {"brain": 2}


def test_doc281_tampered_selection_receipt_fails_closed_without_reselection(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    assert first["job_id"] and calls == {"brain": 1}
    records = handlers.project_service.project_store._private_records[project["project_id"]]["doc281_general_selection_receipts_v2"]  # noqa: SLF001
    records[-1]["receipt_digest"] = "0" * 64
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=calls))
    second = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(second["job_id"])
    assert record is not None and record.request.uploaded_asset_ids == [] and calls == {"brain": 1}


def test_doc281_prompt_only_receipt_replays_without_brain(tmp_path) -> None:
    handlers, project, _asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None, calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    assert calls == {"brain": 1}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None, calls=calls))
    replay = handlers.post_project_job(project["project_id"], _general_payload())
    assert replay["job_id"] == first["job_id"] and calls == {"brain": 1}


def test_doc281_transient_brain_block_replans_same_command_after_recovery(tmp_path) -> None:
    handlers, project, _asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None, calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(first["job_id"])
    assert record is not None
    record.status = "blocked"
    record.request.metadata["generation_lifecycle_failure"] = {
        "schema_version": "v3_generation_lifecycle_failure_v1",
        "status": "blocked",
        "owner": "v3_product_api_runtime",
        "failure_family": "remote_creative_brain",
        "failure_code": "remote_brain_unavailable",
        "reason_code": "remote_brain_unavailable",
        "provider_request_started": False,
        "remote_creative_brain_outcome": {
            "schema_version": "v3_remote_creative_brain_outcome_v1",
            "state": "blocked",
            "reason_code": "remote_brain_unavailable",
            "remote_error_class": "timeout",
        },
    }
    handlers.service.job_store.save(record)
    assert not handlers.project_service._doc270_general_existing_job_replayable(  # noqa: SLF001
        handlers.project_service._require_project(project["project_id"]),
        record,
    )
    assert handlers.project_service._doc270_general_retryable_command_exists(  # noqa: SLF001
        handlers.project_service._require_project(project["project_id"]),  # noqa: SLF001
        record.request.metadata["doc270_general_command_identity"],
    )

    retry = handlers.post_project_job(project["project_id"], _general_payload())
    assert retry["job_id"] != first["job_id"]
    assert calls == {"brain": 1}


def test_doc281_generated_without_persisted_output_is_not_replayed(tmp_path) -> None:
    handlers, project, _asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None, calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(first["job_id"])
    assert record is not None
    record.status = "generated"
    handlers.service.job_store.save(record)
    assert handlers.project_service._doc270_general_retryable_command_exists(  # noqa: SLF001
        handlers.project_service._require_project(project["project_id"]),
        record.request.metadata["doc270_general_command_identity"],
    )

    rebuilt = handlers.post_project_job(project["project_id"], _general_payload())
    assert rebuilt["job_id"] != first["job_id"]

    stored = handlers.service.output_store.save_base64_output(
        job_id=rebuilt["job_id"],
        candidate_id="doc281-replay-candidate",
        asset_id="doc281-replay-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64(),
    )
    rebuilt_record = handlers.service.get_job_record(rebuilt["job_id"])
    assert rebuilt_record is not None
    rebuilt_record.status = "generated"
    handlers.service.job_store.save(rebuilt_record)
    replay = handlers.post_project_job(project["project_id"], _general_payload())
    assert replay["job_id"] == rebuilt["job_id"]
    assert stored.file_path and Path(stored.file_path).is_file()


def test_doc281_explicit_terminal_retry_opens_new_job(tmp_path) -> None:
    handlers, project, _asset_ids, snapshot = _general_project(tmp_path)
    calls = {"brain": 0}
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=None, calls=calls))
    first = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(first["job_id"])
    assert record is not None
    record.status = "generated"
    handlers.service.job_store.save(record)

    retry = handlers.post_project_job(
        project["project_id"],
        _general_payload(metadata={"v3_retry_after_terminal_job_id": first["job_id"]}),
    )

    assert retry["job_id"] != first["job_id"]
    assert calls == {"brain": 1}


def test_doc281_public_activation_has_no_private_selection_disclosure(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    _replace_general_service(handlers, _selection_registry(snapshot, target_asset_id=asset_ids[0]))
    created = handlers.post_project_job(project["project_id"], _general_payload())
    public = handlers.get_project(project["project_id"])["project"]
    assert "doc281_used_source_disclosures" not in public["metadata"]
    _public_safe(public["metadata"].get("doc270_general_source_activation", {}))
    assert created["status"] == "planned"
