"""Phase 0 red contracts for Doc263 product-truth projection recovery.

These tests deliberately describe the approved behavior before runtime work
lands. They must remain deterministic and must not reach an external provider.
"""

from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ReferenceInputAdmissionError,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode.ecommerce_view_activation import (
    DisabledEcommerceViewActivationIssuer,
)
from alchemy_creative_agent_3_0.app.project_mode import service as project_mode_service
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    ProductTruthAdmission,
    ProductTruthSource,
    build_physical_product_projection,
    build_product_truth_admission,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (96, 72), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    path.write_bytes(_png_bytes(color))
    return path


def _reference(
    *,
    asset_id: str,
    role: str,
    path: Path,
    provider_input_required: bool,
) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "role": role,
        "file_path": str(path),
        "filename": path.name,
        "mime_type": "image/png",
        "provider_input_required": provider_input_required,
        "metadata": {
            "provider_input_required": provider_input_required,
            "codex_native_reference_channel": (
                "product_truth" if role == "product_reference" else "portrait_identity"
            ),
        },
    }


def _template_plan(
    *,
    pool_product_ids: list[str],
    selected_product_ids: list[str],
) -> dict[str, object]:
    return {
        "plan_id": "doc263_ecommerce_template_plan",
        "template_id": "ecommerce_template",
        "scenario_id": "ecommerce",
        "owner": "ecommerce_scenario_pack",
        "creative_direction_owner": "remote_v3_llm_brain",
        "requested_image_count": 1,
        "effective_image_count": 1,
        "deliverables": [
            {
                "deliverable_id": "doc263_deliverable_1",
                "output_index": 1,
                "image_intent": "show the selected physical product truth faithfully",
                "source": "remote_v3_llm_brain",
                "factual_acceptance": ["product_truth"],
                "metadata": {
                    "product_truth_pool_asset_ids": list(pool_product_ids),
                    "product_truth_selection_role": (
                        "product_detail_or_print_view"
                        if len(selected_product_ids) == 2
                        else "lifestyle_primary_product_view"
                    ),
                    "selected_product_truth_asset_ids": list(selected_product_ids),
                    "admitted_product_truth_asset_ids": list(selected_product_ids),
                    "max_product_truth_source_refs_per_output": 2,
                    "product_truth_selection_source": (
                        "remote_brain_image_set_plan.evidence_dimensions_by_output"
                    ),
                },
            }
        ],
        "provenance": [],
    }


def _adaptive_cluster(product_ids: list[str]) -> dict[str, object]:
    return {
        "adaptive_reference_selection_plan": {
            "applies": True,
            "ordered_source_ids": list(reversed(product_ids)),
            "excluded_source_ids": [],
            "max_identity_sources": 1,
            "target_view": "unknown",
            "target_framing": "unknown",
        },
        "subject_continuity_asset_package": {
            "evidence": [
                {
                    "source_id": asset_id,
                    "asset_id": asset_id,
                    "authority": "uploaded_root_truth",
                    "view_hint": "unknown",
                    "framing_hint": "unknown",
                    "trust_score": 1.0,
                }
                for asset_id in product_ids
            ]
        },
    }


def _generation_request(
    *,
    references: list[dict[str, object]],
    pool_product_ids: list[str],
    selected_product_ids: list[str],
) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc263_product_truth",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="1:1",
        purpose="professional ecommerce product image",
        priority=1,
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc263_product_truth",
            asset_id=asset.asset_id,
            visual_prompt="professional product image",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(
            condition_plan_id="condition_doc263_product_truth",
            asset_id=asset.asset_id,
        ),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc263_product_truth",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "uploaded_assets": references,
            "professional_product_truth_required": True,
            "professional_ecommerce_product_truth_pool_asset_ids": list(pool_product_ids),
            "template_deliverable_plan": _template_plan(
                pool_product_ids=pool_product_ids,
                selected_product_ids=selected_product_ids,
            ),
            "visual_cluster": _adaptive_cluster(pool_product_ids),
        },
    )
    return _attach_server_owned_ecommerce_contract(
        request,
        references=references,
        pool_product_ids=pool_product_ids,
        selected_product_ids=selected_product_ids,
    )


