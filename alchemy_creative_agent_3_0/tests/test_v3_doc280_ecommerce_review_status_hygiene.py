"""Phase 0 red contracts for Doc280 E-Commerce review-status hygiene.

The suite uses only local stores and Playwright fixtures. It never calls a
Provider, MCP, ImageGen, VPS, or a live project/job/output.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import ReviewEvidencePlan
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_evidence import review_plan_digest
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc260_review_evidence_plan import _png_base64
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _job_payload,
)


RAW_REFINE_WARNING = "asset asset_doc280_private exhausted refine budget"
RAW_REJECT_WARNING = "asset asset_doc280_private packaged with reject recommendation"
RAW_PROVIDER_TRACE = "provider_payload trace=private-route hash=private-hash"


def _doc280_output_id(label: str) -> str:
    return f"v3_output_{hashlib.sha256(label.encode('ascii')).hexdigest()[:20]}"


def _ecommerce_record(tmp_path, *, key: str):
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename=f"{key}.png",
        color=(92, 132, 172),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[product_id], key=key),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.planning_result is not None
    return handlers, project, record


def _review_package(*, state: str, output_id: str = "output-doc280", asset_id: str = "asset-doc280") -> dict[str, Any]:
    inspection_status = {
        "final_delivery_available": "pass",
        "review_withheld_manual_confirmation": "manual_review",
        "review_withheld_review_failure": "fail_final",
    }[state]
    return {
        "review_evidence_receipt_status": "complete",
        "resolutions": [{"output_id": output_id, "status": "ready"}],
        "inspections": [
            {
                "output_id": output_id,
                "asset_id": asset_id,
                "mode": "vision_model",
                "status": inspection_status,
                "verification_state": "verified",
                "evidence": {"provider_pixel_result_certified": True},
            }
        ],
        "review_evidence_plans": {},
    }


def _final_delivery_facts(state: str) -> dict[str, Any]:
    return {
        "delivery_gate_applies": True,
        "final_delivery_status": {
            "final_delivery_available": "ready",
            "review_withheld_manual_confirmation": "withheld_manual_confirmation",
            "review_withheld_review_failure": "withheld_review_failure",
        }[state],
        "automatic_delivery_available": state == "final_delivery_available",
        "manual_confirmation_required": state == "review_withheld_manual_confirmation",
    }


def _persist_generated_review_state(
    record,
    handlers,
    *,
    state: str,
    output_id: str | None = None,
    asset_id: str = "asset-doc280",
    persist_output: bool = True,
    output_job_id: str | None = None,
    output_final_delivery: dict[str, Any] | None = None,
) -> Any | None:
    output_id = output_id or _doc280_output_id(f"canonical-{state}")
    output = None
    if persist_output:
        output = handlers.service.output_store.save_base64_output(
            job_id=output_job_id or record.job_id,
            candidate_id=f"candidate-{output_id}",
            asset_id=asset_id,
            provider="local-test",
            model="local-test",
            encoded_image=_png_base64(),
            output_id=output_id,
            metadata={
                "final_delivery": output_final_delivery or _final_delivery_facts(state),
            },
        )
    record.generation_result = record.planning_result.model_copy(deep=True)
    record.status = ProductJobStatusValue.GENERATED
    metadata = dict(record.generation_result.metadata or {})
    metadata["post_generation_review_package"] = _review_package(
        state=state,
        output_id=output_id,
        asset_id=asset_id,
    )
    record.generation_result.metadata = metadata
    handlers.service.job_store.save(record)
    return output


def _persist_formal_export_review_case(record, handlers, statuses: list[str]) -> tuple[set[str], dict[str, str]]:
    result = record.planning_result.model_copy(deep=True)
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    assert intents and len(intents) == len(statuses)
    any_eligible = any(status in {"pass", "warning"} for status in statuses)
    delivery_facts = {
        "delivery_gate_applies": True,
        "final_delivery_status": "ready" if any_eligible else "withheld_review_failure",
        "automatic_delivery_available": any_eligible,
        "manual_confirmation_required": False,
    }
    envelope = {
        "execution_fingerprint": f"fingerprint_{record.job_id}",
        "envelope_id": f"envelope_{record.job_id}",
        "resolved_constraint_ledger": {
            "ledger_id": f"ledger_{record.job_id}",
            "provider_projection": {"capability_projection": {}},
        },
    }
    base_asset = result.asset_pack.assets[0]
    packaged_assets = []
    resolutions = []
    inspections = []
    eligible_ids: set[str] = set()
    status_by_output: dict[str, str] = {}
    for index, (intent, status) in enumerate(zip(intents, statuses), start=1):
        asset_id = str(intent["asset_id"])
        output_id = _doc280_output_id(f"formal-export-{record.job_id}-{index}")
        candidate_id = f"candidate_{output_id}"
        output_delivery_status = (
            "ready"
            if status in {"pass", "warning"}
            else "withheld_manual_confirmation"
            if status in {"manual_review", "fail_retryable"}
            else "withheld_review_failure"
        )
        output_delivery_facts = {
            "delivery_gate_applies": True,
            "final_delivery_status": output_delivery_status,
            "automatic_delivery_available": output_delivery_status == "ready",
            "manual_confirmation_required": output_delivery_status == "withheld_manual_confirmation",
        }
        output = handlers.service.output_store.save_base64_output(
            job_id=record.job_id,
            candidate_id=candidate_id,
            asset_id=asset_id,
            provider="local-export-fixture",
            model="offline",
            encoded_image=_png_base64(),
            output_id=output_id,
            metadata={
                "final_delivery": output_delivery_facts,
                "project_id": record.request.metadata.get("project_id"),
                "capability_execution_envelope": envelope,
            },
        )
        packaged_assets.append(
            base_asset.model_copy(
                update={
                    "asset_id": asset_id,
                    "file_path": output.file_path,
                    "metadata": {
                        **dict(base_asset.metadata or {}),
                        "selected_candidate_id": candidate_id,
                        "candidate_metadata": {
                            "candidate_id": candidate_id,
                            "output_id": output_id,
                            "download_url": output.download_url,
                            "preview_url": output.preview_url,
                            "thumbnail_url": output.thumbnail_url,
                            "width": output.width,
                            "height": output.height,
                            "mime_type": output.mime_type,
                            "format": "png",
                            "v3_owned_output": True,
                        },
                    },
                }
            )
        )
        resolutions.append(
            {
                "resolution_id": f"resolution_{output_id}",
                "job_id": record.job_id,
                "output_id": output_id,
                "asset_id": asset_id,
                "candidate_id": candidate_id,
                "status": "ready",
            }
        )
        inspections.append(
            {
                "inspection_id": f"inspection_{output_id}",
                "output_id": output_id,
                "asset_id": asset_id,
                "mode": "vision_model",
                "verification_state": "verified",
                "status": status,
                "evidence": {"provider_pixel_result_certified": True},
                "detected_issues": [] if status in {"pass", "warning"} else [{"code": "visible_text_artifact"}],
            }
        )
        status_by_output[output_id] = status
        if status in {"pass", "warning"}:
            eligible_ids.add(output_id)

    result.asset_pack = result.asset_pack.model_copy(update={"assets": packaged_assets})
    result.metadata = {
        **dict(result.metadata or {}),
        "capability_execution_envelope": envelope,
        "post_generation_review_package": {
            "review_evidence_receipt_status": "complete",
            "review_evidence_receipt_errors": [],
            "resolutions": resolutions,
            "inspections": inspections,
        },
    }
    record.generation_result = result
    record.status = ProductJobStatusValue.GENERATED
    handlers.service.job_store.save(record)
    return eligible_ids, status_by_output


def _retry_review_package(job_id: str, rows: list[dict[str, str]], package_id: str) -> dict[str, Any]:
    resolutions = []
    inspections = []
    plans = {}
    digests = {}
    for row in rows:
        output_id = row["output_id"]
        asset_id = row["asset_id"]
        resolutions.append(
            {
                "resolution_id": f"resolution_{output_id}",
                "job_id": job_id,
                "output_id": output_id,
                "asset_id": asset_id,
                "candidate_id": f"candidate_{output_id}",
                "status": "ready",
            }
        )
        inspections.append(
            {
                "inspection_id": f"inspection_{output_id}",
                "output_id": output_id,
                "asset_id": asset_id,
                "mode": "vision_model",
                "verification_state": "verified",
                "status": row["status"],
                "evidence": {"provider_pixel_result_certified": True},
                "detected_issues": [] if row["status"] in {"pass", "warning"} else [{"code": "visible_text_artifact"}],
                "score_card": {
                    "same_person_readability": 0.9 if row["status"] in {"pass", "warning"} else 0.3,
                    "prompt_owned_channel_obedience": 0.9 if row["status"] in {"pass", "warning"} else 0.3,
                    "human_realism": 0.9 if row["status"] in {"pass", "warning"} else 0.3,
                    "commercial_finish": 0.9 if row["status"] in {"pass", "warning"} else 0.3,
                },
            }
        )
        plan = ReviewEvidencePlan.model_validate(
            {
                "contract_version": "review_evidence_plan_v1",
                "plan_id": f"plan_{output_id}",
                "job_id": job_id,
                "output_id": output_id,
                "review_mode": "real_pixel",
                "channels": {
                    "product_truth": {"applicability": "not_applicable", "evidence_state": "not_applicable"},
                    "person_identity": {"applicability": "not_applicable", "evidence_state": "not_applicable"},
                    "prompt_semantics": {
                        "applicability": "required",
                        "evidence_state": "available",
                        "evidence_ids": ["prompt_contract"],
                        "source_type": "prompt_contract",
                    },
                    "selected_output": {
                        "applicability": "required",
                        "evidence_state": "available",
                        "evidence_ids": [output_id],
                    },
                },
                "source_binding_digest": f"binding_{output_id}",
                "review_plan_digest": "pending",
            }
        ).model_dump(mode="json")
        plan["review_plan_digest"] = review_plan_digest(plan)
        plans[output_id] = plan
        digests[output_id] = plan["review_plan_digest"]
    return {
        "package_id": package_id,
        "job_id": job_id,
        "review_evidence_receipt_status": "complete",
        "review_evidence_receipt_errors": [],
        "resolutions": resolutions,
        "review_evidence_plans": plans,
        "review_evidence_plan_digests": digests,
        "inspections": inspections,
    }


def _expected_disposition(state: str) -> dict[str, Any]:
    actions = [] if state == "final_delivery_available" else [{"id": "review_generation_history"}]
    return {
        "schema_version": "doc280_ecommerce_review_disposition_v1",
        "state": state,
        "terminal": True,
        "pending": False,
        "next_actions": actions,
    }


def test_doc280_raw_refine_and_reject_diagnostics_remain_private_not_public(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-raw-warning")
    record.warnings.extend([RAW_REFINE_WARNING, RAW_REJECT_WARNING, RAW_PROVIDER_TRACE])
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)
    public_project = handlers.get_project(project["project_id"])
    durable = handlers.service.get_job_record(record.job_id)

    assert durable is not None
    assert RAW_REFINE_WARNING in durable.warnings
    assert RAW_REJECT_WARNING in durable.warnings
    public_text = json.dumps({"job": public_job, "project": public_project}, ensure_ascii=False, sort_keys=True)
    assert "asset_doc280_private" not in public_text
    assert "exhausted refine budget" not in public_text
    assert "packaged with reject recommendation" not in public_text
    assert "private-route" not in public_text
    assert "private-hash" not in public_text


@pytest.mark.parametrize(
    "state",
    [
        "final_delivery_available",
        "review_withheld_manual_confirmation",
        "review_withheld_review_failure",
    ],
)
def test_doc280_public_review_disposition_is_exactly_derived_from_canonical_review(
    tmp_path,
    state: str,
) -> None:
    handlers, _project_record, record = _ecommerce_record(tmp_path, key=f"doc280-disposition-{state}")
    output = _persist_generated_review_state(record, handlers, state=state)

    public_job = handlers.get_job(record.job_id)

    assert output is not None
    assert output.job_id == record.job_id
    assert output.output_id == _doc280_output_id(f"canonical-{state}")
    assert output.asset_id == "asset-doc280"
    assert output.metadata["final_delivery"] == _final_delivery_facts(state)
    assert public_job["metadata"]["review_disposition"] == _expected_disposition(state)
    assert "asset-doc280" not in json.dumps(public_job, ensure_ascii=False, sort_keys=True)
    # DOC321: opaque output IDs are needed for per-image Project review.
    # Provider paths, asset IDs and raw evidence remain private.
    review = public_job["metadata"]["post_generation_review"]
    assert [item["output_id"] for item in review["review_items"]] == [output.output_id]
    assert review["recommended_output_ids"] == ([output.output_id] if state == "final_delivery_available" else [])
    assert all("asset_id" not in item and "evidence" not in item and "file_path" not in item for item in review["review_items"])


def test_doc280_formal_export_excludes_all_failed_outputs(tmp_path) -> None:
    handlers, _project, record = _ecommerce_record(tmp_path, key="doc280-formal-all-fail")
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    eligible_ids, _status_by_output = _persist_formal_export_review_case(
        record,
        handlers,
        ["fail_final"] * len(intents),
    )

    exported = handlers.service.export_job(record.job_id).model_dump(mode="json")
    public_job = handlers.get_job(record.job_id)

    assert eligible_ids == set()
    assert exported["export_package"]["files"] == []
    assert exported["manifest"]["export_files"] == []
    assert exported["manifest"]["generated_assets"] == []
    assert {item["status"] for item in public_job["metadata"]["post_generation_review"]["review_items"]} == {
        "fail_final"
    }


def test_doc280_formal_export_contains_only_eligible_outputs_with_true_review_status(tmp_path) -> None:
    handlers, _project, record = _ecommerce_record(tmp_path, key="doc280-formal-partial")
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    assert len(intents) >= 2
    states = ["warning", *(["fail_final"] * (len(intents) - 1))]
    eligible_ids, status_by_output = _persist_formal_export_review_case(record, handlers, states)

    exported = handlers.service.export_job(record.job_id).model_dump(mode="json")
    public_job = handlers.get_job(record.job_id)
    files = exported["export_package"]["files"]
    generated_assets = exported["manifest"]["generated_assets"]

    assert {item["output_id"] for item in files} == eligible_ids
    assert {item["output_id"] for item in generated_assets} == eligible_ids
    assert {item["review_status"] for item in files} == {"warning"}
    assert {item["review_status"] for item in generated_assets} == {"warning"}
    assert all(status == "fail_final" for output_id, status in status_by_output.items() if output_id not in eligible_ids)
    assert {item["status"] for item in public_job["metadata"]["post_generation_review"]["review_items"]} == {
        "warning",
        "fail_final",
    }


def test_doc280_formal_export_respects_explicit_eligible_selection_subset(tmp_path) -> None:
    handlers, _project, record = _ecommerce_record(tmp_path, key="doc280-formal-selected-subset")
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    eligible_ids, _status_by_output = _persist_formal_export_review_case(
        record,
        handlers,
        ["warning"] * len(intents),
    )
    assert len(eligible_ids) >= 2
    record = handlers.service.get_job_record(record.job_id)
    assert record is not None and record.generation_result is not None
    chosen_asset = record.generation_result.asset_pack.assets[0]
    chosen_output_id = chosen_asset.metadata["candidate_metadata"]["output_id"]

    selection = handlers.service.select_result(
        record.job_id,
        {"selected_asset_ids": [chosen_asset.asset_id]},
    )
    exported = handlers.service.export_job(record.job_id).model_dump(mode="json")

    assert selection.status == ProductJobStatusValue.SELECTED
    assert {item["output_id"] for item in exported["export_package"]["files"]} == {chosen_output_id}
    assert {item["output_id"] for item in exported["manifest"]["generated_assets"]} == {chosen_output_id}


def test_doc280_automatic_product_project_and_export_consumers_share_the_eligible_set(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-consumer-set-equality")
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    eligible_ids, _status_by_output = _persist_formal_export_review_case(
        record,
        handlers,
        ["warning"] * len(intents),
    )
    final_delivery, closure_eligible_ids, _eligible_asset_ids = handlers.service._public_final_delivery_projection(  # noqa: SLF001
        record.generation_result
    )
    assert closure_eligible_ids == eligible_ids
    output_records = handlers.service.output_store.list_by_job(record.job_id)
    result_envelope = output_records[0].metadata["capability_execution_envelope"]
    result_ledger = result_envelope["resolved_constraint_ledger"]
    closure = {
        "schema_version": "v3_output_delivery_closure_v1",
        "job_id": record.job_id,
        "status": "complete",
        "review_evidence_receipt_status": "complete",
        "final_delivery_status": final_delivery["final_delivery_status"],
        "automatic_delivery_available": final_delivery["automatic_delivery_available"],
        "eligible_output_ids": sorted(eligible_ids),
        "execution_fingerprint": result_envelope["execution_fingerprint"],
        "envelope_id": result_envelope["envelope_id"],
        "ledger_id": result_ledger["ledger_id"],
        "outputs": [
            {
                "output_id": item.output_id,
                "job_id": item.job_id,
                "asset_id": item.asset_id,
                "candidate_id": item.candidate_id,
                "content_sha256": item.metadata["content_sha256"],
            }
            for item in output_records
        ],
    }
    closure_valid = handlers.service._valid_output_store_job_closure(  # noqa: SLF001
        closure,
        job_id=record.job_id,
        records=output_records,
    )
    assert closure_valid[0], closure_valid
    handlers.service.output_store.save_job_closure(record.job_id, closure)

    product_status = handlers.get_job(record.job_id)
    project_outputs = handlers.get_project_outputs(project_id=project["project_id"], compact=True)["items"]
    exported = handlers.service.export_job(record.job_id).model_dump(mode="json")

    assert set(product_status["metadata"]["post_generation_review"]["recommended_output_ids"]) == eligible_ids
    assert {item["output_id"] for item in project_outputs} == eligible_ids
    assert {item["output_id"] for item in exported["export_package"]["files"]} == eligible_ids
    assert {item["output_id"] for item in exported["manifest"]["generated_assets"]} == eligible_ids


@pytest.mark.parametrize("mixed_winner_status", [False, True])
def test_doc280_retry_winners_match_product_project_and_formal_export_consumers(
    tmp_path,
    mixed_winner_status: bool,
) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-retry-consumer-equality")
    result = record.planning_result.model_copy(deep=True)
    intents = handlers.service._ecommerce_output_intents(record)  # noqa: SLF001
    assert len(intents) == 2
    roles = [str(item["asset_id"]) for item in intents]
    attempt_rows = {
        "initial": [
            {"output_id": _doc280_output_id("retry-old-a"), "asset_id": roles[0], "status": "warning"},
            {"output_id": _doc280_output_id("retry-old-b"), "asset_id": roles[1], "status": "fail_final"},
        ],
        "retry": [
            {"output_id": _doc280_output_id("retry-new-a"), "asset_id": roles[0], "status": "fail_final"},
            {
                "output_id": _doc280_output_id("retry-new-b"),
                "asset_id": roles[1],
                "status": "fail_final" if mixed_winner_status else "warning",
            },
        ],
    }
    envelope = result.metadata["capability_execution_envelope"]
    base_asset = result.asset_pack.assets[0]

    def packaged_assets(rows: list[dict[str, str]]) -> list[Any]:
        assets = []
        for row in rows:
            output_id = row["output_id"]
            candidate_id = f"candidate_{output_id}"
            output = handlers.service.output_store.save_base64_output(
                job_id=record.job_id,
                candidate_id=candidate_id,
                asset_id=row["asset_id"],
                provider="local-retry-fixture",
                model="offline",
                encoded_image=_png_base64(),
                output_id=output_id,
                metadata={
                    "project_id": project["project_id"],
                    "capability_execution_envelope": envelope,
                    "final_delivery": {
                        "delivery_gate_applies": True,
                        "final_delivery_status": "ready" if row["status"] in {"pass", "warning"} else "withheld_review_failure",
                        "automatic_delivery_available": row["status"] in {"pass", "warning"},
                        "manual_confirmation_required": False,
                    },
                },
            )
            assets.append(
                base_asset.model_copy(
                    update={
                        "asset_id": row["asset_id"],
                        "file_path": output.file_path,
                        "metadata": {
                            **dict(base_asset.metadata or {}),
                            "selected_candidate_id": candidate_id,
                            "candidate_metadata": {
                                "candidate_id": candidate_id,
                                "output_id": output_id,
                                "download_url": output.download_url,
                                "preview_url": output.preview_url,
                                "thumbnail_url": output.thumbnail_url,
                                "width": output.width,
                                "height": output.height,
                                "mime_type": output.mime_type,
                                "format": "png",
                                "v3_owned_output": True,
                            },
                        },
                    }
                )
            )
        return assets

    initial_package = _retry_review_package(record.job_id, attempt_rows["initial"], "initial_attempt")
    retry_package = _retry_review_package(record.job_id, attempt_rows["retry"], "retry_attempt")
    initial_package["user_visible_summary"] = ["The first attempt included one failed image."]
    retry_package["user_visible_summary"] = ["The latest retry still has an unresolved image failure."]
    initial = result.model_copy(
        update={
            "asset_pack": result.asset_pack.model_copy(update={"assets": packaged_assets(attempt_rows["initial"])}),
            "metadata": {**dict(result.metadata), "post_generation_review_package": initial_package},
        }
    )
    retry = result.model_copy(
        update={
            "asset_pack": result.asset_pack.model_copy(update={"assets": packaged_assets(attempt_rows["retry"])}),
            "metadata": {
                **dict(result.metadata),
                "visual_auto_retry_attempt": 1,
                "post_generation_review_package": retry_package,
            },
        }
    )
    merged = handlers.service._merge_retry_generation_result(  # noqa: SLF001
        initial,
        retry,
        records=[],
        max_attempts=1,
    )
    preferred = handlers.service._apply_reviewed_delivery_preference(merged)  # noqa: SLF001
    record.generation_result = preferred
    record.status = ProductJobStatusValue.GENERATED
    handlers.service.job_store.save(record)
    winner_ids = (
        {_doc280_output_id("retry-old-a"), _doc280_output_id("retry-new-b")}
    )
    eligible_winner_ids = (
        {_doc280_output_id("retry-old-a")}
        if mixed_winner_status
        else winner_ids
    )
    assert handlers.service._public_final_delivery_projection(preferred)[1] == eligible_winner_ids  # noqa: SLF001
    assert handlers.service._persist_output_store_job_closure(record, preferred)  # noqa: SLF001

    product_status = handlers.get_job(record.job_id)
    project_outputs = handlers.get_project_outputs(project_id=project["project_id"], compact=True)["items"]
    exported = handlers.service.export_job(record.job_id).model_dump(mode="json")

    assert set(product_status["metadata"]["post_generation_review"]["recommended_output_ids"]) == eligible_winner_ids
    assert product_status["metadata"]["review_disposition"] == _expected_disposition(
        "final_delivery_available"
    )
    assert {item["output_id"] for item in project_outputs} == eligible_winner_ids
    expected_export_ids = eligible_winner_ids if mixed_winner_status else winner_ids
    assert {item["output_id"] for item in exported["export_package"]["files"]} == expected_export_ids
    assert {item["output_id"] for item in exported["manifest"]["generated_assets"]} == expected_export_ids
    assert {item["review_status"] for item in exported["manifest"]["generated_assets"]} == {"warning"}
    if mixed_winner_status:
        assert {item["status"] for item in product_status["metadata"]["post_generation_review"]["review_items"]} == {
            "warning",
            "fail_final",
        }


def test_doc280_extra_append_only_output_without_matching_closure_fails_closed(tmp_path) -> None:
    handlers, _project, record = _ecommerce_record(tmp_path, key="doc280-extra-output-without-closure")
    output = _persist_generated_review_state(record, handlers, state="final_delivery_available")
    assert output is not None
    handlers.service.output_store.save_base64_output(
        job_id=record.job_id,
        candidate_id="candidate-unclosed-extra",
        asset_id="asset-unclosed-extra",
        provider="local-test",
        model="local-test",
        encoded_image=_png_base64(),
        output_id=_doc280_output_id("unclosed-extra"),
        metadata={"final_delivery": _final_delivery_facts("final_delivery_available")},
    )

    public_job = handlers.get_job(record.job_id)

    assert "review_disposition" not in public_job["metadata"]


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_output",
        "foreign_output_job",
        "resolution_output_mismatch",
        "inspection_asset_mismatch",
        "final_delivery_conflict",
    ],
)
def test_doc280_unbound_or_conflicting_review_package_fails_closed_without_disposition_or_history_action(
    tmp_path,
    corruption: str,
) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key=f"doc280-unbound-{corruption}")
    output_id = _doc280_output_id("bound")
    asset_id = "asset-doc280-bound"
    kwargs: dict[str, Any] = {
        "state": "review_withheld_manual_confirmation",
        "output_id": output_id,
        "asset_id": asset_id,
    }
    if corruption == "missing_output":
        kwargs["persist_output"] = False
    elif corruption == "foreign_output_job":
        kwargs["output_job_id"] = "job_doc280_foreign"
    elif corruption == "final_delivery_conflict":
        kwargs["output_final_delivery"] = _final_delivery_facts("final_delivery_available")
    _persist_generated_review_state(record, handlers, **kwargs)

    package = record.generation_result.metadata["post_generation_review_package"]
    if corruption == "resolution_output_mismatch":
        package["resolutions"][0]["output_id"] = _doc280_output_id("other")
    elif corruption == "inspection_asset_mismatch":
        package["inspections"][0]["asset_id"] = "asset-doc280-other"
    record.generation_result.metadata["post_generation_review_package"] = package
    record.warnings.append(RAW_REJECT_WARNING)
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)
    public_project = handlers.get_project(project["project_id"])
    public_text = json.dumps({"job": public_job, "project": public_project}, ensure_ascii=False, sort_keys=True)
    operation = public_project["metadata"].get("current_operation")

    assert "review_disposition" not in public_job["metadata"]
    assert operation is None or operation.get("next_actions") != [{"id": "review_generation_history"}]
    assert RAW_REJECT_WARNING not in public_text
    if corruption == "resolution_output_mismatch":
        assert _doc280_output_id("other") not in public_text
    if corruption == "inspection_asset_mismatch":
        assert "asset-doc280-other" not in public_text


def test_doc280_no_output_terminal_has_typed_disposition_without_browser_authority(tmp_path) -> None:
    handlers, _project_record, record = _ecommerce_record(tmp_path, key="doc280-no-output")
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        **dict(record.request.metadata or {}),
        "review_disposition": _expected_disposition("review_withheld_manual_confirmation"),
        "warnings": [RAW_REFINE_WARNING],
    }
    handlers.service.job_store.save(record)

    public_job = handlers.get_job(record.job_id)

    assert public_job["metadata"]["review_disposition"] == {
        "schema_version": "doc280_ecommerce_review_disposition_v1",
        "state": "no_delivery_terminal",
        "terminal": True,
        "pending": False,
        "next_actions": [],
    }
    assert "asset_doc280_private" not in json.dumps(public_job, ensure_ascii=False, sort_keys=True)


def test_doc280_review_only_media_is_history_only_and_never_final_home_delivery(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-review-history")
    output = _persist_generated_review_state(
        record,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("review"),
        asset_id="asset-doc280-review",
    )

    assert output is not None
    public_project = handlers.get_project(project["project_id"])
    view = public_project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]

    assert public_project["metadata"]["project_outputs"] == []
    assert [item["output_id"] for item in view["review_withheld_outputs"]] == [output.output_id]
    assert public_project["metadata"]["current_operation"]["next_actions"] == [{"id": "review_generation_history"}]


def test_doc280_forged_browser_review_fields_cannot_create_current_review_operation(tmp_path) -> None:
    handlers, project, record = _ecommerce_record(tmp_path, key="doc280-forged-browser-review")
    record.request.metadata = {
        **dict(record.request.metadata or {}),
        "review_disposition": _expected_disposition("review_withheld_manual_confirmation"),
        "current_operation": {
            "state": "review_withheld_manual_confirmation",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_generation_history"}],
        },
        "review_generation_history": [{"output_id": "browser-forged-output"}],
    }
    handlers.service.job_store.save(record)

    public_project = handlers.get_project(project["project_id"])

    operation = public_project["metadata"].get("current_operation")
    assert operation is not None and operation["state"] == "planning"
    assert operation["state"] != "review_withheld_manual_confirmation"
    assert "browser-forged-output" not in json.dumps(public_project, ensure_ascii=False, sort_keys=True)


def test_doc280_newest_planned_command_masks_prior_review_operation_without_rewriting_history(tmp_path) -> None:
    handlers, project, prior = _ecommerce_record(tmp_path, key="doc280-prior-review")
    _persist_generated_review_state(prior, handlers, state="review_withheld_manual_confirmation")
    prior_metadata = deepcopy(prior.generation_result.metadata)
    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key="doc280-new-command"),
    )

    public_project = handlers.get_project(project["project_id"])
    durable_prior = handlers.service.get_job_record(prior.job_id)

    assert newer["job_id"] in public_project["project"]["job_ids"]
    assert public_project["metadata"]["current_operation"]["state"] == "planning"
    assert durable_prior is not None and durable_prior.generation_result is not None
    assert durable_prior.generation_result.metadata == prior_metadata


@pytest.mark.parametrize("newer_status", [ProductJobStatusValue.GENERATED, ProductJobStatusValue.BLOCKED])
def test_doc280_newer_job_cannot_reuse_prior_output_as_its_current_review_disposition(
    tmp_path,
    newer_status: ProductJobStatusValue,
) -> None:
    handlers, project, prior = _ecommerce_record(tmp_path, key=f"doc280-prior-bound-{newer_status.value}")
    prior_output = _persist_generated_review_state(
        prior,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("prior"),
        asset_id="asset-doc280-prior",
    )
    assert prior_output is not None

    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key=f"doc280-newer-{newer_status.value}"),
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None and newer_record.planning_result is not None
    newer_record.generation_result = newer_record.planning_result.model_copy(deep=True)
    newer_record.status = newer_status
    metadata = dict(newer_record.generation_result.metadata or {})
    metadata["post_generation_review_package"] = _review_package(
        state="review_withheld_manual_confirmation",
        output_id=prior_output.output_id,
        asset_id=prior_output.asset_id,
    )
    newer_record.generation_result.metadata = metadata
    handlers.service.job_store.save(newer_record)

    public_job = handlers.get_job(newer_record.job_id)
    public_project = handlers.get_project(project["project_id"])
    operation = public_project["metadata"].get("current_operation")

    assert "review_disposition" not in public_job["metadata"]
    assert operation is None or operation.get("state") != "review_withheld_manual_confirmation"
    assert operation is None or operation.get("next_actions") != [{"id": "review_generation_history"}]


def test_doc280_doc276_face_withheld_has_one_compatible_review_action_and_exact_newest_binding(tmp_path) -> None:
    """Doc280 must not duplicate Doc276's shared review-withheld operation."""

    handlers, project, prior = _ecommerce_record(tmp_path, key="doc280-doc276-prior")
    output = _persist_generated_review_state(
        prior,
        handlers,
        state="review_withheld_manual_confirmation",
        output_id=_doc280_output_id("doc276-face"),
        asset_id="asset-doc280-face",
    )
    assert output is not None
    metadata = dict(prior.generation_result.metadata or {})
    metadata["post_generation_review_package"] = {
        **_review_package(
            state="review_withheld_manual_confirmation",
            output_id=output.output_id,
            asset_id=output.asset_id,
        ),
        "doc276_face_integrity_required_output_ids": [output.output_id],
        "inspections": [
            {
                "output_id": output.output_id,
                "asset_id": output.asset_id,
                "mode": "hybrid",
                "status": "manual_review",
                "verification_state": "verified",
                "evidence": {
                    "provider_pixel_result_certified": True,
                    "face_integrity_attestation": {"status": "missing"},
                },
            }
        ],
    }
    prior.generation_result.metadata = metadata
    handlers.service.job_store.save(prior)

    prior_job = handlers.get_job(prior.job_id)
    prior_project = handlers.get_project(project["project_id"])

    assert prior_job["metadata"]["review_disposition"] == _expected_disposition(
        "review_withheld_manual_confirmation"
    )
    assert prior_project["metadata"]["current_operation"] == {
        "state": "review_withheld_face_integrity",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_history"}],
    }

    newer = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[prior.request.uploaded_asset_ids[0]], key="doc280-doc276-newer"),
    )
    newer_record = handlers.service.get_job_record(newer["job_id"])
    assert newer_record is not None
    newer_record.status = ProductJobStatusValue.BLOCKED
    handlers.service.job_store.save(newer_record)

    current_project = handlers.get_project(project["project_id"])
    assert current_project["metadata"]["current_operation"]["state"] != "review_withheld_face_integrity"
    assert current_project["metadata"]["current_operation"]["next_actions"] != [
        {"id": "review_generation_history"}
    ]


