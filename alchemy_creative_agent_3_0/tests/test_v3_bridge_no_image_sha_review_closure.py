from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.physical_renderer_reference_plan import (
    DOC269_PHYSICAL_PLAN_NO_IMAGE_SHA_SCHEMA,
    PhysicalRendererReferenceEntry,
    PhysicalRendererReferencePlan,
    _digest as doc269_digest,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.provider_deliverability_closure import (
    _physical_reference_bindings,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    PhysicalProductReferenceProjection,
)

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.creative_core.doc281_output_plan_binding import (
    DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY,
    doc73_batch_plan_digest,
    finalize_doc73_auto_identity_anchor_binding,
    issue_doc73_auto_identity_anchor_source_skeleton,
)


def test_bridge_review_closure_uses_output_identity_without_reading_image_bytes(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "bridge-output.png"
    image_path.write_bytes(b"stored output placeholder")
    output = SimpleNamespace(
        output_id="bridge-output-id",
        asset_id="bridge-asset-id",
        candidate_id="bridge-candidate-id",
        file_path=str(image_path),
        metadata={},
    )
    record = SimpleNamespace(
        job_id="bridge-job-id",
        request=SimpleNamespace(metadata={"render_bridge_primary_no_image_sha": True}),
        generation_result=None,
        status=None,
        warnings=[],
        lifecycle=None,
    )

    class OutputStore:
        def list_by_job(self, _job_id):
            return [output]

    class JobStore:
        def save(self, _record):
            return None

    service = object.__new__(V3ProductApiService)
    service.output_store = OutputStore()
    service.job_store = JobStore()
    service._build_lifecycle = lambda _record: None
    service._status_from_record = lambda current: current

    def fail_read_bytes(_path):
        raise AssertionError("Bridge no-image-SHA closure must not read image bytes")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    result = service._close_post_generation_review_finalization(record)

    assert result is record
    closure = record.request.metadata["post_generation_review_closure"]
    assert closure["schema_version"] == "doc267_post_generation_review_closure_v2"
    assert closure["output_ids"] == ["bridge-output-id"]
    assert closure["pixel_bindings"] == [
        {
            "output_id": "bridge-output-id",
            "asset_id": "bridge-asset-id",
            "candidate_id": "bridge-candidate-id",
        }
    ]


def test_project_projection_accepts_identity_bound_no_sha_closure() -> None:
    metadata = {
        "post_generation_review_closure": {
            "schema_version": "doc267_post_generation_review_closure_v2",
            "authority": "v3_product_api",
            "state": "review_withheld_finalization_failed",
            "job_id": "bridge-job-id",
            "output_ids": ["bridge-output-id"],
            "pixel_bindings": [
                {
                    "output_id": "bridge-output-id",
                    "asset_id": "bridge-asset-id",
                    "candidate_id": "bridge-candidate-id",
                }
            ],
            "history_only": True,
            "real_pixel_review": False,
            "automatic_delivery_available": False,
            "manual_confirmation_required": True,
            "automatic_replay": False,
        }
    }

    assert V3ProjectModeService._doc267_review_withheld_closure_is_valid(
        metadata,
        job_id="bridge-job-id",
    )


def test_bridge_ecommerce_review_disposition_uses_output_identity_without_reading_image_bytes(
    tmp_path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "bridge-ecommerce-output.png"
    image_path.write_bytes(b"stored output placeholder")
    output = SimpleNamespace(
        output_id="bridge-output-id",
        job_id="bridge-job-id",
        asset_id="bridge-asset-id",
        candidate_id="bridge-candidate-id",
        file_path=str(image_path),
        metadata={
            "final_delivery": {
                "delivery_gate_applies": True,
                "final_delivery_status": "ready",
                "automatic_delivery_available": True,
                "manual_confirmation_required": False,
            }
        },
    )
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "review_evidence_receipt_status": "complete",
                "resolutions": [{"output_id": "bridge-output-id", "status": "ready"}],
                "inspections": [
                    {"output_id": "bridge-output-id", "asset_id": "bridge-asset-id", "status": "pass"}
                ],
            }
        }
    )
    record = SimpleNamespace(
        job_id="bridge-job-id",
        request=SimpleNamespace(metadata={"render_bridge_primary_no_image_sha": True}),
        generation_result=result,
        status=None,
    )

    class OutputStore:
        def list_by_job(self, _job_id):
            return [output]

    service = object.__new__(V3ProductApiService)
    service.output_store = OutputStore()
    service._is_ecommerce_request = lambda _request: True
    service._public_final_delivery_projection = lambda _result: (
        {"final_delivery_status": "ready"},
        {"bridge-output-id"},
        {"bridge-asset-id"},
    )

    def fail_read_bytes(_path):
        raise AssertionError("Bridge E-Commerce status projection must not read image bytes")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    disposition = service._doc280_ecommerce_review_disposition(record)

    assert disposition == {
        "schema_version": "doc280_ecommerce_review_disposition_v1",
        "state": "final_delivery_available",
        "terminal": True,
        "pending": False,
        "next_actions": [],
    }