def _attach_server_owned_ecommerce_contract(
    request: GenerationRequest,
    *,
    references: list[dict[str, object]],
    pool_product_ids: list[str],
    selected_product_ids: list[str],
    projection_state: str = "ready",
    historical_lineage_id: str | None = None,
) -> GenerationRequest:
    by_asset_id = {str(item["asset_id"]): item for item in references}
    sources = []
    for asset_id in pool_product_ids:
        reference = by_asset_id[asset_id]
        path = Path(str(reference["file_path"]))
        content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        sources.append(
            ProductTruthSource(
                asset_id=asset_id,
                content_sha256=content_sha256,
                consent_reference=f"fixture:{asset_id}:consent",
                rights_reference=f"fixture:{asset_id}:rights",
                receipt_digest=hashlib.sha256(
                    "|".join(
                        (
                            "v3_upload_authorization_receipt_v1",
                            asset_id,
                            content_sha256,
                            "product_reference",
                            "product_truth",
                            f"fixture:{asset_id}:consent",
                            f"fixture:{asset_id}:rights",
                        )
                    ).encode("utf-8")
                ).hexdigest(),
                role="product_reference",
                product_truth_channel="product_truth",
                readiness="ready",
                file_integrity="sha256_verified",
                provenance="fixture_product_api",
            )
        )
    admission = build_product_truth_admission(
        project_id="doc263_project",
        job_id="doc263_server_job",
        sources=sources,
        product_truth_plan_digest=hashlib.sha256(
            b"doc263_fixture_plan_digest"
        ).hexdigest(),
    )
    projection = build_physical_product_projection(
        job_id=admission.job_id,
        output_index=1,
        admission=admission,
        selected_product_asset_ids=selected_product_ids,
        selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
        selection_role=(
            "product_detail_or_print_view"
            if len(selected_product_ids) == 2
            else "lifestyle_primary_product_view"
        ),
        cap_reservation=2,
        projection_state=projection_state,
        historical_lineage_id=historical_lineage_id,
    )
    request.metadata = {
        **request.metadata,
        "project_id": admission.project_id,
        "job_id": admission.job_id,
        "professional_ecommerce_contract_authority": "v3_product_api",
        "professional_ecommerce_product_truth_admission": admission.model_dump(),
        "professional_ecommerce_physical_product_projection": projection.model_dump(),
        "professional_ecommerce_physical_product_projections": {"1": projection.model_dump()},
    }
    return request


