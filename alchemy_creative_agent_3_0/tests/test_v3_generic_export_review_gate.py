from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3UploadedAssetStore
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _general_job_with_review(tmp_path, *, statuses: list[str]):
    service = ecommerce_test_service(
        asset_store=V3UploadedAssetStore(storage_root=tmp_path / "uploads"),
    )
    created = service.create_job(
        {
            "user_input": "Create a set of abstract landscape images",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {"requested_image_count": len(statuses)},
            },
            "metadata": {"requested_image_count": len(statuses)},
        }
    )
    record = service.get_job_record(created.job_id)
    assert record is not None and record.planning_result is not None
    result = record.planning_result.model_copy(deep=True)
    assets = []
    inspections = []
    for index, (asset, status) in enumerate(zip(result.asset_pack.assets, statuses), start=1):
        output_id = f"generic-output-{index}"
        candidate_id = f"generic-candidate-{index}"
        metadata = dict(asset.metadata or {})
        metadata.update(
            {
                "selected_candidate_id": candidate_id,
                "candidate_metadata": {
                    **dict(metadata.get("candidate_metadata") or {}),
                    "output_id": output_id,
                    "download_url": f"/media/{output_id}/full",
                    "thumbnail_url": f"/media/{output_id}/thumb",
                },
            }
        )
        assets.append(asset.model_copy(update={"metadata": metadata}))
        inspections.append(
            {
                "output_id": output_id,
                "asset_id": asset.asset_id,
                "mode": "vision_model",
                "status": status,
                "verification_state": "verified",
                "evidence": {"provider_pixel_result_certified": True},
            }
        )
    result.asset_pack = result.asset_pack.model_copy(update={"assets": assets})
    result.metadata["post_generation_review_package"] = {
        "review_evidence_receipt_status": "complete",
        "resolutions": [{"output_id": item["output_id"], "status": "ready"} for item in inspections],
        "inspections": inspections,
    }
    record.generation_result = result
    record.status = ProductJobStatusValue.GENERATED
    service.job_store.save(record)
    return service, record


def test_generic_export_manifest_excludes_failed_and_held_images(tmp_path) -> None:
    service, record = _general_job_with_review(
        tmp_path,
        statuses=["pass", "fail_final"],
    )

    response = service.export_job(record.job_id)
    generated = response.manifest["generated_assets"]

    assert {item["output_id"] for item in generated} == {"generic-output-1"}
    assert {item["review_status"] for item in generated} == {"pass"}
    assert response.manifest["metadata"]["export_scope"] == "formal_delivery_only"
    downloaded = service.export_job_download(record.job_id)
    assert "/media/generic-output-2/" not in downloaded.content


def test_generic_export_manifest_is_empty_when_no_image_is_eligible(tmp_path) -> None:
    service, record = _general_job_with_review(
        tmp_path,
        statuses=["fail_final", "manual_review"],
    )

    response = service.export_job(record.job_id)

    assert response.manifest["generated_assets"] == []
    downloaded = service.export_job_download(record.job_id)
    assert "/media/generic-output-1/" not in downloaded.content
    assert "/media/generic-output-2/" not in downloaded.content


def test_generic_export_requires_exact_reviewed_output_asset_binding(tmp_path) -> None:
    service, record = _general_job_with_review(
        tmp_path,
        statuses=["pass", "pass"],
    )
    result = record.generation_result.model_copy(deep=True)
    assets = list(result.asset_pack.assets)
    second_metadata = dict(assets[1].metadata or {})
    second_candidate_metadata = dict(second_metadata.get("candidate_metadata") or {})
    second_candidate_metadata["output_id"] = "generic-output-1"
    second_metadata["candidate_metadata"] = second_candidate_metadata
    assets[1] = assets[1].model_copy(update={"metadata": second_metadata})
    result.asset_pack = result.asset_pack.model_copy(update={"assets": assets})
    record.generation_result = result
    service.job_store.save(record)

    response = service.export_job(record.job_id)
    generated = response.manifest["generated_assets"]
    downloaded = service.export_job_download(record.job_id)

    assert [(item["output_id"], item["asset_id"]) for item in generated] == [
        ("generic-output-1", str(assets[0].asset_id)),
    ]
    assert json.loads(downloaded.content) == response.manifest


def test_generic_export_selection_does_not_cross_bind_shared_asset_ids(tmp_path) -> None:
    service, record = _general_job_with_review(
        tmp_path,
        statuses=["pass", "pass"],
    )
    result = record.generation_result.model_copy(deep=True)
    assets = list(result.asset_pack.assets)
    shared_asset_id = "shared-logical-asset"
    for index, asset in enumerate(assets):
        inspections = result.metadata["post_generation_review_package"]["inspections"]
        inspections[index]["asset_id"] = shared_asset_id
        assets[index] = asset.model_copy(update={"asset_id": shared_asset_id})
    result.asset_pack = result.asset_pack.model_copy(update={"assets": assets})
    record.generation_result = result
    service.job_store.save(record)
    selection = service.select_result(
        record.job_id,
        {"selected_candidate_ids": ["generic-candidate-2"]},
    )
    assert selection.selected_result.metadata["selection_status"] == "selected"
    assert selection.selected_result.selected_candidate_ids == ["generic-candidate-2"]
    assert selection.selected_result.selected_asset_ids == [shared_asset_id]

    response = service.export_job(record.job_id)
    downloaded = service.export_job_download(record.job_id)

    assert {item["output_id"] for item in response.manifest["generated_assets"]} == {
        "generic-output-2",
    }
    assert json.loads(downloaded.content) == response.manifest