def test_project_doc73_bridge_anchor_uses_record_identity_without_reading_image_bytes(tmp_path, monkeypatch) -> None:
    job_id = "bridge-job-id"
    project_id = "bridge-project-id"
    asset_id = "bridge-asset-id"
    candidate_id = "bridge-candidate-id"
    output_id = "v3_output_" + "a" * 20
    metadata = {
        "project_id": project_id,
        "doc73_batch_plan_digest": doc73_batch_plan_digest(
            job_id=job_id,
            assets=[{"asset_id": asset_id, "asset_type": "single_image", "aspect_ratio": "1:1"}],
        ),
        "auto_batch_identity_anchor_policy": {"enabled": True},
        "render_bridge_primary_no_image_sha": True,
    }
    skeleton = issue_doc73_auto_identity_anchor_source_skeleton(
        metadata,
        job_id=job_id,
        project_id=project_id,
        asset_id=asset_id,
        plan_position=0,
        output_index=1,
        candidate_id=candidate_id,
    )
    bound_metadata = finalize_doc73_auto_identity_anchor_binding(
        {**metadata, "doc73_auto_identity_anchor_skeleton": skeleton},
        job_id=job_id,
        project_id=project_id,
        candidate_id=candidate_id,
        asset_id=asset_id,
        output_id=output_id,
        content_sha256="",
    )
    binding = bound_metadata[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY]
    image_path = tmp_path / "bridge-anchor.png"
    image_path.write_bytes(b"stored output placeholder")
    record = SimpleNamespace(
        output_id=output_id,
        job_id=job_id,
        asset_id=asset_id,
        candidate_id=candidate_id,
        created_at="2026-11-06T00:00:00Z",
        file_path=str(image_path),
        metadata=bound_metadata,
    )

    class OutputStore:
        def list_by_job(self, _job_id):
            return [record]

        def get_doc73_auto_identity_anchor_receipt(self, _job_id):
            return binding

    service = object.__new__(V3ProjectModeService)
    service.product_service = SimpleNamespace(output_store=OutputStore())
    service._doc73_auto_identity_anchor_control_state = lambda *_args: "bound"
    project = SimpleNamespace(project_id=project_id, job_ids=[job_id])

    def fail_read_bytes(_path):
        raise AssertionError("Bridge Doc73 anchor lookup must not read image bytes")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    anchor = service._doc73_auto_identity_anchor_record(project)

    assert anchor is not None
    assert anchor["record"] is record
    assert anchor["binding"] == binding
    assert anchor["state"] == "bound"


def test_doc271_bridge_physical_reference_binding_uses_ids_without_reading_image_bytes(
    tmp_path, monkeypatch
) -> None:
    image_path = tmp_path / "bridge-product.png"
    image_path.write_bytes(b"bridge input bytes are not read")
    reference = PhysicalRendererReferenceEntry(
        reference_id="product-asset-id",
        source_id="product-asset-id",
        role="product_reference",
        channel="product_truth",
        source_type="uploaded",
        file_path=str(image_path),
        ordinal=1,
    )
    payload = {
        "schema_version": DOC269_PHYSICAL_PLAN_NO_IMAGE_SHA_SCHEMA,
        "job_id": "bridge-job-id",
        "output_index": 1,
        "projection_digest": "b" * 64,
        "maximum_reference_images": 1,
        "references": [reference.model_dump(mode="json", exclude_none=True)],
        "reference_image_asset_ids": ["product-asset-id"],
        "reference_image_count": 1,
    }
    plan = PhysicalRendererReferencePlan(**payload, plan_digest=doc269_digest(payload))

    class TestProjection:
        job_id = "bridge-job-id"
        output_index = 1
        projection_digest = "b" * 64

        @classmethod
        def from_mapping(cls, _value):
            return cls()

    monkeypatch.setattr(PhysicalProductReferenceProjection, "from_mapping", TestProjection.from_mapping)
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: (_ for _ in ()).throw(AssertionError("image bytes read")),
    )
    bindings = _physical_reference_bindings(
        {
            "physical_renderer_reference_plans": {"1": plan.model_dump(mode="json")},
            "professional_ecommerce_physical_product_projections": {"1": {"fixture": True}},
        },
        "bridge-job-id",
    )

    assert bindings is not None
    binding = bindings[0]["reference_binding"]
    assert binding["schema_version"] == "doc271_physical_reference_binding_v2"
    assert binding["ordered_reference_ids"] == ["product-asset-id"]
    assert "ordered_reference_sha256" not in binding