def _doc263_references(
    tmp_path: Path,
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    product_ids = [f"product_{index}" for index in range(4)]
    products = [
        _reference(
            asset_id=asset_id,
            role="product_reference",
            path=_image(tmp_path / f"{asset_id}.png", (120 + index, 80, 150)),
            provider_input_required=False,
        )
        for index, asset_id in enumerate(product_ids)
    ]
    face_ids = [f"face_{index}" for index in range(3)]
    faces = [
        _reference(
            asset_id=asset_id,
            role="face_reference",
            path=_image(tmp_path / f"{asset_id}.png", (190, 150 + index, 130)),
            provider_input_required=True,
        )
        for index, asset_id in enumerate(face_ids)
    ]
    return [*products, *faces], product_ids, face_ids


class _NoProviderDispatch(ProductionImageGenerationProvider):
    def __init__(self) -> None:
        super().__init__()
        self.dispatch_calls = 0

    def _run_app_provider_with_timeout_retry(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.dispatch_calls += 1
        raise AssertionError("Doc263 local preflight must stop before provider dispatch.")


def _failure_code(provider: ProductionImageGenerationProvider, request: GenerationRequest) -> str:
    with pytest.raises(ReferenceInputAdmissionError) as raised:
        provider._reference_assets(request)  # noqa: SLF001
    detail = getattr(raised.value, "detail", {})
    return str(detail.get("reference_input_failure_code") or "")


def _active_product_references(project: dict[str, object]) -> list[dict[str, object]]:
    return [
        item
        for item in project.get("reference_assets", [])
        if item.get("status") == "active"
        and item.get("source_type") == "uploaded"
        and item.get("use_policy") == "product"
    ]


def _doc263_handlers(*, output_store=None) -> V3ProductRouteHandlers:
    service_kwargs = {} if output_store is None else {"output_store": output_store}
    return V3ProductRouteHandlers(
        service=ecommerce_test_service(**service_kwargs),
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
    )


def test_doc263_legacy_handler_fixture_ignores_enabled_environment_issuer(
    tmp_path,
    monkeypatch,
) -> None:
    """Legacy product-truth tests must not inherit a developer E31 deployment route."""

    class _EnvironmentEnabledIssuer:
        def capability(self, *, project_id: str) -> dict[str, object]:
            return {"enabled": True, "project_id": project_id}

        def supports_output_count(self, *, expected_output_count: int) -> bool:
            return expected_output_count > 0

        def issue(self, **_kwargs):
            raise AssertionError("The Doc263 legacy fixture must not use the environment issuer.")

    environment_issuer = _EnvironmentEnabledIssuer()
    monkeypatch.setattr(project_mode_service, "issuer_from_environment", lambda: environment_issuer)

    handlers = _doc263_handlers()
    assert isinstance(
        handlers.project_service.ecommerce_view_activation_issuer,
        DisabledEcommerceViewActivationIssuer,
    )
    assert handlers.project_service.ecommerce_view_activation_issuer is not environment_issuer

    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )

    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create the current product image.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert "professional_ecommerce_product_truth_admission" in record.request.metadata
    assert "professional_ecommerce_physical_product_projections" in record.request.metadata


def _ready_product_upload(
    handlers,
    tmp_path: Path,
    *,
    color: tuple[int, int, int] = (180, 130, 90),
) -> str:
    handlers.service.asset_store.storage_root = tmp_path / "uploads"
    content = _png_bytes(color)
    created = handlers.post_uploads(
        {
            "filename": "doc263-current-product.png",
            "mime_type": "image/png",
            "size_bytes": len(content),
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        created["asset_id"],
        {
            "content_base64": base64.b64encode(content).decode("ascii"),
            "mime_type": "image/png",
        },
    )
    handlers.post_upload_complete(created["asset_id"])
    return str(created["asset_id"])


def _persist_projection_drift_failure(handlers, job_id: str) -> None:
    record = handlers.service.get_job_record(job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        **dict(record.request.metadata),
        "doc263_reference_projection_drift_receipt": {
            "schema_version": "doc263_reference_projection_drift_receipt_v1",
            "authority": "v3_product_api",
            "job_id": job_id,
            "project_id": record.request.metadata["project_id"],
            "failure_code": "reference_projection_drift",
            "source": "provider_pre_dispatch_contract",
        },
        "historical_reference_projection": {
            "failure_code": "reference_projection_drift",
            "stale_input_asset_ids": ["stale_failed_job_product"],
        },
        "historical_failure_text": "old projection failure must stay in append-only history",
    }
    record.warnings.append(
        "reference_projection_drift: old projection failure must stay in append-only history"
    )
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)


def test_doc263_admitted_projection_reaches_pre_dispatch_materialization_without_provider_call(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    provider = _NoProviderDispatch()
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )

    assets = provider._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == ["product_3", "face_0", "face_1", "face_2"]
    assert provider.dispatch_calls == 0


@pytest.mark.parametrize(
    ("selected_product_ids", "expected_asset_ids"),
    [
        (["product_3"], ["product_3", "face_0", "face_1", "face_2"]),
        (
            ["product_2", "product_3"],
            ["product_2", "product_3", "face_0", "face_1", "face_2"],
        ),
    ],
)
def test_doc263_freezes_selected_physical_product_projection_before_adaptive_selection(
    tmp_path,
    selected_product_ids: list[str],
    expected_asset_ids: list[str],
) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=selected_product_ids,
    )

    assets = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == expected_asset_ids
    assert len(assets) <= 5
    assert request.metadata["professional_ecommerce_product_truth_projection"] == {
        "output_index": 1,
        "selected_product_truth_asset_ids": selected_product_ids,
        "suppressed_product_truth_asset_ids": [
            asset_id for asset_id in product_ids if asset_id not in selected_product_ids
        ],
    }


def test_doc263_missing_canonical_source_fails_as_admission_before_projection(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "uploaded_assets": [item for item in references if item["asset_id"] != "product_0"],
            }
        }
    )

    assert _failure_code(
        ProductionImageGenerationProvider(),
        request,
    ) == "product_truth_admission_invalid"


