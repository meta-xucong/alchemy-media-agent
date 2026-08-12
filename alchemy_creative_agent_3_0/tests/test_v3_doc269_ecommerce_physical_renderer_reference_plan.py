"""Phase 0 red contracts for the final E-Commerce renderer reference plan.

The fixture creates a real Project Mode/Product API Professional E-Commerce
job, then captures its local GenerationRequest. It never selects an app
provider, makes a network request, contacts MCP/ImageGen, or mutates a live
project.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRouter,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import ReferenceInputAdmissionError
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _png_base64,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _CapturingMockGenerationProvider,
    _add_product_references,
    _bind_locked_person_identity,
    _job_payload,
)
from app.providers.openai_image import OpenAIGPTImageProvider
from app.services.asset_planning import reference_image_paths


def _ecommerce_fixture(tmp_path):
    """Construct the observed Doc263/267 input shape through public handlers."""

    handlers, catalog = _handlers(tmp_path)
    capture = _CapturingMockGenerationProvider()
    handlers.service.scenario_runtime.generation_router = GenerationRouter(provider=capture)
    project = _project(handlers)
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"doc269-product-{index}.png",
            color=(80 + index * 20, 130, 165),
        )
        for index in range(4)
    ]
    _add_product_references(handlers, project["project_id"], product_ids)
    identity_output_ids = _bind_locked_person_identity(
        handlers,
        catalog,
        project_id=project["project_id"],
    )
    return handlers, capture, project, product_ids, identity_output_ids


def _capture_ecommerce_request(handlers, capture, project, product_ids, identity_output_ids, *, key: str):
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc269-final-plan")
    payload["metadata"]["requested_image_count"] = 1
    payload["metadata"]["idempotency_key"] = key
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    generated = handlers.post_project_job_generate(project["project_id"], record.job_id)
    assert generated["status"] == "generated"
    assert len(capture.requests) == 1
    projection = record.request.metadata["professional_ecommerce_physical_product_projections"]["1"]
    return capture.requests[0], product_ids, identity_output_ids, projection


def _captured_default_ecommerce_request(tmp_path):
    handlers, capture, project, product_ids, identity_output_ids = _ecommerce_fixture(tmp_path)
    request, _product_ids, _face_output_ids, projection = _capture_ecommerce_request(
        handlers,
        capture,
        project,
        product_ids,
        identity_output_ids,
        key="doc269-final-plan",
    )
    return request, product_ids, identity_output_ids, projection


def _final_materialization(request):
    # This is the production materialization boundary, but it does not select
    # or invoke an app provider.
    return ProductionImageGenerationProvider().materialize_final_prompt(request)


def _source_ids(reference_assets: list[dict]) -> list[str]:
    return [str(item.get("source_asset_id") or item.get("asset_id") or "") for item in reference_assets]


def _typed_plan_from_current_admission(request) -> dict:
    """Describe the intended immutable plan from the current trusted sources."""

    admitted = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001
    references = []
    for item in admitted:
        path = Path(str(item["file_path"])).resolve()
        references.append(
            {
                "reference_id": str(item.get("asset_id") or item.get("output_id") or ""),
                "source_id": str(item.get("output_id") or item.get("asset_id") or ""),
                "role": item["role"],
                "channel": "product_truth" if item["role"] == "product_reference" else "people_identity",
                "file_path": str(path),
                "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "schema_version": "doc269_physical_renderer_reference_plan_v1",
        "job_id": request.metadata["job_id"],
        "output_index": 1,
        "references": references,
        "reference_image_asset_ids": [item["reference_id"] for item in references],
        "reference_image_count": len(references),
        "maximum_reference_images": 5,
    }


def test_doc269_final_plan_and_web_adapter_are_exactly_one_product_plus_three_locked_faces(tmp_path) -> None:
    request, product_ids, face_output_ids, projection = _captured_default_ecommerce_request(tmp_path)

    materialization = _final_materialization(request)
    provider_plan = materialization.asset_plan["provider_input_plan"]
    physical_assets = ProductionImageGenerationProvider()._materialized_provider_reference_assets(  # noqa: SLF001
        materialization.asset_plan
    )
    adapter_paths = reference_image_paths(materialization.asset_plan, max_images=5)

    expected_source_ids = [projection["selected_product_asset_ids"][0], *face_output_ids]
    assert provider_plan["reference_image_asset_ids"] == expected_source_ids
    assert provider_plan["reference_image_count"] == 4
    assert [item["asset_id"] for item in physical_assets] == expected_source_ids
    assert _source_ids(physical_assets) == expected_source_ids
    assert [item["role"] for item in physical_assets] == [
        "product_reference",
        "face_reference",
        "face_reference",
        "face_reference",
    ]
    assert len(physical_assets) == 4
    expected_adapter_inputs = list(
        zip(
            expected_source_ids,
            [Path(path).resolve() for path in adapter_paths],
            strict=True,
        )
    )
    assert [
        (item["asset_id"], Path(item["file_path"]).resolve())
        for item in physical_assets
    ] == expected_adapter_inputs
    assert [item["asset_id"] for item in materialization.reference_assets] == expected_source_ids
    assert set(product_ids) - {projection["selected_product_asset_ids"][0]}
    assert not {
        item.get("source_asset_id") for item in physical_assets
    }.intersection(set(product_ids) - {projection["selected_product_asset_ids"][0]})
    assert all(item.get("source_type") != "generated_selected" for item in physical_assets)


def test_doc269_default_does_not_infer_generated_history_as_continuation(tmp_path) -> None:
    request, _product_ids, face_output_ids, projection = _captured_default_ecommerce_request(tmp_path)
    history = request.metadata["professional_anchor_reference_assets"][0]
    request.metadata["generated_and_review_history"] = [deepcopy(history)]

    materialization = _final_materialization(request)
    physical_assets = ProductionImageGenerationProvider()._materialized_provider_reference_assets(  # noqa: SLF001
        materialization.asset_plan
    )

    assert _source_ids(physical_assets) == [projection["selected_product_asset_ids"][0], *face_output_ids]
    assert all(item.get("source_type") != "generated_selected" for item in physical_assets)


def test_doc269_explicit_selected_continuation_is_the_only_continuation_admission_path(tmp_path) -> None:
    handlers, capture, project, product_ids, face_output_ids = _ecommerce_fixture(tmp_path)
    source = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=product_ids, key="doc269-continuation-source"),
    )
    continuation = handlers.service.output_store.save_base64_output(
        job_id=source["job_id"],
        candidate_id="doc269-continuation-candidate",
        asset_id="doc269-continuation-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((125, 150, 175)),
    )
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": continuation.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": source["job_id"],
            "created_from_output_id": continuation.output_id,
            "use_policy": "style",
        },
    )
    request, _product_ids, _face_output_ids, projection = _capture_ecommerce_request(
        handlers,
        capture,
        project,
        product_ids,
        face_output_ids,
        key="doc269-explicit-continuation",
    )

    materialization = _final_materialization(request)
    physical_assets = ProductionImageGenerationProvider()._materialized_provider_reference_assets(  # noqa: SLF001
        materialization.asset_plan
    )

    assert _source_ids(physical_assets) == [
        projection["selected_product_asset_ids"][0],
        *face_output_ids,
        continuation.output_id,
    ]
    assert materialization.asset_plan["provider_input_plan"]["reference_image_count"] == 5
    assert [item.get("source_type") for item in physical_assets].count("generated_selected") == 1


@pytest.mark.parametrize(
    "fault",
    ["duplicate", "projection_drift", "digest_drift", "missing_file", "over_cap"],
)
def test_doc269_invalid_final_plan_stops_before_adapter_or_provider_dispatch(tmp_path, monkeypatch, fault: str) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    typed_plan = _typed_plan_from_current_admission(request)
    if fault == "duplicate":
        typed_plan["references"].append(deepcopy(typed_plan["references"][0]))
    elif fault == "projection_drift":
        typed_plan["references"][0]["source_id"] = "forged-product-source"
    elif fault == "digest_drift":
        typed_plan["references"][0]["content_sha256"] = "0" * 64
    elif fault == "missing_file":
        typed_plan["references"][0]["file_path"] = str(tmp_path / "missing-doc269-input.png")
    else:
        typed_plan["references"].extend(deepcopy(typed_plan["references"]))
    typed_plan["reference_image_asset_ids"] = [
        item["reference_id"] for item in typed_plan["references"]
    ]
    typed_plan["reference_image_count"] = len(typed_plan["references"])
    request.metadata["physical_renderer_reference_plan"] = typed_plan

    web_adapter_requests: list[object] = []

    async def unexpected_web_adapter_generate(_self, app_request):  # noqa: ANN001
        web_adapter_requests.append(app_request)
        raise AssertionError("invalid E-Commerce physical plan reached web adapter materialization")

    monkeypatch.setattr(OpenAIGPTImageProvider, "generate", unexpected_web_adapter_generate)

    class _NoDispatchProductionProvider(ProductionImageGenerationProvider):
        def _app_provider(self, provider_name: str):  # noqa: ANN201
            assert provider_name == "openai_gpt_image"
            return OpenAIGPTImageProvider(model="gpt-image-2")

    provider = _NoDispatchProductionProvider()
    with pytest.raises(ReferenceInputAdmissionError) as failure:
        provider.generate(request)

    assert web_adapter_requests == []
    assert provider._last_provider_failure_retry_summary["outer_request_count"] == 0  # noqa: SLF001
    public_failure = str(failure.value)
    assert str(typed_plan["references"][0]["file_path"]) not in public_failure
    assert str(typed_plan["references"][0]["content_sha256"]) not in public_failure
