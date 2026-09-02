import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.creative_core import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.creative_core.central_brain import GenerationOutputCountMismatch
from alchemy_creative_agent_3_0.app.creative_core.doc281_output_plan_binding import (
    DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY,
    doc73_batch_plan_digest,
    issue_doc73_auto_identity_anchor_source_skeleton,
    issue_doc73_auto_identity_anchor_target_skeleton,
    validate_doc73_binding,
)
from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationProvider,
    GenerationRequest,
    GenerationResponse,
    GenerationRouter,
)
from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import AssetType, CandidateResult, PackagedAsset, Platform, ProviderStrategy
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_evidence import ExactReviewEvidenceResolver


class RecordingImageProvider(GenerationProvider):
    provider_name = "recording_image_provider"

    def __init__(self, output_dir: Path, empty_request_indexes: set[int] | None = None) -> None:
        self.output_dir = output_dir
        self.output_store = V3GeneratedOutputStore(output_dir / "records")
        self.requests: list[dict] = []
        self.empty_request_indexes = set(empty_request_indexes or set())

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        snapshot = request.model_dump(mode="json")
        self.requests.append(snapshot)
        index = len(self.requests)
        if index in self.empty_request_indexes:
            return GenerationResponse(
                candidates=[],
                provider_metadata={"provider_name": self.provider_name, "simulated_empty_response": True},
            )
        output_path = self.output_dir / f"generated_{index}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (96, 96), color=(120 + index, 180, 210)).save(output_path)
        job_id = str(request.metadata.get("job_id") or request.generation_plan.metadata.get("job_id") or "job_doc73")
        project_id = str(request.metadata.get("project_id") or "project_doc73")
        candidate_id = f"candidate_doc73_{index}"
        plan_position = request.metadata.get("output_index")
        planned_output_index = request.metadata.get("doc281_output_plan_index")
        source_receipt = request.metadata.get("doc73_auto_identity_anchor_receipt")
        skeleton = {}
        if index == 1 and type(plan_position) is int:
            if isinstance(source_receipt, dict):
                skeleton = issue_doc73_auto_identity_anchor_target_skeleton(
                    request.metadata,
                    source_binding=source_receipt,
                    job_id=job_id,
                    project_id=project_id,
                    asset_id=request.generation_plan.asset_id,
                    plan_position=plan_position,
                )
            elif type(planned_output_index) is int:
                skeleton = issue_doc73_auto_identity_anchor_source_skeleton(
                    request.metadata,
                    job_id=job_id,
                    project_id=project_id,
                    asset_id=request.generation_plan.asset_id,
                    plan_position=plan_position,
                    output_index=planned_output_index,
                    candidate_id=candidate_id,
                    refine_round=int(request.metadata.get("refine_round") or 0),
                    retry_attempt=int(request.metadata.get("retry_attempt") or 0),
                )
        encoded_image = base64.b64encode(output_path.read_bytes()).decode("ascii")
        output_record = self.output_store.save_base64_output(
            job_id=job_id,
            candidate_id=candidate_id,
            asset_id=request.generation_plan.asset_id,
            provider=self.provider_name,
            model="doc73-test",
            encoded_image=encoded_image,
            metadata={
                "project_id": project_id,
                "doc73_batch_plan_digest": request.metadata.get("doc73_batch_plan_digest"),
                "auto_batch_identity_anchor_policy": request.metadata.get("auto_batch_identity_anchor_policy", {}),
                **(
                    {"doc73_auto_identity_anchor_skeleton": skeleton}
                    if skeleton
                    else {}
                ),
            },
        )
        record_metadata = dict(output_record.metadata)
        candidate = CandidateResult(
            candidate_id=candidate_id,
            asset_id=request.generation_plan.asset_id,
            file_path=output_record.file_path,
            uri=output_record.thumbnail_url,
            provider=self.provider_name,
            prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
            condition_plan_id=request.condition_plan.condition_plan_id,
            is_mock=False,
            metadata={
                "output_id": output_record.output_id,
                "mime_type": output_record.mime_type,
                "mode_role_recipe": request.metadata.get("mode_role_recipe", {}),
                "reference_asset_count": len(request.metadata.get("reference_assets") or []),
                **record_metadata,
            },
        )
        return GenerationResponse(candidates=[candidate], provider_metadata={"provider_name": self.provider_name})