def test_doc263_injected_legacy_projection_loss_is_reference_projection_drift(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    request = _attach_server_owned_ecommerce_contract(
        request,
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
        projection_state="legacy_drift_recovery",
        historical_lineage_id="job_historical_projection_drift",
    )
    injected_projection = [
        references[3],
        references[4],
        references[5],
        references[6],
    ]

    assert _failure_code(
        ProductionImageGenerationProvider(),
        request.model_copy(update={"metadata": {**request.metadata, "uploaded_assets": injected_projection}}),
    ) == "reference_projection_drift"


@pytest.mark.parametrize(
    "mutation",
    [
        "forged_admission",
        "forged_projection",
        "admission_schema",
        "projection_digest",
        "job_binding",
        "project_binding",
        "missing_consent",
        "file_digest_drift",
        "duplicate_product_input",
        "role_channel_drift",
        "nested_claimed_channel_drift",
        "projection_map_missing",
        "projection_map_extra",
        "projection_map_cross_continuation",
    ],
)
def test_doc263_provider_rejects_forged_or_drifted_server_contract_before_dispatch(
    tmp_path,
    mutation: str,
) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    metadata = dict(request.metadata)
    if mutation == "forged_admission":
        metadata["professional_ecommerce_product_truth_admission"] = {"forged": True}
    elif mutation == "forged_projection":
        metadata["professional_ecommerce_physical_product_projection"] = {"forged": True}
    elif mutation == "admission_schema":
        admission = dict(metadata["professional_ecommerce_product_truth_admission"])
        admission["schema_version"] = "forged_schema"
        metadata["professional_ecommerce_product_truth_admission"] = admission
    elif mutation == "projection_digest":
        projection = dict(metadata["professional_ecommerce_physical_product_projection"])
        projection["projection_digest"] = "forged"
        metadata["professional_ecommerce_physical_product_projection"] = projection
    elif mutation == "job_binding":
        admission = build_product_truth_admission(
            project_id="doc263_project",
            job_id="other_server_job",
            sources=[
                ProductTruthSource(**source)
                for source in metadata["professional_ecommerce_product_truth_admission"]["sources"]
            ],
            product_truth_plan_digest=hashlib.sha256(
                b"doc263_fixture_plan_digest"
            ).hexdigest(),
        )
        projection = build_physical_product_projection(
            job_id=admission.job_id,
            output_index=1,
            admission=admission,
            selected_product_asset_ids=["product_3"],
            selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
            selection_role="lifestyle_primary_product_view",
            cap_reservation=1,
        )
        metadata["professional_ecommerce_product_truth_admission"] = admission.model_dump()
        metadata["professional_ecommerce_physical_product_projection"] = projection.model_dump()
    elif mutation == "project_binding":
        admission = build_product_truth_admission(
            project_id="other_project",
            job_id="doc263_server_job",
            sources=[
                ProductTruthSource(**source)
                for source in metadata["professional_ecommerce_product_truth_admission"]["sources"]
            ],
            product_truth_plan_digest=hashlib.sha256(
                b"doc263_fixture_plan_digest"
            ).hexdigest(),
        )
        projection = build_physical_product_projection(
            job_id=admission.job_id,
            output_index=1,
            admission=admission,
            selected_product_asset_ids=["product_3"],
            selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
            selection_role="lifestyle_primary_product_view",
            cap_reservation=1,
        )
        metadata["professional_ecommerce_product_truth_admission"] = admission.model_dump()
        metadata["professional_ecommerce_physical_product_projection"] = projection.model_dump()
    elif mutation == "missing_consent":
        admission = dict(metadata["professional_ecommerce_product_truth_admission"])
        sources = [dict(item) for item in admission["sources"]]
        sources[0]["consent_reference"] = ""
        admission["sources"] = sources
        metadata["professional_ecommerce_product_truth_admission"] = admission
    elif mutation == "duplicate_product_input":
        metadata["uploaded_assets"] = [*references, references[-4]]
    elif mutation == "role_channel_drift":
        drifted = [dict(item) for item in references]
        drifted[0] = {
            **drifted[0],
            "metadata": {
                **dict(drifted[0]["metadata"]),
                "codex_native_reference_channel": "portrait_identity",
            },
        }
        metadata["uploaded_assets"] = drifted
    elif mutation == "nested_claimed_channel_drift":
        drifted = [dict(item) for item in references]
        drifted[0] = {
            **drifted[0],
            "metadata": {
                **dict(drifted[0]["metadata"]),
                "asset_metadata": {
                    "candidate_metadata": {
                        "reference_truth_channel": "unknown_channel",
                    }
                },
            },
        }
        metadata["uploaded_assets"] = drifted
    elif mutation == "projection_map_missing":
        metadata.pop("professional_ecommerce_physical_product_projections")
    elif mutation == "projection_map_extra":
        projections = dict(metadata["professional_ecommerce_physical_product_projections"])
        projections["2"] = dict(projections["1"])
        metadata["professional_ecommerce_physical_product_projections"] = projections
    elif mutation == "projection_map_cross_continuation":
        metadata["job_id"] = "doc263_fresh_continuation_job"
    else:
        Path(str(references[0]["file_path"])).write_bytes(_png_bytes((1, 2, 3)))
    request = request.model_copy(update={"metadata": metadata})

    expected_failure = (
        "ecommerce_product_truth_selection_missing"
        if mutation in {"projection_map_missing", "projection_map_extra"}
        else "product_truth_admission_invalid"
    )
    assert _failure_code(ProductionImageGenerationProvider(), request) == expected_failure


def test_doc263_multi_output_projection_map_is_complete_and_job_bound(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    metadata = dict(request.metadata)
    plan = dict(metadata["template_deliverable_plan"])
    first = dict(plan["deliverables"][0])
    second = {
        **first,
        "deliverable_id": "doc263_deliverable_2",
        "output_index": 2,
        "metadata": {
            **dict(first["metadata"]),
            "product_truth_selection_role": "product_detail_or_print_view",
            "selected_product_truth_asset_ids": ["product_2", "product_3"],
            "admitted_product_truth_asset_ids": ["product_2", "product_3"],
        },
    }
    plan["requested_image_count"] = 2
    plan["effective_image_count"] = 2
    plan["deliverables"] = [first, second]
    admission = ProductTruthAdmission.from_mapping(
        metadata["professional_ecommerce_product_truth_admission"]
    )
    second_projection = build_physical_product_projection(
        job_id=admission.job_id,
        output_index=2,
        admission=admission,
        selected_product_asset_ids=["product_2", "product_3"],
        selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
        selection_role="product_detail_or_print_view",
        cap_reservation=2,
    )
    metadata["template_deliverable_plan"] = plan
    metadata["professional_ecommerce_physical_product_projections"] = {
        **dict(metadata["professional_ecommerce_physical_product_projections"]),
        "2": second_projection.model_dump(),
    }
    request = request.model_copy(
        update={
            "asset_spec": request.asset_spec.model_copy(update={"priority": 2}),
            "metadata": metadata,
        }
    )

    assets = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == [
        "product_2",
        "product_3",
        "face_0",
        "face_1",
        "face_2",
    ]
    assert len(assets) == 5


def test_doc263_multi_output_projection_map_rejects_missing_output_and_cross_job_reuse(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    metadata = dict(request.metadata)
    plan = dict(metadata["template_deliverable_plan"])
    first = dict(plan["deliverables"][0])
    second = {
        **first,
        "deliverable_id": "doc263_deliverable_2",
        "output_index": 2,
        "metadata": {
            **dict(first["metadata"]),
            "product_truth_selection_role": "product_detail_or_print_view",
            "selected_product_truth_asset_ids": ["product_2", "product_3"],
            "admitted_product_truth_asset_ids": ["product_2", "product_3"],
        },
    }
    plan["deliverables"] = [first, second]
    admission = ProductTruthAdmission.from_mapping(
        metadata["professional_ecommerce_product_truth_admission"]
    )
    second_projection = build_physical_product_projection(
        job_id=admission.job_id,
        output_index=2,
        admission=admission,
        selected_product_asset_ids=["product_2", "product_3"],
        selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
        selection_role="product_detail_or_print_view",
        cap_reservation=2,
    )
    metadata["template_deliverable_plan"] = plan
    metadata["professional_ecommerce_physical_product_projections"] = {
        "1": metadata["professional_ecommerce_physical_product_projections"]["1"],
        "2": second_projection.model_dump(),
    }
    second_output_request = request.model_copy(
        update={
            "asset_spec": request.asset_spec.model_copy(update={"priority": 2}),
            "metadata": metadata,
        }
    )

    missing = dict(second_output_request.metadata)
    missing["professional_ecommerce_physical_product_projections"] = {
        "1": missing["professional_ecommerce_physical_product_projections"]["1"]
    }
    assert _failure_code(
        ProductionImageGenerationProvider(),
        second_output_request.model_copy(update={"metadata": missing}),
    ) == "ecommerce_product_truth_selection_missing"

    reused = dict(second_output_request.metadata)
    reused["job_id"] = "doc263_new_continuation_job"
    assert _failure_code(
        ProductionImageGenerationProvider(),
        second_output_request.model_copy(update={"metadata": reused}),
    ) == "product_truth_admission_invalid"


def test_doc263_product_api_issues_projection_from_current_project_pool_and_brain_plan(tmp_path) -> None:
    handlers = _doc263_handlers()
    handlers.service.asset_store.storage_root = tmp_path / "uploads"
    product_ids = [
        _ready_product_upload(handlers, tmp_path, color=(100 + index, 120, 140))
        for index in range(4)
    ]
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image set.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    for product_id in product_ids:
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": product_id,
                "source_type": "uploaded",
                "use_policy": "product",
            },
        )

    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create the current canonical product image set.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    metadata = record.request.metadata
    admission = metadata["professional_ecommerce_product_truth_admission"]
    projections = metadata["professional_ecommerce_physical_product_projections"]
    plan = metadata["template_deliverable_plan"]

    assert metadata["professional_ecommerce_contract_authority"] == "v3_product_api"
    assert admission["canonical_asset_ids"] == product_ids
    for deliverable in plan["deliverables"]:
        output_index = str(deliverable["output_index"])
        expected = deliverable["metadata"]["selected_product_truth_asset_ids"]
        assert projections[output_index]["selected_product_asset_ids"] == expected
        assert projections[output_index]["admission_binding_digest"] == admission["source_binding_digest"]


def test_doc263_tampered_server_upload_authorization_receipt_closes_before_planning(
    tmp_path,
    monkeypatch,
) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    upload = handlers.service.get_uploaded_asset(product_id)
    assert upload is not None
    tampered_metadata = {
        **upload.metadata,
        "upload_authorization_receipt": {
            **upload.metadata["upload_authorization_receipt"],
            "receipt_digest": "forged",
        },
    }
    handlers.service.asset_store._save_record(  # noqa: SLF001
        upload.model_copy(update={"metadata": tampered_metadata})
    )
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    calls = {"plan": 0, "dispatch": 0}

    def _unexpected_plan(*_args, **_kwargs):
        calls["plan"] += 1
        raise AssertionError("Tampered product evidence must close before planning.")

    def _unexpected_dispatch(*_args, **_kwargs):
        calls["dispatch"] += 1
        raise AssertionError("Tampered product evidence must close before dispatch.")

    monkeypatch.setattr(handlers.service.scenario_runtime, "plan_job", _unexpected_plan)
    monkeypatch.setattr(handlers.service.scenario_runtime, "generate_job", _unexpected_dispatch)

    status = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create from the current product original.",
        },
    )

    assert status["status"] == "blocked"
    assert status["metadata"]["current_operation"] == {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    assert calls == {"plan": 0, "dispatch": 0}


def test_doc263_does_not_change_ordinary_reference_materialization(tmp_path) -> None:
    reference = _reference(
        asset_id="ordinary_product",
        role="product_reference",
        path=_image(tmp_path / "ordinary.png", (80, 120, 160)),
        provider_input_required=False,
    )
    request = _generation_request(
        references=[reference],
        pool_product_ids=["ordinary_product"],
        selected_product_ids=["ordinary_product"],
    )
    request = request.model_copy(
        update={
            "metadata": {
                "uploaded_assets": [reference],
                "visual_cluster": request.metadata["visual_cluster"],
                "professional_product_truth_required": False,
            }
        }
    )

    assert [
        item["asset_id"]
        for item in ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001
    ] == ["ordinary_product"]


def test_doc263_client_drift_marker_cannot_upgrade_missing_admission_to_projection_drift(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "legacy_reference_projection": {"projection_status": "lost_after_admission"},
                "uploaded_assets": [item for item in references if item["asset_id"] != "product_0"],
            }
        }
    )

    assert _failure_code(ProductionImageGenerationProvider(), request) == "product_truth_admission_invalid"


