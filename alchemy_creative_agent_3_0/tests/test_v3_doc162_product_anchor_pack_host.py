"""Doc162: formal Product API host closes the shared AnchorPack seam."""

from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.visual_assets.catalog import InMemoryVisualAssetCatalog
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    PeopleAsset,
    RootSourceProvenance,
)


class _OutputStore:
    def __init__(self) -> None:
        self.by_job: dict[str, list[SimpleNamespace]] = {}

    def list_by_job(self, job_id: str):  # noqa: ANN201
        return list(self.by_job.get(job_id, []))


class _SharedProductService:
    """Test double for the already-tested Product API/Provider/Vision path."""

    def __init__(self) -> None:
        self.visual_asset_catalog = InMemoryVisualAssetCatalog()
        self.output_store = _OutputStore()
        self.jobs: dict[str, SimpleNamespace] = {}
        self.requests: list[dict] = []

    def create_professional_anchor_preparation_job(
        self,
        payload,
        *,
        view_role,
        reference_evidence_ids,
        stage_plan_source_job_id=None,
    ):  # noqa: ANN001, ANN201
        job_id = f"job_{len(self.requests) + 1}"
        self.requests.append(
            {
                "job_id": job_id,
                "payload": payload,
                "view_role": view_role,
                "reference_evidence_ids": list(reference_evidence_ids),
                "stage_plan_source_job_id": stage_plan_source_job_id,
            }
        )
        return SimpleNamespace(status=ProductJobStatusValue.PLANNED, job_id=job_id)

    def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
        frozen = next(item for item in self.requests if item["job_id"] == job_id)
        role = frozen["view_role"]
        expected_references = {"standard_front": 2, "three_quarter": 3, "profile": 5}[role]
        output_id = f"output_{job_id}"
        candidate_id = f"candidate_{job_id}"
        output = SimpleNamespace(
            output_id=output_id,
            candidate_id=candidate_id,
            metadata={
                "provider_prompt_sha256": f"sha256:{job_id}",
                "prompt_compilation_id": f"prompt_{job_id}",
                "provider_reference_image_count": expected_references,
                "provider_reference_assets": [
                    {
                        "provider_reference_derivative": True,
                        "identity_face_localization_applied": True,
                        "identity_face_localization_status": "detected",
                        "identity_nonidentity_pixel_suppression_profile": (
                            "face_localized_nonidentity_suppression_v1"
                        ),
                    }
                    for _ in range(expected_references)
                ],
            },
        )
        self.output_store.by_job[job_id] = [output]
        score_card = {
            "same_person_readability": 0.90 + len(self.requests) / 1000,
            "distinctive_feature_readability": 0.91,
            "human_realism": 0.90,
            "pose_compliance": 0.92,
            "visual_quality": 0.89,
            "ai_overperfection_penalty": 0.04,
            "overall": 0.90,
        }
        self.jobs[job_id] = SimpleNamespace(
            generation_result=SimpleNamespace(
                planning_result_id=f"planning_{job_id}",
                metadata={
                    "post_generation_review_package": {
                        "inspections": [
                            {
                                "output_id": output_id,
                                "mode": "hybrid",
                                "verification_state": "verified",
                                "status": "pass",
                                "score_card": score_card,
                                "issue_codes": [],
                            }
                        ]
                    }
                },
            )
        )
        return SimpleNamespace(status=ProductJobStatusValue.GENERATED)

    def get_job_record(self, job_id):  # noqa: ANN001, ANN201
        return self.jobs.get(job_id)


def _asset() -> PeopleAsset:
    return PeopleAsset(
        people_asset_id="person_doc162",
        project_id="project_doc162",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_doc162",
            people_asset_id="person_doc162",
        ),
    )


def _root() -> RootSourceProvenance:
    return RootSourceProvenance(
        source_type="uploaded_portrait",
        source_asset_id="v3_asset_root",
        project_id="project_doc162",
        consent_reference="authorized-test-source",
    )


def test_doc162_product_host_runs_three_by_three_by_three_through_shared_service() -> None:
    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "review"
    assert len(service.requests) == 9
    assert [item["view_role"] for item in service.requests] == [
        "standard_front", "standard_front", "standard_front",
        "three_quarter", "three_quarter", "three_quarter",
        "profile", "profile", "profile",
    ]
    front_winner = result.pack.anchor_views[0].output_id
    three_quarter_winner = result.pack.anchor_views[1].output_id
    assert all(
        item["reference_evidence_ids"] == ["v3_asset_root", front_winner]
        for item in service.requests[3:6]
    )
    assert all(
        item["reference_evidence_ids"] == [
            "v3_asset_root",
            front_winner,
            three_quarter_winner,
        ]
        for item in service.requests[6:]
    )
    assert all(attempt.candidate.prompt_reference_parity_verified for attempt in result.attempts)
    assert all(attempt.candidate.brain_plan_id.startswith("planning_job_") for attempt in result.attempts)
    assert service.requests[0]["stage_plan_source_job_id"] is None
    assert service.requests[1]["stage_plan_source_job_id"] == service.requests[0]["job_id"]
    assert service.requests[2]["stage_plan_source_job_id"] == service.requests[0]["job_id"]
    assert service.requests[3]["stage_plan_source_job_id"] is None
    assert service.requests[6]["stage_plan_source_job_id"] is None
    assert service.requests[0]["payload"]["user_input"].endswith(
        "Remote Brain must author the complete visual direction."
    )
    assert "prompt" not in service.requests[0]["payload"]["metadata"]


