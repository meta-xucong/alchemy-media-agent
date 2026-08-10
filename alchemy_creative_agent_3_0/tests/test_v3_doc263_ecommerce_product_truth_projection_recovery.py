"""Phase 0 red contracts for Doc263 product-truth projection recovery.

These tests deliberately describe the approved behavior before runtime work
lands. They must remain deterministic and must not reach an external provider.
"""

from __future__ import annotations

import base64
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
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)


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
    return GenerationRequest(
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


def test_doc263_reproduces_legacy_adaptive_projection_drift_without_provider_dispatch(tmp_path) -> None:
    references, product_ids, _face_ids = _doc263_references(tmp_path)
    provider = _NoProviderDispatch()
    request = _generation_request(
        references=references,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )

    with pytest.raises(ReferenceInputAdmissionError, match="truth pool"):
        provider.generate(request)

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
    missing_current_product = [
        item for item in references if item["asset_id"] != "product_0"
    ]
    request = _generation_request(
        references=missing_current_product,
        pool_product_ids=product_ids,
        selected_product_ids=["product_3"],
    )
    request.metadata.pop("visual_cluster", None)

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
    request.metadata["legacy_reference_projection"] = {
        "selected_product_truth_asset_ids": ["product_3"],
        "projection_status": "lost_after_admission",
    }
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


def test_doc263_repeated_current_reference_command_has_one_identity(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
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


def test_doc263_projection_drift_continuation_is_clean_and_superseding(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
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
    assert continuation["metadata"]["product_truth_admission"]["canonical_asset_ids"] == product_ids
    assert continuation["ecommerce"]["product_truth"]["evidence_sources"] == [
        f"uploaded_asset:{product_id}" for product_id in product_ids
    ]
    assert "stale_failed_job_product" not in json.dumps(continuation, sort_keys=True)
    assert "old projection failure must stay in append-only history" not in json.dumps(
        continuation,
        sort_keys=True,
    )


def test_doc263_terminal_public_status_has_one_safe_next_action(tmp_path) -> None:
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    handlers = V3ProductRouteHandlers(service=ecommerce_test_service())
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
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service

    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    handlers = V3ProductRouteHandlers(service=ecommerce_test_service(output_store=output_store))
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
    generated = output_store.save_base64_output(
        job_id="doc263-generated-review-job",
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