def test_doc263_public_projection_map_and_drift_receipt_cannot_be_forged() -> None:
    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService

    service = V3ProductApiService()
    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Create a professional ecommerce product image.",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {
                    "professional_ecommerce_physical_product_projections": {"1": {}},
                },
            }
        )
    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Continue a professional ecommerce product image.",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {
                    "doc263_reference_projection_drift_receipt": {
                        "schema_version": "doc263_reference_projection_drift_receipt_v1",
                    },
                },
            }
        )


def test_doc263_public_historical_drift_marker_cannot_create_superseding_job(tmp_path) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    original = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create from the current product original.",
            "uploaded_asset_ids": [product_id],
            "metadata": {"idempotency_key": "doc263-public-marker-original"},
        },
    )
    old_record = handlers.service.get_job_record(original["job_id"])
    assert old_record is not None
    old_record.status = ProductJobStatusValue.BLOCKED
    old_record.request.metadata = {
        **dict(old_record.request.metadata),
        "historical_reference_projection": {"failure_code": "reference_projection_drift"},
        "legacy_reference_projection": {"projection_status": "lost_after_admission"},
    }
    old_record.warnings.append("reference_projection_drift: public marker only")
    old_record.lifecycle = handlers.service._build_lifecycle(old_record)  # noqa: SLF001
    handlers.service.job_store.save(old_record)

    next_job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create again from current canonical originals.",
            "metadata": {"idempotency_key": "doc263-public-marker-next"},
        },
    )

    assert next_job["job_id"] != original["job_id"]
    assert "supersedes_job_id" not in next_job["metadata"]