def _browser_project() -> dict[str, Any]:
    return {
        "project_id": "doc263-project",
        "primary_template_id": "ecommerce_template",
        "user_goal": "Create a product image.",
        "short_summary": "Create a product image.",
        "job_ids": ["doc280-old-review"],
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": [{"asset_ref_id": "product-original", "label": "Product original"}]},
                    "locked_person_identity": {"items": []},
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [{"output_id": "review-output", "review_only": True}],
                        "failed_attempts": [],
                    },
                },
            },
            "current_operation": {
                "state": "review_withheld_manual_confirmation",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            },
        },
    }


@pytest.mark.parametrize(
    (
        "html_path",
        "script_path",
        "state_name",
        "start_expression",
        "start_session_expression",
        "owns_expression",
        "old_recovery_expression",
        "old_refresh_expression",
        "old_output_expression",
    ),
    [
        (
            DESKTOP_HTML,
            DESKTOP_JS,
            "v3State",
            "createV3Job()",
            "v3StartEcommerceGenerationSession('doc263-project')",
            "v3EcommerceGenerationSessionOwns",
            """(receipt) => recoverV3GeneratedJob(
                'doc263-project',
                'doc280-old-review',
                new Error('doc280-old-recovery'),
                { shouldContinue: () => v3EcommerceGenerationSessionOwns(receipt) },
            ).catch(() => null)""",
            """(receipt) => refreshV3CurrentProject({
                silent: true,
                shouldContinue: () => v3EcommerceGenerationSessionOwns(receipt),
                sessionReceipt: receipt,
            }).catch(() => null)""",
            """(receipt) => loadV3ProjectOutputs({
                silent: true,
                force: true,
                projectId: 'doc263-project',
                shouldContinue: () => v3EcommerceGenerationSessionOwns(receipt),
                sessionReceipt: receipt,
            }).catch(() => null)""",
        ),
        (
            MOBILE_HTML,
            MOBILE_JS,
            "mobileV3State",
            "generateMobileV3Job()",
            "mobileV3StartEcommerceGenerationSession('doc263-project')",
            "mobileV3EcommerceGenerationSessionOwns",
            """(receipt) => recoverMobileV3GeneratedJob(
                'doc263-project',
                'doc280-old-review',
                { recoveryReceipt: receipt },
            ).catch(() => null)""",
            """(receipt) => refreshMobileV3ProjectDetail(
                'doc263-project',
                { shouldContinue: () => mobileV3EcommerceGenerationSessionOwns(receipt) },
            ).catch(() => null)""",
            "",
        ),
    ],
)
def test_doc280_new_ecommerce_generation_session_discards_late_prior_recovery_and_renders_current_response(
    html_path,
    script_path,
    state_name: str,
    start_expression: str,
    start_session_expression: str,
    owns_expression: str,
    old_recovery_expression: str,
    old_refresh_expression: str,
    old_output_expression: str,
) -> None:
    """Both real submit paths must reject a delayed prior recovery response."""

    project = _browser_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=html_path, script_path=script_path)
            page.evaluate(
                """
                ({ project, stateName }) => {
                  window.__doc263ServerProject = project;
                  window.__doc280StateName = stateName;
                  if (stateName === "v3State") {
                    v3State.currentProject = project;
                    v3State.currentJob = { job_id: "doc280-old-review", status: "blocked", warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """] };
                    v3State.selectedScenario = "ecommerce";
                    v3State.templateCatalogStatus = "ready";
                    v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                    v3State.loading = true;
                    v3State.progressStageKey = "failed";
                    v3State.progressDetail = "old review terminal";
                    v3State.progressTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldProgressTimer = v3State.progressTimer;
                    v3State.recoverPollTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldRecoverTimer = v3State.recoverPollTimer;
                    document.querySelector("#v3CreateJobBtn").addEventListener("click", createV3Job);
                    renderV3ProjectDetail();
                  } else {
                    ensureMobileLayers();
                    setupMobileV3Adapter();
                    mobileV3State.currentProject = project;
                    mobileV3State.projects = [project];
                    mobileV3State.currentJob = { job_id: "doc280-old-review", status: "blocked", warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """] };
                    mobileV3State.selectedTemplate = "ecommerce_template";
                    mobileV3State.loading = true;
                    mobileV3State.progressStageKey = "failed";
                    mobileV3State.progressDetail = "old review terminal";
                    mobileV3State.progressTimer = window.setTimeout(() => {}, 10000);
                    window.__doc280OldProgressTimer = mobileV3State.progressTimer;
                    document.querySelector("#mobileV3GenerateBtn").addEventListener("click", generateMobileV3Job);
                    renderMobileV3ProjectCurrentOperation(project);
                  }
                }
                """,
                {"project": project, "stateName": state_name},
            )

            page.evaluate(
                """
                () => {
                  window.__doc280OldRecoveryResolvers = [];
                  window.__doc280CurrentPostResolvers = [];
                  window.__doc280OldProjectRefreshResolvers = [];
                  window.__doc280OldProjectOutputsResolvers = [];
                  window.__doc280OldRecoveryRequests = 0;
                  window.__doc280CurrentPosts = 0;
                  window.__doc280OldProjectRefreshRequests = 0;
                  window.__doc280OldProjectOutputsRequests = 0;
                  window.__doc280CurrentProjectOutputsRequests = 0;
                  window.__doc280HoldOldProjectRefresh = true;
                  window.__doc280HoldOldProjectOutputs = window.__doc280StateName === "v3State";
                  window.fetch = (input, init = {}) => {
                    const url = String(input);
                    const method = String(init.method || "GET").toUpperCase();
                    window.__doc263Requests.push({ url, method });
                    if (method === "POST" && /\\/projects\\/doc263-project\\/jobs$/.test(url)) {
                      window.__doc280CurrentPosts += 1;
                      return new Promise((resolve) => window.__doc280CurrentPostResolvers.push(resolve));
                    }
                    if (/\\/jobs\\/doc280-old-review$/.test(url)) {
                      window.__doc280OldRecoveryRequests += 1;
                      return new Promise((resolve) => window.__doc280OldRecoveryResolvers.push(resolve));
                    }
                    if (/\\/jobs\\/doc280-current-job$/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({
                        job_id: "doc280-current-job",
                        status: "planned",
                        metadata: { project_outputs: [] },
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/projects\\/doc263-project$/.test(url)) {
                      if (window.__doc280HoldOldProjectRefresh) {
                        window.__doc280OldProjectRefreshRequests += 1;
                        return new Promise((resolve) => window.__doc280OldProjectRefreshResolvers.push(resolve));
                      }
                      return Promise.resolve(new Response(JSON.stringify({
                        project: window.__doc263ServerProject,
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/timeline/.test(url)) {
                      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    if (/\\/project-outputs/.test(url)) {
                      if (window.__doc280HoldOldProjectOutputs) {
                        window.__doc280OldProjectOutputsRequests += 1;
                        return new Promise((resolve) => window.__doc280OldProjectOutputsResolvers.push(resolve));
                      }
                      window.__doc280CurrentProjectOutputsRequests += 1;
                      return Promise.resolve(new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } }));
                  };
                }
                """
            )

            assert page.evaluate(f"typeof {owns_expression} === 'function'") is True
            old_receipt = page.evaluate(start_session_expression)
            page.evaluate(
                f"""
                (receipt) => {{
                  void ({old_recovery_expression})(receipt);
                  return true;
                }}
                """,
                old_receipt,
            )
            page.wait_for_function("window.__doc280OldRecoveryRequests === 1", timeout=5000)
            page.evaluate(
                f"""
                (receipt) => {{
                  void ({old_refresh_expression})(receipt);
                  return true;
                }}
                """,
                old_receipt,
            )
            page.wait_for_function("window.__doc280OldProjectRefreshRequests === 1", timeout=5000)
            if old_output_expression:
                page.evaluate(
                    f"""
                    (receipt) => {{
                      void ({old_output_expression})(receipt);
                      return true;
                    }}
                    """,
                    old_receipt,
                )
                page.wait_for_function("window.__doc280OldProjectOutputsRequests === 1", timeout=5000)

            page.evaluate(
                """
                () => {
                  window.__doc263ServerProject = {
                    ...window.__doc263ServerProject,
                    job_ids: ["doc280-current-job"],
                    metadata: {
                      ...window.__doc263ServerProject.metadata,
                      current_operation: { state: "planning", terminal: false, pending: true, next_actions: [] },
                    },
                  };
                  window.__doc280HoldOldProjectRefresh = false;
                  window.__doc280HoldOldProjectOutputs = false;
                }
                """
            )
            page.evaluate(
                f"""
                () => {{
                  void {start_expression};
                  return true;
                }}
                """
            )
            page.wait_for_function("window.__doc280CurrentPosts === 1", timeout=5000)

            # The new session clears the old terminal presentation before its
            # own POST has settled.
            assert page.evaluate(f"{state_name}.currentJob === null") is True
            assert page.evaluate(f"{state_name}.progressTimer !== window.__doc280OldProgressTimer") is True
            if state_name == "v3State":
                assert page.evaluate("v3State.recoverPollTimer !== window.__doc280OldRecoverTimer") is True
            assert page.evaluate(f"{state_name}.progressStageKey !== 'failed'") is True
            assert page.evaluate(f"!String({state_name}.progressDetail || '').includes('old review terminal')") is True
            action_selector = (
                "[data-v3-project-action='review_generation_history']"
                if state_name == "v3State"
                else "[data-mobile-v3-project-action='review_generation_history']"
            )
            assert page.locator(action_selector).count() == 0
            assert RAW_REJECT_WARNING not in page.locator("body").inner_text()

            page.evaluate(
                """
                () => {
                  const resolve = window.__doc280CurrentPostResolvers.shift();
                  resolve(new Response(JSON.stringify({
                    job_id: "doc280-current-job",
                    status: "planned",
                    metadata: { project_outputs: [] },
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                """
            )
            page.wait_for_function(
                f"{state_name}.currentJob && {state_name}.currentJob.job_id === 'doc280-current-job'",
                timeout=5000,
            )
            if old_output_expression:
                page.wait_for_function("window.__doc280CurrentProjectOutputsRequests >= 1", timeout=5000)

            page.evaluate(
                """
                () => {
                  const resolve = window.__doc280OldRecoveryResolvers.shift();
                  resolve(new Response(JSON.stringify({
                    job_id: "doc280-old-review",
                    status: "blocked",
                    warnings: [""" + json.dumps(RAW_REJECT_WARNING) + """],
                    metadata: {
                      current_operation: {
                        state: "review_withheld_manual_confirmation",
                        terminal: true,
                        pending: false,
                        next_actions: [{ id: "review_generation_history" }],
                      },
                    },
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                """
            )
            page.evaluate(
                """
                () => {
                  const resolve = window.__doc280OldProjectRefreshResolvers.shift();
                  resolve(new Response(JSON.stringify({
                    project: {
                      ...window.__doc263ServerProject,
                      job_ids: ["doc280-old-review"],
                      metadata: {
                        ...window.__doc263ServerProject.metadata,
                        current_operation: {
                          state: "review_withheld_manual_confirmation",
                          terminal: true,
                          pending: false,
                          next_actions: [{ id: "review_generation_history" }],
                        },
                      },
                    },
                  }), { status: 200, headers: { "Content-Type": "application/json" } }));
                }
                """
            )
            if old_output_expression:
                page.evaluate(
                    """
                    () => {
                      const resolve = window.__doc280OldProjectOutputsResolvers.shift();
                      resolve(new Response(JSON.stringify({
                        items: [{
                          output_id: "doc280-old-output",
                          project_id: "doc263-project",
                          review_only: true,
                          review_reason: "old review",
                        }],
                        review_items: [{
                          output_id: "doc280-old-output",
                          project_id: "doc263-project",
                          review_only: true,
                        }],
                      }), { status: 200, headers: { "Content-Type": "application/json" } }));
                    }
                    """
                )
            page.wait_for_timeout(50)

            assert page.evaluate(f"{state_name}.currentJob?.job_id") == "doc280-current-job"
            assert page.evaluate(
                f"{state_name}.currentProject?.metadata?.current_operation?.state !== 'review_withheld_manual_confirmation'"
            ) is True
            assert page.evaluate(f"{state_name}.progressStageKey !== 'failed'") is True
            assert page.evaluate(f"!String({state_name}.progressDetail || '').includes('old review terminal')") is True
            assert page.locator(action_selector).count() == 0
            assert RAW_REJECT_WARNING not in page.locator("body").inner_text()
            if old_output_expression:
                assert page.evaluate(
                    "!((v3State.projectOutputs || []).some((item) => item.output_id === 'doc280-old-output'))"
                ) is True
                assert page.evaluate(
                    "!((v3State.projectReviewOutputs || []).some((item) => item.output_id === 'doc280-old-output'))"
                ) is True
        finally:
            browser.close()