def _encoded_test_png(color: tuple[int, int, int]) -> str:
    buffer = BytesIO()
    Image.new("RGB", (96, 96), color=color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_doc73_first_output_becomes_identity_anchor_when_user_has_no_reference(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    result = brain.run_generation_loop(
        "Create a summer cool East Asian beauty portrait set for a social cover campaign. "
        "The same young woman has subtle green-highlighted dark hair, white summer styling, and seaside daylight.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "doc73_batch_plan_digest": "0" * 64,
            "project_id": "project_doc73",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "llm_brain": {
                "visual_task_profile": {
                    "subject_entities": [
                        {"entity_id": "portrait_subject_1", "entity_type": "person", "confidence": 0.98}
                    ]
                }
            },
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is True
    assert first_metadata.get("reference_assets") == []
    assert second_metadata["auto_batch_identity_anchor_applied"] is True
    assert second_metadata["reference_assets"][0]["source_type"] == "auto_batch_continuity"
    assert second_metadata["reference_assets"][0]["use_policy"] == "continuity"
    assert second_metadata["reference_assets"][0]["strength"] == "hard"
    source_output_id = second_metadata["reference_assets"][0]["output_id"]
    source_record = provider.output_store.get_output(source_output_id)
    assert source_record is not None
    assert second_metadata["reference_assets"][0]["file_path"] == source_record.file_path
    source_binding = source_record.metadata[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY]
    assert validate_doc73_binding(
        source_binding,
        expected_job_id=first_metadata["job_id"],
        expected_project_id="project_doc73",
        expected_output_id=source_output_id,
        expected_source_plan_position=0,
        expected_source_candidate_id=source_record.candidate_id,
    )
    assert second_metadata["doc73_auto_identity_anchor_receipt"] == source_binding
    assert "eye shape and spacing" in second_metadata["reference_assets"][0]["lock_targets"]
    assert result.metadata["candidate_loop"] is True


def test_generic_generation_fails_closed_when_a_planned_output_has_no_candidate(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs", empty_request_indexes={2})
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    with pytest.raises(GenerationOutputCountMismatch) as exc_info:
        brain.run_generation_loop(
            "Create a two-image summer portrait set with the same subject and natural daylight.",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            runtime_metadata={
                "requested_image_count": 2,
                "requested_image_size": "1024x1024",
                "template_id": "general_template",
                "scenario_id": "general_creative",
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
            },
        )

    assert exc_info.value.code == "v3_output_count_mismatch"
    assert len(provider.requests) == 2
    assert len(provider.output_store.list_outputs()) == 1


def test_doc73_later_output_cannot_replace_a_missing_first_output(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs", empty_request_indexes={1})
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    with pytest.raises(GenerationOutputCountMismatch):
        brain.run_generation_loop(
            "Create a two-image summer portrait set with the same subject and natural daylight.",
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            runtime_metadata={
                "requested_image_count": 2,
                "requested_image_size": "1024x1024",
                "project_id": "project_doc73_missing_first",
                "template_id": "general_template",
                "scenario_id": "general_creative",
                "variation_mode": "delivery_suite",
                "effective_variation_mode": "delivery_suite",
                "llm_brain": {
                    "visual_task_profile": {
                        "subject_entities": [
                            {"entity_id": "portrait_subject_1", "entity_type": "person", "confidence": 0.98}
                        ]
                    }
                },
            },
        )

    assert provider.output_store.list_outputs() == []


def test_doc73_user_selected_reference_has_priority_over_auto_first_output(tmp_path) -> None:
    selected_reference = tmp_path / "selected_reference.png"
    Image.new("RGB", (96, 96), color=(220, 200, 180)).save(selected_reference)
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Create a summer cool East Asian beauty portrait set for a social cover campaign. "
        "Keep the same young woman but vary expression and crop.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "reference_assets": [
                {
                    "asset_id": "user_selected_identity_ref",
                    "source_type": "selected_output",
                    "use_policy": "identity",
                    "role": "identity_anchor",
                    "strength": "hard",
                    "file_path": str(selected_reference),
                }
            ],
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert first_metadata["auto_batch_identity_anchor_policy"]["explicit_references_present"] is True
    assert second_metadata.get("auto_batch_identity_anchor_applied") is not True
    assert len(second_metadata["reference_assets"]) == 1
    assert second_metadata["reference_assets"][0]["asset_id"] == "user_selected_identity_ref"
    assert second_metadata["reference_assets"][0]["file_path"] == str(selected_reference)


def test_doc134_raw_person_or_cartoon_words_do_not_start_an_identity_chain_without_brain_evidence(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Photograph the same young woman wearing a real blue dress with a cartoon print.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
        },
    )

    assert len(provider.requests) >= 2
    assert provider.requests[0]["metadata"]["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert provider.requests[1]["metadata"].get("auto_batch_identity_anchor_applied") is not True


def test_doc73_product_profile_does_not_turn_a_no_reference_set_into_an_edit_chain(tmp_path) -> None:
    provider = RecordingImageProvider(tmp_path / "outputs")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=provider))

    brain.run_generation_loop(
        "Create a clean glass product model still-life set with three translucent spheres on a neutral surface.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 2,
            "requested_image_size": "1024x1024",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "delivery_suite",
            "effective_variation_mode": "delivery_suite",
            "llm_brain": {
                "visual_task_profile": {
                    "subject_entities": [
                        {"entity_id": "product_1", "entity_type": "product", "confidence": 0.95}
                    ]
                }
            },
        },
    )

    assert len(provider.requests) >= 2
    first_metadata = provider.requests[0]["metadata"]
    second_metadata = provider.requests[1]["metadata"]
    assert first_metadata["auto_batch_identity_anchor_policy"]["enabled"] is False
    assert second_metadata.get("auto_batch_identity_anchor_applied") is not True
    assert not any(
        item.get("source_type") == "generated_first_output"
        for item in second_metadata.get("reference_assets", [])
    )


def test_doc73_output_store_binding_is_available_to_review_without_formal_identity_evidence(tmp_path) -> None:
    job_id = "job_doc73_review"
    project_id = "project_doc73_review"
    source_asset_id = "asset_doc73_source"
    target_asset_id = "asset_doc73_target"
    source_candidate_id = "candidate_doc73_source"
    target_candidate_id = "candidate_doc73_target"
    batch_digest = doc73_batch_plan_digest(
        job_id=job_id,
        assets=[
            {"asset_id": source_asset_id, "asset_type": "single_image", "aspect_ratio": "1:1"},
            {"asset_id": target_asset_id, "asset_type": "single_image", "aspect_ratio": "1:1"},
        ],
    )
    policy = {"enabled": True}
    source_metadata = {
        "project_id": project_id,
        "doc73_batch_plan_digest": batch_digest,
        "auto_batch_identity_anchor_policy": policy,
    }
    source_skeleton = issue_doc73_auto_identity_anchor_source_skeleton(
        source_metadata,
        job_id=job_id,
        project_id=project_id,
        asset_id=source_asset_id,
        plan_position=0,
        output_index=1,
        candidate_id=source_candidate_id,
    )
    store = V3GeneratedOutputStore(tmp_path / "records")
    source_record = store.save_base64_output(
        job_id=job_id,
        candidate_id=source_candidate_id,
        asset_id=source_asset_id,
        provider="doc73_test",
        model="doc73-test",
        encoded_image=_encoded_test_png((120, 180, 210)),
        metadata={**source_metadata, "doc73_auto_identity_anchor_skeleton": source_skeleton},
    )
    source_binding = source_record.metadata[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY]
    assert validate_doc73_binding(
        source_binding,
        expected_job_id=job_id,
        expected_project_id=project_id,
        expected_batch_plan_digest=batch_digest,
        expected_output_id=source_record.output_id,
        expected_source_asset_id=source_asset_id,
        expected_source_plan_position=0,
        expected_source_candidate_id=source_candidate_id,
    )
    target_skeleton = issue_doc73_auto_identity_anchor_target_skeleton(
        source_metadata,
        source_binding=source_binding,
        job_id=job_id,
        project_id=project_id,
        asset_id=target_asset_id,
        plan_position=1,
    )
    target_record = store.save_base64_output(
        job_id=job_id,
        candidate_id=target_candidate_id,
        asset_id=target_asset_id,
        provider="doc73_test",
        model="doc73-test",
        encoded_image=_encoded_test_png((220, 160, 120)),
        metadata={
            **source_metadata,
            "doc73_auto_identity_anchor_skeleton": target_skeleton,
            "reference_asset_ids": [],
            "reference_truth_source_ids": [],
        },
    )
    target_asset = PackagedAsset(
        asset_id=target_asset_id,
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="continuity target",
        metadata={"output_id": target_record.output_id},
    )
    resolution = GeneratedOutputResolver(store).resolve_asset(job_id, target_asset, project_id=project_id)
    assert resolution.status == "ready"
    request = SimpleNamespace(
        job_id=job_id,
        uploaded_asset_ids=[],
        product_profile=None,
        metadata={"project_id": project_id, "doc73_batch_plan_digest": batch_digest},
    )
    record = SimpleNamespace(job_id=job_id, request=request)
    review_metadata = ExactReviewEvidenceResolver(
        asset_store=SimpleNamespace(get_upload=lambda _asset_id: None),
        output_store=store,
    ).resolve(record=record, resolution=resolution)

    assert review_metadata["doc73_auto_identity_anchor_review"] == {"state": "available", "role": "target"}
    review_plan = review_metadata["review_evidence_plan"]
    person_channel = review_plan["channels"]["person_identity"]
    assert person_channel["applicability"] == "not_applicable"
    assert person_channel["evidence_state"] == "not_applicable"
    assert "review_evidence_person_identity_invalid" not in person_channel["reason_codes"]

    replay_service = object.__new__(V3ProductApiService)
    replay_service.output_store = store
    replayed = replay_service._doc73_retry_metadata(
        SimpleNamespace(
            creative_job=SimpleNamespace(job_id=job_id),
            metadata={"doc73_batch_plan_digest": batch_digest},
            asset_pack=SimpleNamespace(metadata={}, manifest={}, assets=[]),
        )
    )
    assert replayed["doc73_auto_identity_anchor_receipt"] == source_binding

    tampered_request = SimpleNamespace(
        job_id=job_id,
        uploaded_asset_ids=[],
        product_profile=None,
        metadata={"project_id": project_id, "doc73_batch_plan_digest": "f" * 64},
    )
    tampered_record = SimpleNamespace(job_id=job_id, request=tampered_request)
    tampered_review = ExactReviewEvidenceResolver(
        asset_store=SimpleNamespace(get_upload=lambda _asset_id: None),
        output_store=store,
    ).resolve(record=tampered_record, resolution=resolution)
    assert tampered_review["doc73_auto_identity_anchor_review"]["state"] == "invalid"


def test_doc73_auto_anchor_cannot_be_promoted_by_explicit_truth_ids() -> None:
    source_output_id = "v3_output_doc73_formal_truth_guard"
    record = {
        "reference_truth_source_ids": [source_output_id],
        DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY: {
            "origin": "auto_batch_continuity",
            "source_output_id": source_output_id,
            "target_output_id": "v3_output_doc73_target",
        },
    }

    assert ExactReviewEvidenceResolver._source_specs([record]) == []


def test_doc73_private_anchor_metadata_is_hidden_from_output_store_recovery(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    output = store.save_base64_output(
        job_id="job_doc73_public_recovery",
        candidate_id="candidate_doc73_public_recovery",
        asset_id="asset_doc73_public_recovery",
        provider="doc73_test",
        model="doc73-test",
        encoded_image=_encoded_test_png((140, 170, 210)),
        metadata={
            "doc73_batch_plan_digest": "a" * 64,
            "doc73_auto_identity_anchor_binding": {"source_output_id": "v3_output_private_anchor"},
            "doc73_auto_identity_anchor_skeleton": {"source_output_id": "v3_output_private_anchor"},
            "doc73_auto_identity_anchor_receipt": {"source_output_id": "v3_output_private_anchor"},
            "doc73_auto_identity_anchor_reference": {"output_id": "v3_output_private_anchor"},
            "auto_batch_identity_anchor_policy": {"source_rule": "first_generated_output_if_no_user_reference"},
            "auto_batch_identity_anchor_applied": True,
            "auto_batch_identity_anchor_source_output_id": "v3_output_private_anchor",
            "auto_batch_identity_anchor_source_candidate_id": "candidate_doc73_private_anchor",
            "provider_reference_assets": [{"output_id": "v3_output_private_anchor", "file_path": "private.png"}],
        },
    )

    status = V3ProductApiService(output_store=store).get_job(output.job_id)
    public_values = [
        status.asset_series[0].metadata["candidate_metadata"],
        status.candidates[0].metadata,
    ]
    hidden_keys = {
        "doc73_batch_plan_digest",
        "doc73_auto_identity_anchor_binding",
        "doc73_auto_identity_anchor_skeleton",
        "doc73_auto_identity_anchor_receipt",
        "doc73_auto_identity_anchor_reference",
        "auto_batch_identity_anchor_policy",
        "auto_batch_identity_anchor_applied",
        "auto_batch_identity_anchor_source_output_id",
        "auto_batch_identity_anchor_source_candidate_id",
        "provider_reference_assets",
    }
    assert all(hidden_keys.isdisjoint(value) for value in public_values)
    assert all(value["output_id"] == output.output_id for value in public_values)


def test_doc73_tampered_skeleton_is_discarded_before_output_record_binding(tmp_path) -> None:
    job_id = "job_doc73_tamper"
    project_id = "project_doc73_tamper"
    batch_digest = doc73_batch_plan_digest(
        job_id=job_id,
        assets=[{"asset_id": "asset_doc73_tamper", "asset_type": "single_image", "aspect_ratio": "1:1"}],
    )
    metadata = {
        "project_id": project_id,
        "doc73_batch_plan_digest": batch_digest,
        "auto_batch_identity_anchor_policy": {"enabled": True},
    }
    skeleton = issue_doc73_auto_identity_anchor_source_skeleton(
        metadata,
        job_id=job_id,
        project_id=project_id,
        asset_id="asset_doc73_tamper",
        plan_position=0,
        output_index=1,
        candidate_id="candidate_doc73_tamper",
    )
    tampered = {**skeleton, "source_candidate_id": "candidate_doc73_forged"}
    store = V3GeneratedOutputStore(tmp_path / "records")
    record = store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate_doc73_tamper",
        asset_id="asset_doc73_tamper",
        provider="doc73_test",
        model="doc73-test",
        encoded_image=_encoded_test_png((100, 140, 190)),
        metadata={**metadata, "doc73_auto_identity_anchor_skeleton": tampered},
    )
    assert DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY not in record.metadata
    assert store.get_doc73_auto_identity_anchor_receipt(job_id) is None


def test_doc73_concurrent_source_claim_is_first_writer_wins(tmp_path) -> None:
    job_id = "job_doc73_concurrent"
    project_id = "project_doc73_concurrent"
    asset_id = "asset_doc73_concurrent"
    batch_digest = doc73_batch_plan_digest(
        job_id=job_id,
        assets=[{"asset_id": asset_id, "asset_type": "single_image", "aspect_ratio": "1:1"}],
    )

    def save_candidate(candidate_id: str, color: tuple[int, int, int]):
        metadata = {
            "project_id": project_id,
            "doc73_batch_plan_digest": batch_digest,
            "auto_batch_identity_anchor_policy": {"enabled": True},
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
        store = V3GeneratedOutputStore(tmp_path / "records")
        return store.save_base64_output(
            job_id=job_id,
            candidate_id=candidate_id,
            asset_id=asset_id,
            provider="doc73_test",
            model="doc73-test",
            encoded_image=_encoded_test_png(color),
            metadata={**metadata, "doc73_auto_identity_anchor_skeleton": skeleton},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(save_candidate, "candidate_doc73_a", (110, 150, 190)),
            executor.submit(save_candidate, "candidate_doc73_b", (190, 150, 110)),
        ]
        [future.result() for future in futures]

    records = V3GeneratedOutputStore(tmp_path / "records").list_outputs(limit=10)
    bound_records = [
        record
        for record in records
        if DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY in dict(record.metadata or {})
    ]
    assert len(bound_records) == 1
    receipt = V3GeneratedOutputStore(tmp_path / "records").get_doc73_auto_identity_anchor_receipt(job_id)
    assert receipt == bound_records[0].metadata[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY]


def test_doc73_auto_anchor_with_missing_canonical_record_fails_closed(tmp_path) -> None:
    missing_output_id = "v3_output_" + "a" * 20
    asset = PackagedAsset(
        asset_id="asset_doc73_missing",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC,
        aspect_ratio="1:1",
        purpose="missing continuity output",
        file_path=str(tmp_path / "orphan.png"),
        metadata={
            "output_id": missing_output_id,
            "candidate_metadata": {
                DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY: {
                    "origin": "auto_batch_continuity",
                }
            },
        },
    )
    resolution = GeneratedOutputResolver(V3GeneratedOutputStore(tmp_path / "records")).resolve_asset(
        "job_doc73_missing",
        asset,
        project_id="project_doc73_missing",
    )
    assert resolution.status == "unbound"
    assert resolution.file_path is None