def test_doc263_product_api_records_server_owned_drift_receipt_from_pre_dispatch_failure(
    tmp_path,
    monkeypatch,
) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    created = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create from the current product original.",
            "uploaded_asset_ids": [product_id],
        },
    )

    def fail_pre_dispatch(*_args, **_kwargs):
        raise ReferenceInputAdmissionError(
            "Injected local projection receipt mismatch.",
            provider="fixture_provider",
            detail={
                "reference_input_failure_code": "reference_projection_drift",
                "fallback": "blocked",
            },
        )

    monkeypatch.setattr(handlers.service.scenario_runtime, "generate_job", fail_pre_dispatch)
    blocked = handlers.service.generate_asset_series(created["job_id"])
    record = handlers.service.get_job_record(created["job_id"])

    assert blocked.status == ProductJobStatusValue.BLOCKED
    assert record is not None
    assert record.request.metadata["doc263_reference_projection_drift_receipt"] == {
        "schema_version": "doc263_reference_projection_drift_receipt_v1",
        "authority": "v3_product_api",
        "job_id": created["job_id"],
        "project_id": project["project_id"],
        "failure_code": "reference_projection_drift",
        "source": "provider_pre_dispatch_contract",
    }


def test_doc263_repeated_current_reference_command_has_one_identity(tmp_path) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image set.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    reference = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": product_id,
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    command_payload = {
        "template_id": "ecommerce_template",
        "user_input": "Continue from the current canonical product originals.",
        "metadata": {
            "idempotency_key": "doc263-current-reference-command",
        },
    }

    first = handlers.post_project_job(project["project_id"], command_payload)
    repeated_after_reload = handlers.post_project_job(project["project_id"], command_payload)

    assert first["job_id"] == repeated_after_reload["job_id"]
    derived_digest = str(first["metadata"].get("current_reference_binding_digest") or "")
    assert derived_digest
    assert derived_digest != "fixture-current-binding"
    assert repeated_after_reload["metadata"]["current_reference_binding_digest"] == derived_digest
    assert len(handlers.get_project(project["project_id"])["project"]["job_ids"]) == 1
    assert reference["reference"]["asset_ref_id"] == product_id

    forged_payload = {
        **command_payload,
        "metadata": {
            "idempotency_key": "doc263-forged-reference-command",
            "current_reference_binding_digest": "fixture-current-binding",
        },
    }
    try:
        forged = handlers.post_project_job(project["project_id"], forged_payload)
    except ValueError:
        pass
    else:
        forged_digest = str(forged["metadata"].get("current_reference_binding_digest") or "")
        assert forged_digest
        assert forged_digest != "fixture-current-binding"


