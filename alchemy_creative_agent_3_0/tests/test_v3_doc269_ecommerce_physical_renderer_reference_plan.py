"""Phase 0 red contracts for the final E-Commerce renderer reference plan.

The fixture creates a real Project Mode/Product API Professional E-Commerce
job, then captures its local GenerationRequest. It never selects an app
provider, makes a network request, contacts MCP/ImageGen, or mutates a live
project.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRouter,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import ReferenceInputAdmissionError
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.physical_renderer_reference_plan import (
    PhysicalRendererReferenceEntry,
    PhysicalRendererReferencePlan,
)
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
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from app.providers.openai_image import OpenAIGPTImageProvider
from app.services.asset_planning import reference_image_paths


def _ecommerce_fixture(tmp_path):
    """Construct the observed Doc263/267 input shape through public handlers."""

    handlers, catalog = _handlers(tmp_path)
    handlers.service.scenario_runtime.llm_brain_adapter = V3LLMBrainAdapter(
        provider=EcommerceRemoteBrainTestProvider(visible_ecommerce_person=True)
    )
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


def _apparel_on_model_payload(*, product_ids: list[str], key: str) -> dict:
    payload = _job_payload(uploaded_asset_ids=product_ids, key=key)
    payload["user_input"] = "Generate an apparel-on-model listing image with the supplied product."
    payload["commerce_profile_patch"] = {
        "product_category": "apparel",
        "apparel_construction": {
            "silhouette": "short-sleeve garment",
            "material": "soft knit fabric",
        },
    }
    return payload


def _capture_ecommerce_request(handlers, capture, project, product_ids, identity_output_ids, *, key: str):
    payload = _apparel_on_model_payload(product_ids=product_ids, key="doc269-final-plan")
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


def _reject_unexpected_ecommerce_adapter(monkeypatch):
    adapter_requests: list[object] = []

    async def unexpected_adapter(_self, app_request):  # noqa: ANN001
        adapter_requests.append(app_request)
        raise AssertionError("invalid locked People evidence reached web adapter")

    return adapter_requests, unexpected_adapter


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


@pytest.mark.parametrize("fault", ["missing", "fourth"])
def test_doc269_locked_people_face_count_closes_after_brain_before_adapter(
    tmp_path,
    monkeypatch,
    fault: str,
) -> None:
    handlers, _capture, project, product_ids, _face_output_ids = _ecommerce_fixture(tmp_path)
    original = handlers.service._library_visual_asset_reference_assets  # noqa: SLF001
    adapter_requests, unexpected_adapter = _reject_unexpected_ecommerce_adapter(monkeypatch)

    def corrupted_references(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        references = original(*args, **kwargs)
        if fault == "missing":
            return references[:-1]
        extra = deepcopy(references[-1])
        extra["output_id"] = "doc269-forged-fourth-face"
        extra["asset_id"] = "doc269-forged-fourth-face"
        return [*references, extra]

    monkeypatch.setattr(
        handlers.service,
        "_library_visual_asset_reference_assets",
        corrupted_references,
    )
    monkeypatch.setattr(OpenAIGPTImageProvider, "generate", unexpected_adapter)
    before_job_ids = list(handlers.get_project(project["project_id"])["project"]["job_ids"])

    with pytest.raises(
        ValueError,
        match="ecommerce_locked_identity_reference_(count_invalid|invalid)",
    ) as failure:
        handlers.post_project_job(
            project["project_id"],
            _apparel_on_model_payload(
                product_ids=product_ids,
                key=f"doc269-{fault}-locked-face",
            ),
        )

    assert "doc269-forged-fourth-face" not in str(failure.value)
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_job_ids
    brain_provider = handlers.service.scenario_runtime.llm_brain_adapter.provider
    assert isinstance(brain_provider, EcommerceRemoteBrainTestProvider)
    assert brain_provider.requests
    assert adapter_requests == []


@pytest.mark.parametrize("fault", ["missing", "fourth"])
def test_doc269_persisted_locked_people_face_count_closes_before_adapter(
    tmp_path,
    monkeypatch,
    fault: str,
) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(
        tmp_path
    )
    for metadata in (request.metadata, request.generation_plan.metadata):
        references = metadata["professional_anchor_reference_assets"]
        if fault == "missing":
            metadata["professional_anchor_reference_assets"] = references[:-1]
        else:
            extra = deepcopy(references[-1])
            extra["output_id"] = "doc269-forged-persisted-fourth-face"
            extra["asset_id"] = "doc269-forged-persisted-fourth-face"
            metadata["professional_anchor_reference_assets"] = [*references, extra]
    adapter_requests: list[object] = []

    async def unexpected_adapter(_self, app_request):  # noqa: ANN001
        adapter_requests.append(app_request)
        raise AssertionError("invalid persisted locked People evidence reached web adapter")

    monkeypatch.setattr(OpenAIGPTImageProvider, "generate", unexpected_adapter)
    provider = ProductionImageGenerationProvider()
    with pytest.raises(ReferenceInputAdmissionError) as failure:
        provider.generate(request)

    assert "doc269-forged-persisted-fourth-face" not in str(failure.value)
    assert adapter_requests == []
    assert provider._last_provider_failure_retry_summary["outer_request_count"] == 0  # noqa: SLF001


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


def test_doc269_product_only_plan_excludes_active_people_and_history(tmp_path) -> None:
    handlers, capture, project, product_ids, face_output_ids = _ecommerce_fixture(tmp_path)
    handlers.service.scenario_runtime.llm_brain_adapter = V3LLMBrainAdapter(
        provider=EcommerceRemoteBrainTestProvider(visible_ecommerce_person=False)
    )
    payload = _apparel_on_model_payload(product_ids=product_ids, key="doc269-product-only")
    payload["user_input"] = (
        "Product-only flat lay for the supplied garment. No person wearing it, "
        "no model, no child, and no face."
    )
    payload["metadata"]["requested_image_count"] = 1
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert "ecommerce_locked_identity_authority" not in record.request.metadata
    assert "ecommerce_locked_identity_reference_assets" not in record.request.metadata
    record.request.metadata["generated_and_review_history"] = [
        {
            "output_id": face_output_ids[0],
            "source_type": "generated_selected",
        }
    ]
    generated = handlers.post_project_job_generate(project["project_id"], record.job_id)
    assert generated["status"] == "generated"

    request = capture.requests[-1]
    projection = request.metadata["professional_ecommerce_physical_product_projections"]["1"]
    materialization = _final_materialization(request)
    physical_assets = ProductionImageGenerationProvider()._materialized_provider_reference_assets(  # noqa: SLF001
        materialization.asset_plan
    )

    assert request.metadata["physical_renderer_reference_plans"]["1"]["reference_image_asset_ids"] == [
        projection["selected_product_asset_ids"][0]
    ]
    assert _source_ids(physical_assets) == [projection["selected_product_asset_ids"][0]]
    assert [item["source_type"] for item in physical_assets] == ["uploaded"]
    assert set(face_output_ids).isdisjoint(_source_ids(physical_assets))


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
    entry = request.metadata["physical_renderer_reference_plans"]["1"]["references"][-1]
    admission = request.metadata["doc269_selected_continuation_admissions"][0]
    assert entry["selection_binding"] == {
        key: admission[key]
        for key in (
            "selection_authority",
            "project_id",
            "reference_id",
            "output_id",
            "source_job_id",
            "project_job_ids",
            "content_sha256",
        )
    }


def test_doc269_planning_snapshot_generated_selected_cannot_enter_renderer_plan(tmp_path) -> None:
    handlers, capture, project, product_ids, face_output_ids = _ecommerce_fixture(tmp_path)
    source = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=product_ids, key="doc269-snapshot-source"),
    )
    continuation = handlers.service.output_store.save_base64_output(
        job_id=source["job_id"],
        candidate_id="doc269-snapshot-candidate",
        asset_id="doc269-snapshot-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((90, 120, 150)),
    )
    capture.requests.clear()
    payload = _apparel_on_model_payload(product_ids=product_ids, key="doc269-planning-snapshot")
    payload["metadata"]["requested_image_count"] = 1
    payload["metadata"]["reference_assets"] = [
        {
            "output_id": continuation.output_id,
            "source_type": "generated_selected",
            "use_policy": "style",
            "role": "selected_continuation_reference",
            "file_path": continuation.file_path,
        }
    ]
    created = handlers.post_project_job(project["project_id"], payload)
    generated = handlers.post_project_job_generate(project["project_id"], created["job_id"])
    assert generated["status"] == "generated"
    request = capture.requests[-1]
    materialization = _final_materialization(request)

    assert _source_ids(
        ProductionImageGenerationProvider()._materialized_provider_reference_assets(  # noqa: SLF001
            materialization.asset_plan
        )
    ) == [
        request.metadata["professional_ecommerce_physical_product_projections"]["1"][
            "selected_product_asset_ids"
        ][0],
        *face_output_ids,
    ]
    assert request.metadata["doc269_selected_continuation_admissions"] == []


def test_doc269_cross_project_generated_output_cannot_become_selected_continuation(tmp_path) -> None:
    handlers, _capture, project, product_ids, _face_output_ids = _ecommerce_fixture(tmp_path)
    other_project = _project(handlers)
    source = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=product_ids, key="doc269-cross-project-source"),
    )
    continuation = handlers.service.output_store.save_base64_output(
        job_id=source["job_id"],
        candidate_id="doc269-cross-project-candidate",
        asset_id="doc269-cross-project-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((40, 90, 140)),
    )
    before_references = handlers.get_project(other_project["project_id"])["project"]["reference_assets"]

    with pytest.raises(ValueError, match="continuation output reference project mismatch"):
        handlers.post_project_reference(
            other_project["project_id"],
            {
                "asset_ref_id": continuation.output_id,
                "source_type": "generated_selected",
                "created_from_job_id": source["job_id"],
                "created_from_output_id": continuation.output_id,
                "use_policy": "style",
            },
        )
    assert handlers.get_project(other_project["project_id"])["project"]["reference_assets"] == before_references


def test_doc269_public_metadata_cannot_author_or_override_renderer_plan(tmp_path) -> None:
    handlers, _capture, project, product_ids, _face_output_ids = _ecommerce_fixture(tmp_path)
    before_job_ids = list(handlers.get_project(project["project_id"])["project"]["job_ids"])
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc269-forged-public-plan")
    payload["metadata"]["physical_renderer_reference_plan"] = {
        "schema_version": "doc269_physical_renderer_reference_plan_v1",
        "job_id": "forged-job",
    }
    payload["metadata"]["doc269_selected_continuation_admissions"] = [
        {"selection_authority": "doc265_project_mode", "project_id": project["project_id"]}
    ]

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        handlers.post_project_job(project["project_id"], payload)
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == before_job_ids


def test_doc269_internal_continuation_admission_drift_stops_before_adapter(tmp_path, monkeypatch) -> None:
    handlers, capture, project, product_ids, face_output_ids = _ecommerce_fixture(tmp_path)
    source = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=product_ids, key="doc269-drift-source"),
    )
    continuation = handlers.service.output_store.save_base64_output(
        job_id=source["job_id"],
        candidate_id="doc269-drift-candidate",
        asset_id="doc269-drift-asset",
        provider="fixture",
        model="fixture",
        encoded_image=_png_base64((110, 60, 30)),
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
    request, _product_ids, _face_output_ids, _projection = _capture_ecommerce_request(
        handlers,
        capture,
        project,
        product_ids,
        face_output_ids,
        key="doc269-drift-target",
    )
    request.metadata["doc269_selected_continuation_admissions"][0]["source_job_id"] = "job-forged"
    request.generation_plan.metadata["doc269_selected_continuation_admissions"][0]["source_job_id"] = "job-forged"
    adapter_requests: list[object] = []

    async def unexpected_adapter(_self, app_request):  # noqa: ANN001
        adapter_requests.append(app_request)
        raise AssertionError("drifted continuation reached adapter")

    monkeypatch.setattr(OpenAIGPTImageProvider, "generate", unexpected_adapter)
    provider = ProductionImageGenerationProvider()
    with pytest.raises(ReferenceInputAdmissionError):
        provider.generate(request)
    assert adapter_requests == []


def _rehashed_plan(raw_plan: dict) -> dict:
    candidate = deepcopy(raw_plan)
    digest_payload = {
        key: candidate[key]
        for key in (
            "schema_version",
            "job_id",
            "output_index",
            "projection_digest",
            "maximum_reference_images",
            "references",
            "reference_image_asset_ids",
            "reference_image_count",
        )
    }
    candidate["plan_digest"] = hashlib.sha256(
        json.dumps(
            digest_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return candidate


def test_doc269_freezes_distinct_plan_for_each_output_without_first_output_alias(tmp_path) -> None:
    handlers, capture, project, product_ids, face_output_ids = _ecommerce_fixture(tmp_path)
    payload = _apparel_on_model_payload(product_ids=product_ids, key="doc269-multi-output")
    payload["metadata"]["requested_image_count"] = 2
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None and record.planning_result is not None
    plans = record.request.metadata["physical_renderer_reference_plans"]
    projections = record.request.metadata["professional_ecommerce_physical_product_projections"]
    assert set(plans) == set(projections) == {"1", "2"}
    assert plans["1"] is not plans["2"]
    for output_key in ("1", "2"):
        plan = plans[output_key]
        projection = projections[output_key]
        assert plan["output_index"] == int(output_key)
        assert plan["projection_digest"] == projection["projection_digest"]
        assert plan["reference_image_asset_ids"] == [
            *projection["selected_product_asset_ids"],
            *face_output_ids,
        ]
        assert plan["reference_image_count"] <= plan["maximum_reference_images"] == 5

    generated = handlers.post_project_job_generate(project["project_id"], record.job_id)
    assert generated["status"] == "generated"
    assert len(capture.requests) == 2
    for request in capture.requests:
        materialization = _final_materialization(request)
        output_key = str(request.asset_spec.priority)
        assert materialization.asset_plan["provider_input_plan"]["reference_image_asset_ids"] == plans[
            output_key
        ]["reference_image_asset_ids"]


@pytest.mark.parametrize("scenario_id", ["general_creative", "photography"])
def test_doc269_specialized_materializer_does_not_activate_for_general_or_photography(
    tmp_path,
    scenario_id: str,
) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    ordinary = request.model_copy(deep=True)
    for key in (
        "professional_product_truth_required",
        "professional_ecommerce_product_truth_admission",
        "professional_ecommerce_physical_product_projection",
        "professional_ecommerce_physical_product_projections",
        "physical_renderer_reference_plans",
    ):
        ordinary.metadata.pop(key, None)
        ordinary.generation_plan.metadata.pop(key, None)
    ordinary.metadata["scenario_id"] = scenario_id
    ordinary.generation_plan.metadata["scenario_id"] = scenario_id

    provider = ProductionImageGenerationProvider()
    assert provider._has_doc269_ecommerce_physical_plan(ordinary) is False  # noqa: SLF001


def test_doc269_typed_plan_is_frozen_extra_forbidden_and_digest_bound(tmp_path) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    raw_plan = request.metadata["physical_renderer_reference_plans"]["1"]
    plan = PhysicalRendererReferencePlan.model_validate(raw_plan)

    with pytest.raises(Exception, match="frozen"):
        plan.references += plan.references[:1]
    with pytest.raises(Exception):
        PhysicalRendererReferencePlan.model_validate({**raw_plan, "forged": True})
    tampered = deepcopy(raw_plan)
    tampered["references"][0]["content_sha256"] = "0" * 64
    with pytest.raises(Exception, match="doc269_plan_digest_mismatch"):
        PhysicalRendererReferencePlan.model_validate(tampered)


def test_doc269_distinct_locked_people_faces_may_share_content_bytes(tmp_path) -> None:
    request, _product_ids, face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    raw_plan = deepcopy(request.metadata["physical_renderer_reference_plans"]["1"])
    face_entries = raw_plan["references"][1:]
    shared_digest = face_entries[0]["content_sha256"]
    for entry in face_entries[1:]:
        entry["content_sha256"] = shared_digest

    assert len(face_entries) == 3
    assert len({item["reference_id"] for item in face_entries}) == 3
    assert len({item["source_id"] for item in face_entries}) == 3
    assert len({item["content_sha256"] for item in face_entries}) == 1
    assert [item["reference_id"] for item in face_entries] == face_output_ids
    plan = PhysicalRendererReferencePlan.model_validate(_rehashed_plan(raw_plan))
    assert plan.reference_image_count == 4


def test_doc269_same_bytes_are_rejected_for_duplicate_product_entries(tmp_path) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    raw_plan = deepcopy(request.metadata["physical_renderer_reference_plans"]["1"])
    duplicate = deepcopy(raw_plan["references"][0])
    duplicate.update(
        {
            "reference_id": "forged-duplicate-product",
            "source_id": "forged-duplicate-product",
            "ordinal": len(raw_plan["references"]) + 1,
        }
    )
    raw_plan["references"].append(duplicate)
    raw_plan["reference_image_asset_ids"].append(duplicate["reference_id"])
    raw_plan["reference_image_count"] += 1

    with pytest.raises(ValueError, match="doc269_plan_content_duplicate_invalid"):
        PhysicalRendererReferencePlan.model_validate(_rehashed_plan(raw_plan))


def test_doc269_same_bytes_are_rejected_across_product_and_generated_channels(tmp_path) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    raw_plan = deepcopy(request.metadata["physical_renderer_reference_plans"]["1"])
    continuation = deepcopy(raw_plan["references"][0])
    continuation.update(
        {
            "reference_id": "forged-duplicate-continuation",
            "source_id": "forged-duplicate-continuation",
            "role": "selected_continuation_reference",
            "channel": "generated_selected",
            "source_type": "generated_selected",
            "ordinal": len(raw_plan["references"]) + 1,
            "selection_binding": {
                "selection_authority": "doc265_project_mode",
                "project_id": "project-forged",
                "reference_id": "reference-forged",
                "output_id": "forged-duplicate-continuation",
                "source_job_id": "job-forged",
                "project_job_ids": ["job-forged"],
                "content_sha256": continuation["content_sha256"],
            },
        }
    )
    raw_plan["references"].append(continuation)
    raw_plan["reference_image_asset_ids"].append(continuation["reference_id"])
    raw_plan["reference_image_count"] += 1

    with pytest.raises(ValueError, match="doc269_plan_content_duplicate_invalid"):
        PhysicalRendererReferencePlan.model_validate(_rehashed_plan(raw_plan))


def test_doc269_same_bytes_are_rejected_between_product_and_people_channels(tmp_path) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    raw_plan = deepcopy(request.metadata["physical_renderer_reference_plans"]["1"])
    product_digest = raw_plan["references"][0]["content_sha256"]
    raw_plan["references"][1]["content_sha256"] = product_digest

    with pytest.raises(ValueError, match="doc269_plan_content_duplicate_invalid"):
        PhysicalRendererReferencePlan.model_validate(_rehashed_plan(raw_plan))


def test_doc269_doc263_record_without_verified_plan_fails_before_materialization(tmp_path) -> None:
    request, _product_ids, _face_output_ids, _projection = _captured_default_ecommerce_request(tmp_path)
    request.metadata.pop("physical_renderer_reference_plans")
    request.generation_plan.metadata.pop("physical_renderer_reference_plans")

    with pytest.raises(ReferenceInputAdmissionError, match="renderer reference plan is missing"):
        ProductionImageGenerationProvider().materialize_final_prompt(request)


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
