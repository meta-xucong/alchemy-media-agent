"""Phase 0 red contracts for Doc264 legacy E-Commerce reference recovery.

These tests define the recovery boundary before runtime work. They use only
in-memory/local stores and real local desktop/mobile DOM rendering. No test
may call Provider, MCP, ImageGen, or a remote service.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import ANY

import pytest
from PIL import Image
from playwright.sync_api import Browser, Page, sync_playwright

from alchemy_creative_agent_3_0.app.product_api.contracts import (
    ProductJobStatusValue,
    V3AssetUploadStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceAsset,
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    ProjectVisualAssetBinding,
    ProjectVisualAssetBindingService,
    ProjectVisualAssetBindingSet,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
DESKTOP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE_HTML = ROOT / "src_skeleton" / "app" / "mobile_static" / "index.html"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"

LEGACY_VISUAL_ASSET_ID = "visual_asset_0000_professional_card_rebuild_fresh_20260726"
LEGACY_VISUAL_ASSET_NAME = "Six-Year-Old Child Professional Character Card"
SAFE_LOCKED_IDENTITY_NAME = "已绑定人物资产"


def _png_base64(color: tuple[int, int, int]) -> str:
    image = Image.new("RGB", (32, 24), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _handlers(tmp_path) -> tuple[V3ProductRouteHandlers, VisualAssetLibraryCatalog]:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(catalog)
    return (
        V3ProductRouteHandlers(
            service=service,
            project_store=InMemoryProjectStore(),
            visual_asset_library_catalog=catalog,
            project_visual_asset_binding_service=bindings,
        ),
        catalog,
    )


def _ready_product_upload(
    handlers: V3ProductRouteHandlers,
    *,
    filename: str,
    color: tuple[int, int, int],
    content_base64: str | None = None,
) -> str:
    content = content_base64 or _png_base64(color)
    created = handlers.post_uploads(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(base64.b64decode(content)),
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {"content_base64": content, "mime_type": "image/png"},
    )
    ready = handlers.post_upload_complete(created["asset_id"])
    assert ready["status"] == "ready"
    return str(created["asset_id"])


def _project(handlers: V3ProductRouteHandlers) -> dict:
    return handlers.post_projects(
        {
            "user_goal": "Create a faithful Professional E-Commerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]


def _server_owned_legacy_upload_facts(
    handlers: V3ProductRouteHandlers,
    asset_id: str,
    *,
    mutation: str | None = None,
) -> None:
    """Simulate a durable pre-Doc263 ready record, never browser metadata."""

    record = handlers.service.get_uploaded_asset(asset_id)
    assert record is not None
    metadata = dict(record.metadata)
    receipt = dict(metadata.pop("upload_authorization_receipt"))
    facts = {
        "schema_version": "v3_legacy_upload_authorization_facts_v1",
        "authority": "v3_uploaded_asset_store",
        "asset_id": asset_id,
        "content_sha256": receipt["content_sha256"],
        "persisted_role": receipt["persisted_role"],
        "reference_channel": receipt["reference_channel"],
        "consent_basis": receipt["consent_basis"],
        "rights_basis": receipt["rights_basis"],
    }
    if mutation == "sha_drift":
        facts["content_sha256"] = "f" * 64
    elif mutation == "role_drift":
        facts["persisted_role"] = "face_reference"
    elif mutation == "channel_drift":
        facts["reference_channel"] = "portrait_identity"
    elif mutation == "missing_consent":
        facts["consent_basis"] = ""
    elif mutation == "missing_rights":
        facts["rights_basis"] = ""
    update = {"metadata": metadata}
    if mutation == "not_ready":
        update["status"] = V3AssetUploadStatusValue.STORED
    metadata["legacy_upload_authorization_facts"] = facts
    handlers.service.asset_store._save_record(  # noqa: SLF001
        record.model_copy(update=update)
    )


def _strip_authorization_facts(handlers: V3ProductRouteHandlers, asset_id: str) -> None:
    record = handlers.service.get_uploaded_asset(asset_id)
    assert record is not None
    metadata = dict(record.metadata)
    metadata.pop("upload_authorization_receipt", None)
    metadata.pop("legacy_upload_authorization_facts", None)
    handlers.service.asset_store._save_record(  # noqa: SLF001
        record.model_copy(update={"metadata": metadata})
    )


def _append_legacy_duplicate_references(
    handlers: V3ProductRouteHandlers,
    project_id: str,
    duplicate_asset_ids: list[str],
) -> None:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    originals = [
        item
        for item in project.reference_assets
        if item.source_type == ProjectReferenceSourceType.UPLOADED
        and item.use_policy == ProjectReferenceUsePolicy.PRODUCT
        and item.status == ProjectReferenceStatus.ACTIVE
    ]
    assert len(originals) == 4
    assert len(duplicate_asset_ids) == len(originals)
    for index, (reference, duplicate_asset_id) in enumerate(
        zip(originals, duplicate_asset_ids, strict=True),
        start=1,
    ):
        project.reference_assets.append(
            ProjectReferenceAsset(
                reference_id=f"legacy_duplicate_reference_{index}",
                project_id=project.project_id,
                source_type=ProjectReferenceSourceType.UPLOADED,
                asset_ref_id=duplicate_asset_id,
                preview_url=reference.preview_url,
                created_at=reference.created_at,
                label="Legacy duplicate product record",
                status=ProjectReferenceStatus.ACTIVE,
                use_policy=ProjectReferenceUsePolicy.PRODUCT,
                metadata={"legacy_duplicate": True},
            )
        )
        duplicate_record = handlers.service.get_uploaded_asset(duplicate_asset_id)
        assert duplicate_record is not None
        project.uploaded_asset_refs.append(
            {
                "asset_id": duplicate_asset_id,
                "source": "legacy_project_upload_ref",
                "role": "product",
                "reference_id": f"legacy_duplicate_reference_{index}",
                "status": "active",
                "content_sha256": duplicate_record.content_sha256,
                "legacy_duplicate": True,
            }
        )
    handlers.project_service.project_store.save_project(project)


def _active_product_refs(project: dict) -> list[dict]:
    return [
        item
        for item in project["reference_assets"]
        if item["status"] == "active"
        and item["source_type"] == "uploaded"
        and item["use_policy"] == "product"
    ]


def _inactive_legacy_duplicates(project: dict) -> list[dict]:
    return [
        item
        for item in project["reference_assets"]
        if item["status"] == "inactive"
        and item["metadata"].get("legacy_duplicate") is True
    ]


def _inactive_legacy_upload_ref_mirrors(project: dict) -> list[dict]:
    return [
        item
        for item in project["uploaded_asset_refs"]
        if item["status"] == "inactive"
        and item.get("legacy_duplicate") is True
    ]


def _forbid_planning_and_dispatch(monkeypatch, handlers: V3ProductRouteHandlers) -> dict[str, int]:
    calls = {"plan": 0, "dispatch": 0}

    def _unexpected_plan(*_args, **_kwargs):
        calls["plan"] += 1
        raise AssertionError("Doc264 invalid admission must close before Brain planning.")

    def _unexpected_dispatch(*_args, **_kwargs):
        calls["dispatch"] += 1
        raise AssertionError("Doc264 invalid admission must close before provider dispatch.")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", _unexpected_plan)
    monkeypatch.setattr(handlers.service.scenario_runtime, "generate_job", _unexpected_dispatch)
    return calls


def _assert_exact_reattestation_receipts(
    handlers: V3ProductRouteHandlers,
    asset_id: str,
) -> tuple[dict, dict]:
    record = handlers.service.get_uploaded_asset(asset_id)
    assert record is not None
    receipt = dict(record.metadata["upload_authorization_receipt"])
    expected_receipt_keys = {
        "schema_version",
        "authority",
        "asset_id",
        "content_sha256",
        "persisted_role",
        "reference_channel",
        "consent_basis",
        "rights_basis",
        "receipt_digest",
    }
    assert set(receipt) == expected_receipt_keys
    expected_digest = hashlib.sha256(
        "|".join(
            (
                "v3_upload_authorization_receipt_v1",
                asset_id,
                str(record.content_sha256),
                "product_reference",
                "product_truth",
                "user_uploaded_asset_for_v3_generation",
                "uploader_attestation_v3_upload_terms",
            )
        ).encode("utf-8")
    ).hexdigest()
    assert receipt == {
        "schema_version": "v3_upload_authorization_receipt_v1",
        "authority": "v3_uploaded_asset_store",
        "asset_id": asset_id,
        "content_sha256": record.content_sha256,
        "persisted_role": "product_reference",
        "reference_channel": "product_truth",
        "consent_basis": "user_uploaded_asset_for_v3_generation",
        "rights_basis": "uploader_attestation_v3_upload_terms",
        "receipt_digest": expected_digest,
    }
    marker = dict(record.metadata["legacy_product_reference_reattestation"])
    assert marker == {
        "schema_version": "doc264_legacy_product_reference_reattestation_v1",
        "authority": "v3_product_api",
        "asset_id": asset_id,
        "content_sha256": record.content_sha256,
        "persisted_role": "product_reference",
        "reference_channel": "product_truth",
        "migration_source": "v3_legacy_upload_authorization_facts_v1",
    }
    return receipt, marker


def _persist_pre_doc263_blocked_job(handlers: V3ProductRouteHandlers, job_id: str) -> None:
    record = handlers.service.get_job_record(job_id)
    assert record is not None
    metadata = {
        key: value
        for key, value in dict(record.request.metadata).items()
        if not key.startswith("doc263_")
        and not key.startswith("professional_ecommerce_product_truth")
        and key != "professional_ecommerce_contract_authority"
    }
    metadata["legacy_job_schema"] = "pre_doc263_frozen_product_inputs_v1"
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = metadata
    record.warnings.append(
        "product_truth_admission_invalid: stale legacy job diagnostics must remain historical."
    )
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)


def _inline_shell(path: Path) -> str:
    return re.sub(
        r"<script\b[^>]*\bsrc=[^>]*></script>",
        "",
        path.read_text(encoding="utf-8"),
        flags=re.IGNORECASE,
    )


def _browser_page(browser: Browser, *, html_path: Path, script_path: Path) -> Page:
    page = browser.new_page()
    page.set_content(_inline_shell(html_path))
    page.add_script_tag(content=script_path.read_text(encoding="utf-8"))
    page.evaluate("document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; })")
    return page


def _display_name_project(*, display_name: str | None = LEGACY_VISUAL_ASSET_NAME) -> dict:
    return {
        "project_id": "doc264-project",
        "primary_template_id": "ecommerce_template",
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": []},
                    "locked_person_identity": {
                        "items": [
                            {
                                "visual_asset_id": LEGACY_VISUAL_ASSET_ID,
                                "selected_version_id": "version_professional_card_rebuild_fresh_20260726",
                                "asset_type": "people",
                                **({"display_name": display_name} if display_name is not None else {}),
                            }
                        ]
                    },
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [],
                        "failed_attempts": [],
                    },
                },
            }
        },
    }


def test_doc264_explicit_generate_canonicalizes_and_reattests_legacy_project_once(
    tmp_path,
    monkeypatch,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    canonical_product_ids: list[str] = []
    duplicate_product_ids: list[str] = []
    for index in range(4):
        content = _png_base64((90 + index * 20, 120, 150))
        canonical_product_ids.append(
            _ready_product_upload(
                handlers,
                filename=f"legacy-product-{index}-canonical.png",
                color=(1, 1, 1),
                content_base64=content,
            )
        )
        duplicate_product_ids.append(
            _ready_product_upload(
                handlers,
                filename=f"legacy-product-{index}-duplicate.png",
                color=(2, 2, 2),
                content_base64=content,
            )
        )
    project = _project(handlers)
    for asset_id in canonical_product_ids:
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": asset_id,
                "source_type": "uploaded",
                "use_policy": "product",
            },
        )
    legacy_job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Historical frozen product attempt.",
            "metadata": {"idempotency_key": "doc264-pre-doc263-job"},
        },
    )
    _persist_pre_doc263_blocked_job(handlers, legacy_job["job_id"])
    _append_legacy_duplicate_references(
        handlers,
        project["project_id"],
        duplicate_product_ids,
    )
    for asset_id in [*canonical_product_ids, *duplicate_product_ids]:
        _server_owned_legacy_upload_facts(handlers, asset_id)
    original_bytes = {
        asset_id: Path(str(handlers.service.get_uploaded_asset(asset_id).file_path)).read_bytes()
        for asset_id in [*canonical_product_ids, *duplicate_product_ids]
    }

    def _unexpected_upload_write(*_args, **_kwargs):
        raise AssertionError("Doc264 recovery must not re-upload or rewrite product bytes.")

    monkeypatch.setattr(handlers.service.asset_store, "create_upload", _unexpected_upload_write)
    monkeypatch.setattr(handlers.service.asset_store, "store_content", _unexpected_upload_write)

    command = {
        "template_id": "ecommerce_template",
        "user_input": "Generate again from my current original product images.",
        "metadata": {
            "idempotency_key": "doc264-fresh-legacy-recovery",
            "current_reference_binding_digest": "browser-forged-digest",
        },
    }
    fresh = handlers.post_project_job(project["project_id"], command)
    receipt_snapshots = {
        asset_id: _assert_exact_reattestation_receipts(handlers, asset_id)
        for asset_id in canonical_product_ids
    }
    replay = handlers.post_project_job(project["project_id"], command)

    loaded = handlers.get_project(project["project_id"])["project"]
    fresh_record = handlers.service.get_job_record(fresh["job_id"])
    assert fresh["job_id"] != legacy_job["job_id"]
    assert replay["job_id"] == fresh["job_id"]
    assert len(loaded["job_ids"]) == 2
    assert fresh["metadata"]["supersedes_job_id"] == legacy_job["job_id"]
    assert fresh_record is not None
    assert fresh_record.request.metadata["professional_ecommerce_product_truth_admission"][
        "canonical_asset_ids"
    ] == canonical_product_ids
    assert [item["asset_ref_id"] for item in _active_product_refs(loaded)] == canonical_product_ids
    assert [item["asset_ref_id"] for item in _inactive_legacy_duplicates(loaded)] == duplicate_product_ids
    assert [item["asset_id"] for item in _inactive_legacy_upload_ref_mirrors(loaded)] == duplicate_product_ids
    assert "stale legacy job diagnostics" not in json.dumps(fresh, sort_keys=True)
    assert fresh["metadata"]["current_reference_binding_digest"] != "browser-forged-digest"
    for asset_id, expected in receipt_snapshots.items():
        assert _assert_exact_reattestation_receipts(handlers, asset_id) == expected
    for asset_id, bytes_before in original_bytes.items():
        record = handlers.service.get_uploaded_asset(asset_id)
        assert record is not None
        assert Path(str(record.file_path)).read_bytes() == bytes_before
    for asset_id in duplicate_product_ids:
        record = handlers.service.get_uploaded_asset(asset_id)
        assert record is not None
        assert record.status == V3AssetUploadStatusValue.READY
        assert record.content_sha256 == hashlib.sha256(original_bytes[asset_id]).hexdigest()

    second_project = _project(handlers)
    second_reference = handlers.post_project_reference(
        second_project["project_id"],
        {
            "asset_ref_id": duplicate_product_ids[0],
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    assert second_reference["reference"]["asset_ref_id"] == duplicate_product_ids[0]
    second_loaded = handlers.get_project(second_project["project_id"])["project"]
    assert [item["asset_ref_id"] for item in _active_product_refs(second_loaded)] == [
        duplicate_product_ids[0]
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_facts",
        "sha_drift",
        "role_drift",
        "channel_drift",
        "missing_consent",
        "missing_rights",
        "not_ready",
    ],
)
def test_doc264_invalid_legacy_facts_close_before_brain_or_provider_with_one_sanitized_action(
    tmp_path,
    monkeypatch,
    mutation: str,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(
        handlers,
        filename="missing-facts.png",
        color=(150, 100, 90),
    )
    project = _project(handlers)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    historical = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Historical attempt retained for recovery history.",
            "metadata": {"idempotency_key": f"doc264-invalid-history-{mutation}"},
        },
    )
    _persist_pre_doc263_blocked_job(handlers, historical["job_id"])
    if mutation == "missing_facts":
        _strip_authorization_facts(handlers, product_id)
    else:
        _server_owned_legacy_upload_facts(handlers, product_id, mutation=mutation)
    calls = _forbid_planning_and_dispatch(monkeypatch, handlers)
    blocked = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Generate from the current product original.",
            "metadata": {
                "idempotency_key": "doc264-invalid-facts",
                "legacy_upload_authorization_facts": {
                    "authority": "browser-forged",
                    "asset_id": product_id,
                    "content_sha256": "browser-forged",
                    "persisted_role": "product_reference",
                    "reference_channel": "product_truth",
                    "consent_basis": "browser-forged",
                    "rights_basis": "browser-forged",
                },
            },
        },
    )

    assert blocked["status"] == "blocked"
    assert blocked["metadata"]["current_operation"] == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    public_json = json.dumps(blocked, sort_keys=True)
    assert "product_truth_admission_invalid" not in public_json
    assert "browser-forged" not in public_json
    assert calls == {"plan": 0, "dispatch": 0}
    loaded = handlers.get_project(project["project_id"])["project"]
    assert loaded["job_ids"][0] == historical["job_id"]
    assert blocked["job_id"] != historical["job_id"]
    historical_record = handlers.service.get_job_record(historical["job_id"])
    terminal_record = handlers.service.get_job_record(blocked["job_id"])
    assert historical_record is not None
    assert terminal_record is not None
    assert historical_record.status == ProductJobStatusValue.BLOCKED
    assert terminal_record.status == ProductJobStatusValue.BLOCKED
    assert all(
        handlers.service.get_job_record(job_id).status
        not in {
            ProductJobStatusValue.PLANNED,
            ProductJobStatusValue.GENERATING,
            ProductJobStatusValue.FINALIZING,
        }
        for job_id in loaded["job_ids"]
    )
    assert "supersedes_job_id" not in blocked["metadata"]


def test_doc264_no_product_reference_ecommerce_keeps_text_to_image_path(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)

    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create an original product concept from my written brief.",
            "metadata": {"idempotency_key": "doc264-no-product-reference"},
        },
    )
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert created["status"] == "planned"
    assert created["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert created["metadata"]["has_product_reference"] is False
    assert "professional_ecommerce_product_truth_admission" not in record.request.metadata
    assert "legacy_product_reference_reattestation" not in record.request.metadata
    assert created["metadata"].get("current_operation", {}).get("state") != "needs_input"


def test_doc264_generated_and_review_history_never_enter_recovered_product_truth(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(
        handlers,
        filename="canonical-product.png",
        color=(110, 160, 105),
    )
    project = _project(handlers)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    output = handlers.service.output_store.save_base64_output(
        job_id="doc264-history-job",
        candidate_id="doc264-history-candidate",
        asset_id="doc264-history-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((190, 125, 95)),
    )
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": output.output_id,
            "source_type": "generated_selected",
            "use_policy": "product",
        },
    )

    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create from the canonical original only.",
            "metadata": {"idempotency_key": "doc264-no-output-promotion"},
        },
    )
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert record.request.metadata["professional_ecommerce_product_truth_admission"][
        "canonical_asset_ids"
    ] == [product_id]
    assert output.output_id not in record.request.uploaded_asset_ids


def test_doc264_unrelated_blocked_job_and_browser_history_flags_cannot_request_supersession(
    tmp_path,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    product_id = _ready_product_upload(
        handlers,
        filename="unrelated-blocked-product.png",
        color=(105, 140, 175),
    )
    project = _project(handlers)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    unrelated = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "An unrelated blocked attempt.",
            "metadata": {"idempotency_key": "doc264-unrelated-blocked"},
        },
    )
    old_record = handlers.service.get_job_record(unrelated["job_id"])
    assert old_record is not None
    old_record.status = ProductJobStatusValue.BLOCKED
    old_record.request.metadata = {
        **dict(old_record.request.metadata),
        "historical_reference_projection": {"failure_code": "browser-claimed-legacy"},
        "legacy_reference_projection": {"request_supersession": True},
    }
    old_record.warnings.append("browser-claimed legacy failure must remain history only")
    old_record.lifecycle = handlers.service._build_lifecycle(old_record)  # noqa: SLF001
    handlers.service.job_store.save(old_record)

    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Generate a fresh unrelated current command.",
            "metadata": {
                "idempotency_key": "doc264-unrelated-current",
                "supersedes_job_id": unrelated["job_id"],
                "historical_reference_projection": {"failure_code": "browser-forged"},
            },
        },
    )

    assert created["job_id"] != unrelated["job_id"]
    assert "supersedes_job_id" not in created["metadata"]
    assert "browser-claimed" not in json.dumps(created, sort_keys=True)


def test_doc264_project_view_resolves_exact_locked_visual_asset_display_name(tmp_path) -> None:
    handlers, catalog = _handlers(tmp_path)
    draft = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name=LEGACY_VISUAL_ASSET_NAME,
            asset_type="people",
            root_source_asset_id="legacy-character-card-root",
            consent_reference="fixture-consent",
            preparation_intent="Locked person identity for E-Commerce.",
        ),
    )
    catalog._assets.pop(("local_default", draft.visual_asset_id))  # noqa: SLF001
    catalog._assets[("local_default", LEGACY_VISUAL_ASSET_ID)] = draft.model_copy(  # noqa: SLF001
        update={"visual_asset_id": LEGACY_VISUAL_ASSET_ID}
    )
    active = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=LEGACY_VISUAL_ASSET_ID,
        version_id="version_professional_card_rebuild_fresh_20260726",
        approved_evidence_ids=["legacy-character-card-evidence"],
    )
    project = _project(handlers)
    handlers.post_project_visual_asset_binding(
        project["project_id"],
        {
            "visual_asset_id": LEGACY_VISUAL_ASSET_ID,
            "selected_version_id": active.active_version_id,
            "confirm_binding": True,
        },
    )
    binding_service = handlers.project_service.project_visual_asset_binding_service
    assert binding_service is not None
    binding_service._current[project["project_id"]][0] = (  # noqa: SLF001
        binding_service._current[project["project_id"]][0].model_copy(  # noqa: SLF001
            update={"provenance": {"display_name": "Caller forged visual asset name"}}
        )
    )

    view = handlers.get_project(project["project_id"])["metadata"]["ecommerce_project_view"]
    assert view["groups"]["locked_person_identity"]["items"] == [
        {
            "binding_id": ANY,
            "visual_asset_id": LEGACY_VISUAL_ASSET_ID,
            "selected_version_id": "version_professional_card_rebuild_fresh_20260726",
            "asset_type": "people",
            "display_name": LEGACY_VISUAL_ASSET_NAME,
        }
    ]


class _MissingCatalogBindingService:
    """Fixture seam: a durable binding whose catalog record no longer resolves."""

    def current(self, *, project_id: str) -> ProjectVisualAssetBindingSet:
        return ProjectVisualAssetBindingSet(
            project_id=project_id,
            state="valid",
            bindings=[
                ProjectVisualAssetBinding(
                    binding_id="binding_missing_catalog",
                    project_id=project_id,
                    visual_asset_id="visual_asset_missing_catalog",
                    selected_version_id="version_missing_catalog",
                    owner_scope="local_default",
                    user_confirmed=True,
                    created_at="2026-08-10T00:00:00Z",
                    provenance={"display_name": "Caller supplied false name"},
                )
            ],
        )


def test_doc264_missing_catalog_binding_uses_safe_generic_display_name(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    handlers.project_service.project_visual_asset_binding_service = _MissingCatalogBindingService()

    view = handlers.get_project(project["project_id"])["metadata"]["ecommerce_project_view"]
    locked = view["groups"]["locked_person_identity"]["items"]

    assert locked == [
        {
            "binding_id": "binding_missing_catalog",
            "visual_asset_id": "visual_asset_missing_catalog",
            "selected_version_id": "version_missing_catalog",
            "asset_type": "people",
            "display_name": SAFE_LOCKED_IDENTITY_NAME,
        }
    ]


@pytest.mark.parametrize(
    ("html_path", "script_path", "mode"),
    [
        (DESKTOP_HTML, DESKTOP_JS, "desktop"),
        (MOBILE_HTML, MOBILE_JS, "mobile"),
    ],
)
def test_doc264_desktop_and_mobile_render_locked_asset_display_name(
    html_path: Path,
    script_path: Path,
    mode: str,
) -> None:
    project = _display_name_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mode == "desktop":
                page.evaluate(
                    """
                    (project) => {
                      v3State.currentProject = project;
                      renderV3UsefulReferences();
                    }
                    """,
                    project,
                )
                primary = page.locator(
                    "#v3UsefulReferenceBoard .locked_person_identity .v3-locked-identity-tile strong"
                ).inner_text()
            else:
                page.evaluate(
                    """
                    (project) => {
                      ensureMobileLayers();
                      mobileV3State.currentProject = project;
                      renderMobileV3ReferenceBoard(project);
                    }
                    """,
                    project,
                )
                primary = page.locator(
                    "#mobileV3ReferenceBoard .locked_person_identity .v3-mobile-reference-tile strong"
                ).inner_text()

            assert primary == LEGACY_VISUAL_ASSET_NAME
            assert primary != "people"
            assert primary != LEGACY_VISUAL_ASSET_ID
        finally:
            browser.close()


@pytest.mark.parametrize(
    ("html_path", "script_path", "mode"),
    [
        (DESKTOP_HTML, DESKTOP_JS, "desktop"),
        (MOBILE_HTML, MOBILE_JS, "mobile"),
    ],
)
def test_doc264_desktop_and_mobile_use_safe_primary_fallback_for_missing_display_name(
    html_path: Path,
    script_path: Path,
    mode: str,
) -> None:
    project = _display_name_project(display_name=None)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            if mode == "desktop":
                page.evaluate(
                    """
                    (project) => {
                      v3State.currentProject = project;
                      renderV3UsefulReferences();
                    }
                    """,
                    project,
                )
                primary = page.locator(
                    "#v3UsefulReferenceBoard .locked_person_identity .v3-locked-identity-tile strong"
                ).inner_text()
            else:
                page.evaluate(
                    """
                    (project) => {
                      ensureMobileLayers();
                      mobileV3State.currentProject = project;
                      renderMobileV3ReferenceBoard(project);
                    }
                    """,
                    project,
                )
                primary = page.locator(
                    "#mobileV3ReferenceBoard .locked_person_identity .v3-mobile-reference-tile strong"
                ).inner_text()

            assert primary == SAFE_LOCKED_IDENTITY_NAME
            assert primary != "people"
            assert primary != LEGACY_VISUAL_ASSET_ID
        finally:
            browser.close()