def test_doc263_first_selected_product_command_is_immediately_idempotent(tmp_path) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image set.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    command_payload = {
        "template_id": "ecommerce_template",
        "user_input": "Create from this selected current product original.",
        "uploaded_asset_ids": [product_id],
        "metadata": {
            "idempotency_key": "doc263-first-selected-product-replay",
            "current_reference_binding_digest": "client-forged-stale-digest",
        },
    }

    first = handlers.post_project_job(project["project_id"], command_payload)
    replay = handlers.post_project_job(project["project_id"], command_payload)
    loaded = handlers.get_project(project["project_id"])["project"]
    active_products = _active_product_references(loaded)
    derived_digest = str(first["metadata"].get("current_reference_binding_digest") or "")

    assert first["job_id"] == replay["job_id"]
    assert len(loaded["job_ids"]) == 1
    assert [item["asset_ref_id"] for item in active_products] == [product_id]
    assert derived_digest
    assert derived_digest != "client-forged-stale-digest"
    assert replay["metadata"]["current_reference_binding_digest"] == derived_digest


def test_doc263_projection_drift_continuation_is_clean_and_superseding(tmp_path) -> None:
    handlers = _doc263_handlers()
    handlers.service.asset_store.storage_root = tmp_path / "uploads"
    product_ids = [
        _ready_product_upload(
            handlers,
            tmp_path,
            color=(120 + index, 80, 150),
        )
        for index in range(4)
    ]
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image set.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    for product_id in product_ids:
        handlers.post_project_reference(
            project["project_id"],
            {
                "asset_ref_id": product_id,
                "source_type": "uploaded",
                "use_policy": "product",
            },
        )
    old_job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create the initial product image.",
            "metadata": {"idempotency_key": "doc263-old-command"},
        },
    )
    _persist_projection_drift_failure(handlers, old_job["job_id"])

    continuation = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Continue from the current canonical product originals.",
            "metadata": {"idempotency_key": "doc263-drift-recovery-command"},
        },
    )

    assert continuation["job_id"] != old_job["job_id"]
    assert continuation["metadata"]["supersedes_job_id"] == old_job["job_id"]
    continuation_record = handlers.service.get_job_record(continuation["job_id"])
    assert continuation_record is not None
    assert continuation_record.request.metadata["professional_ecommerce_product_truth_admission"][
        "canonical_asset_ids"
    ] == product_ids
    assert continuation["ecommerce"]["product_truth"]["evidence_sources"] == [
        f"uploaded_asset:{product_id}" for product_id in product_ids
    ]
    assert "stale_failed_job_product" not in json.dumps(continuation, sort_keys=True)
    assert "old projection failure must stay in append-only history" not in json.dumps(
        continuation,
        sort_keys=True,
    )