def test_doc162_product_host_fails_review_when_typed_score_is_incomplete() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def incomplete(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        inspection = service.jobs[job_id].generation_result.metadata[
            "post_generation_review_package"
        ]["inspections"][0]
        inspection["score_card"].pop("same_person_readability")
        return status

    service.generate_job = incomplete  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["no_passing_front_candidate"]
    assert len(service.requests) == 3
    assert all(
        "professional_anchor_review_score_incomplete" in attempt.review.issue_codes
        for attempt in result.attempts
    )


def test_doc163_product_host_withholds_anchor_when_face_localization_falls_back() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def unlocalized(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        output = service.output_store.by_job[job_id][0]
        output.metadata["provider_reference_assets"][0]["identity_face_localization_applied"] = False
        output.metadata["provider_reference_assets"][0]["identity_face_localization_status"] = (
            "heuristic_fallback"
        )
        return status

    service.generate_job = unlocalized  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["no_passing_front_candidate"]
    assert len(service.requests) == 3
    assert all(
        "professional_anchor_face_localization_unverified" in attempt.review.issue_codes
        for attempt in result.attempts
    )


def test_doc163_selected_anchor_winner_has_canonical_provider_binding(tmp_path) -> None:
    upload_store = V3UploadedAssetStore(tmp_path / "uploads")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(asset_store=upload_store, output_store=output_store)
    image = Image.new("RGB", (64, 64), (130, 110, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    upload = service.create_uploaded_asset(
        {
            "filename": "root.png",
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": encoded, "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[upload.asset_id],
    )

    references = service._professional_anchor_reference_assets(  # noqa: SLF001
        request,
        view_role="three_quarter",
        reference_evidence_ids=[upload.asset_id, winner.output_id],
    )

    assert len(references) == 1
    assert references[0]["asset_id"] == winner.output_id
    assert references[0]["output_id"] == winner.output_id
    assert references[0]["source_type"] == "selected_output"
    assert references[0]["role"] == "face_reference"
    assert references[0]["use_policy"] == "identity"
    assert references[0]["strength"] == "hard"
    assert references[0]["provider_input_required"] is True
    assert references[0]["metadata"]["canonical_output_binding"] is True
    assert references[0]["metadata"]["professional_anchor_lineage_evidence"] is True
    assert references[0]["metadata"]["professional_anchor_lineage_role"] == "prior_view_winner"


def test_doc164_runtime_freezes_selected_anchor_winner_as_output_reference(tmp_path) -> None:
    upload_store = V3UploadedAssetStore(tmp_path / "uploads")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(asset_store=upload_store, output_store=output_store)
    image = Image.new("RGB", (64, 64), (130, 110, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    upload = service.create_uploaded_asset(
        {
            "filename": "root.png",
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": encoded, "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[upload.asset_id],
        metadata={
            "professional_anchor_reference_assets": service._professional_anchor_reference_assets(  # noqa: SLF001
                CreateCreativeJobRequest(
                    user_input="Prepare a supplementary anchor.",
                    uploaded_asset_ids=[upload.asset_id],
                ),
                view_role="three_quarter",
                reference_evidence_ids=[upload.asset_id, winner.output_id],
            )
        },
    )

    payload = service._runtime_request_payload(request)  # noqa: SLF001
    runtime_request = ScenarioRuntimeRequest.model_validate(payload)
    references = service.scenario_runtime._reference_assets_from_request_metadata(  # noqa: SLF001
        runtime_request
    )
    selected = next(item for item in references if item.get("asset_id") == winner.output_id)

    assert selected["output_id"] == winner.output_id
    assert selected["source_type"] == "selected_output"
    assert selected["use_policy"] == "identity"
    assert selected["strength"] == "hard"
    assert selected["provider_input_required"] is True
    assert selected["metadata"]["professional_anchor_lineage_role"] == "prior_view_winner"


def test_doc162_shared_review_receives_frozen_selected_winner_sources(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    image = Image.new("RGB", (32, 32), (120, 100, 90))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    service = V3ProductApiService(output_store=output_store)
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[],
        metadata={
            "professional_anchor_reference_assets": [
                {"asset_id": winner.output_id, "metadata": {"source_type": "selected_output"}}
            ]
        },
    )
    record = ProductJobRecord(
        request=request,
        status=ProductJobStatusValue.GENERATED,
        job_id_value="job_review_projection",
    )
    resolution = SimpleNamespace(
        metadata={
            "candidate_metadata": {
                "reference_input_execution": {
                    "admission_outcome": "admitted",
                    "operation_outcome": "pixels_received",
                    "reference_count": 1,
                },
                "reference_truth_source_ids": [winner.output_id],
            }
        }
    )

    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001

    assert metadata["review_reference_evidence_available"] is True
    assert metadata["reference_assets"] == [
        {
            "asset_id": winner.output_id,
            "output_id": winner.output_id,
            "role": "face_reference",
            "source_type": "selected_output",
            "use_policy": "admitted_generation_reference",
            "file_path": winner.file_path,
            "mime_type": "image/png",
        }
    ]