def test_doc263_terminal_public_status_has_one_safe_next_action(tmp_path) -> None:
    handlers = _doc263_handlers()
    product_id = _ready_product_upload(handlers, tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a product image.",
            "uploaded_asset_ids": [product_id],
        },
    )
    record = handlers.service.get_job_record(job["job_id"])
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.warnings.append(
        "reference_projection_drift: C:\\private\\product.png sha256:forged-secret"
    )
    record.lifecycle = handlers.service._build_lifecycle(record)  # noqa: SLF001
    handlers.service.job_store.save(record)

    public_status = handlers.get_job(job["job_id"])

    assert public_status["status"] == "blocked"
    assert public_status["metadata"].get("terminal") is True
    assert public_status["metadata"].get("next_action") == "continue"
    public_json = json.dumps(public_status, sort_keys=True)
    assert "C:\\private\\product.png" not in public_json
    assert "sha256:forged-secret" not in public_json


def test_doc263_continuation_dedupes_product_content_and_does_not_promote_generated_review_output(
    tmp_path,
) -> None:
    from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    handlers = _doc263_handlers(output_store=output_store)
    content = base64.b64encode(_png_bytes((150, 170, 190))).decode("ascii")
    first_upload = _ready_product_upload(handlers, tmp_path, color=(150, 170, 190))
    duplicate_created = handlers.post_uploads(
        {
            "filename": "doc263-duplicate-product.png",
            "mime_type": "image/png",
            "size_bytes": len(_png_bytes((150, 170, 190))),
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        duplicate_created["asset_id"],
        {"content_base64": content, "mime_type": "image/png"},
    )
    handlers.post_upload_complete(duplicate_created["asset_id"])
    project = handlers.post_projects(
        {
            "user_goal": "Create a professional ecommerce product image.",
            "primary_template_id": "ecommerce_template",
        }
    )["project"]
    first_reference = handlers.post_project_reference(
        project["project_id"],
        {"asset_ref_id": first_upload, "source_type": "uploaded", "use_policy": "product"},
    )
    duplicate_reference = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": duplicate_created["asset_id"],
            "source_type": "uploaded",
            "use_policy": "product",
        },
    )
    history_job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a prior project image for continuation direction.",
            "metadata": {"idempotency_key": "doc263-generated-review-history"},
        },
    )
    generated = output_store.save_base64_output(
        job_id=history_job["job_id"],
        candidate_id="doc263-generated-review-candidate",
        asset_id="doc263-generated-review-asset",
        provider="fixture",
        model="fixture",
        encoded_image=content,
    )
    generated_reference = handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": generated.output_id,
            "source_type": "generated_selected",
            "use_policy": "product",
        },
    )

    continuation = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Continue from current canonical product originals.",
            "metadata": {"idempotency_key": "doc263-dedup-continuation"},
        },
    )
    loaded = handlers.get_project(project["project_id"])
    active_products = _active_product_references(loaded["project"])

    assert first_reference["reference"]["asset_ref_id"] == first_upload
    assert duplicate_reference["reference"]["asset_ref_id"] == first_upload
    assert generated_reference["reference"]["source_type"] == "generated_selected"
    assert [item["asset_ref_id"] for item in active_products] == [first_upload]
    assert continuation["ecommerce"]["product_truth"]["evidence_sources"] == [
        f"uploaded_asset:{first_upload}"
    ]
